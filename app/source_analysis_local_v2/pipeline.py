"""
Pipeline fenêtre V2 isolé. FakeAI only. Pas branché sur analyzer.py.

Transport-first. 1 generate. Aucun retry. Subdivision = plan only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
from app.source_analysis_local_v2.constants import (
    SEMANTIC_TRANSPORT_VERSION_V2,
    WINDOW_ANALYSIS_PROMPT_VERSION_V121,
)
from app.source_analysis_local_v2.decoder import decode_v2_transport, looks_like_truncated_json
from app.source_analysis_local_v2.prompt import (
    build_window_system_prompt_v121,
    build_window_user_prompt_v121,
    window_prompt_v121_fingerprint,
)
from app.source_analysis_local_v2.result import v2_transport_to_window_result
from app.source_analysis_local_v2.schema import (
    build_semantic_transport_v2_schema,
    semantic_transport_v2_fingerprint,
)
from app.source_analysis_local_v2.subdivision import (
    LocalV2SubdivisionNotTriggered,
    SubdivisionPlan,
    plan_subdivision,
)
from app.source_analysis_local_v2.validator import validate_v2_transport
from app.source_analysis_thinking_contract.v2_config import (
    V2_EFFORT,
    V2_THINKING_CONTRACT,
    V2_THINKING_MODE,
    v2_thinking_metadata,
)


@dataclass
class LocalV2WindowOutcome:
    ready: bool
    transport: dict[str, Any] | None
    result: WindowSemanticResult | None
    errors: tuple[str, ...] = ()
    capacity_signaled: bool = False
    subdivision_plan: SubdivisionPlan | None = None
    parse_ok: bool = False
    provider_ok: bool = False
    retried: bool = False
    subdivided_executed: bool = False
    provider_calls: int = 0
    request: AIRequest | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "transport_present": self.transport is not None,
            "result_present": self.result is not None,
            "errors": list(self.errors),
            "capacity_signaled": self.capacity_signaled,
            "subdivision_plan": (
                self.subdivision_plan.to_dict() if self.subdivision_plan else None
            ),
            "parse_ok": self.parse_ok,
            "provider_ok": self.provider_ok,
            "retried": self.retried,
            "subdivided_executed": self.subdivided_executed,
            "provider_calls": self.provider_calls,
        }


def build_v2_window_request(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    model: str = "fake-model",
) -> AIRequest:
    content = materialize_window_content(transcript, window)
    system = build_window_system_prompt_v121(transcript.primary_language)
    user = build_window_user_prompt_v121(transcript, window, content)
    return AIRequest(
        prompt=user,
        system_prompt=system,
        model=model,
        max_output_tokens=WINDOW_MAX_OUTPUT_TOKENS,
        response_schema=build_semantic_transport_v2_schema(),
        thinking_mode=V2_THINKING_MODE,
        effort=V2_EFFORT,
        metadata={
            "stage": STAGE_WINDOW,
            "window_id": window.window_id,
            "transport_version": SEMANTIC_TRANSPORT_VERSION_V2,
            "schema_sha256": semantic_transport_v2_fingerprint(),
            "thinking_contract": V2_THINKING_CONTRACT,
            **v2_thinking_metadata(),
            "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V121,
            "prompt_sha256": window_prompt_v121_fingerprint(system, user),
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


def analyze_window_v2(
    window: WindowInput,
    transcript: TranscriptInput,
    engine,
    *,
    parent_depth: int = 0,
) -> LocalV2WindowOutcome:
    if engine is None:
        raise ValueError("FakeAI engine obligatoire — aucun get_engine_for_stage")
    request = build_v2_window_request(window, transcript, model=engine.resolve_model())
    try:
        response = engine.generate(request)
    except AIStructuredOutputError as exc:
        text = getattr(getattr(exc, "response", None), "text", "") or ""
        truncated = looks_like_truncated_json(text)
        return LocalV2WindowOutcome(
            ready=False,
            transport=None,
            result=None,
            errors=(str(exc),),
            parse_ok=False,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )
    except AIError as exc:
        return LocalV2WindowOutcome(
            ready=False,
            transport=None,
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
        return LocalV2WindowOutcome(
            ready=False,
            transport=None,
            result=None,
            errors=("parsed absent — no repair",),
            parse_ok=False,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )

    try:
        decoded = decode_v2_transport(
            transport,
            allowed_source_refs=set(window.owned_src_refs) | set(window.context_src_refs),
        )
    except (WindowTransportValidationError, Exception) as exc:
        return LocalV2WindowOutcome(
            ready=False,
            transport=transport,
            result=None,
            errors=(str(exc),),
            parse_ok=False,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )

    try:
        validate_v2_transport(decoded, window)
    except WindowSemanticCapacityExceeded as exc:
        plan = None
        try:
            plan = plan_subdivision(
                window,
                transcript,
                decoded,
                parent_depth=parent_depth,
                trigger_validated=True,
                parse_ok=True,
                provider_ok=True,
                truncated=False,
            )
        except (LocalV2SubdivisionNotTriggered, Exception) as sub_exc:
            return LocalV2WindowOutcome(
                ready=False,
                transport=decoded,
                result=None,
                errors=(str(exc), str(sub_exc)),
                capacity_signaled=True,
                parse_ok=True,
                provider_ok=True,
                provider_calls=1,
                request=request,
            )
        return LocalV2WindowOutcome(
            ready=False,
            transport=decoded,
            result=None,
            errors=(str(exc),),
            capacity_signaled=True,
            subdivision_plan=plan,
            parse_ok=True,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )
    except (WindowGranularityLimitExceeded, WindowSourceRefError, WindowTransportValidationError) as exc:
        return LocalV2WindowOutcome(
            ready=False,
            transport=decoded,
            result=None,
            errors=(str(exc),),
            parse_ok=True,
            provider_ok=True,
            provider_calls=1,
            request=request,
        )

    signature = content_hash(
        window_prompt_v121_fingerprint(request.system_prompt or "", request.prompt)
        + "\n"
        + thinking_fingerprint(request.thinking_mode, request.effort)
    )
    result = v2_transport_to_window_result(
        decoded,
        window,
        signature=signature,
        provider_metadata=_provider_metadata(response),
    )
    return LocalV2WindowOutcome(
        ready=True,
        transport=decoded,
        result=result,
        parse_ok=True,
        provider_ok=True,
        provider_calls=1,
        request=request,
    )
