"""
Precall cost bound for the remaining-13 lot. Cap is 2.24 USD.

Unknown is never treated as zero. Historical remainders are not this cap.
Theoretical maximum uses request max_tokens. Thinking stays disabled.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from app.book_generation_4b221.costing import actual_cost, tokens_to_usd
from app.book_generation_4b223.costing import (
    estimate_input_tokens,
    evidence_derived_max_output,
    pricing_context,
)
from app.book_generation_4b227.constants import (
    BUDGET_CAP_DISPLAY,
    BUDGET_CAP_USD,
    MODEL,
    PHASE,
    PREPARATION_CENTRAL_USD,
    PREPARATION_MAX_USD,
    PREPARATION_RECOMMENDED_USD,
    PRICING_EFFECTIVE_DATE,
    PROVIDER,
)
from app.book_generation_4b227.guard import BookGeneration4227Error


def remaining_budget(
    *,
    accumulated_actual: Decimal,
    reserved_or_uncertain: Decimal,
) -> Decimal:
    return BUDGET_CAP_USD - accumulated_actual - reserved_or_uncertain


def reserve_chapter_budget(
    identity: Mapping[str, Any],
    *,
    chapter_id: str,
    idea_count: int,
    section_count: int,
    remaining: Decimal,
) -> dict[str, Any]:
    pricing = pricing_context()
    if pricing.get("status") == "UNKNOWN" or pricing.get("verified") is not True:
        raise BookGeneration4227Error(
            "Applicable tariff is UNKNOWN. STOP before provider call."
        )
    if pricing.get("unmodeled_regimes"):
        raise BookGeneration4227Error(
            "A billable pricing regime cannot be bounded. STOP."
        )
    thinking_ok = (
        identity.get("thinking_mode") in {None, "disabled"}
        and identity.get("thinking_disabled") is not False
        and identity.get("thinking_type") in {None, "disabled"}
    )
    if identity.get("thinking_type") not in {None, "disabled"}:
        raise BookGeneration4227Error(
            "Thinking is enabled and cannot be bounded. STOP."
        )
    if not thinking_ok and identity.get("thinking_present"):
        raise BookGeneration4227Error(
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
    if not established:
        raise BookGeneration4227Error(
            f"{chapter_id} theoretical maximum is UNKNOWN. STOP."
        )
    theoretical_decimal = Decimal(str(theoretical["decimal_total"]))
    over_remaining = theoretical_decimal > remaining
    over_global = theoretical_decimal > BUDGET_CAP_USD
    within = not over_remaining and not over_global
    block_reason = None
    if over_global or over_remaining:
        block_reason = "COST_MAXIMUM_EXCEEDS_REMAINING_BUDGET"
    if long_context:
        raise BookGeneration4227Error(
            f"{chapter_id} crosses a known long-context tariff threshold. STOP."
        )
    return {
        "phase": PHASE,
        "chapter_id": chapter_id,
        "provider": PROVIDER,
        "model": MODEL,
        "model_id": f"{PROVIDER}/{MODEL}",
        "maximum_remote_calls": 1,
        "budget_cap_usd": float(BUDGET_CAP_USD),
        "budget_cap_display": BUDGET_CAP_DISPLAY,
        "remaining_budget_usd": float(remaining),
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
        "theoretical_maximum_decimal": str(theoretical_decimal),
        "theoretical_maximum_breakdown": {
            "input_cost_usd": theoretical["input_cost_usd"],
            "output_cost_usd": theoretical["output_cost_usd"],
        },
        "preparation_central_usd": float(PREPARATION_CENTRAL_USD),
        "preparation_max_usd": float(PREPARATION_MAX_USD),
        "preparation_recommended_usd": float(PREPARATION_RECOMMENDED_USD),
        "central_estimate_is_not_the_safety_cap": True,
        "historical_remaining_is_not_this_authorization": True,
        "unknown_is_not_zero": True,
        "within_budget": within,
        "blocked": not within,
        "block_reason": block_reason,
        "secrets_included": False,
    }


def assert_lot_within_cap(theoretical_by_chapter: Mapping[str, Decimal]) -> Decimal:
    lot = Decimal("0")
    for chapter_id, value in theoretical_by_chapter.items():
        if value is None:
            raise BookGeneration4227Error(
                f"{chapter_id} theoretical maximum is UNKNOWN. STOP."
            )
        lot += value
    if lot > BUDGET_CAP_USD:
        raise BookGeneration4227Error(
            f"Sum of calculable maxima {lot} exceeds {BUDGET_CAP_USD}. "
            "STOP without changing parameters."
        )
    return lot


__all__ = [
    "actual_cost",
    "assert_lot_within_cap",
    "estimate_input_tokens",
    "evidence_derived_max_output",
    "pricing_context",
    "remaining_budget",
    "reserve_chapter_budget",
    "tokens_to_usd",
]
