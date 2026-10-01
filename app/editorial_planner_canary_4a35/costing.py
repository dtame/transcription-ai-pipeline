"""A.3.5 actual cost vs A.3.4 estimate and historical A.3 / A.3.3."""

from __future__ import annotations

from typing import Any

from app.ai.pricing import COST_STATUS_UNKNOWN, build_default_catalog
from app.editorial_planner_canary_4a35.constants import (
    A2_CONSERVATIVE_OUTPUT_TOKENS,
    A2_EXPECTED_OUTPUT_TOKENS,
    A2_HARD_OUTPUT_TOKENS,
    A3_ACTUAL_COST_USD,
    A3_ACTUAL_INPUT_TOKENS,
    A3_ACTUAL_OUTPUT_TOKENS,
    A3_ACTUAL_THINKING_TOKENS,
    A33_ACTUAL_COST_USD,
    A33_ACTUAL_INPUT_TOKENS,
    A33_ACTUAL_OUTPUT_TOKENS,
    A33_ACTUAL_THINKING_TOKENS,
    A34_CALIBRATED_INPUT_ESTIMATE,
    A34_CONSERVATIVE_INPUT_ESTIMATE,
    A34_ESTIMATED_COST_DISPLAY,
    A34_ESTIMATED_COST_USD,
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
        "Actual A.3.5 production canary cost. Stage=editorial_planning. "
        "Does not double-count historical A.3 / A.3.3 / A.3.4."
    )
    payload["stage"] = "editorial_planning"
    return payload


def estimator_error_note(*, input_tokens: int | None) -> str:
    if input_tokens is None:
        return (
            "No provider input tokens. Estimator not modified. "
            "A.3.4 conservative envelope 60455 is a payload-inclusive "
            "pessimistic bound; A.3.3-calibrated estimate is 42603."
        )
    return (
        "A.3.4 conservative envelope=60455. A.3.4 A.3.3-calibrated "
        f"estimate=42603. A.3.3 actual={A33_ACTUAL_INPUT_TOKENS}. "
        f"A.3.5 actual={input_tokens} (delta vs conservative "
        f"{int(input_tokens) - A34_CONSERVATIVE_INPUT_ESTIMATE}, "
        f"delta vs calibrated {int(input_tokens) - A34_CALIBRATED_INPUT_ESTIMATE}, "
        f"delta vs A.3.3 actual {int(input_tokens) - A33_ACTUAL_INPUT_TOKENS}). "
        "Cost variance is not a technical failure. Estimator not modified."
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
        "phase": "4A.3.5",
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "estimator_modified": False,
        "cost_variance_not_technical_failure": True,
        "estimator_error_explanation": estimator_error_note(input_tokens=input_tokens),
        "input": {
            "actual_provider_tokens": input_tokens,
            "a34_conservative_envelope": A34_CONSERVATIVE_INPUT_ESTIMATE,
            "a34_calibrated_estimate": A34_CALIBRATED_INPUT_ESTIMATE,
            "a33_actual": A33_ACTUAL_INPUT_TOKENS,
            "a3_actual": A3_ACTUAL_INPUT_TOKENS,
            "this_phase_planning_estimate": planning_input_estimate,
            "error_pct_vs_a34_conservative": _pct_error(
                input_tokens, A34_CONSERVATIVE_INPUT_ESTIMATE
            ),
            "error_pct_vs_a34_calibrated": _pct_error(
                input_tokens, A34_CALIBRATED_INPUT_ESTIMATE
            ),
            "error_pct_vs_a33_actual": _pct_error(
                input_tokens, A33_ACTUAL_INPUT_TOKENS
            ),
        },
        "output": {
            "actual_provider_tokens": output_tokens,
            "thinking_tokens": thinking_tokens,
            "expected": A2_EXPECTED_OUTPUT_TOKENS,
            "conservative": A2_CONSERVATIVE_OUTPUT_TOKENS,
            "hard": A2_HARD_OUTPUT_TOKENS,
            "max": PRODUCTION_MAX_OUTPUT_TOKENS,
            "a33_actual": A33_ACTUAL_OUTPUT_TOKENS,
            "a33_thinking": A33_ACTUAL_THINKING_TOKENS,
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
            "do_not_treat_thinking_volume_as_failure": True,
        },
        "cost": {
            "actual": actual,
            "actual_usd": actual_usd,
            "a34_estimated_usd": A34_ESTIMATED_COST_USD,
            "a34_estimated_display": A34_ESTIMATED_COST_DISPLAY,
            "a33_historical_actual_usd": A33_ACTUAL_COST_USD,
            "a3_historical_actual_usd": A3_ACTUAL_COST_USD,
            "error_pct_vs_a34_estimate": _pct_error(actual_usd, A34_ESTIMATED_COST_USD),
            "error_pct_vs_a33_actual": _pct_error(actual_usd, A33_ACTUAL_COST_USD),
            "error_pct_vs_a3_actual": _pct_error(actual_usd, A3_ACTUAL_COST_USD),
            "not_a_hard_pass_fail_threshold": True,
        },
    }


__all__ = ["actual_cost", "budget_calibration", "estimator_error_note"]
