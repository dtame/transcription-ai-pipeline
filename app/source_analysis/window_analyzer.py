"""
WindowAnalyzer — analyse sémantique d'UNE fenêtre.

    WindowInput
        → materialize owned/context
        → window-analysis-1.1 (1.0 historique inchangé)
        → AIRequest (Generation C)
        → FakeAIEngine ONLY en 3B.7.2
        → persist exact transport FIRST
        → decoder fail-closed existant
        → WindowSemanticResult
        → validator
        → result.json atomique

Ne planifie pas toutes les fenêtres.
Ne consolide pas.
Ne produit pas de SourceMap.
Ne met pas project_state SUCCESS.
N'est PAS branché dans analyzer.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from app.ai.contracts import AIRequest, AIResponse
from app.ai.errors import AIError, AIStructuredOutputError
from app.ai.provider_forensics import (
    persist_error_forensics,
    persist_interrupt_forensics,
    provider_forensic_scope,
)
from app.ai.structured_forensics import persist_structured_output_forensics
from app.ai.settings import StageSettings, resolve_stage_settings
from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
    WindowAnalysisError,
    WindowGranularityLimitExceeded,
    WindowResultValidationError,
    WindowSemanticCapacityExceeded,
    WindowSourceRefError,
    WindowTransportValidationError,
    WindowTransportWriteError,
)
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.ultra_compact_schema import (
    SEMANTIC_TRANSPORT_VERSION,
    build_ultra_compact_response_schema,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.window_models import (
    STAGE_WINDOW,
    WINDOW_MAX_OUTPUT_TOKENS,
    WINDOW_RESULT_SCHEMA_VERSION,
    WindowCandidateMetadata,
    WindowProviderMetadata,
    WindowSemanticResult,
    assign_intermediate_records,
    compute_coverage,
    compute_record_stats,
)
from app.source_analysis.window_granularity import (
    validate_window_transport_granularity,
)
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    build_window_system_prompt,
    build_window_user_prompt,
    estimate_window_request_tokens,
    resolve_window_prompt_version,
)
from app.source_analysis.window_signature import (
    WindowSignatureInputs,
    build_window_analysis_signature,
    signature_inputs_for,
)
from app.source_analysis.window_validator import (
    decode_window_transport,
    validate_window_result,
)
from app.source_analysis.window_writer import (
    artifact_sha256,
    leftover_partial,
    metadata_path,
    result_path,
    transport_path,
    write_window_metadata,
    write_window_result,
    write_window_transport,
)
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_hybrid.materialize import materialize_window_content


@dataclass(frozen=True)
class WindowAnalysisHooks:
    """Instrumentation de tests — ordre transport-first."""

    after_generate: Callable[[AIResponse], None] | None = None
    after_transport_write: Callable[[Path], None] | None = None
    before_decode: Callable[[Mapping[str, Any]], None] | None = None
    after_validate: Callable[[WindowSemanticResult], None] | None = None
    before_result_write: Callable[[WindowSemanticResult], None] | None = None


@dataclass(frozen=True)
class WindowRequestBundle:
    request: AIRequest
    system_prompt: str
    user_prompt: str
    response_schema: dict
    response_schema_sha256: str
    signature: str
    settings: StageSettings
    token_estimate: dict[str, Any]
    signature_inputs: WindowSignatureInputs


def resolve_window_settings(settings: StageSettings | None = None) -> StageSettings:
    return settings or resolve_stage_settings(STAGE_WINDOW)


def build_window_ai_request(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    settings: StageSettings | None = None,
    provider: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
) -> WindowRequestBundle:
    """Construit un vrai AIRequest V2. N'appelle pas engine.generate."""
    chosen_prompt = resolve_window_prompt_version(prompt_version)
    resolved = resolve_window_settings(settings)
    content = materialize_window_content(transcript, window)
    system_prompt = build_window_system_prompt(
        transcript.primary_language, version=chosen_prompt
    )
    user_prompt = build_window_user_prompt(
        transcript, window, content, version=chosen_prompt
    )
    response_schema = build_ultra_compact_response_schema()
    schema_sha = ultra_compact_schema_fingerprint(response_schema)
    max_output = resolved.max_output_tokens or WINDOW_MAX_OUTPUT_TOKENS
    resolved_model = model or resolved.model
    resolved_provider = provider or resolved.provider
    request = AIRequest(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model=resolved_model,
        temperature=resolved.temperature,
        max_output_tokens=int(max_output),
        response_schema=response_schema,
        metadata={
            "stage": STAGE_WINDOW,
            "window_id": window.window_id,
            "output_language": transcript.primary_language,
        },
    )
    inputs = signature_inputs_for(
        window,
        transcript,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_schema_sha256=schema_sha,
        provider=str(resolved_provider),
        model=str(resolved_model or ""),
        temperature=resolved.temperature,
        max_output_tokens=int(max_output),
        context_safety_ratio=float(resolved.context_safety_ratio),
        prompt_version=chosen_prompt,
    )
    signature = build_window_analysis_signature(inputs)
    estimate = estimate_window_request_tokens(
        transcript, window, content=content, version=chosen_prompt
    )
    return WindowRequestBundle(
        request=request,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_schema=response_schema,
        response_schema_sha256=schema_sha,
        signature=signature,
        settings=resolved,
        token_estimate=estimate,
        signature_inputs=inputs,
    )


