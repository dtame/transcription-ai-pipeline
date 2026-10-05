"""
Precall cost bound for the CH003–CH004 resume. Cap is 0.32 USD.

Unknown is never treated as zero. The 4B.2.23 remainder is not this cap.
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
    reserve_chapter_budget as _historical_reserve,
)
from app.book_generation_4b225.constants import (
    BUDGET_CAP_DISPLAY,
    BUDGET_CAP_USD,
    CURSOR_FORECAST_USD,
    HISTORICAL_REMAINING_BUDGET_USD,
    PHASE,
)
from app.book_generation_4b225.guard import BookGeneration4225Error


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
    payload = _historical_reserve(
        identity,
        chapter_id=chapter_id,
        idea_count=idea_count,
        section_count=section_count,
        remaining_budget=remaining,
    )
    theoretical_raw = payload.get("theoretical_maximum_decimal")
    if theoretical_raw in {None, "UNKNOWN"}:
        raise BookGeneration4225Error(
            f"{chapter_id} theoretical maximum is UNKNOWN. STOP."
        )
    theoretical = Decimal(str(theoretical_raw))
    over_remaining = theoretical > remaining
    over_global = theoretical > BUDGET_CAP_USD
    within = not over_remaining and not over_global and payload.get("blocked") is not True
    block_reason = payload.get("block_reason")
    if over_global or over_remaining:
        within = False
        block_reason = "COST_MAXIMUM_EXCEEDS_REMAINING_BUDGET"
    payload.update(
        {
            "phase": PHASE,
            "budget_cap_usd": float(BUDGET_CAP_USD),
            "budget_cap_display": BUDGET_CAP_DISPLAY,
            "remaining_budget_usd": float(remaining),
            "cursor_forecast_usd": float(CURSOR_FORECAST_USD),
            "historical_remaining_budget_usd": float(HISTORICAL_REMAINING_BUDGET_USD),
            "historical_remaining_is_not_this_authorization": True,
            "within_budget": within,
            "blocked": not within,
            "block_reason": None if within else block_reason,
        }
    )
    return payload


def assert_lot_within_cap(theoretical_by_chapter: Mapping[str, Decimal]) -> Decimal:
    lot = Decimal("0")
    for chapter_id, value in theoretical_by_chapter.items():
        if value is None:
            raise BookGeneration4225Error(
                f"{chapter_id} theoretical maximum is UNKNOWN. STOP."
            )
        lot += value
    if lot > BUDGET_CAP_USD:
        raise BookGeneration4225Error(
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
