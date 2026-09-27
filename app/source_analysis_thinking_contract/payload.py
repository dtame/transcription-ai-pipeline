"""Contrats de payload Anthropic V2 — construction offline uniquement."""

from __future__ import annotations

from typing import Any

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.thinking import (
    EFFORT_HIGH,
    EFFORT_LOW,
    EFFORT_MEDIUM,
    THINKING_MODE_ADAPTIVE,
    THINKING_MODE_DISABLED,
)
from app.source_analysis_local_v2.schema import build_semantic_transport_v2_schema
from app.source_analysis_thinking_contract.constants import (
    MAX_OUTPUT_TOKENS_FROZEN,
    MODE,
    MODEL,
    PHASE,
    SCHEMA_VERSION,
    SELECTED_CONTRACT,
    SELECTED_EFFORT,
    SELECTED_THINKING_MODE,
)


def _engine() -> AnthropicEngine:
    return AnthropicEngine(model=MODEL, api_key="cle-de-test")


def build_v2_payload_request(
    *,
    thinking_mode: str | None = None,
    effort: str | None = None,
    thinking_budget_tokens: int | None = None,
    temperature: float | None = None,
    prompt: str = "tiny synthetic grammar probe — not pastoral",
) -> AIRequest:
    return AIRequest(
        prompt=prompt,
        system_prompt="window-analysis-1.2",
        model=MODEL,
        temperature=temperature,
        max_output_tokens=MAX_OUTPUT_TOKENS_FROZEN,
        response_schema=build_semantic_transport_v2_schema(),
        thinking_mode=thinking_mode,
        effort=effort,
        thinking_budget_tokens=thinking_budget_tokens,
    )


def build_named_payload(name: str) -> dict[str, Any]:
    mapping = {
        "THINKING_DISABLED": {
            "thinking_mode": THINKING_MODE_DISABLED,
            "effort": None,
        },
        "ADAPTIVE_LOW": {
            "thinking_mode": THINKING_MODE_ADAPTIVE,
            "effort": EFFORT_LOW,
        },
        "ADAPTIVE_MEDIUM": {
            "thinking_mode": THINKING_MODE_ADAPTIVE,
            "effort": EFFORT_MEDIUM,
        },
        "ADAPTIVE_HIGH": {
            "thinking_mode": THINKING_MODE_ADAPTIVE,
            "effort": EFFORT_HIGH,
        },
        "provider_default": {
            "thinking_mode": None,
            "effort": None,
        },
    }
    spec = mapping[name]
    request = build_v2_payload_request(**spec)
    payload = _engine().build_payload(request, MODEL)
    return {
        "name": name,
        "request_thinking_mode": request.thinking_mode,
        "request_effort": request.effort,
        "payload": payload,
        "thinking": payload.get("thinking"),
        "effort": (payload.get("output_config") or {}).get("effort"),
        "format_present": "format" in (payload.get("output_config") or {}),
        "temperature_present": "temperature" in payload,
    }


def payload_contract() -> dict[str, Any]:
    disabled = build_named_payload("THINKING_DISABLED")
    low = build_named_payload("ADAPTIVE_LOW")
    medium = build_named_payload("ADAPTIVE_MEDIUM")
    high = build_named_payload("ADAPTIVE_HIGH")
    default = build_named_payload("provider_default")
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "model": MODEL,
        "selected_contract": SELECTED_CONTRACT,
        "selected_thinking_mode": SELECTED_THINKING_MODE,
        "selected_effort": SELECTED_EFFORT,
        "thinking_disabled_plus_effort": (
            "Official contract does not require effort with thinking disabled. "
            "Prefer omitting effort. Explicit disabled+effort is not locally "
            "forbidden because no official restriction was supplied."
        ),
        "temperature_policy": (
            "AIRequest.temperature=None omits the field. claude-sonnet-5 "
            "payloads also drop temperature because official Sonnet 5 docs "
            "reject non-default sampling parameters. Other Anthropic models "
            "are unchanged."
        ),
        "output_config_merge": (
            "effort is written into the existing output_config dict so "
            "format remains present."
        ),
        "manual_budget_tokens": "rejected locally — never sent",
        "task_budget": "not implemented — unsupported on claude-sonnet-5",
        "max_output_unchanged": MAX_OUTPUT_TOKENS_FROZEN,
        "payloads": {
            "THINKING_DISABLED": disabled,
            "ADAPTIVE_LOW": low,
            "ADAPTIVE_MEDIUM": medium,
            "ADAPTIVE_HIGH": high,
            "provider_default": default,
        },
    }


__all__ = [
    "build_named_payload",
    "build_v2_payload_request",
    "payload_contract",
]
