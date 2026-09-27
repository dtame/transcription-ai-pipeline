"""
Pipeline fenêtre V3 isolé. FakeAI only. Pas branché sur analyzer.py.

Transport-first. 1 generate. Aucun retry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.ai.contracts import AIRequest, AIResponse
from app.ai.errors import AIError, AIStructuredOutputError
from app.ai.thinking import thinking_fingerprint
from app.file_utils import content_hash
from app.source_analysis.errors import (
    WindowGranularityLimitExceeded,
    WindowSemanticCapacityExceeded,
    WindowSourceRefError,
    WindowTransportValidationError,
)
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_models import (
    STAGE_WINDOW,
    WINDOW_MAX_OUTPUT_TOKENS,
    WindowProviderMetadata,
    WindowSemanticResult,
)
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_hybrid.materialize import materialize_window_content
from app.source_analysis_local_v3.constants import (
    SEMANTIC_TRANSPORT_VERSION_V3,
    SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
    WINDOW_ANALYSIS_PROMPT_VERSION_V132,
    WINDOW_ANALYSIS_PROMPT_VERSION_V140,
)
from app.source_analysis_local_v3.decoder import (
    decode_v3_transport,
    decode_v31_local_lite_transport,
    looks_like_truncated_json,
)
from app.source_analysis_local_v3.prompt import (
    build_window_system_prompt_v13,
    build_window_system_prompt_v131,
    build_window_system_prompt_v132,
    build_window_system_prompt_v140,
    build_window_user_prompt_v13,
    build_window_user_prompt_v131,
    build_window_user_prompt_v132,
    build_window_user_prompt_v140,
    window_prompt_v13_fingerprint,
    window_prompt_v131_fingerprint,
    window_prompt_v132_fingerprint,
    window_prompt_v140_fingerprint,
)
from app.source_analysis_local_v3.result import (
    v3_transport_to_window_result,
    v31_transport_to_window_result,
)
from app.source_analysis_local_v3.schema import (
    build_semantic_transport_v3_schema,
    build_semantic_transport_v31_local_lite_schema,
    semantic_transport_v3_fingerprint,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis_local_v3.validator import validate_v3_transport
from app.source_analysis_thinking_contract.v2_config import (
    V2_EFFORT,
    V2_THINKING_CONTRACT,
    V2_THINKING_MODE,
    v2_thinking_metadata,
)


@dataclass
class LocalV3WindowOutcome:
    ready: bool
    transport: dict[str, Any] | None
    resolved: dict[str, Any] | None
    result: WindowSemanticResult | None
    errors: tuple[str, ...] = ()
    capacity_signaled: bool = False
    parse_ok: bool = False
    provider_ok: bool = False
    retried: bool = False
    provider_calls: int = 0
    request: AIRequest | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "transport_present": self.transport is not None,
            "resolved_present": self.resolved is not None,
            "result_present": self.result is not None,
            "errors": list(self.errors),
            "capacity_signaled": self.capacity_signaled,
            "parse_ok": self.parse_ok,
            "provider_ok": self.provider_ok,
            "retried": self.retried,
            "provider_calls": self.provider_calls,
        }


def build_v3_window_request(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    model: str = "fake-model",
) -> AIRequest:
    content = materialize_window_content(transcript, window)
    system = build_window_system_prompt_v13(transcript.primary_language)
    user = build_window_user_prompt_v13(transcript, window, content)
    return AIRequest(
        prompt=user,
        system_prompt=system,
        model=model,
        max_output_tokens=WINDOW_MAX_OUTPUT_TOKENS,
        response_schema=build_semantic_transport_v3_schema(),
        thinking_mode=V2_THINKING_MODE,
        effort=V2_EFFORT,
        metadata={
            "stage": STAGE_WINDOW,
            "window_id": window.window_id,
            "transport_version": SEMANTIC_TRANSPORT_VERSION_V3,
            "schema_sha256": semantic_transport_v3_fingerprint(),
            "thinking_contract": V2_THINKING_CONTRACT,
            **v2_thinking_metadata(),
            "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V13,
            "prompt_sha256": window_prompt_v13_fingerprint(system, user),
        },
    )


def build_v131_window_request(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    model: str = "fake-model",
) -> AIRequest:
    """Requête 1.3.1 isolée. Ne remplace pas build_v3_window_request (1.3)."""
    content = materialize_window_content(transcript, window)
    system = build_window_system_prompt_v131(transcript.primary_language)
    user = build_window_user_prompt_v131(transcript, window, content)
    return AIRequest(
        prompt=user,
        system_prompt=system,
        model=model,
        max_output_tokens=WINDOW_MAX_OUTPUT_TOKENS,
        response_schema=build_semantic_transport_v3_schema(),
        thinking_mode=V2_THINKING_MODE,
        effort=V2_EFFORT,
        metadata={
            "stage": STAGE_WINDOW,
            "window_id": window.window_id,
            "transport_version": SEMANTIC_TRANSPORT_VERSION_V3,
            "schema_sha256": semantic_transport_v3_fingerprint(),
            "thinking_contract": V2_THINKING_CONTRACT,
            **v2_thinking_metadata(),
            "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V131,
            "prompt_sha256": window_prompt_v131_fingerprint(system, user),
        },
    )


def build_v132_window_request(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    model: str = "fake-model",
) -> AIRequest:
    """Requête 1.3.2 isolée. Ne remplace pas 1.3 / 1.3.1."""
    content = materialize_window_content(transcript, window)
    system = build_window_system_prompt_v132(transcript.primary_language)
    user = build_window_user_prompt_v132(transcript, window, content)
    return AIRequest(
        prompt=user,
        system_prompt=system,
        model=model,
        max_output_tokens=WINDOW_MAX_OUTPUT_TOKENS,
        response_schema=build_semantic_transport_v3_schema(),
        thinking_mode=V2_THINKING_MODE,
        effort=V2_EFFORT,
        metadata={
            "stage": STAGE_WINDOW,
            "window_id": window.window_id,
            "transport_version": SEMANTIC_TRANSPORT_VERSION_V3,
            "schema_sha256": semantic_transport_v3_fingerprint(),
            "thinking_contract": V2_THINKING_CONTRACT,
            **v2_thinking_metadata(),
            "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V132,
            "prompt_sha256": window_prompt_v132_fingerprint(system, user),
        },
    )


def build_v140_window_request(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    model: str = "fake-model",
) -> AIRequest:
    """Requête 1.4.0 / v3.1-local-lite. Ne remplace pas 1.3 / 1.3.1 / 1.3.2."""
    content = materialize_window_content(transcript, window)
    system = build_window_system_prompt_v140(transcript.primary_language)
    user = build_window_user_prompt_v140(transcript, window, content)
    return AIRequest(
        prompt=user,
        system_prompt=system,
        model=model,
        max_output_tokens=WINDOW_MAX_OUTPUT_TOKENS,
        response_schema=build_semantic_transport_v31_local_lite_schema(),
        thinking_mode=V2_THINKING_MODE,
        effort=V2_EFFORT,
        metadata={
            "stage": STAGE_WINDOW,
            "window_id": window.window_id,
            "transport_version": SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
            "schema_sha256": semantic_transport_v31_local_lite_fingerprint(),
            "thinking_contract": V2_THINKING_CONTRACT,
            **v2_thinking_metadata(),
            "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V140,
            "prompt_sha256": window_prompt_v140_fingerprint(system, user),
        },
    )


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


def analyze_window_v3(
    window: WindowInput,
    transcript: TranscriptInput,
    engine,
    *,
    parent_depth: int = 0,
) -> LocalV3WindowOutcome:
    del parent_depth
    if engine is None:
        raise ValueError("FakeAI engine obligatoire — aucun get_engine_for_stage")
    request = build_v3_window_request(window, transcript, model=engine.resolve_model())
    try:
        response = engine.generate(request)
    except AIStructuredOutputError as exc:
        return LocalV3WindowOutcome(
            ready=False,
            transport=None,
            resolved=None,
            result=None,
            errors=(str(exc),),
            parse_ok=False,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )
    except AIError as exc:
        return LocalV3WindowOutcome(
            ready=False,
            transport=None,
            resolved=None,
            result=None,
            errors=(str(exc),),
            parse_ok=False,
            provider_ok=False,
            provider_calls=1,
            request=request,
        )

    parsed = response.parsed
    transport: dict[str, Any] | None = dict(parsed) if isinstance(parsed, Mapping) else None
    if transport is None:
        return LocalV3WindowOutcome(
            ready=False,
            transport=None,
            resolved=None,
            result=None,
            errors=("parsed absent — no repair",),
            parse_ok=False,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )

    try:
        decoded = decode_v3_transport(
            transport,
            allowed_source_refs=set(window.owned_src_refs) | set(window.context_src_refs),
        )
    except (WindowTransportValidationError, Exception) as exc:
        return LocalV3WindowOutcome(
            ready=False,
            transport=transport,
            resolved=None,
            result=None,
            errors=(str(exc),),
            parse_ok=False,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )

    try:
        resolved = validate_v3_transport(decoded, window)
    except WindowSemanticCapacityExceeded as exc:
        return LocalV3WindowOutcome(
            ready=False,
            transport=decoded,
            resolved=None,
            result=None,
            errors=(str(exc),),
            capacity_signaled=True,
            parse_ok=True,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )
    except (
        WindowGranularityLimitExceeded,
        WindowSourceRefError,
        WindowTransportValidationError,
    ) as exc:
        return LocalV3WindowOutcome(
            ready=False,
            transport=decoded,
            resolved=None,
            result=None,
            errors=(str(exc),),
            parse_ok=True,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )

    signature = content_hash(
        window_prompt_v13_fingerprint(request.system_prompt or "", request.prompt)
        + "\n"
        + thinking_fingerprint(request.thinking_mode, request.effort)
    )
    result = v3_transport_to_window_result(
        resolved,
        window,
        signature=signature,
        provider_metadata=_provider_metadata(response),
    )
    return LocalV3WindowOutcome(
        ready=True,
        transport=decoded,
        resolved=resolved,
        result=result,
        parse_ok=True,
        provider_ok=True,
        provider_calls=1,
        request=request,
    )


def analyze_window_v31(
    window: WindowInput,
    transcript: TranscriptInput,
    engine,
    *,
    parent_depth: int = 0,
) -> LocalV3WindowOutcome:
    del parent_depth
    if engine is None:
        raise ValueError("FakeAI engine obligatoire — aucun get_engine_for_stage")
    request = build_v140_window_request(window, transcript, model=engine.resolve_model())
    try:
        response = engine.generate(request)
    except AIStructuredOutputError as exc:
        return LocalV3WindowOutcome(
            ready=False,
            transport=None,
            resolved=None,
            result=None,
            errors=(str(exc),),
            parse_ok=False,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )
    except AIError as exc:
        return LocalV3WindowOutcome(
            ready=False,
            transport=None,
            resolved=None,
            result=None,
            errors=(str(exc),),
            parse_ok=False,
            provider_ok=False,
            provider_calls=1,
            request=request,
        )

    parsed = response.parsed
    transport: dict[str, Any] | None = dict(parsed) if isinstance(parsed, Mapping) else None
    if transport is None:
        return LocalV3WindowOutcome(
            ready=False,
            transport=None,
            resolved=None,
            result=None,
            errors=("parsed absent — no repair",),
            parse_ok=False,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )

    try:
        decoded = decode_v31_local_lite_transport(
            transport,
            allowed_source_refs=set(window.owned_src_refs) | set(window.context_src_refs),
        )
    except (WindowTransportValidationError, Exception) as exc:
        return LocalV3WindowOutcome(
            ready=False,
            transport=transport,
            resolved=None,
            result=None,
            errors=(str(exc),),
            parse_ok=False,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )

    try:
        resolved = validate_v3_transport(decoded, window)
    except WindowSemanticCapacityExceeded as exc:
        return LocalV3WindowOutcome(
            ready=False,
            transport=decoded,
            resolved=None,
            result=None,
            errors=(str(exc),),
            capacity_signaled=True,
            parse_ok=True,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )
    except (
        WindowGranularityLimitExceeded,
        WindowSourceRefError,
        WindowTransportValidationError,
    ) as exc:
        return LocalV3WindowOutcome(
            ready=False,
            transport=decoded,
            resolved=None,
            result=None,
            errors=(str(exc),),
            parse_ok=True,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )

    signature = content_hash(
        window_prompt_v140_fingerprint(request.system_prompt or "", request.prompt)
        + "\n"
        + thinking_fingerprint(request.thinking_mode, request.effort)
    )
    result = v31_transport_to_window_result(
        resolved,
        window,
        signature=signature,
        provider_metadata=_provider_metadata(response),
    )
    return LocalV3WindowOutcome(
        ready=True,
        transport=decoded,
        resolved=resolved,
        result=result,
        parse_ok=True,
        provider_ok=True,
        provider_calls=1,
        request=request,
    )
