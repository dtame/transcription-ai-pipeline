"""
Durable lock state machine for the future 13-chapter authorization.

This phase prepares the mechanism and may simulate transitions in memory.
It does not reserve a real paid call.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.book_full_generation_preparation_4b226.constants import (
    FUTURE_AUTHORIZATION_SCOPE,
    FUTURE_LOCK_VERSION,
    LOCK_CONSUMED_STATES,
    LOCK_RESUME_WITHOUT_RECALL,
    LOCK_STATE_NOT_STARTED,
    LOCK_STOP_STATES,
    PHASE,
    REMAINING_CHAPTER_IDS,
)
from app.book_full_generation_preparation_4b226.guard import (
    BookFullGenerationPreparation4226Error,
    reject_replay,
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_lock(*, chapter_id: str) -> dict[str, Any]:
    if chapter_id not in REMAINING_CHAPTER_IDS:
        raise BookFullGenerationPreparation4226Error(
            f"{chapter_id} is outside the remaining-13 lock scope."
        )
    return {
        "phase": PHASE,
        "lock_version": FUTURE_LOCK_VERSION,
        "authorization_scope": FUTURE_AUTHORIZATION_SCOPE,
        "authorization_activated": False,
        "chapter_id": chapter_id,
        "state": LOCK_STATE_NOT_STARTED,
        "consumed": False,
        "reusable": False,
        "retry": "forbidden",
        "fallback": "forbidden",
        "real_reservation": False,
        "created_at": _now(),
        "updated_at": _now(),
        "history": [],
        "note": "Prepared lock. No paid reservation.",
        "secrets_included": False,
    }


class SimulationLockStore:
    """In-memory locks for offline simulation. Never a financial reservation."""

    def __init__(self) -> None:
        self.locks: dict[str, dict[str, Any]] = {
            chapter_id: empty_lock(chapter_id=chapter_id)
            for chapter_id in REMAINING_CHAPTER_IDS
        }

    def read(self, chapter_id: str) -> dict[str, Any]:
        return dict(self.locks[chapter_id])

    def consumed(self, chapter_id: str) -> bool:
        payload = self.locks[chapter_id]
        state = str(payload.get("state") or "")
        return bool(payload.get("consumed")) or state in LOCK_CONSUMED_STATES

    def transition(
        self,
        chapter_id: str,
        *,
        state: str,
        note: str = "",
        real_reservation: bool = False,
    ) -> dict[str, Any]:
        if real_reservation:
            raise BookFullGenerationPreparation4226Error(
                "Real paid reservations are forbidden in Phase 4B.2.26."
            )
        current = self.locks[chapter_id]
        current_state = str(current.get("state") or "")
        if current_state in LOCK_STOP_STATES and state not in {
            current_state,
        }:
            if state != current_state:
                reject_replay()
        if current_state in LOCK_RESUME_WITHOUT_RECALL and state in LOCK_CONSUMED_STATES:
            raise BookFullGenerationPreparation4226Error(
                f"{chapter_id} is already RESPONSE_VALIDATED. No second call."
            )
        history = list(current.get("history") or [])
        history.append({"state": current_state, "updated_at": current.get("updated_at")})
        payload = dict(current)
        payload.update(
            {
                "state": state,
                "consumed": state in LOCK_CONSUMED_STATES,
                "updated_at": _now(),
                "history": history[-16:],
                "note": note,
                "real_reservation": False,
            }
        )
        self.locks[chapter_id] = payload
        return dict(payload)


def next_admissible_chapter(
    *,
    chapter_ids: tuple[str, ...] | list[str],
    store: SimulationLockStore,
    accepted_ids: tuple[str, ...] | list[str],
) -> dict[str, Any]:
    skipped: list[dict[str, Any]] = []
    for chapter_id in chapter_ids:
        if chapter_id in accepted_ids:
            skipped.append({"chapter_id": chapter_id, "reason": "accepted"})
            continue
        if chapter_id not in REMAINING_CHAPTER_IDS:
            skipped.append({"chapter_id": chapter_id, "reason": "out_of_scope"})
            continue
        payload = store.read(chapter_id)
        state = str(payload.get("state") or "")
        if state in LOCK_RESUME_WITHOUT_RECALL:
            skipped.append({"chapter_id": chapter_id, "reason": "already_validated"})
            continue
        if state in LOCK_STOP_STATES:
            return {
                "chapter_id": None,
                "blocked": True,
                "reason": f"{chapter_id}_{state}_NO_REPLAY",
                "skipped": skipped,
            }
        return {
            "chapter_id": chapter_id,
            "blocked": False,
            "ready": True,
            "skipped": skipped,
        }
    return {
        "chapter_id": None,
        "blocked": False,
        "ready": False,
        "reason": "no_pending_chapter",
        "skipped": skipped,
    }


__all__ = [
    "SimulationLockStore",
    "empty_lock",
    "next_admissible_chapter",
]
