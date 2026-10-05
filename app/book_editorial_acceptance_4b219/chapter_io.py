"""Read-only access to the accepted 4B.2.18 CH012 pair and the 4B.2.17 original."""

from __future__ import annotations

import json
from typing import Any, Iterator

from app.book_authorial_voice_4b218.chapter_io import (
    iter_paragraphs,
    paragraph_ids,
    render_chapter_markdown,
    section_ids,
)
from app.book_editorial_acceptance_4b219.constants import (
    CHAPTER_ID,
    CHAPTER_TITLE,
    PARAGRAPH_COUNT,
    PARAGRAPH_IDS,
    SECTION_IDS,
)
from app.book_editorial_acceptance_4b219.guard import BookEditorialAcceptance4219Error
from app.book_editorial_acceptance_4b219.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    original_chapter_json_path,
    original_chapter_md_path,
)


def _load_chapter(path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise BookEditorialAcceptance4219Error(f"{label} missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BookEditorialAcceptance4219Error(f"{label} is not an object")
    if payload.get("chapter_id") != CHAPTER_ID:
        raise BookEditorialAcceptance4219Error(
            f"{label} chapter_id {payload.get('chapter_id')!r} ≠ {CHAPTER_ID}"
        )
    if payload.get("title") != CHAPTER_TITLE:
        raise BookEditorialAcceptance4219Error(
            f"{label} title {payload.get('title')!r} ≠ {CHAPTER_TITLE}"
        )
    ids = paragraph_ids(payload)
    if ids != PARAGRAPH_IDS:
        raise BookEditorialAcceptance4219Error(
            f"{label} paragraph IDs {ids} ≠ {PARAGRAPH_IDS}"
        )
    found_sections = section_ids(payload)
    if found_sections != SECTION_IDS:
        raise BookEditorialAcceptance4219Error(
            f"{label} section IDs {found_sections} ≠ {SECTION_IDS}"
        )
    if len(ids) != PARAGRAPH_COUNT:
        raise BookEditorialAcceptance4219Error(
            f"{label} paragraph count {len(ids)} ≠ {PARAGRAPH_COUNT}"
        )
    return payload


def load_accepted_chapter() -> dict[str, Any]:
    return _load_chapter(accepted_chapter_json_path(), label="accepted CH012 JSON")


def load_accepted_markdown() -> str:
    path = accepted_chapter_md_path()
    if not path.is_file():
        raise BookEditorialAcceptance4219Error(f"accepted CH012 markdown missing: {path}")
    return path.read_text(encoding="utf-8")


def load_original_chapter() -> dict[str, Any]:
    return _load_chapter(original_chapter_json_path(), label="original CH012 JSON")


def load_original_markdown() -> str:
    path = original_chapter_md_path()
    if not path.is_file():
        raise BookEditorialAcceptance4219Error(f"original CH012 markdown missing: {path}")
    return path.read_text(encoding="utf-8")


def paragraph_idea_handles(chapter: dict[str, Any]) -> list[str]:
    handles: list[str] = []
    for _pid, row in iter_paragraphs(chapter):
        for handle in row["evidence_handles"]:
            if str(handle).startswith("IDEA"):
                handles.append(str(handle))
        handles.extend(str(item) for item in row["idea_refs"] if str(item).startswith("IDEA"))
    return handles


def all_paragraph_texts(chapter: dict[str, Any]) -> list[str]:
    return [row["text"] for _pid, row in iter_paragraphs(chapter)]


__all__ = [
    "all_paragraph_texts",
    "iter_paragraphs",
    "load_accepted_chapter",
    "load_accepted_markdown",
    "load_original_chapter",
    "load_original_markdown",
    "paragraph_idea_handles",
    "paragraph_ids",
    "render_chapter_markdown",
    "section_ids",
]
