"""
Durable exclusive one-shot lock for CH018.

States distinguish preparation, reservation, possible send, receipt,
validation, failure, and uncertainty. Reservation is persisted before
the network send. A consumed lock is never erased for a second call.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.book_generation_4b221.constants import (
    AUTHORIZATION_SCOPE,
    LOCK_CONSUMED_STATES,
    LOCK_STATE_PREPARATION,
    LOCK_STATE_RESERVED,
    PHASE,
)
from app.book_generation_4b221.guard import BookGeneration4221Error
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_lock(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    import json

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "phase": PHASE,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "state": "UNCERTAIN",
            "consumed": True,
            "reusable": False,
            "parse_error": True,
            "note": "Lock exists but could not be parsed. Authorization treated as consumed.",
        }
    if not isinstance(payload, dict):
        return {
            "phase": PHASE,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "state": "UNCERTAIN",
            "consumed": True,
            "reusable": False,
            "parse_error": True,
        }
    return payload


def lock_state(path: Path) -> str | None:
    payload = read_lock(path)
    if payload is None:
        return None
    return str(payload.get("state") or "") or None


def lock_already_consumed(path: Path) -> bool:
    payload = read_lock(path)
    if payload is None:
        return False
    state = str(payload.get("state") or "")
    if payload.get("consumed") is True:
        return True
    return state in LOCK_CONSUMED_STATES


def write_lock(
    path: Path,
    *,
    state: str,
    request_sha256: str | None = None,
    note: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing = read_lock(path) or {}
    history = list(existing.get("history") or [])
    if existing.get("state"):
        history.append(
            {
                "state": existing.get("state"),
                "updated_at": existing.get("updated_at"),
            }
        )
    consumed = state in LOCK_CONSUMED_STATES or bool(existing.get("consumed"))
    payload = {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "state": state,
        "consumed": consumed,
        "reusable": False,
        "fallback": "forbidden",
        "retry": "forbidden",
        "openai": "forbidden",
        "terra": "forbidden",
        "other_chapters": "forbidden",
        "production_writes": "forbidden",
        "request_sha256": request_sha256 or existing.get("request_sha256"),
        "created_at": existing.get("created_at") or _now(),
        "updated_at": _now(),
        "history": history[-12:],
        "note": note,
        "secrets_included": False,
    }
    if extra:
        payload.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_bytes_atomic(path, payload)
    return payload


def persist_preparation(path: Path) -> dict[str, Any]:
    if lock_already_consumed(path):
        raise BookGeneration4221Error(
            "CH018 real-call lock already consumed — authorization used. NO RETRY."
        )
    return write_lock(
        path,
        state=LOCK_STATE_PREPARATION,
        note="Preparation without a remote call.",
    )


def reserve_call(path: Path, *, request_sha256: str) -> dict[str, Any]:
    if lock_already_consumed(path):
        raise BookGeneration4221Error(
            "CH018 real-call lock already consumed — authorization used. NO RETRY."
        )
    return write_lock(
        path,
        state=LOCK_STATE_RESERVED,
        request_sha256=request_sha256,
        note="Reservation persisted before network send.",
        extra={"boundary": "remote_invocation", "http_sent": False},
    )


def transition_lock(
    path: Path,
    *,
    state: str,
    request_sha256: str | None = None,
    note: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not path.is_file():
        raise BookGeneration4221Error(
            "Cannot transition a missing CH018 lock. Reservation is required first."
        )
    current = read_lock(path) or {}
    if str(current.get("authorization_scope") or "") not in {"", AUTHORIZATION_SCOPE}:
        raise BookGeneration4221Error("Lock authorization scope mismatch.")
    payload = extra or {}
    return write_lock(
        path,
        state=state,
        request_sha256=request_sha256 or current.get("request_sha256"),
        note=note,
        extra=payload,
    )


__all__ = [
    "lock_already_consumed",
    "lock_state",
    "persist_preparation",
    "read_lock",
    "reserve_call",
    "transition_lock",
    "write_lock",
]
