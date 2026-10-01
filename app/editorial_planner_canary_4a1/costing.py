"""Coût canary — unknown ≠ 0. Pas d'extrapolation production."""

from __future__ import annotations

from typing import Any

from app.ai.pricing import COST_STATUS_UNKNOWN, build_default_catalog
from app.editorial_planner_canary_4a1.constants import MODEL, PROVIDER


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
        "Actual canary cost only. Do not extrapolate production cost "
        "from this tiny fixture."
    )
    return payload


__all__ = ["actual_cost"]
