"""Book roles are explicit. A depositor is not an author unless assigned as one."""

from __future__ import annotations

from typing import Any

from app.cover.constants import ATTRIBUTION_ROLES


class AttributionError(ValueError):
    """Role assignment rejected."""


def register_depositor(*, project_id: str, person_ref: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "person_ref": person_ref,
        "role": "DEPOSITOR",
        "author_id": None,
        "implies_book_author": False,
        "implies_recorded_speaker": False,
        "implies_commissioning_client": False,
        "implies_project_owner": False,
    }


def assign_role(
    *,
    project_id: str,
    author_id: str,
    role: str,
) -> dict[str, Any]:
    if role not in ATTRIBUTION_ROLES or role == "DEPOSITOR":
        raise AttributionError(f"role {role!r} is not an author-library book role")
    if not author_id:
        raise AttributionError("an author role requires an existing author_id")
    return {
        "project_id": project_id,
        "author_id": author_id,
        "role": role,
        "implied_from_depositor": False,
    }


def book_author_ids(attributions: list[dict[str, Any]], project_id: str) -> list[str]:
    return [
        str(item["author_id"])
        for item in attributions
        if item.get("project_id") == project_id
        and item.get("role") == "BOOK_AUTHOR"
        and item.get("author_id")
    ]


__all__ = [
    "AttributionError",
    "assign_role",
    "book_author_ids",
    "register_depositor",
]
