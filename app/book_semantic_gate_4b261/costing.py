"""Cost scenarios. Unknown != zero. Cost is not linear with max budget."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.ai.pricing import build_default_catalog
from app.book_semantic_gate_4b261.constants import (
    MODEL,
    OBSERVED_4B26_COST_USD,
    OBSERVED_4B26_INPUT_TOKENS,
    OBSERVED_4B26_OUTPUT_TOKENS,
    PHASE,
    PROVIDER,
    SEMANTIC_TOKEN_BUDGET,
    STRATEGY_A_BUDGETS,
    STRATEGY_C_BATCH_SIZES,
)


def _money(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(Decimal("0.000001")))


def pricing_context() -> dict[str, Any]:
    catalog = build_default_catalog()
    pricing = catalog.get(PROVIDER, MODEL)
    if pricing is None:
        return {
            "provider": PROVIDER,
            "model": MODEL,
            "verified": False,
            "status": "unknown",
            "counted_as_zero": False,
        }
    return {
        "provider": PROVIDER,
        "model": MODEL,
        "verified": bool(pricing.verified),
        "effective_date": pricing.effective_date,
        "source": pricing.source,
        "input_cost_per_1m_tokens": float(pricing.input_cost_per_1m_tokens),
        "output_cost_per_1m_tokens": float(pricing.output_cost_per_1m_tokens),
        "status": pricing.cost_status,
        "unmodeled_regimes": pricing.unmodeled_regimes,
        "notes": pricing.notes,
        "counted_as_zero": False,
    }


def estimate_cost(input_tokens: int, output_tokens: int) -> dict[str, Any]:
    catalog = build_default_catalog()
    breakdown = catalog.estimate_cost(PROVIDER, MODEL, int(input_tokens), int(output_tokens))
    return {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "reasoning_tokens": "UNKNOWN",
        "input_cost_usd": _money(breakdown.input_cost),
        "output_cost_usd": _money(breakdown.output_cost),
        "total_cost_usd": _money(breakdown.total_cost),
        "status": breakdown.status,
        "unknown_or_incomplete": breakdown.status != "known",
        "counted_as_zero": False,
        "note": (
            "Estimate uses configured Terra rates. Actual billed tokens may "
            "include hidden reasoning. Cost does not scale automatically with "
            "max_completion_tokens; it scales with tokens actually used."
        ),
    }


def observed_4b26_cost() -> dict[str, Any]:
    recomputed = estimate_cost(OBSERVED_4B26_INPUT_TOKENS, OBSERVED_4B26_OUTPUT_TOKENS)
    return {
        "observed_total_usd": OBSERVED_4B26_COST_USD,
        "recomputed_from_usage": recomputed,
        "matches_recompute": recomputed.get("total_cost_usd") == OBSERVED_4B26_COST_USD,
        "input_tokens": OBSERVED_4B26_INPUT_TOKENS,
        "output_tokens": OBSERVED_4B26_OUTPUT_TOKENS,
        "reasoning_tokens": "UNKNOWN",
        "calls": 1,
    }


def strategy_cost_scenarios(
    *,
    historical_input_tokens: int,
    compact_input_tokens_10: int,
    compact_input_tokens_1: int,
    compact_min_output_10: int,
    compact_min_output_1: int,
) -> dict[str, Any]:
    observed = observed_4b26_cost()
    strategy_a = []
    for budget in STRATEGY_A_BUDGETS:
        strategy_a.append(
            {
                "budget": budget,
                "if_budget_fully_consumed": estimate_cost(historical_input_tokens, budget),
                "if_same_usage_as_4b26": estimate_cost(
                    historical_input_tokens, OBSERVED_4B26_OUTPUT_TOKENS
                ),
                "not_a_linear_guarantee": True,
                "risk": "The model may again consume the entire budget without JSON.",
            }
        )
    strategy_b = {
        "ten_cases_compact_if_min_json": estimate_cost(
            compact_input_tokens_10, compact_min_output_10
        ),
        "ten_cases_compact_if_budget_exhausted": estimate_cost(
            compact_input_tokens_10, SEMANTIC_TOKEN_BUDGET
        ),
        "note": "Min-JSON cost is an estimate of visible payload only.",
    }
    strategy_c = []
    for size in STRATEGY_C_BATCH_SIZES:
        calls = (10 + size - 1) // size
        per_input = compact_input_tokens_1 if size == 1 else compact_input_tokens_10
        if size == 1:
            per_input = compact_input_tokens_1
        elif size == 10:
            per_input = compact_input_tokens_10
        else:
            # Mixed: scale from 1-case trimmed input plus shared overhead.
            per_input = int(compact_input_tokens_1 * size * 0.85 + 400)
        min_out = max(80, compact_min_output_1 * size)
        strategy_c.append(
            {
                "batch_size": size,
                "calls": calls,
                "per_call_input_tokens_estimate": per_input,
                "if_one_call_returns_min_json": estimate_cost(per_input, min_out),
                "if_one_call_exhausts_8192": estimate_cost(per_input, SEMANTIC_TOKEN_BUDGET),
                "if_full_benchmark_min_json": {
                    **estimate_cost(per_input * calls, min_out * calls),
                    "calls": calls,
                },
                "if_full_benchmark_each_call_exhausts_8192": {
                    **estimate_cost(per_input * calls, SEMANTIC_TOKEN_BUDGET * calls),
                    "calls": calls,
                },
            }
        )
    return {
        "phase": PHASE,
        "pricing": pricing_context(),
        "observed_4b26": observed,
        "strategy_a": strategy_a,
        "strategy_b": strategy_b,
        "strategy_c": strategy_c,
        "do_not_assume_all_completion_tokens_are_visible": True,
        "do_not_assume_cost_scales_with_max_budget": True,
        "unknown_is_not_zero": True,
        "secrets_included": False,
    }


__all__ = [
    "estimate_cost",
    "observed_4b26_cost",
    "pricing_context",
    "strategy_cost_scenarios",
]
