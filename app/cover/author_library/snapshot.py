"""Freeze the biography approved for one edition. Later profile edits do not rewrite it."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.cover.models.author import AuthorProfile


def freeze_biography(
    profile: AuthorProfile | None,
    *,
    text: str | None,
    status: str,
) -> dict[str, Any]:
    if status == "APPROVED" and not (text or "").strip():
        raise ValueError("an approved biography snapshot needs text")
    if status == "MISSING_OPTIONAL":
        text = None
    facts = profile.approved_facts() if profile is not None else ()
    return {
        "author_id": None if profile is None else profile.author_id,
        "display_name": None if profile is None else profile.display_name,
        "text": text,
        "status": status,
        "approved_fact_ids": [fact.fact_id for fact in facts],
        "profile_updated_at": None if profile is None else profile.updated_at,
        "frozen_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def snapshot_unchanged(before: dict[str, Any], after_profile_update: dict[str, Any]) -> bool:
    return before == after_profile_update


__all__ = ["freeze_biography", "snapshot_unchanged"]
