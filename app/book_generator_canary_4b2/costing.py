"""CH016 canary cost estimate and actual. Unknown ≠ 0. Not production cost."""

from __future__ import annotations

from typing import Any

from app.ai.pricing import COST_STATUS_UNKNOWN, build_default_catalog
from app.book_generation.costing import estimate_production_cost
from app.book_generator_canary_4b2.constants import (
    MODEL,
    PROVIDER,
    STAGE_CANARY,
)


def estimate_chapter_cost(budget: dict[str, Any]) -> dict[str, Any]:
    estimate = estimate_production_cost([budget], provider=PROVIDER, model=MODEL)
    estimate["status"] = "ESTIMATED"
    estimate["stage"] = STAGE_CANARY
    estimate["pass_fail_criterion"] = False
    estimate["note"] = (
        "Single CH016 canary estimate. Not a completed production manuscript cost."
    )
    return estimate


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
            "stage": STAGE_CANARY,
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
        "Actual 4B.2 CH016 canary cost. Stage=book_generation_canary. "
        "Not production manuscript cost."
    )
    payload["stage"] = STAGE_CANARY
    return payload


def cost_calibration(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    thinking_tokens: int | None,
    actual: dict[str, Any],
    estimate: dict[str, Any] | None = None,
    max_output: int,
) -> dict[str, Any]:
    utilization = None
    if output_tokens is not None and max_output:
        utilization = round(float(output_tokens) / float(max_output), 6)
    return {
        "phase": "4B.2",
        "stage": STAGE_CANARY,
        "production_manuscript_cost": False,
        "max_output": max_output,
        "estimate": estimate or {},
        "estimate_status": "ESTIMATED",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "output_utilization": utilization,
        "actual": actual,
        "pass_fail_criterion": False,
    }


__all__ = ["actual_cost", "cost_calibration", "estimate_chapter_cost"]