def resolve_window_execution(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    settings: StageSettings | None = None,
    engine=None,
    provider: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
) -> WindowRequestBundle:
    """
    Contrat d'exécution + signature attendue.

    Si un moteur injecté expose provider/modèle (FakeAI), la signature
    porte CE couple — sinon le cache divergerait de l'appel réel.
    N'appelle pas engine.generate.
    """
    bundle = build_window_ai_request(
        window,
        transcript,
        settings=settings,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
    )
    if engine is None:
        return bundle
    engine_model = getattr(engine, "resolve_model", None)
    engine_provider = getattr(engine, "provider_name", None)
    if not (callable(engine_model) or engine_provider):
        return bundle
    resolved_model = engine_model() if callable(engine_model) else bundle.request.model
    resolved_provider = str(engine_provider or bundle.settings.provider)
    request = AIRequest(
        prompt=bundle.request.prompt,
        system_prompt=bundle.request.system_prompt,
        model=resolved_model,
        temperature=bundle.request.temperature,
        max_output_tokens=bundle.request.max_output_tokens,
        response_schema=bundle.request.response_schema,
        metadata=dict(bundle.request.metadata),
    )
    inputs = signature_inputs_for(
        window,
        transcript,
        system_prompt=bundle.system_prompt,
        user_prompt=bundle.user_prompt,
        response_schema_sha256=bundle.response_schema_sha256,
        provider=resolved_provider,
        model=str(resolved_model or ""),
        temperature=bundle.settings.temperature,
        max_output_tokens=request.max_output_tokens,
        context_safety_ratio=float(bundle.settings.context_safety_ratio),
        prompt_version=bundle.signature_inputs.prompt_version,
    )
    return WindowRequestBundle(
        request=request,
        system_prompt=bundle.system_prompt,
        user_prompt=bundle.user_prompt,
        response_schema=bundle.response_schema,
        response_schema_sha256=bundle.response_schema_sha256,
        signature=build_window_analysis_signature(inputs),
        settings=bundle.settings,
        token_estimate=bundle.token_estimate,
        signature_inputs=inputs,
    )


