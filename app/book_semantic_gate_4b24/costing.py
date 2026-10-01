"""Terra canary cost estimate and actual. Unknown != zero."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from app.ai.capabilities import resolve_capabilities
from app.ai.estimation import estimate_tokens
from app.ai.pricing import (
    COST_STATUS_BASE_ESTIMATE,
    REGIME_LONG_CONTEXT,
    build_default_catalog,
)
from app.ai.settings import resolve_stage_settings
from app.book_semantic_gate_4b24.constants import (
    CONSERVATIVE_MAX_OUTPUT_TOKENS,
    MODEL,
    PROVIDER,
    SEMANTIC_GATE_STAGE,
    STAGE_CANARY,
)


def _money(value: Decimal | None) -> str:
    if value is None:
        return "unknown"
    return f"{value.quantize(Decimal('0.000001'))} USD"


def estimate_canary_cost(
    *,
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int,
) -> dict[str, Any]:
    catalog = build_default_catalog()
    pricing = catalog.get(PROVIDER, MODEL)
    local = estimate_tokens(system_prompt + "\n" + user_prompt)
    request_chars = len(system_prompt) + len(user_prompt)
    pessimistic = int((request_chars / 1.9365384615384615) + 0.999)
    mid = max(int(local.tokens or 0), int((request_chars / 2.5) + 0.999))
    output = max(1500, min(max_output_tokens, CONSERVATIVE_MAX_OUTPUT_TOKENS))
    caps = resolve_capabilities(PROVIDER, MODEL)
    stage = resolve_stage_settings(SEMANTIC_GATE_STAGE)
    usable = int(caps.context_window * stage.context_safety_ratio) - max_output_tokens
    context_safe = pessimistic < usable and mid < usable
    utilization = round(pessimistic / usable, 6) if usable else 1.0
    long_context = "NOT APPLICABLE"
    if not caps.context_window:
        long_context = "UNKNOWN"
    elif pessimistic >= 200_000:
        long_context = "UNKNOWN"
    breakdown = None
    if pricing is not None:
        breakdown = catalog.estimate_cost(PROVIDER, MODEL, pessimistic, output)
    amount = breakdown.total_cost if breakdown is not None else None
    return {
        "status": "ESTIMATED",
        "stage": STAGE_CANARY,
        "production_chapter_validation": False,
        "provider": PROVIDER,
        "model": MODEL,
        "pricing_verified": bool(pricing.verified) if pricing else False,
        "local_input_tokens": {
            "tokens": local.tokens,
            "estimated": local.estimated,
            "method": local.method,
        },
        "request_chars": request_chars,
        "provider_adjusted_mid": mid,
        "provider_adjusted_pessimistic": pessimistic,
        "output_tokens_conservative": output,
        "max_output_tokens": max_output_tokens,
        "context_window": caps.context_window,
        "usable_input_tokens": usable,
        "context_utilization_pessimistic": utilization,
        "context_safe": context_safe,
        "long_context_regime": long_context,
        "long_context_threshold_modeled": False,
        "long_context_assumed_applied": False,
        "input_cost_usd": (
            float(breakdown.input_cost)
            if breakdown is not None and breakdown.input_cost is not None
            else None
        ),
        "output_cost_usd": (
            float(breakdown.output_cost)
            if breakdown is not None and breakdown.output_cost is not None
            else None
        ),
        "total_cost_usd": float(amount) if amount is not None else None,
        "total_cost_display": _money(amount),
        "cost_status": breakdown.status if breakdown is not None else "unknown",
        "unknown_or_incomplete": (
            breakdown is None or breakdown.status != "known"
        ),
        "unmodeled_regimes": (
            breakdown.unmodeled_regimes if breakdown is not None else REGIME_LONG_CONTEXT
        ),
        "note": (
            "Single semantic-validation canary estimate. Not a completed "
            "production chapter validation. Long-context pricing threshold "
            "is not modeled; current request is a small fraction of the "
            "1,050,000-token context window."
        ),
        "cost_status_is_not_known": (
            breakdown is not None and breakdown.status == COST_STATUS_BASE_ESTIMATE
        ),
    }


def actual_cost(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
) -> dict[str, Any]:
    if input_tokens is None and output_tokens is None:
        return {
            "status": "unknown",
            "total_cost": None,
            "display": "UNKNOWN",
            "notes": "Provider usage unavailable — not inferred as zero.",
            "stage": STAGE_CANARY,
            "production_chapter_validation": False,
        }
    breakdown = build_default_catalog().estimate_cost(
        PROVIDER, MODEL, input_tokens, output_tokens
    )
    payload = breakdown.to_dict()
    if breakdown.total_cost is None:
        payload["display"] = "UNKNOWN"
    else:
        payload["display"] = f"{breakdown.total_cost} {breakdown.currency or 'USD'}"
    payload["notes"] = (
        "Actual 4B.2.4 Terra semantic-validation canary cost. "
        "Not a completed production chapter validation."
    )
    payload["stage"] = STAGE_CANARY
    payload["production_chapter_validation"] = False
    return payload


def cost_calibration(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    thinking_tokens: int | None,
    actual: Mapping[str, Any],
    estimate: Mapping[str, Any] | None = None,
    max_output: int,
) -> dict[str, Any]:
    utilization = None
    if output_tokens is not None and max_output:
        utilization = round(float(output_tokens) / float(max_output), 6)
    return {
        "phase": "4B.2.4",
        "stage": STAGE_CANARY,
        "production_chapter_validation": False,
        "nineteen_chapter_rollout_not_spent": True,
        "max_output": max_output,
        "estimate": dict(estimate or {}),
        "estimate_status": "ESTIMATED",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "thinking_tokens_status": (
            "unknown" if thinking_tokens is None else "reported"
        ),
        "output_utilization": utilization,
        "actual": dict(actual),
        "pass_fail_criterion": False,
    }


__all__ = ["actual_cost", "cost_calibration", "estimate_canary_cost"]
