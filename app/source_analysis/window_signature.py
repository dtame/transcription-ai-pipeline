"""
Window analysis signature — identité de cache future d'une fenêtre.

Philosophie identique à SourceAnalyzer.build_signature :
données + contrat + code réel + routage + réglages.
Aucun timestamp, aucune latence, aucun request_id.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.file_utils import content_hash
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_models import STAGE_WINDOW
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    resolve_window_prompt_version,
    window_prompt_fingerprint,
)
from app.ai.thinking import (
    is_historical_thinking_default,
    normalize_effort,
    normalize_thinking_mode,
)
from app.source_analysis_hybrid.constants import (
    PLANNER_VERSION,
    WINDOW_TRANSPORT_VERSION,
)
from app.source_analysis_hybrid.contracts import WindowInput


@dataclass(frozen=True)
class WindowSignatureInputs:
    window_input_hash: str
    window_id: str
    transcript_id: str
    transcript_sha256: str
    planner_version: str
    prompt_version: str
    prompt_sha256: str
    transport_version: str
    response_schema_sha256: str
    provider: str
    model: str
    temperature: float | None
    max_output_tokens: int | None
    output_language: str
    context_safety_ratio: float
    stage: str = STAGE_WINDOW
    thinking_mode: str | None = None
    effort: str | None = None
    thinking_budget_tokens: int | None = None

    def to_dict(self) -> dict:
        payload = {
            "context_safety_ratio": self.context_safety_ratio,
            "max_output_tokens": self.max_output_tokens,
            "model": self.model,
            "output_language": self.output_language,
            "planner_version": self.planner_version,
            "prompt_sha256": self.prompt_sha256,
            "prompt_version": self.prompt_version,
            "provider": self.provider,
            "response_schema_sha256": self.response_schema_sha256,
            "stage": self.stage,
            "temperature": self.temperature,
            "transcript_id": self.transcript_id,
            "transcript_sha256": self.transcript_sha256,
            "transport_version": self.transport_version,
            "window_id": self.window_id,
            "window_input_hash": self.window_input_hash,
        }
        if not is_historical_thinking_default(
            self.thinking_mode, self.effort, self.thinking_budget_tokens
        ):
            payload["thinking_mode"] = normalize_thinking_mode(self.thinking_mode)
            payload["effort"] = normalize_effort(self.effort)
            if self.thinking_budget_tokens is not None:
                payload["thinking_budget_tokens"] = int(self.thinking_budget_tokens)
        return payload


def build_window_analysis_signature(inputs: WindowSignatureInputs) -> str:
    payload = json.dumps(inputs.to_dict(), ensure_ascii=False, sort_keys=True)
    return content_hash(payload)


def signature_inputs_for(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    system_prompt: str,
    user_prompt: str,
    response_schema_sha256: str,
    provider: str,
    model: str,
    temperature: float | None,
    max_output_tokens: int | None,
    context_safety_ratio: float,
    prompt_version: str | None = None,
    thinking_mode: str | None = None,
    effort: str | None = None,
    thinking_budget_tokens: int | None = None,
) -> WindowSignatureInputs:
    return WindowSignatureInputs(
        window_input_hash=window.input_hash,
        window_id=window.window_id,
        transcript_id=transcript.transcript_id,
        transcript_sha256=transcript.content_sha256,
        planner_version=window.planner_version or PLANNER_VERSION,
        prompt_version=resolve_window_prompt_version(
            prompt_version or WINDOW_ANALYSIS_PROMPT_VERSION
        ),
        prompt_sha256=window_prompt_fingerprint(system_prompt, user_prompt),
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
        thinking_budget_tokens=thinking_budget_tokens,
    )


__all__ = [
    "WindowSignatureInputs",
    "build_window_analysis_signature",
    "signature_inputs_for",
]
