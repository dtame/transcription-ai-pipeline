"""Estimated future 1.0.1 call cost. ESTIMATED, not actual. 0 provider calls."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.ai.pricing import build_default_catalog
from app.editorial_planner_language_policy_4a32.constants import (
    A2_CONSERVATIVE_COST_USD,
    A2_EXPECTED_COST_USD,
    A2_HARD_COST_USD,
    A3_COST_USD,
    A3_INPUT_TOKENS,
    A3_OUTPUT_TOKENS,
    A3_THINKING_TOKENS,
    MODEL,
    PROVIDER,
)
from app.editorial_planner_preflight_4a2.costing import estimate_pair, long_context_status


def _as_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def future_cost_estimate(
    *,
    input_tokens: int,
    expected_output: int,
    conservative_output: int,
    hard_output: int,
) -> dict[str, Any]:
    catalog = build_default_catalog()
    a3_check = catalog.estimate_cost(
        PROVIDER,
        MODEL,
        A3_INPUT_TOKENS,
        A3_OUTPUT_TOKENS,
    )
    expected = estimate_pair(input_tokens=input_tokens, output_tokens=expected_output)
    conservative = estimate_pair(
        input_tokens=input_tokens, output_tokens=conservative_output
    )
    hard = estimate_pair(input_tokens=input_tokens, output_tokens=hard_output)
    return {
        "cost_status_mark": "ESTIMATED",
        "not_actual": True,
        "a3_actual_calibration": {
            "input_tokens": A3_INPUT_TOKENS,
            "output_tokens": A3_OUTPUT_TOKENS,
            "thinking_tokens": A3_THINKING_TOKENS,
            "cost_usd": A3_COST_USD,
            "catalog_recompute": _as_float(a3_check.total_cost),
            "note": (
                "A.3 actual cost is historical calibration evidence. "
                "Future 1.0.1 cost is estimated separately. Thinking is not "
                "assumed to equal 6443."
            ),
        },
        "a2_historical_estimates": {
            "expected_usd": A2_EXPECTED_COST_USD,
            "conservative_usd": A2_CONSERVATIVE_COST_USD,
            "hard_usd": A2_HARD_COST_USD,
        },
        "pricing": {
            "provider": PROVIDER,
            "model": MODEL,
            "input_cost_per_1m": 5.00,
            "output_cost_per_1m": 25.00,
            "source": "Phase 2B catalog / A.2–A.3 pricing",
        },
        "long_context": long_context_status(input_tokens),
        "expected": expected,
        "conservative": conservative,
        "hard": hard,
        "expected_cost": expected.get("display"),
        "conservative_cost": conservative.get("display"),
        "hard_cost": hard.get("display"),
        "estimated_cost": expected.get("display"),
    }


__all__ = ["future_cost_estimate"]
