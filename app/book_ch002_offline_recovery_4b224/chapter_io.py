"""Read-only helpers for original and derived chapter JSON."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

from app.book_generation.models import BookSection, ChapterCandidate


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_from_dict(data: dict[str, Any]) -> ChapterCandidate:
    return ChapterCandidate(
        chapter_id=str(data.get("chapter_id") or ""),
        title=str(data.get("title") or ""),
        sections=tuple(BookSection.from_dict(section) for section in data.get("sections") or []),
        idea_refs=tuple(data.get("idea_refs") or ()),
        source_refs=tuple(data.get("source_refs") or ()),
        provider_raw_sha256=str(data.get("provider_raw_sha256") or ""),
        cache_signature=str(data.get("cache_signature") or ""),
    )


def iter_candidate_paragraphs(
    chapter: dict[str, Any],
) -> Iterator[tuple[str, int, dict[str, Any]]]:
    for section in chapter.get("sections") or []:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "")
        for index, paragraph in enumerate(section.get("paragraphs") or []):
            if isinstance(paragraph, dict):
                yield section_id, index, paragraph


def iter_raw_paragraphs(
    parsed: dict[str, Any],
) -> Iterator[tuple[str, int, dict[str, Any]]]:
    for section in parsed.get("sections") or []:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("sid") or "")
        for index, paragraph in enumerate(section.get("paras") or []):
            if isinstance(paragraph, dict):
                yield section_id, index, paragraph


def find_candidate_paragraph(
    chapter: dict[str, Any], paragraph_id: str
) -> tuple[str, int, dict[str, Any]] | None:
    for section_id, index, paragraph in iter_candidate_paragraphs(chapter):
        if str(paragraph.get("paragraph_id") or "") == paragraph_id:
            return section_id, index, paragraph
    return None


def find_raw_paragraph(
    parsed: dict[str, Any], handle: str
) -> tuple[str, int, dict[str, Any]] | None:
    for section_id, index, paragraph in iter_raw_paragraphs(parsed):
        if str(paragraph.get("h") or "") == handle:
            return section_id, index, paragraph
    return None


def deepcopy_chapter(chapter: dict[str, Any]) -> dict[str, Any]:
    copied = deepcopy(chapter)
    if not isinstance(copied, dict):
        raise TypeError("chapter payload is not an object")
    return copied


def paragraph_ids(chapter: dict[str, Any]) -> list[str]:
    return [
        str(paragraph.get("paragraph_id") or "")
        for _section_id, _index, paragraph in iter_candidate_paragraphs(chapter)
        if paragraph.get("paragraph_id")
    ]


def idea_handles(chapter: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for _section_id, _index, paragraph in iter_candidate_paragraphs(chapter):
        for handle in list(paragraph.get("evidence_handles") or []) + list(
            paragraph.get("idea_refs") or []
        ):
            if str(handle).startswith("IDEA"):
                found.append(str(handle))
    return found


__all__ = [
    "candidate_from_dict",
    "deepcopy_chapter",
    "find_candidate_paragraph",
    "find_raw_paragraph",
    "idea_handles",
    "iter_candidate_paragraphs",
    "iter_raw_paragraphs",
    "load_json",
    "paragraph_ids",
]
