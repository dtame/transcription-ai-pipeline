"""Coûts d'architecture. CostTracker non muté. Chiffre A.38 historique préservé."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.source_analysis_v31_global_output_architecture.constants import (
    A38_COST_USD,
    A38_INPUT_TOKENS,
    A38_OUTPUT_TOKENS,
    INPUT_COST_PER_1M,
    MODEL,
    OUTPUT_COST_PER_1M,
    PROVIDER,
)


def estimate_cost(*, input_tokens: int, output_tokens: int) -> dict[str, Any]:
    inp = (Decimal(input_tokens) / Decimal(1_000_000)) * Decimal(str(INPUT_COST_PER_1M))
    out = (Decimal(output_tokens) / Decimal(str(1_000_000))) * Decimal(
        str(OUTPUT_COST_PER_1M)
    )
    total = (inp + out).quantize(Decimal("0.000001"))
    return {
        "marked": "ESTIMATE",
        "provider": PROVIDER,
        "model": MODEL,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": float(inp.quantize(Decimal("0.000001"))),
        "output_cost_usd": float(out.quantize(Decimal("0.000001"))),
        "total_usd": float(total),
        "display": f"{total} USD",
        "pricing": f"{PROVIDER} {MODEL} ${INPUT_COST_PER_1M}/1M in ${OUTPUT_COST_PER_1M}/1M out",
        "cost_tracker_mutated": False,
    }


def a38_historical_cost() -> dict[str, Any]:
    return {
        "actual_usd": A38_COST_USD,
        "input_tokens": A38_INPUT_TOKENS,
        "output_tokens": A38_OUTPUT_TOKENS,
        "rewritten": False,
        "cost_tracker_mutated": False,
        "status": "historical FAIL cost preserved",
    }


__all__ = ["a38_historical_cost", "estimate_cost"]
