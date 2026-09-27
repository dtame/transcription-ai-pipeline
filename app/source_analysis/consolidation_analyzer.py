"""
ConsolidationAnalyzer — pipeline FakeAI 3B.7.4.

    ALL_WINDOWS_READY
        → ConsolidationInputBuilder
        → consolidation-1.0
        → AIRequest (consolidation-transport-v1)
        → FakeAIEngine ONLY
        → persist exact transport FIRST
        → decoder fail-closed
        → ConsolidationSemanticResult
        → validator
        → result.json atomique

Ne reconstruit pas le SourceMap.
Ne publie pas analysis/source_map.json.
N'est PAS branché dans analyzer.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from app.ai.contracts import AIRequest, AIResponse
from app.ai.errors import AIError
from app.ai.settings import StageSettings, resolve_stage_settings
from app.source_analysis.consolidation_decoder import decode_consolidation_transport
from app.source_analysis.consolidation_input import build_consolidation_input
from app.source_analysis.consolidation_models import (
    CONSOLIDATION_MAX_OUTPUT_TOKENS,
    CONSOLIDATION_OUTPUT_LANGUAGE,
    CONSOLIDATION_RESULT_SCHEMA_VERSION,
    STAGE_CONSOLIDATION,
    ConsolidationInput,
    ConsolidationProviderMetadata,
    ConsolidationSemanticResult,
)
from app.source_analysis.consolidation_prompt import (
    CONSOLIDATION_ANALYSIS_PROMPT_VERSION,
    build_consolidation_system_prompt,
    build_consolidation_user_prompt,
    consolidation_prompt_fingerprint,
    estimate_consolidation_request_tokens,
)
from app.source_analysis.consolidation_schema import (
    build_consolidation_response_schema,
    consolidation_schema_fingerprint,
)
from app.source_analysis.consolidation_signature import (
    ConsolidationSignatureInputs,
    build_consolidation_signature,
    signature_inputs_for,
)
from app.source_analysis.consolidation_validator import validate_consolidation_result
from app.source_analysis_hybrid.contracts import WINDOW_RECORD_ID_PATTERN
from app.source_analysis.consolidation_writer import (
    leftover_partial,
    metadata_path,
    result_path,
    transport_path,
    write_consolidation_input,
    write_consolidation_metadata,
    write_consolidation_result,
    write_consolidation_transport,
)
from app.source_analysis.errors import (
    ConsolidationError,
    ConsolidationInputError,
    ConsolidationResultValidationError,
    ConsolidationTransportValidationError,
    ConsolidationTransportWriteError,
    SourceMapEditorialLeakError,
    SourceMapValidationError,
    WindowsIncompleteError,
)
from app.source_analysis.orchestration_models import WindowOrchestrationResult
from app.source_analysis.window_writer import artifact_sha256
from app.source_analysis_hybrid.contracts import WindowPlan


@dataclass(frozen=True)
class ConsolidationAnalysisHooks:
    after_generate: Callable[[AIResponse], None] | None = None
    after_transport_write: Callable[[Path], None] | None = None
    before_decode: Callable[[Mapping[str, Any]], None] | None = None
    after_validate: Callable[[ConsolidationSemanticResult], None] | None = None
    before_result_write: Callable[[ConsolidationSemanticResult], None] | None = None


@dataclass(frozen=True)
class ConsolidationRequestBundle:
    request: AIRequest
    system_prompt: str
    user_prompt: str
    response_schema: dict
    response_schema_sha256: str
    signature: str
    settings: StageSettings
    token_estimate: dict[str, Any]
    signature_inputs: ConsolidationSignatureInputs
    consolidation_input: ConsolidationInput


def resolve_consolidation_settings(settings: StageSettings | None = None) -> StageSettings:
    return settings or resolve_stage_settings(STAGE_CONSOLIDATION)


def build_consolidation_ai_request(
    consolidation_input: ConsolidationInput,
    *,
    settings: StageSettings | None = None,
    provider: str | None = None,
    model: str | None = None,
    output_language: str = CONSOLIDATION_OUTPUT_LANGUAGE,
) -> ConsolidationRequestBundle:
    resolved = resolve_consolidation_settings(settings)
    system_prompt = build_consolidation_system_prompt(output_language)
    user_prompt = build_consolidation_user_prompt(
        consolidation_input, primary_language=output_language
    )
    response_schema = build_consolidation_response_schema()
    schema_sha = consolidation_schema_fingerprint(response_schema)
    max_output = resolved.max_output_tokens or CONSOLIDATION_MAX_OUTPUT_TOKENS
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
            "stage": STAGE_CONSOLIDATION,
            "output_language": output_language,
        },
    )
    inputs = signature_inputs_for(
        consolidation_input,
        prompt_sha256=consolidation_prompt_fingerprint(system_prompt, user_prompt),
        response_schema_sha256=schema_sha,
        provider=str(resolved_provider),
        model=str(resolved_model or ""),
        temperature=resolved.temperature,
        max_output_tokens=int(max_output),
        context_safety_ratio=float(resolved.context_safety_ratio),
        output_language=output_language,
    )
    return ConsolidationRequestBundle(
        request=request,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_schema=response_schema,
        response_schema_sha256=schema_sha,
        signature=build_consolidation_signature(inputs),
        settings=resolved,
        token_estimate=estimate_consolidation_request_tokens(
            consolidation_input, primary_language=output_language
        ),
        signature_inputs=inputs,
        consolidation_input=consolidation_input,
    )


def resolve_consolidation_execution(
    consolidation_input: ConsolidationInput,
    *,
    settings: StageSettings | None = None,
    engine=None,
    provider: str | None = None,
    model: str | None = None,
    output_language: str = CONSOLIDATION_OUTPUT_LANGUAGE,
) -> ConsolidationRequestBundle:
    bundle = build_consolidation_ai_request(
        consolidation_input,
        settings=settings,
        provider=provider,
        model=model,
        output_language=output_language,
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
        consolidation_input,
        prompt_sha256=consolidation_prompt_fingerprint(
            bundle.system_prompt, bundle.user_prompt
        ),
        response_schema_sha256=bundle.response_schema_sha256,
        provider=resolved_provider,
        model=str(resolved_model or ""),
        temperature=bundle.settings.temperature,
        max_output_tokens=request.max_output_tokens,
        context_safety_ratio=float(bundle.settings.context_safety_ratio),
        output_language=output_language,
    )
    return ConsolidationRequestBundle(
        request=request,
        system_prompt=bundle.system_prompt,
        user_prompt=bundle.user_prompt,
        response_schema=bundle.response_schema,
        response_schema_sha256=bundle.response_schema_sha256,
        signature=build_consolidation_signature(inputs),
        settings=bundle.settings,
        token_estimate=bundle.token_estimate,
        signature_inputs=inputs,
        consolidation_input=consolidation_input,
    )


def build_consolidation_metadata_payload(
    *,
    bundle: ConsolidationRequestBundle,
    transport_sha256: str,
    provider_metadata: ConsolidationProviderMetadata | None = None,
) -> dict[str, Any]:
    inputs = bundle.signature_inputs
    identity = {
        "consolidation_input_hash": inputs.consolidation_input_hash,
        "consolidation_signature": bundle.signature,
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
        "window_result_hashes": list(inputs.window_result_hashes),
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
        "schema_version": CONSOLIDATION_RESULT_SCHEMA_VERSION,
        "identity": identity,
        "observability": observability,
    }


def _require_parsed(response: AIResponse) -> Mapping[str, Any]:
    parsed = response.parsed
    if not isinstance(parsed, Mapping):
        raise ConsolidationTransportValidationError(
            "AIResponse.parsed absent ou non objet — le chemin normal "
            "consomme parsed, jamais json.loads(text) dans le service."
        )
    return parsed


def _provider_metadata(response: AIResponse) -> ConsolidationProviderMetadata:
    return ConsolidationProviderMetadata(
        provider=response.provider,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        total_tokens=response.total_tokens,
        usage_source=response.usage_source,
        finish_reason=response.finish_reason,
    )


def consolidate(
    consolidation_input: ConsolidationInput,
    engine,
    *,
    settings: StageSettings | None = None,
    consolidation_root: Path,
    project_name: str = "fixture",
    hooks: ConsolidationAnalysisHooks | None = None,
    write_input: bool = True,
    allowed_record_id_pattern=WINDOW_RECORD_ID_PATTERN,
) -> ConsolidationSemanticResult:
    """
    Pipeline de consolidation. engine obligatoire (FakeAI en 3B.7.4).

    max_attempts = 1 : un seul engine.generate. Aucun retry local.
    """
    if engine is None:
        raise ConsolidationError(
            "ConsolidationAnalyzer exige un moteur injecté. "
            "Aucun get_engine_for_stage : 3B.7.4 est FakeAI only."
        )

    bundle = resolve_consolidation_execution(
        consolidation_input, settings=settings, engine=engine
    )
    request = bundle.request
    signature = bundle.signature

    from app.source_analysis.consolidation_writer import input_path

    i_path = input_path(project_name, root=consolidation_root)
    t_path = transport_path(project_name, root=consolidation_root)
    r_path = result_path(project_name, root=consolidation_root)
    m_path = metadata_path(project_name, root=consolidation_root)

    if write_input:
        write_consolidation_input(i_path, consolidation_input.to_dict())
        leftover = leftover_partial(i_path)
        if leftover is not None:
            leftover.unlink(missing_ok=True)

    try:
        response = engine.generate(request)
    except KeyboardInterrupt:
        raise
    except AIError:
        raise

    if hooks and hooks.after_generate:
        hooks.after_generate(response)

    transport = _require_parsed(response)

    try:
        write_consolidation_transport(t_path, transport)
    except ConsolidationTransportWriteError:
        raise
    except KeyboardInterrupt:
        raise

    if leftover_partial(t_path) is not None:
        leftover_partial(t_path).unlink(missing_ok=True)

    write_consolidation_metadata(
        m_path,
        build_consolidation_metadata_payload(
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
        result = decode_consolidation_transport(
            transport,
            consolidation_input,
            signature=signature,
            provider_metadata=_provider_metadata(response),
        )
        validate_consolidation_result(
            result,
            consolidation_input,
            allowed_record_id_pattern=allowed_record_id_pattern,
        )
    except (
        SourceMapEditorialLeakError,
        SourceMapValidationError,
        ConsolidationTransportValidationError,
        ConsolidationResultValidationError,
    ):
        raise
    except KeyboardInterrupt:
        raise

    if hooks and hooks.after_validate:
        hooks.after_validate(result)
    if hooks and hooks.before_result_write:
        hooks.before_result_write(result)

    write_consolidation_result(r_path, result.to_dict())
    leftover = leftover_partial(r_path)
    if leftover is not None:
        leftover.unlink(missing_ok=True)
    return result


def consolidate_from_orchestration(
    orchestration: WindowOrchestrationResult,
    engine,
    *,
    plan: WindowPlan | None = None,
    settings: StageSettings | None = None,
    consolidation_root: Path,
    project_name: str = "fixture",
    hooks: ConsolidationAnalysisHooks | None = None,
) -> ConsolidationSemanticResult:
    """
    Porte ALL_WINDOWS_READY. Si le jeu est incomplet : 0 appel FakeAI.
    """
    try:
        consolidation_input = build_consolidation_input(orchestration, plan=plan)
    except (WindowsIncompleteError, ConsolidationInputError):
        raise
    return consolidate(
        consolidation_input,
        engine,
        settings=settings,
        consolidation_root=consolidation_root,
        project_name=project_name,
        hooks=hooks,
    )


__all__ = [
    "ConsolidationAnalysisHooks",
    "ConsolidationRequestBundle",
    "build_consolidation_ai_request",
    "build_consolidation_metadata_payload",
    "consolidate",
    "consolidate_from_orchestration",
    "resolve_consolidation_execution",
    "resolve_consolidation_settings",
]
