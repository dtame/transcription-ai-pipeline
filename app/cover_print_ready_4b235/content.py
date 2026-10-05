"""Resolve cover copy from approved records. Do not invent an author or a biography."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.cover.author_library.attribution import book_author_ids
from app.cover.content.contract import approval_blockers, description_within_range, word_count
from app.cover.models.author import AuthorProfile
from app.cover_print_ready_4b235.constants import (
    AUTHOR_STATUS_MISSING,
    BIOGRAPHY_STATUS_MISSING,
    DESCRIPTION_STATUS_APPROVED,
    DESCRIPTION_STATUS_MISSING,
    DESCRIPTION_STATUS_PROPOSED,
    PROJECT_NAME,
)
from app.cover_print_ready_4b235.guard import CoverPrintReady4235Error

PROPOSED_DESCRIPTION = (
    "The Life You Already Inherited follows one claim through nineteen chapters: "
    "resurrection life is an inheritance already given, not a prize still to be earned. "
    "It begins by unlearning what was handed down, then turns to the resurrection received "
    "in flesh and bone, to a death already destroyed, and to the offices of priest, prophet, "
    "and king. Access is set apart from achievement. Union is considered beside the love "
    "already given to Jesus.\n\n"
    "The later chapters take up a mind set above, the laws a person has given himself, "
    "and spirit, soul, and body. They move through reasonings and strongholds, through "
    "prayer returned to its place, and through the renewed mind. What has been received "
    "is to be put into practice. Grace is treated as barely touched. Death is considered "
    "as gain, and nothing is left to chance. Testimonies of resurrection gather near the "
    "close, and the final chapter stays with what comes out of the eater.\n\n"
    "The book remains with that subject: resurrection life, union with God, and the "
    "practice of spiritual authority."
)

assert description_within_range(PROPOSED_DESCRIPTION)
assert not approval_blockers(PROPOSED_DESCRIPTION)
assert 130 <= word_count(PROPOSED_DESCRIPTION) <= 180


def load_book_fields(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    project = payload.get("project") if isinstance(payload.get("project"), dict) else {}
    absent = payload.get("absent_editorial_fields")
    return {
        "title": str(payload.get("title") or "").strip(),
        "subtitle": str(payload.get("subtitle") or "").strip(),
        "author": payload.get("author"),
        "absent_editorial_fields": absent if isinstance(absent, dict) else {},
        "project_id": str(project.get("name") or "").strip(),
        "document_version": str(payload.get("document_version") or "").strip(),
    }


def resolve_subtitle(book: dict[str, Any]) -> dict[str, Any]:
    subtitle = str(book.get("subtitle") or "").strip()
    if not subtitle:
        return {"text": None, "status": "ABSENT"}
    return {"text": subtitle, "status": "PRESENT"}


def resolve_author(book: dict[str, Any], library_index: dict[str, Any] | None) -> dict[str, Any]:
    """A display name requires an explicit BOOK_AUTHOR link and publication consent."""
    absent = book.get("absent_editorial_fields") or {}
    book_author = book.get("author")
    if "author" in absent or book_author in (None, "", [], {}):
        book_name = None
    elif isinstance(book_author, str) and book_author.strip():
        book_name = book_author.strip()
    else:
        book_name = None
    index = library_index or {}
    attributions = [item for item in index.get("attributions") or [] if isinstance(item, dict)]
    project_id = str(book.get("project_id") or PROJECT_NAME)
    author_ids = book_author_ids(attributions, project_id)
    authors = index.get("authors") if isinstance(index.get("authors"), dict) else {}
    if len(author_ids) == 1:
        raw = authors.get(author_ids[0])
        if isinstance(raw, dict):
            profile = AuthorProfile.from_public_dict(raw)
            if profile.name_publication_authorized and profile.display_name:
                return {
                    "name": profile.display_name,
                    "status": "APPROVED",
                    "author_id": profile.author_id,
                    "source": "author_library.BOOK_AUTHOR",
                }
    if book_name and "author" not in absent:
        return {
            "name": book_name,
            "status": "APPROVED",
            "author_id": None,
            "source": "book.author",
        }
    return {
        "name": None,
        "status": AUTHOR_STATUS_MISSING,
        "author_id": None,
        "source": None,
    }


def resolve_biography(library_index: dict[str, Any] | None, author_id: str | None) -> dict[str, Any]:
    if not author_id:
        return {"text": None, "status": BIOGRAPHY_STATUS_MISSING}
    authors = (library_index or {}).get("authors")
    raw = authors.get(author_id) if isinstance(authors, dict) else None
    if not isinstance(raw, dict):
        return {"text": None, "status": BIOGRAPHY_STATUS_MISSING}
    profile = AuthorProfile.from_public_dict(raw)
    approved = [
        fact.text
        for fact in profile.approved_facts()
        if fact.kind.lower() in {"biography", "author_biography"} and fact.text.strip()
    ]
    if len(approved) == 1:
        return {"text": approved[0], "status": "APPROVED"}
    return {"text": None, "status": BIOGRAPHY_STATUS_MISSING}


def find_approved_descriptions(root: Path) -> list[str]:
    found: list[str] = []
    roots = [root / "sortie", root / "audit"]
    for base in roots:
        if not base.is_dir():
            continue
        for path in base.rglob("*.json"):
            posix = path.as_posix().lower()
            if "cover" not in posix:
                continue
            if path.stat().st_size > 2_000_000:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            _collect_approved(payload, found)
    unique: list[str] = []
    for text in found:
        if text not in unique:
            unique.append(text)
    return unique


def resolve_description(
    approved_texts: list[str],
    *,
    allow_proposal: bool,
) -> dict[str, Any]:
    if len(approved_texts) > 1:
        raise CoverPrintReady4235Error(
            "more than one approved back-cover description exists. STOP."
        )
    if len(approved_texts) == 1:
        return {
            "text": approved_texts[0],
            "status": DESCRIPTION_STATUS_APPROVED,
            "canonical": True,
            "requires_approval": False,
            "word_count": word_count(approved_texts[0]),
        }
    if allow_proposal:
        return {
            "text": PROPOSED_DESCRIPTION,
            "status": DESCRIPTION_STATUS_PROPOSED,
            "canonical": False,
            "requires_approval": True,
            "word_count": word_count(PROPOSED_DESCRIPTION),
            "basis": "canonical title, canonical subtitle, and the nineteen chapter titles",
            "uses_chapter_bodies": False,
        }
    return {
        "text": None,
        "status": DESCRIPTION_STATUS_MISSING,
        "canonical": False,
        "requires_approval": True,
        "word_count": 0,
    }


def _collect_approved(node: Any, found: list[str]) -> None:
    if isinstance(node, dict):
        status = node.get("book_description_status")
        text = node.get("book_description")
        if status == DESCRIPTION_STATUS_APPROVED and isinstance(text, str) and text.strip():
            found.append(text.strip())
        for value in node.values():
            _collect_approved(value, found)
    elif isinstance(node, list):
        for value in node:
            _collect_approved(value, found)


__all__ = [
    "PROPOSED_DESCRIPTION",
    "find_approved_descriptions",
    "load_book_fields",
    "resolve_author",
    "resolve_biography",
    "resolve_description",
    "resolve_subtitle",
]
