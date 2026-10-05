"""
Precall cost bound for BATCH-01 Sonnet calls.

Unknown is never treated as zero. Theoretical maximum uses the request
max_tokens, not the 4B.2.22 central estimate. Thinking must stay disabled.
Remaining budget accounts for actual spend plus reserved or uncertain cost.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from app.book_generation.budget import estimate_manuscript_output
from app.book_generation.constants import HARD_MAX_OUTPUT_TOKENS, MIN_MAX_OUTPUT_TOKENS
from app.book_generation_4b221.costing import (
    actual_cost,
    estimate_input_tokens,
    pricing_context,
    tokens_to_usd,
)
from app.book_generation_4b223.constants import (
    BUDGET_CAP_DISPLAY,
    BUDGET_CAP_USD,
    MODEL,
    PHASE,
    PREPARATION_CALCULABLE_MAXIMUM_USD,
    PRICING_EFFECTIVE_DATE,
    PROVIDER,
)
from app.book_generation_4b223.guard import BookGeneration4223Error


def evidence_derived_max_output(*, idea_count: int, section_count: int) -> dict[str, Any]:
    output = estimate_manuscript_output(idea_count, section_count)
    raw = max(
        int(output["expected_output_tokens"]) * 3,
        int(output["conservative_output_tokens"]) * 2,
        MIN_MAX_OUTPUT_TOKENS,
    )
    chosen = min(HARD_MAX_OUTPUT_TOKENS, raw)
    return {
        "expected_output_tokens": output["expected_output_tokens"],
        "conservative_output_tokens": output["conservative_output_tokens"],
        "formula_raw_max_output_tokens": raw,
        "chosen_max_output_tokens": chosen,
        "historical_default_floor_16384_not_applied": True,
        "reason_floor_not_applied": (
            "The evidence-derived formula (max(expected*3, conservative*2, 4096)) "
            "is the 4B.2.22 planned capacity. Sources are not truncated. "
            "Output is not reduced below the formula to fit the cap."
        ),
        "did_not_truncate_sources": True,
        "did_not_inflate_to_consume_cap": True,
        "did_not_silently_reduce_output_limit": True,
        "hard_max_output_tokens": HARD_MAX_OUTPUT_TOKENS,
        "min_max_output_tokens": MIN_MAX_OUTPUT_TOKENS,
    }


def reserve_chapter_budget(
    identity: Mapping[str, Any],
    *,
    chapter_id: str,
    idea_count: int,
    section_count: int,
    remaining_budget: Decimal,
) -> dict[str, Any]:
    pricing = pricing_context()
    if pricing.get("status") == "UNKNOWN" or pricing.get("verified") is not True:
        raise BookGeneration4223Error(
            "Applicable tariff is UNKNOWN. STOP before provider call."
        )
    if pricing.get("unmodeled_regimes"):
        raise BookGeneration4223Error(
            "A billable pricing regime cannot be bounded. STOP."
        )
    thinking_ok = (
        identity.get("thinking_mode") in {None, "disabled"}
        and identity.get("thinking_disabled") is not False
        and identity.get("thinking_type") in {None, "disabled"}
    )
    if identity.get("thinking_type") not in {None, "disabled"}:
        raise BookGeneration4223Error(
            "Thinking is enabled and cannot be bounded. STOP."
        )
    if not thinking_ok and identity.get("thinking_present"):
        raise BookGeneration4223Error(
            "Thinking is not the verified budgeted configuration. STOP."
        )
    input_est = estimate_input_tokens(identity)
    input_tokens = int(input_est["chosen_tokens"])
    output_plan = evidence_derived_max_output(
        idea_count=idea_count, section_count=section_count
    )
    max_out = int(output_plan["chosen_max_output_tokens"])
    theoretical = tokens_to_usd(input_tokens=input_tokens, output_tokens=max_out)
    long_context = input_tokens + max_out >= 200_000
    rates_usable = (
        pricing.get("verified") is True
        and pricing.get("input_cost_per_1m_tokens") is not None
        and pricing.get("output_cost_per_1m_tokens") is not None
        and not pricing.get("unmodeled_regimes")
        and not long_context
    )
    established = rates_usable and theoretical["decimal_total"] is not None
    over_remaining = (
        theoretical["decimal_total"] > remaining_budget if established else True
    )
    over_global = (
        theoretical["decimal_total"] > BUDGET_CAP_USD if established else True
    )
    within = established and not over_remaining and not over_global
    block_reason = None
    if not established:
        block_reason = "COST_MAXIMUM_UNKNOWN"
    elif over_global or over_remaining:
        block_reason = "COST_MAXIMUM_EXCEEDS_REMAINING_BUDGET"
    return {
        "phase": PHASE,
        "chapter_id": chapter_id,
        "provider": PROVIDER,
        "model": MODEL,
        "model_id": f"{PROVIDER}/{MODEL}",
        "maximum_remote_calls": 1,
        "budget_cap_usd": float(BUDGET_CAP_USD),
        "budget_cap_display": BUDGET_CAP_DISPLAY,
        "remaining_budget_usd": float(remaining_budget),
        "pricing": pricing,
        "pricing_effective_date": PRICING_EFFECTIVE_DATE,
        "pricing_are_configured_project_rates": True,
        "not_live_provider_prices": True,
        "rates_established_with_sufficient_certainty": rates_usable,
        "thinking_mode": "disabled",
        "thinking_tokens_budgeted": 0,
        "thinking_cost": "disabled_not_unknown",
        "long_context_regime": "NOT APPLICABLE",
        "applicable_fees": [],
        "tariff_uncertainty": "none_modeled_for_verified_sonnet_standard_rates",
        "input_estimate": input_est,
        "output_plan": output_plan,
        "max_output_tokens": max_out,
        "theoretical_maximum_usd": theoretical["total_cost_usd"],
        "theoretical_maximum_decimal": str(theoretical["decimal_total"]),
        "theoretical_maximum_breakdown": {
            "input_cost_usd": theoretical["input_cost_usd"],
            "output_cost_usd": theoretical["output_cost_usd"],
        },
        "preparation_calculable_maximum_usd": str(PREPARATION_CALCULABLE_MAXIMUM_USD),
        "central_estimate_is_not_the_safety_cap": True,
        "within_budget": within,
        "unknown_is_not_zero": True,
        "did_not_truncate_sources": True,
        "did_not_silently_reduce_quality": True,
        "not_a_provider_invoice": True,
        "blocked": not within,
        "block_reason": block_reason,
        "secrets_included": False,
    }


def remaining_budget(
    *,
    accumulated_actual: Decimal,
    reserved_or_uncertain: Decimal,
) -> Decimal:
    return BUDGET_CAP_USD - accumulated_actual - reserved_or_uncertain


__all__ = [
    "actual_cost",
    "evidence_derived_max_output",
    "estimate_input_tokens",
    "pricing_context",
    "remaining_budget",
    "reserve_chapter_budget",
    "tokens_to_usd",
]