def build_window_metadata_payload(
    *,
    window: WindowInput,
    bundle: WindowRequestBundle,
    transport_sha256: str,
    provider_metadata: WindowProviderMetadata | None = None,
) -> dict[str, Any]:
    """
    Identité déterministe séparée de l'observabilité runtime.

    latency / request_id / timestamps exclus — hors signature de cache.
    """
    inputs = bundle.signature_inputs
    identity = {
        "window_id": window.window_id,
        "window_input_hash": window.input_hash,
        "window_analysis_signature": bundle.signature,
        "planner_version": inputs.planner_version,
        "prompt_version": inputs.prompt_version,
        "prompt_sha256": inputs.prompt_sha256,
        "transport_version": inputs.transport_version,
        "response_schema_sha256": inputs.response_schema_sha256,
        "provider": inputs.provider,
        "model": inputs.model,
        "temperature": inputs.temperature,
        "max_output_tokens": inputs.max_output_tokens,
        "output_language": inputs.output_language,
        "context_safety_ratio": inputs.context_safety_ratio,
        "stage": inputs.stage,
        "transport_sha256": transport_sha256,
    }
    observability: dict[str, Any] = {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "usage_source": "",
        "finish_reason": None,
    }
    if provider_metadata is not None:
        observability = {
            "input_tokens": provider_metadata.input_tokens,
            "output_tokens": provider_metadata.output_tokens,
            "total_tokens": provider_metadata.total_tokens,
            "usage_source": provider_metadata.usage_source,
            "finish_reason": provider_metadata.finish_reason,
        }
    return {
        "schema_version": WINDOW_RESULT_SCHEMA_VERSION,
        "identity": identity,
        "observability": observability,
    }


def _require_parsed(response: AIResponse) -> Mapping[str, Any]:
    parsed = response.parsed
    if not isinstance(parsed, Mapping):
        raise WindowTransportValidationError(
            "AIResponse.parsed absent ou non objet — le chemin normal "
            "consomme parsed, jamais json.loads(text) dans le service."
        )
    return parsed


def _provider_metadata(response: AIResponse) -> WindowProviderMetadata:
    return WindowProviderMetadata(
        provider=response.provider,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        total_tokens=response.total_tokens,
        usage_source=response.usage_source,
        finish_reason=response.finish_reason,
    )


def _build_result(
    *,
    window: WindowInput,
    transport: Mapping[str, Any],
    decoded: Mapping[str, Any],
    signature: str,
    response: AIResponse,
    prompt_version: str = WINDOW_ANALYSIS_PROMPT_VERSION,
) -> WindowSemanticResult:
    records_in = transport.get("records") or []
    if not isinstance(records_in, list):
        records_in = []
    records = assign_intermediate_records(records_in, window_id=window.window_id)
    analysis = decoded.get("source_analysis") or {}
    intent = analysis.get("author_intent") or {}
    audience = analysis.get("target_audience") or {}
    candidates = WindowCandidateMetadata(
        theme=str(analysis.get("main_theme") or transport.get("theme") or ""),
        intent=str(intent.get("summary") or transport.get("intent") or ""),
        intent_confidence=str(intent.get("confidence") or transport.get("ic") or ""),
        audience=str(audience.get("summary") or transport.get("aud") or ""),
        audience_confidence=str(
            audience.get("confidence") or transport.get("ac") or ""
        ),
        intent_kinds=tuple(intent.get("kinds") or ()),
        audience_kinds=tuple(audience.get("kinds") or ()),
    )
    voice = decoded.get("author_voice_profile") or {}
    return WindowSemanticResult(
        schema_version=WINDOW_RESULT_SCHEMA_VERSION,
        window_id=window.window_id,
        window_input_hash=window.input_hash,
        window_analysis_signature=signature,
        transport_version=SEMANTIC_TRANSPORT_VERSION,
        prompt_version=prompt_version,
        planner_version=window.planner_version,
        owned_src_refs=window.owned_src_refs,
        context_src_refs=window.context_src_refs,
        candidates=candidates,
        records=records,
        coverage=compute_coverage(window, records),
        stats=compute_record_stats(records),
        provider_metadata=_provider_metadata(response),
        voice_evidence=dict(voice) if isinstance(voice, Mapping) else {},
    )


