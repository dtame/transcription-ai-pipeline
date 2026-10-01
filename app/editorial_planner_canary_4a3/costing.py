"""A.3 actual cost and A.2 estimate calibration. Unknown ≠ 0."""

from __future__ import annotations

from typing import Any

from app.ai.pricing import COST_STATUS_UNKNOWN, build_default_catalog
from app.editorial_planner_canary_4a3.constants import (
    A2_CONSERVATIVE_COST_USD,
    A2_CONSERVATIVE_OUTPUT_TOKENS,
    A2_EXPECTED_COST_USD,
    A2_EXPECTED_OUTPUT_TOKENS,
    A2_HARD_COST_USD,
    A2_HARD_OUTPUT_TOKENS,
    A2_LOCAL_INPUT_ESTIMATE,
    A2_PROVIDER_ADJUSTED_PESSIMISTIC,
    A2_THINKING_HEADROOM_TOKENS,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROVIDER,
)


def _pct_error(actual: float | None, expected: float) -> float | None:
    if actual is None or expected == 0:
        return None
    return round(((float(actual) - float(expected)) / float(expected)) * 100.0, 4)


def actual_cost(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
) -> dict[str, Any]:
    if input_tokens is None and output_tokens is None:
        return {
            "status": COST_STATUS_UNKNOWN,
            "total_cost": None,
            "display": "UNKNOWN",
            "notes": "Provider usage unavailable — not inferred as zero.",
        }
    breakdown = build_default_catalog().estimate_cost(
        PROVIDER, MODEL, input_tokens, output_tokens
    )
    payload = breakdown.to_dict()
    if breakdown.total_cost is None:
        payload["display"] = "UNKNOWN"
    else:
        payload["display"] = f"{breakdown.total_cost} {breakdown.currency or 'USD'}"
    payload["notes"] = "Actual A.3 production canary cost. Stage=editorial_planning."
    return payload


def budget_calibration(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    thinking_tokens: int | None,
    actual: dict[str, Any],
    planning_input_estimate: int | None = None,
) -> dict[str, Any]:
    utilization = None
    if output_tokens is not None:
        utilization = round(float(output_tokens) / float(PRODUCTION_MAX_OUTPUT_TOKENS), 6)
    actual_total = actual.get("total_cost")
    try:
        actual_usd = float(actual_total) if actual_total is not None else None
    except (TypeError, ValueError):
        actual_usd = None
    return {
        "phase": "4A.3",
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "input": {
            "actual_provider_tokens": input_tokens,
            "a2_local_estimate": A2_LOCAL_INPUT_ESTIMATE,
            "a2_provider_adjusted_pessimistic": A2_PROVIDER_ADJUSTED_PESSIMISTIC,
            "a2_payload_inclusive_planning_estimate": planning_input_estimate,
            "error_pct_vs_local": _pct_error(input_tokens, A2_LOCAL_INPUT_ESTIMATE),
            "error_pct_vs_provider_adjusted": _pct_error(
                input_tokens, A2_PROVIDER_ADJUSTED_PESSIMISTIC
            ),
            "error_pct_vs_planning": _pct_error(
                input_tokens, planning_input_estimate or 0
            )
            if planning_input_estimate
            else None,
        },
        "output": {
            "actual_provider_tokens": output_tokens,
            "thinking_tokens": thinking_tokens,
            "a2_expected": A2_EXPECTED_OUTPUT_TOKENS,
            "a2_conservative": A2_CONSERVATIVE_OUTPUT_TOKENS,
            "a2_hard": A2_HARD_OUTPUT_TOKENS,
            "delta_vs_expected": (
                None
                if output_tokens is None
                else int(output_tokens) - A2_EXPECTED_OUTPUT_TOKENS
            ),
            "delta_vs_conservative": (
                None
                if output_tokens is None
                else int(output_tokens) - A2_CONSERVATIVE_OUTPUT_TOKENS
            ),
            "delta_vs_hard": (
                None if output_tokens is None else int(output_tokens) - A2_HARD_OUTPUT_TOKENS
            ),
            "error_pct_vs_expected": _pct_error(output_tokens, A2_EXPECTED_OUTPUT_TOKENS),
            "error_pct_vs_conservative": _pct_error(
                output_tokens, A2_CONSERVATIVE_OUTPUT_TOKENS
            ),
            "error_pct_vs_hard": _pct_error(output_tokens, A2_HARD_OUTPUT_TOKENS),
            "output_utilization_vs_65536": utilization,
            "thinking_headroom_used_in_a2_estimate": A2_THINKING_HEADROOM_TOKENS,
            "unproven_shared_max_tokens_claim": False,
            "note": (
                "Utilization is output_tokens / 65536. Whether thinking shares "
                "max_tokens is observed, not assumed. A.1 reported thinking "
                "inside usage.output_tokens_details; engine records "
                "output_tokens without subtracting thinking."
            ),
        },
        "cost": {
            "actual": actual,
            "actual_usd": actual_usd,
            "a2_expected_usd": A2_EXPECTED_COST_USD,
            "a2_conservative_usd": A2_CONSERVATIVE_COST_USD,
            "a2_hard_usd": A2_HARD_COST_USD,
            "error_pct_vs_expected": _pct_error(actual_usd, A2_EXPECTED_COST_USD),
            "error_pct_vs_conservative": _pct_error(
                actual_usd, A2_CONSERVATIVE_COST_USD
            ),
            "error_pct_vs_hard": _pct_error(actual_usd, A2_HARD_COST_USD),
        },
    }


__all__ = ["actual_cost", "budget_calibration"]
