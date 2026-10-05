"""Read-only access to the immutable 4B.2.17 CH012 candidate."""

from __future__ import annotations

import json
from typing import Any, Iterator

from app.book_authorial_voice_4b218.constants import (
    EXPECTED_PARAGRAPH_COUNT,
    EXPECTED_PARAGRAPH_IDS,
    EXPECTED_SECTION_IDS,
    TARGET_CHAPTER_ID,
    TARGET_CHAPTER_TITLE,
)
from app.book_authorial_voice_4b218.guard import BookAuthorialVoice4218Error
from app.book_authorial_voice_4b218.paths import (
    original_chapter_json_path,
    original_chapter_md_path,
)


def load_original_chapter() -> dict[str, Any]:
    path = original_chapter_json_path()
    if not path.is_file():
        raise BookAuthorialVoice4218Error(f"original CH012 candidate missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BookAuthorialVoice4218Error("original CH012 candidate is not an object")
    if payload.get("chapter_id") != TARGET_CHAPTER_ID:
        raise BookAuthorialVoice4218Error(
            f"original chapter_id {payload.get('chapter_id')!r} ≠ {TARGET_CHAPTER_ID}"
        )
    if payload.get("title") != TARGET_CHAPTER_TITLE:
        raise BookAuthorialVoice4218Error(
            f"original title {payload.get('title')!r} ≠ {TARGET_CHAPTER_TITLE}"
        )
    ids = tuple(paragraph_id for paragraph_id, _row in iter_paragraphs(payload))
    if ids != EXPECTED_PARAGRAPH_IDS:
        raise BookAuthorialVoice4218Error(
            f"original paragraph IDs {ids} ≠ {EXPECTED_PARAGRAPH_IDS}"
        )
    section_ids = tuple(
        str(section.get("section_id") or "")
        for section in payload.get("sections") or []
    )
    if section_ids != EXPECTED_SECTION_IDS:
        raise BookAuthorialVoice4218Error(
            f"original section IDs {section_ids} ≠ {EXPECTED_SECTION_IDS}"
        )
    if len(ids) != EXPECTED_PARAGRAPH_COUNT:
        raise BookAuthorialVoice4218Error(
            f"original paragraph count {len(ids)} ≠ {EXPECTED_PARAGRAPH_COUNT}"
        )
    return payload


def load_original_markdown() -> str:
    path = original_chapter_md_path()
    if not path.is_file():
        raise BookAuthorialVoice4218Error(f"original CH012 markdown missing: {path}")
    return path.read_text(encoding="utf-8")


def iter_paragraphs(chapter: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for section in chapter.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for paragraph in section.get("paragraphs") or []:
            if not isinstance(paragraph, dict):
                continue
            paragraph_id = str(paragraph.get("paragraph_id") or "")
            yield paragraph_id, {
                "paragraph_id": paragraph_id,
                "section_id": str(section.get("section_id") or ""),
                "section_title": str(section.get("title") or ""),
                "text": str(paragraph.get("text") or ""),
                "kind": str(paragraph.get("kind") or ""),
                "evidence_handles": list(paragraph.get("evidence_handles") or []),
                "source_refs": list(paragraph.get("source_refs") or []),
                "idea_refs": list(paragraph.get("idea_refs") or []),
                "example_refs": list(paragraph.get("example_refs") or []),
                "reference_refs": list(paragraph.get("reference_refs") or []),
                "uncertainty_refs": list(paragraph.get("uncertainty_refs") or []),
                "provider_handle": str(paragraph.get("provider_handle") or ""),
            }


def render_chapter_markdown(chapter: dict[str, Any]) -> str:
    lines = [f"# {chapter.get('title') or TARGET_CHAPTER_TITLE}", ""]
    for section in chapter.get("sections") or []:
        title = section.get("title") or section.get("section_id")
        lines.append(f"## {title}")
        lines.append("")
        for paragraph in section.get("paragraphs") or []:
            text = str(paragraph.get("text") or "").strip()
            if text:
                lines.append(text)
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def paragraph_ids(chapter: dict[str, Any]) -> tuple[str, ...]:
    return tuple(pid for pid, _row in iter_paragraphs(chapter))


def section_ids(chapter: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(section.get("section_id") or "")
        for section in chapter.get("sections") or []
    )


__all__ = [
    "iter_paragraphs",
    "load_original_chapter",
    "load_original_markdown",
    "paragraph_ids",
    "render_chapter_markdown",
    "section_ids",
]
