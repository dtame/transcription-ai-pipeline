"""Cover-copy contract. This phase stores human drafts; it does not write them."""

from __future__ import annotations

from typing import Any

from app.cover.constants import (
    DESCRIPTION_WORD_MAX,
    DESCRIPTION_WORD_MIN,
    PROHIBITED_BACK_COVER_ELEMENTS,
)
from app.cover.models.author import AuthorProfile
from app.cover.models.statuses import require_content_status

PROHIBITED_PHRASES = (
    "testimonial",
    "as seen on",
    "bestseller",
    "award-winning",
    "experts agree",
    "isbn",
    "barcode",
    "five stars",
)


class ContentContractError(ValueError):
    """Cover copy transition rejected."""


def initial_content(profile: AuthorProfile | None = None) -> dict[str, Any]:
    biography_status = "MISSING_OPTIONAL" if _biography_missing(profile) else "NOT_STARTED"
    return {
        "book_description": None,
        "book_description_status": "NOT_STARTED",
        "book_description_word_min": DESCRIPTION_WORD_MIN,
        "book_description_word_max": DESCRIPTION_WORD_MAX,
        "author_biography": None,
        "author_biography_status": biography_status,
        "llm_invoked": False,
        "auto_approved": False,
        "invented_biography": False,
        "source_fact_ids": [fact.fact_id for fact in profile.approved_facts()] if profile else [],
        "prohibited_elements": list(PROHIBITED_BACK_COVER_ELEMENTS),
    }


def store_description_draft(state: dict[str, Any], text: str) -> dict[str, Any]:
    updated = dict(state)
    body = str(text or "").strip()
    if not body:
        raise ContentContractError("a description draft must be supplied; it is not generated here")
    updated["book_description"] = body
    updated["book_description_status"] = "DRAFT"
    updated["book_description_word_count"] = word_count(body)
    updated["book_description_within_range"] = description_within_range(body)
    updated["approval_blockers"] = approval_blockers(body)
    updated["llm_invoked"] = False
    updated["auto_approved"] = False
    return updated


def store_biography_draft(state: dict[str, Any], text: str) -> dict[str, Any]:
    updated = dict(state)
    body = str(text or "").strip()
    if not body:
        raise ContentContractError("a biography draft must be supplied; it is not invented here")
    updated["author_biography"] = body
    updated["author_biography_status"] = "DRAFT"
    updated["llm_invoked"] = False
    updated["invented_biography"] = False
    updated["auto_approved"] = False
    return updated


def biography_for_missing_profile(state: dict[str, Any]) -> dict[str, Any]:
    updated = dict(state)
    updated["author_biography"] = None
    updated["author_biography_status"] = "MISSING_OPTIONAL"
    updated["invented_biography"] = False
    updated["llm_invoked"] = False
    return updated


def submit_for_review(state: dict[str, Any], field: str) -> dict[str, Any]:
    status_key = _status_key(field)
    if state.get(status_key) != "DRAFT":
        raise ContentContractError(f"{field} must be a draft before review")
    if field == "book_description" and approval_blockers(str(state.get("book_description") or "")):
        raise ContentContractError("description draft contains a prohibited cover claim")
    updated = dict(state)
    updated[status_key] = "PENDING_HUMAN_REVIEW"
    updated["auto_approved"] = False
    return updated


def approve(state: dict[str, Any], field: str, *, reviewer: str) -> dict[str, Any]:
    if not str(reviewer or "").strip():
        raise ContentContractError("approval requires a human reviewer")
    status_key = _status_key(field)
    if state.get(status_key) != "PENDING_HUMAN_REVIEW":
        raise ContentContractError(f"{field} is not awaiting human review")
    if field == "book_description" and not description_within_range(str(state.get("book_description") or "")):
        raise ContentContractError("description is outside the configured word range")
    updated = dict(state)
    updated[status_key] = require_content_status("APPROVED")
    updated["auto_approved"] = False
    updated["approved_by"] = reviewer.strip()
    return updated


def word_count(text: str) -> int:
    return len([token for token in str(text or "").split() if token])


def description_within_range(
    text: str,
    *,
    minimum: int = DESCRIPTION_WORD_MIN,
    maximum: int = DESCRIPTION_WORD_MAX,
) -> bool:
    count = word_count(text)
    return minimum <= count <= maximum


def approval_blockers(text: str) -> list[str]:
    lowered = str(text or "").lower()
    return [phrase for phrase in PROHIBITED_PHRASES if phrase in lowered]


def back_layout_blocks(state: dict[str, Any]) -> list[str]:
    blocks: list[str] = []
    if state.get("book_description"):
        blocks.append("book_description")
    biography = state.get("author_biography")
    status = state.get("author_biography_status")
    if biography and status != "MISSING_OPTIONAL":
        blocks.append("author_biography")
    return blocks


def content_contract_document() -> dict[str, Any]:
    return {
        "fields": ["book_description", "author_biography"],
        "description": {
            "source": "manuscript_only",
            "word_min": DESCRIPTION_WORD_MIN,
            "word_max": DESCRIPTION_WORD_MAX,
            "configurable": True,
            "auto_approved": False,
            "llm_in_this_phase": False,
            "must_not_invent": list(PROHIBITED_BACK_COVER_ELEMENTS),
        },
        "biography": {
            "optional": True,
            "missing_status": "MISSING_OPTIONAL",
            "missing_value": None,
            "invented_biography_allowed": False,
            "auto_approved": False,
            "uses_only_approved_facts": True,
        },
        "statuses": [
            "NOT_STARTED",
            "DRAFT",
            "PENDING_HUMAN_REVIEW",
            "APPROVED",
            "MISSING_OPTIONAL",
        ],
        "phase": "contracts_and_validation_only",
    }


def _biography_missing(profile: AuthorProfile | None) -> bool:
    if profile is None:
        return True
    if profile.biography_reference:
        return False
    return not profile.approved_facts()


def _status_key(field: str) -> str:
    if field == "book_description":
        return "book_description_status"
    if field == "author_biography":
        return "author_biography_status"
    raise ContentContractError(f"unknown content field {field!r}")


__all__ = [
    "ContentContractError",
    "approval_blockers",
    "approve",
    "back_layout_blocks",
    "biography_for_missing_profile",
    "content_contract_document",
    "description_within_range",
    "initial_content",
    "store_biography_draft",
    "store_description_draft",
    "submit_for_review",
    "word_count",
]
