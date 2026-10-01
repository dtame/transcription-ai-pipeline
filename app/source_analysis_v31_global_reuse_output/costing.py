"""Coût estimé architecture retenue. CostTracker non muté. 0 spend."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.source_analysis_v31_global_drop_domain.prompt_v201 import prompt_v201_bundle
from app.source_analysis_v31_global_reuse_output.constants import (
    A38_PRODUCTION_INPUT_TOKENS,
    INPUT_COST_PER_1M,
    MODEL,
    OUTPUT_COST_PER_1M,
    PROVIDER,
)
from app.source_analysis_v31_global_reuse_output.prompt_v30 import prompt_v30_bundle


def estimate_cost(*, input_tokens: int, output_tokens: int) -> dict[str, Any]:
    inp = (Decimal(input_tokens) / Decimal(1_000_000)) * Decimal(str(INPUT_COST_PER_1M))
    out = (Decimal(output_tokens) / Decimal(1_000_000)) * Decimal(
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
        "spend": 0,
    }


def production_cost_estimate(budget: dict[str, Any]) -> dict[str, Any]:
    old = prompt_v201_bundle()
    new = prompt_v30_bundle()
    old_chars = len(str(old.get("system") or "") + str(old.get("instructions") or ""))
    new_chars = len(str(new.get("system") or "") + str(new.get("instructions") or ""))
    delta_chars = new_chars - old_chars
    # A.38 production input 68138 used prompt 1.0.1. Compact 2.0.1 is shorter;
    # reuse 3.0 adds reuse rules. Apply char delta / 2.06 as a small adjustment
    # on the observed A.38 production request, without claiming a new live count.
    delta_tokens = int(round(delta_chars / 2.06)) if delta_chars else 0
    estimated_input = A38_PRODUCTION_INPUT_TOKENS + max(delta_tokens, 0)
    expected_out = int(budget.get("p50_expected") or 0)
    conservative_out = int(budget.get("conservative") or 0)
    hard_out = int(budget.get("hard_planning") or 0)
    return {
        "a38_actual_input": A38_PRODUCTION_INPUT_TOKENS,
        "prompt_char_delta_vs_2_0_1": delta_chars,
        "estimated_real_input": estimated_input,
        "estimated_real_output_expected": expected_out,
        "estimated_real_output_conservative": conservative_out,
        "estimated_real_output_hard": hard_out,
        "expected": estimate_cost(input_tokens=estimated_input, output_tokens=expected_out),
        "conservative": estimate_cost(
            input_tokens=estimated_input, output_tokens=conservative_out
        ),
        "hard": estimate_cost(input_tokens=estimated_input, output_tokens=hard_out),
        "cost_tracker_mutated": False,
        "spend": 0,
        "real_call": False,
    }


__all__ = ["estimate_cost", "production_cost_estimate"]