def analyze_window(
    window: WindowInput,
    transcript: TranscriptInput,
    engine,
    *,
    settings: StageSettings | None = None,
    windows_root: Path,
    project_name: str = "fixture",
    hooks: WindowAnalysisHooks | None = None,
    prompt_version: str | None = None,
) -> WindowSemanticResult:
    """
    Pipeline d'une fenêtre. engine obligatoire (FakeAI en 3B.7.2).

    max_attempts = 1 : un seul engine.generate. Aucun retry local.
    """
    if engine is None:
        raise WindowAnalysisError(
            "WindowAnalyzer exige un moteur injecté. "
            "Aucun get_engine_for_stage : 3B.7.2 est FakeAI only."
        )

    bundle = resolve_window_execution(
        window,
        transcript,
        settings=settings,
        engine=engine,
        prompt_version=prompt_version,
    )
    request = bundle.request
    signature = bundle.signature

    t_path = transport_path(project_name, window.window_id, root=windows_root)
    r_path = result_path(project_name, window.window_id, root=windows_root)
    m_path = metadata_path(project_name, window.window_id, root=windows_root)

    try:
        with provider_forensic_scope(
            windows_root=windows_root,
            window_id=window.window_id,
            analysis_signature=signature,
            provider=getattr(engine, "provider_name", None),
            model=request.model,
        ):
            try:
                response = engine.generate(request)
            except KeyboardInterrupt:
                persist_interrupt_forensics()
                raise
            except AIStructuredOutputError as exc:
                persist_structured_output_forensics(
                    error=exc,
                    windows_root=windows_root,
                    window_id=window.window_id,
                    analysis_signature=signature,
                    provider=getattr(getattr(exc, "response", None), "provider", None),
                    model=getattr(getattr(exc, "response", None), "model", None)
                    or request.model,
                    stage=STAGE_WINDOW,
                )
                persist_error_forensics(
                    exc,
                    windows_root=windows_root,
                    window_id=window.window_id,
                    analysis_signature=signature,
                )
                raise
            except AIError as exc:
                persist_error_forensics(
                    exc,
                    windows_root=windows_root,
                    window_id=window.window_id,
                    analysis_signature=signature,
                )
                raise
    except KeyboardInterrupt:
        raise

    if hooks and hooks.after_generate:
        hooks.after_generate(response)

    transport = _require_parsed(response)

    try:
        write_window_transport(t_path, transport)
    except WindowTransportWriteError:
        raise
    except KeyboardInterrupt:
        raise

    if leftover_partial(t_path) is not None:
        leftover_partial(t_path).unlink(missing_ok=True)

    write_window_metadata(
        m_path,
        build_window_metadata_payload(
            window=window,
            bundle=bundle,
            transport_sha256=artifact_sha256(t_path),
            provider_metadata=_provider_metadata(response),
        ),
    )
    if leftover_partial(m_path) is not None:
        leftover_partial(m_path).unlink(missing_ok=True)

    if hooks and hooks.after_transport_write:
        hooks.after_transport_write(t_path)

    if hooks and hooks.before_decode:
        hooks.before_decode(transport)

    try:
        validate_window_transport_granularity(transport)
        decoded = decode_window_transport(transport, window)
        result = _build_result(
            window=window,
            transport=transport,
            decoded=decoded,
            signature=signature,
            response=response,
            prompt_version=bundle.signature_inputs.prompt_version,
        )
        validate_window_result(result, window)
    except (
        SourceMapEditorialLeakError,
        SourceMapValidationError,
        WindowTransportValidationError,
        WindowSourceRefError,
        WindowResultValidationError,
        WindowSemanticCapacityExceeded,
        WindowGranularityLimitExceeded,
    ):
        raise
    except KeyboardInterrupt:
        raise

    if hooks and hooks.after_validate:
        hooks.after_validate(result)
    if hooks and hooks.before_result_write:
        hooks.before_result_write(result)

    write_window_result(r_path, result.to_dict())
    leftover = leftover_partial(r_path)
    if leftover is not None:
        leftover.unlink(missing_ok=True)
    return result


