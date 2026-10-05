"""
Isolated multi-chapter adapter.

Reuses the existing generator, validator, costing, and lock machinery.
Never calls a provider. Never writes production book.json.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.book_batch_preparation_4b222.constants import (
    ACCEPTED_CHAPTERS,
    FAITHFUL_PROMPT_1_1,
    MODEL,
    PHASE,
    STATUS_ACCEPTED,
    STATUS_GENERATED,
    STATUS_PENDING,
    STATUS_STRUCTURE_FAILED,
    STATUS_UNCERTAIN,
)
from app.book_batch_preparation_4b222.guard import BookBatchPreparation4222Error
from app.book_batch_preparation_4b222.hard_stop import evaluate_hard_stops


def next_chapter_to_generate(
    *,
    chapter_ids: list[str],
    progress: Mapping[str, Any],
    remaining_authorization_calls: int,
) -> dict[str, Any]:
    by_id = {
        row["chapter_id"]: row
        for row in progress.get("chapters") or []
    }
    skipped = []
    for chapter_id in chapter_ids:
        row = by_id.get(chapter_id) or {}
        status = str(row.get("status") or STATUS_PENDING)
        if chapter_id in ACCEPTED_CHAPTERS or status == STATUS_ACCEPTED:
            skipped.append({"chapter_id": chapter_id, "reason": "accepted"})
            continue
        if status == STATUS_GENERATED and row.get("attempt"):
            skipped.append({"chapter_id": chapter_id, "reason": "already_generated"})
            continue
        if status == STATUS_UNCERTAIN:
            raise BookBatchPreparation4222Error(
                f"{chapter_id} is UNCERTAIN. Do not repeat the paid call."
            )
        if remaining_authorization_calls <= 0:
            raise BookBatchPreparation4222Error(
                "Remaining authorization exhausted. Resume only after a new token."
            )
        return {
            "phase": PHASE,
            "chapter_id": chapter_id,
            "model": MODEL,
            "prompt": FAITHFUL_PROMPT_1_1,
            "one_chapter_per_call": True,
            "skipped": skipped,
            "ready": True,
        }
    return {
        "phase": PHASE,
        "chapter_id": None,
        "skipped": skipped,
        "ready": False,
        "reason": "no_pending_chapter",
    }


def simulate_offline_batch(
    *,
    chapter_ids: list[str],
    outcomes: Mapping[str, Mapping[str, Any]],
    authorized: bool,
    remaining_authorization_calls: int,
    cap_usd: float | None,
) -> dict[str, Any]:
    preserved: list[dict[str, Any]] = []
    stopped = None
    calls = 0
    for chapter_id in chapter_ids:
        if chapter_id in ACCEPTED_CHAPTERS:
            preserved.append({"chapter_id": chapter_id, "status": STATUS_ACCEPTED})
            continue
        outcome = dict(outcomes.get(chapter_id) or {})
        status = str(outcome.get("status") or STATUS_PENDING)
        if status == STATUS_GENERATED and outcome.get("attempt"):
            preserved.append({"chapter_id": chapter_id, "status": STATUS_GENERATED})
            continue
        if outcome.get("lock_state") == STATUS_UNCERTAIN:
            stopped = evaluate_hard_stops(
                authorized=authorized,
                theoretical_maximum_usd=outcome.get("theoretical_maximum_usd"),
                cap_usd=cap_usd,
                lock_uncertain=True,
                remaining_authorization=remaining_authorization_calls > 0,
            )
            break
        if outcome.get("lock_consumed"):
            stopped = evaluate_hard_stops(
                authorized=authorized,
                theoretical_maximum_usd=outcome.get("theoretical_maximum_usd"),
                cap_usd=cap_usd,
                lock_consumed=True,
                remaining_authorization=remaining_authorization_calls > 0,
            )
            break
        maximum = outcome.get("theoretical_maximum_usd")
        stops = evaluate_hard_stops(
            authorized=authorized,
            cost_status=str(outcome.get("cost_status") or "known"),
            theoretical_maximum_usd=maximum,
            cap_usd=cap_usd,
            json_valid=outcome.get("json_valid", True),
            truncated=bool(outcome.get("truncated")),
            missing_idea_handles=list(outcome.get("missing_idea_handles") or []),
            invented_idea_handles=list(outcome.get("invented_idea_handles") or []),
            invalid_src=list(outcome.get("invalid_src") or []),
            retry_requested=bool(outcome.get("retry_requested")),
            fallback_requested=bool(outcome.get("fallback_requested")),
            multi_chapter_call=bool(outcome.get("multi_chapter_call")),
            remaining_authorization=remaining_authorization_calls > 0,
        )
        if stops["blocked"]:
            preserved.append(
                {
                    "chapter_id": chapter_id,
                    "status": STATUS_STRUCTURE_FAILED
                    if "invalid_json" in stops["stops"]
                    or "truncated_output" in stops["stops"]
                    or "idea_handles_missing_from_paragraph_evidence" in stops["stops"]
                    or "invalid_src" in stops["stops"]
                    else "BLOCKED",
                    "stops": stops["stops"],
                }
            )
            stopped = stops
            break
        calls += 1
        remaining_authorization_calls -= 1
        preserved.append({"chapter_id": chapter_id, "status": STATUS_GENERATED, "fake": True})
    return {
        "phase": PHASE,
        "provider_calls": 0,
        "simulated_successful_units": calls,
        "preserved": preserved,
        "stopped": stopped,
        "retries": 0,
        "fallbacks": 0,
        "real_provider_used": False,
    }


__all__ = ["next_chapter_to_generate", "simulate_offline_batch"]
