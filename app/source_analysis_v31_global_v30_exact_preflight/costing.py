"""Coût estimé A.45. CostTracker non muté. 0 spend."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    INPUT_COST_PER_1M,
    MODEL,
    OUTPUT_COST_PER_1M,
    PROVIDER,
)


def estimate_cost(*, input_tokens: int, output_tokens: int) -> dict[str, Any]:
    inp = (Decimal(input_tokens) / Decimal(1_000_000)) * Decimal(str(INPUT_COST_PER_1M))
    out = (Decimal(output_tokens) / Decimal(1_000_000)) * Decimal(
        str(OUTPUT_COST_PER_1M)
    )
    total = (inp + out).quantize(Decimal("0.000001"))
    return {
        "marked": "ESTIMATED",
        "provider": PROVIDER,
        "model": MODEL,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": float(inp.quantize(Decimal("0.000001"))),
        "output_cost_usd": float(out.quantize(Decimal("0.000001"))),
        "total_usd": float(total),
        "display": f"{total} USD ESTIMATED",
        "pricing": (
            f"{PROVIDER} {MODEL} ${INPUT_COST_PER_1M}/1M in "
            f"${OUTPUT_COST_PER_1M}/1M out"
        ),
        "cost_tracker_mutated": False,
        "spend": 0,
        "real_call": False,
    }


def production_cost_estimate(
    *,
    input_tokens: int,
    budget: Mapping[str, Any],
) -> dict[str, Any]:
    expected_out = int(budget.get("p50_expected") or 0)
    conservative_out = int(budget.get("conservative") or 0)
    hard_out = int(budget.get("hard_planning") or 0)
    return {
        "spend": 0,
        "real_call": False,
        "cost_tracker_mutated": False,
        "label": "ESTIMATED",
        "input_tokens": input_tokens,
        "expected": estimate_cost(input_tokens=input_tokens, output_tokens=expected_out),
        "conservative": estimate_cost(
            input_tokens=input_tokens, output_tokens=conservative_out
        ),
        "hard": estimate_cost(input_tokens=input_tokens, output_tokens=hard_out),
    }


__all__ = ["estimate_cost", "production_cost_estimate"]