def recover_window_from_transport(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    windows_root: Path,
    project_name: str = "fixture",
    expected_signature: str,
    settings: StageSettings | None = None,
    engine=None,
    metadata: Mapping[str, Any],
    transport: Mapping[str, Any],
    prompt_version: str | None = None,
) -> WindowSemanticResult:
    """
    Reconstruit result.json depuis un transport déjà persisté.

    Aucun engine.generate. Le binding signature/fenêtre/hash doit déjà
    avoir été prouvé par l'appelant (window_cache).
    """
    bundle = resolve_window_execution(
        window,
        transcript,
        settings=settings,
        engine=engine,
        prompt_version=prompt_version,
    )
    if bundle.signature != expected_signature:
        raise WindowResultValidationError(
            "signature attendue ≠ contrat courant — recovery interdite."
        )
    identity = metadata.get("identity") if isinstance(metadata, Mapping) else None
    if not isinstance(identity, Mapping):
        raise WindowResultValidationError("metadata.identity absent.")
    if identity.get("window_analysis_signature") != expected_signature:
        raise WindowResultValidationError("metadata.signature ≠ signature attendue.")
    validate_window_transport_granularity(transport)
    decoded = decode_window_transport(transport, window)
    observability = metadata.get("observability") if isinstance(metadata, Mapping) else {}
    if not isinstance(observability, Mapping):
        observability = {}
    records_in = transport.get("records") or []
    if not isinstance(records_in, list):
        records_in = []
    records = assign_intermediate_records(records_in, window_id=window.window_id)
    voice = decoded.get("author_voice_profile") or {}
    result = WindowSemanticResult(
        schema_version=WINDOW_RESULT_SCHEMA_VERSION,
        window_id=window.window_id,
        window_input_hash=window.input_hash,
        window_analysis_signature=expected_signature,
        transport_version=SEMANTIC_TRANSPORT_VERSION,
        prompt_version=bundle.signature_inputs.prompt_version,
        planner_version=window.planner_version,
        owned_src_refs=window.owned_src_refs,
        context_src_refs=window.context_src_refs,
        candidates=_candidates_from_decoded(transport, decoded),
        records=records,
        coverage=compute_coverage(window, records),
        stats=compute_record_stats(records),
        provider_metadata=WindowProviderMetadata(
            provider=str(identity.get("provider") or bundle.signature_inputs.provider),
            model=str(identity.get("model") or bundle.signature_inputs.model),
            input_tokens=observability.get("input_tokens"),
            output_tokens=observability.get("output_tokens"),
            total_tokens=observability.get("total_tokens"),
            usage_source=str(observability.get("usage_source") or ""),
            finish_reason=observability.get("finish_reason"),
        ),
        voice_evidence=dict(voice) if isinstance(voice, Mapping) else {},
    )
    validate_window_result(result, window)
    r_path = result_path(project_name, window.window_id, root=windows_root)
    write_window_result(r_path, result.to_dict())
    leftover = leftover_partial(r_path)
    if leftover is not None:
        leftover.unlink(missing_ok=True)
    return result


def _candidates_from_decoded(
    transport: Mapping[str, Any], decoded: Mapping[str, Any]
) -> WindowCandidateMetadata:
    analysis = decoded.get("source_analysis") or {}
    intent = analysis.get("author_intent") or {}
    audience = analysis.get("target_audience") or {}
    return WindowCandidateMetadata(
        theme=str(analysis.get("main_theme") or transport.get("theme") or ""),
        intent=str(intent.get("summary") or transport.get("intent") or ""),
        intent_confidence=str(intent.get("confidence") or transport.get("ic") or ""),
        audience=str(audience.get("summary") or transport.get("aud") or ""),
        audience_confidence=str(
            audience.get("confidence") or transport.get("ac") or ""
        ),
        intent_kinds=tuple(intent.get("kinds") or ()),
        audience_kinds=tuple(audience.get("kinds") or ()),
    )


__all__ = [
    "WindowAnalysisHooks",
    "WindowRequestBundle",
    "analyze_window",
    "build_window_ai_request",
    "build_window_metadata_payload",
    "recover_window_from_transport",
    "resolve_window_execution",
    "resolve_window_settings",
]
