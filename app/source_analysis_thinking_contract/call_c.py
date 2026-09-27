"""Reconstruction offline du payload CALL C. Aucun envoi."""

from __future__ import annotations

from typing import Any

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.source_analysis.ultra_compact_schema import build_ultra_compact_response_schema
from app.source_analysis_thinking_contract.constants import (
    CALL_C_EFFECTIVE_EFFORT,
    CALL_C_EFFECTIVE_THINKING_MODE,
    CALL_C_EFFORT_EXPLICIT,
    CALL_C_FINISH,
    CALL_C_OUTPUT,
    CALL_C_PROVIDER_INPUT,
    CALL_C_ROOT_CAUSE,
    CALL_C_THINKING_EXPLICIT,
    CALL_C_THINKING_TOKENS,
    MAX_OUTPUT_TOKENS_FROZEN,
    MODE,
    MODEL,
    PHASE,
    PRIMARY_ROOT_CAUSE,
    SCHEMA_VERSION,
    SMALL_SIGNATURE,
)


def reconstruct_call_c_request() -> AIRequest:
    return AIRequest(
        prompt="historical CALL C reconstruction — not sent",
        system_prompt="window-analysis-1.1 historical",
        model=MODEL,
        temperature=None,
        max_output_tokens=MAX_OUTPUT_TOKENS_FROZEN,
        response_schema=build_ultra_compact_response_schema(),
    )


def reconstruct_call_c_payload() -> dict[str, Any]:
    engine = AnthropicEngine(model=MODEL, api_key="cle-de-test")
    request = reconstruct_call_c_request()
    return engine.build_payload(request, MODEL)


def call_c_effective_contract() -> dict[str, Any]:
    payload = reconstruct_call_c_payload()
    fields = sorted(payload.keys())
    remaining = (
        CALL_C_OUTPUT - CALL_C_THINKING_TOKENS
        if CALL_C_OUTPUT is not None and CALL_C_THINKING_TOKENS is not None
        else None
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "signature": SMALL_SIGNATURE,
        "actual_historical_payload_fields": fields,
        "thinking_explicit": CALL_C_THINKING_EXPLICIT,
        "effort_explicit": CALL_C_EFFORT_EXPLICIT,
        "temperature_in_payload": "temperature" in payload,
        "output_config_format_present": bool(
            isinstance(payload.get("output_config"), dict)
            and "format" in payload["output_config"]
        ),
        "effective_thinking": "adaptive default",
        "effective_thinking_mode": CALL_C_EFFECTIVE_THINKING_MODE,
        "effective_effort": "high default",
        "effective_effort_value": CALL_C_EFFECTIVE_EFFORT,
        "observed_thinking": CALL_C_THINKING_TOKENS,
        "provider_input": CALL_C_PROVIDER_INPUT,
        "max_tokens": MAX_OUTPUT_TOKENS_FROZEN,
        "observed_output_tokens": CALL_C_OUTPUT,
        "implied_remaining_visible_budget": remaining,
        "finish_reason": CALL_C_FINISH,
        "structured_json": "truncated",
        "structured_parse": "FAIL",
        "primary_root_cause_carried": PRIMARY_ROOT_CAUSE,
        "conclusion": CALL_C_ROOT_CAUSE,
        "payload_sent_this_phase": False,
    }


__all__ = [
    "call_c_effective_contract",
    "reconstruct_call_c_payload",
    "reconstruct_call_c_request",
]
