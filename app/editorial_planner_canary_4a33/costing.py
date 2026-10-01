"""A.3.3 actual cost vs A.3.2 estimate and historical A.3. Unknown ≠ 0."""

from __future__ import annotations

from typing import Any

from app.ai.pricing import COST_STATUS_UNKNOWN, build_default_catalog
from app.editorial_planner_canary_4a33.constants import (
    A2_CONSERVATIVE_OUTPUT_TOKENS,
    A2_EXPECTED_OUTPUT_TOKENS,
    A2_HARD_OUTPUT_TOKENS,
    A32_ESTIMATED_COST_DISPLAY,
    A32_ESTIMATED_COST_USD,
    A32_PLANNING_INPUT_ESTIMATE,
    A3_ACTUAL_COST_USD,
    A3_ACTUAL_INPUT_TOKENS,
    A3_ACTUAL_OUTPUT_TOKENS,
    A3_ACTUAL_THINKING_TOKENS,
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
    payload["notes"] = (
        "Actual A.3.3 production canary cost. Stage=editorial_planning. "
        "Does not double-count historical A.3."
    )
    payload["stage"] = "editorial_planning"
    return payload


def estimator_error_note(
    *,
    input_tokens: int | None,
) -> str:
    if input_tokens is None:
        return (
            "No provider input tokens. Estimator not modified. "
            "A.3.2 planning estimate 59542 is a payload-inclusive pessimistic "
            "bound, not a point prediction."
        )
    delta_vs_a32 = int(input_tokens) - A32_PLANNING_INPUT_ESTIMATE
    delta_vs_a3 = int(input_tokens) - A3_ACTUAL_INPUT_TOKENS
    return (
        "A.3.2 planning_input_estimate=59542 is max(local, pessimistic, "
        "payload-inclusive pessimistic, A.3-calibrated). That is a conservative "
        f"bound. A.3 actual input was {A3_ACTUAL_INPUT_TOKENS}. A.3.3 actual="
        f"{input_tokens} (delta vs A.3.2 estimate {delta_vs_a32}, delta vs A.3 "
        f"actual {delta_vs_a3}). The extra 1.0.1 language instruction is a small "
        "prompt increment; most of the 59542 vs 41425 gap is pessimistic "
        "payload-inclusive density, not a generic estimator bug. Estimator not "
        "modified in this phase."
    )


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
        utilization = round(
            float(output_tokens) / float(PRODUCTION_MAX_OUTPUT_TOKENS), 6
        )
    actual_total = actual.get("total_cost")
    try:
        actual_usd = float(actual_total) if actual_total is not None else None
    except (TypeError, ValueError):
        actual_usd = None
    return {
        "phase": "4A.3.3",
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "estimator_modified": False,
        "estimator_error_explanation": estimator_error_note(input_tokens=input_tokens),
        "input": {
            "actual_provider_tokens": input_tokens,
            "a32_planning_estimate": A32_PLANNING_INPUT_ESTIMATE,
            "a3_actual": A3_ACTUAL_INPUT_TOKENS,
            "this_phase_planning_estimate": planning_input_estimate,
            "error_pct_vs_a32_estimate": _pct_error(
                input_tokens, A32_PLANNING_INPUT_ESTIMATE
            ),
            "error_pct_vs_a3_actual": _pct_error(input_tokens, A3_ACTUAL_INPUT_TOKENS),
        },
        "output": {
            "actual_provider_tokens": output_tokens,
            "thinking_tokens": thinking_tokens,
            "expected": A2_EXPECTED_OUTPUT_TOKENS,
            "conservative": A2_CONSERVATIVE_OUTPUT_TOKENS,
            "hard": A2_HARD_OUTPUT_TOKENS,
            "max": PRODUCTION_MAX_OUTPUT_TOKENS,
            "a3_actual": A3_ACTUAL_OUTPUT_TOKENS,
            "a3_thinking": A3_ACTUAL_THINKING_TOKENS,
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
            "output_utilization_vs_65536": utilization,
            "thinking_reported_separately": True,
            "do_not_assume_a1_or_a3_thinking": True,
        },
        "cost": {
            "actual": actual,
            "actual_usd": actual_usd,
            "a32_estimated_usd": A32_ESTIMATED_COST_USD,
            "a32_estimated_display": A32_ESTIMATED_COST_DISPLAY,
            "a3_historical_actual_usd": A3_ACTUAL_COST_USD,
            "error_pct_vs_a32_estimate": _pct_error(actual_usd, A32_ESTIMATED_COST_USD),
            "error_pct_vs_a3_actual": _pct_error(actual_usd, A3_ACTUAL_COST_USD),
            "not_a_hard_pass_fail_threshold": True,
        },
    }


__all__ = ["actual_cost", "budget_calibration", "estimator_error_note"]
