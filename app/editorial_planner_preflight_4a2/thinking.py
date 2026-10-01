"""Thinking vs max_tokens for the Anthropic Opus 5 planner path. Offline."""

from __future__ import annotations

from typing import Any

from app.ai.thinking import (
    THINKING_MODE_PROVIDER_DEFAULT,
    resolve_thinking_capabilities,
)
from app.editorial_planner_preflight_4a2.constants import (
    A1_ELAPSED_MS,
    A1_FINISH,
    A1_MAX_OUTPUT,
    A1_OUTPUT_TOKENS,
    A1_REQUEST_ID,
    A1_TEXT_CHARS,
    A1_THINKING_TOKENS,
    BUDGET_TOKENS,
    EFFORT,
    MODEL,
    OPUS5_PROVIDER_DEFAULT_THINKING_OBSERVED,
    PROVIDER,
    THINKING_HEADROOM_RATIONALE,
    THINKING_HEADROOM_TOKENS,
    THINKING_MODE,
)
from app.editorial_planning.settings import thinking_recommendation
from app.ai.providers._anthropic_thinking import attach_request_output_controls
from app.ai.contracts import AIRequest


def thinking_budget_audit(*, selected_max_output: int) -> dict[str, Any]:
    caps = resolve_thinking_capabilities(PROVIDER, MODEL)
    rec = thinking_recommendation()
    request = AIRequest(
        prompt="offline-identity-only",
        model=MODEL,
        thinking_mode=THINKING_MODE_PROVIDER_DEFAULT,
        effort=None,
        thinking_budget_tokens=None,
        max_output_tokens=selected_max_output,
    )
    payload = attach_request_output_controls(
        {"model": MODEL, "max_tokens": selected_max_output},
        request,
        MODEL,
    )
    shared_proven = bool(caps.known and caps.max_tokens_shared_output)
    # Conservative: treat max_tokens as a shared thinking+visible budget.
    interaction = {
        "repository_opus5_thinking_capabilities_known": caps.known,
        "sonnet5_max_tokens_shared_output": True,
        "opus5_max_tokens_shared_output_proven": shared_proven,
        "engine_sends_max_tokens": True,
        "provider_default_omits_thinking_key": "thinking" not in payload,
        "effort_omitted": "effort" not in payload
        and "effort" not in (payload.get("output_config") or {}),
        "a1_usage": {
            "request_id": A1_REQUEST_ID,
            "max_tokens": A1_MAX_OUTPUT,
            "output_tokens": A1_OUTPUT_TOKENS,
            "thinking_tokens": A1_THINKING_TOKENS,
            "thinking_in_output_tokens_details": True,
            "visible_text_chars": A1_TEXT_CHARS,
            "finish": A1_FINISH,
            "elapsed_ms": A1_ELAPSED_MS,
        },
        "engine_stores_output_tokens_and_thinking_separately": True,
        "engine_does_not_subtract_thinking_from_output_tokens": True,
        "whether_max_tokens_includes_thinking": (
            "PROVEN_SHARED"
            if shared_proven
            else "UNCERTAIN_BUDGET_AS_SHARED"
        ),
        "conservative_treatment": (
            "Assume max_tokens caps thinking + visible structured output "
            "together, matching the verified Sonnet 5 contract, because Opus 5 "
            "thinking capabilities are unverified (known=False)."
        ),
    }
    return {
        "thinking_mode": THINKING_MODE,
        "effort": EFFORT,
        "budget_tokens": BUDGET_TOKENS,
        "do_not_switch_to_thinking_disabled": True,
        "OPUS5_PROVIDER_DEFAULT_THINKING_OBSERVED": (
            OPUS5_PROVIDER_DEFAULT_THINKING_OBSERVED
        ),
        "A1_THINKING_TOKENS": A1_THINKING_TOKENS,
        "do_not_assume_production_thinking_equals_synthetic_ratio": True,
        "invalid_linear_thinking_scale": int(round(A1_THINKING_TOKENS * (286 / 7))),
        "thinking_headroom_tokens": THINKING_HEADROOM_TOKENS,
        "thinking_headroom_rationale": THINKING_HEADROOM_RATIONALE,
        "selected_max_output": selected_max_output,
        "capabilities": caps.to_dict(),
        "phase4a_recommendation": rec,
        "payload_thinking_key": payload.get("thinking"),
        "max_tokens_interaction": interaction,
        "sonnet5_contract_generalized": False,
    }


__all__ = ["thinking_budget_audit"]
