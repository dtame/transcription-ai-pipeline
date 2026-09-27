"""Identités signature / cache / forensics pour thinking V2."""

from __future__ import annotations

import json
from typing import Any

from app.ai.thinking import thinking_fingerprint, thinking_identity
from app.file_utils import content_hash
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_signature import (
    WindowSignatureInputs,
    build_window_analysis_signature,
)
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_thinking_contract.constants import (
    WINDOW_ID,
)


def v2_request_fingerprint(
    *,
    thinking_mode: str | None,
    effort: str | None,
    thinking_budget_tokens: int | None = None,
) -> str:
    return thinking_fingerprint(
        thinking_mode, effort, thinking_budget_tokens
    )


def v2_forensic_identity(
    *,
    window_id: str = WINDOW_ID,
    content_sha256: str,
    thinking_mode: str | None,
    effort: str | None,
    prompt_sha256: str = "",
    schema_sha256: str = "",
) -> str:
    payload = {
        "window_id": window_id,
        "content_sha256": content_sha256,
        "prompt_sha256": prompt_sha256,
        "schema_sha256": schema_sha256,
        **thinking_identity(thinking_mode=thinking_mode, effort=effort),
    }
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def signature_with_thinking(
    base: WindowSignatureInputs,
    *,
    thinking_mode: str | None,
    effort: str | None,
) -> str:
    return build_window_analysis_signature(
        WindowSignatureInputs(
            window_input_hash=base.window_input_hash,
            window_id=base.window_id,
            transcript_id=base.transcript_id,
            transcript_sha256=base.transcript_sha256,
            planner_version=base.planner_version,
            prompt_version=base.prompt_version,
            prompt_sha256=base.prompt_sha256,
            transport_version=base.transport_version,
            response_schema_sha256=base.response_schema_sha256,
            provider=base.provider,
            model=base.model,
            temperature=base.temperature,
            max_output_tokens=base.max_output_tokens,
            output_language=base.output_language,
            context_safety_ratio=base.context_safety_ratio,
            stage=base.stage,
            thinking_mode=thinking_mode,
            effort=effort,
        )
    )


def same_window_thinking_signatures(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    system_prompt: str,
    user_prompt: str,
    response_schema_sha256: str,
    provider: str,
    model: str,
    temperature: float | None,
    max_output_tokens: int,
    context_safety_ratio: float,
    prompt_version: str,
) -> dict[str, Any]:
    from app.source_analysis.window_prompt import window_prompt_fingerprint
    from app.source_analysis_hybrid.constants import (
        PLANNER_VERSION,
        WINDOW_TRANSPORT_VERSION,
    )

    prompt_sha = window_prompt_fingerprint(system_prompt, user_prompt)

    def _inputs(*, thinking_mode=None, effort=None) -> WindowSignatureInputs:
        return WindowSignatureInputs(
            window_input_hash=window.input_hash,
            window_id=window.window_id,
            transcript_id=transcript.transcript_id,
            transcript_sha256=transcript.content_sha256,
            planner_version=window.planner_version or PLANNER_VERSION,
            prompt_version=prompt_version,
            prompt_sha256=prompt_sha,
            transport_version=WINDOW_TRANSPORT_VERSION,
            response_schema_sha256=response_schema_sha256,
            provider=provider,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            output_language=transcript.primary_language,
            context_safety_ratio=float(context_safety_ratio),
            thinking_mode=thinking_mode,
            effort=effort,
        )

    historical = _inputs()
    disabled = _inputs(thinking_mode="disabled", effort=None)
    low = _inputs(thinking_mode="adaptive", effort="low")
    medium = _inputs(thinking_mode="adaptive", effort="medium")
    high = _inputs(thinking_mode="adaptive", effort="high")
    signatures = {
        "provider_default": build_window_analysis_signature(historical),
        "THINKING_DISABLED": build_window_analysis_signature(disabled),
        "ADAPTIVE_LOW": build_window_analysis_signature(low),
        "ADAPTIVE_MEDIUM": build_window_analysis_signature(medium),
        "ADAPTIVE_HIGH": build_window_analysis_signature(high),
    }
    values = list(signatures.values())
    return {
        "signatures": signatures,
        "all_distinct": len(set(values)) == len(values),
        "forensics": {
            name: v2_forensic_identity(
                window_id=window.window_id,
                content_sha256=transcript.content_sha256,
                thinking_mode=mode,
                effort=effort,
                prompt_sha256=historical.prompt_sha256,
                schema_sha256=response_schema_sha256,
            )
            for name, mode, effort in (
                ("provider_default", None, None),
                ("THINKING_DISABLED", "disabled", None),
                ("ADAPTIVE_LOW", "adaptive", "low"),
                ("ADAPTIVE_MEDIUM", "adaptive", "medium"),
                ("ADAPTIVE_HIGH", "adaptive", "high"),
            )
        },
    }


__all__ = [
    "same_window_thinking_signatures",
    "signature_with_thinking",
    "v2_forensic_identity",
    "v2_request_fingerprint",
]
