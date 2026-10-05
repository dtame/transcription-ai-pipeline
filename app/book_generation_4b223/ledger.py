"""Durable BATCH-01 budget ledger. Unspent remainder is not new authorization."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from app.book_generation_4b223.constants import (
    AUTHORIZED_CHAPTER_IDS,
    BATCH_ID,
    BUDGET_CAP_USD,
    PHASE,
)
from app.book_generation_4b223.costing import remaining_budget


def empty_ledger() -> dict[str, Any]:
    chapters = {
        chapter_id: {
            "chapter_id": chapter_id,
            "status": "NOT_STARTED",
            "theoretical_maximum_usd": None,
            "actual_cost_usd": None,
            "reserved_or_uncertain_usd": None,
            "input_tokens": None,
            "output_tokens": None,
            "thinking_tokens": None,
            "cost_status": "n/a",
        }
        for chapter_id in AUTHORIZED_CHAPTER_IDS
    }
    return {
        "phase": PHASE,
        "batch_id": BATCH_ID,
        "authorized_cap_usd": float(BUDGET_CAP_USD),
        "accumulated_actual_usd": 0.0,
        "reserved_or_uncertain_usd": 0.0,
        "remaining_budget_usd": float(BUDGET_CAP_USD),
        "unknown_treated_as_zero": False,
        "unspent_is_not_new_authorization": True,
        "chapters": chapters,
        "secrets_included": False,
    }


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or value == "UNKNOWN":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def update_ledger(
    ledger: Mapping[str, Any],
    *,
    chapter_id: str,
    status: str,
    theoretical_maximum_usd: Any = None,
    actual: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(ledger)
    chapters = {
        key: dict(value)
        for key, value in dict(payload.get("chapters") or {}).items()
    }
    row = dict(chapters.get(chapter_id) or {"chapter_id": chapter_id})
    row["status"] = status
    if theoretical_maximum_usd is not None:
        row["theoretical_maximum_usd"] = float(theoretical_maximum_usd) if theoretical_maximum_usd != "UNKNOWN" else None
        row["theoretical_maximum_raw"] = theoretical_maximum_usd
    if actual is not None:
        row["actual_cost_usd"] = actual.get("total_cost_usd")
        row["cost_status"] = actual.get("status") or actual.get("display") or "known"
        row["input_tokens"] = actual.get("input_tokens")
        row["output_tokens"] = actual.get("output_tokens")
        row["thinking_tokens"] = actual.get("thinking_tokens")
        if actual.get("display") == "UNKNOWN" or actual.get("status") == "UNKNOWN":
            row["reserved_or_uncertain_usd"] = row.get("theoretical_maximum_usd")
            row["actual_cost_usd"] = None
        else:
            row["reserved_or_uncertain_usd"] = None
    elif status in {"CALL_RESERVED", "CALL_MAY_HAVE_BEEN_SENT", "UNCERTAIN", "FAILED"}:
        row["reserved_or_uncertain_usd"] = row.get("theoretical_maximum_usd")
    chapters[chapter_id] = row

    accumulated = Decimal("0")
    reserved = Decimal("0")
    for item in chapters.values():
        actual_cost = _as_decimal(item.get("actual_cost_usd"))
        reserved_cost = _as_decimal(item.get("reserved_or_uncertain_usd"))
        if actual_cost is not None:
            accumulated += actual_cost
        elif reserved_cost is not None:
            reserved += reserved_cost
    remaining = remaining_budget(
        accumulated_actual=accumulated,
        reserved_or_uncertain=reserved,
    )
    payload.update(
        {
            "chapters": chapters,
            "accumulated_actual_usd": float(accumulated),
            "reserved_or_uncertain_usd": float(reserved),
            "remaining_budget_usd": float(remaining),
            "remaining_budget_decimal": str(remaining),
        }
    )
    return payload


__all__ = ["empty_ledger", "update_ledger"]
