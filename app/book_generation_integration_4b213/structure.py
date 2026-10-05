"""Deterministic chapter structure validation. No provider. No invented evidence."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_generation.constants import (
    PARAGRAPH_KIND_CONNECTIVE,
    PARAGRAPH_KIND_SUBSTANTIVE,
    PARAGRAPH_KINDS,
)
from app.book_generation.models import scan_forbidden_book_structure
from app.book_generation_integration_4b213.constants import (
    DECISION_BLOCK,
    DECISION_PASS,
    PHASE,
    SYNTHETIC_PREFIX,
)
from app.book_generation_integration_4b213.guard import BookGenerationIntegration213Error


def iter_paragraphs(chapter: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    chapter_id = str(chapter.get("chapter_id") or "")
    for section in chapter.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        section_id = str(section.get("section_id") or "")
        for para in section.get("paragraphs") or []:
            if not isinstance(para, Mapping):
                continue
            payload = dict(para)
            payload["chapter_id"] = chapter_id
            payload["section_id"] = section_id
            rows.append(payload)
    return rows


def validate_chapter_structure(
    chapter: Mapping[str, Any],
    *,
    allowed_handles: Sequence[str] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(chapter, Mapping):
        raise BookGenerationIntegration213Error("chapter must be a mapping")
    forbidden = scan_forbidden_book_structure(chapter)
    if forbidden:
        errors.extend(f"forbidden_field:{name}" for name in forbidden)
    chapter_id = str(chapter.get("chapter_id") or "").strip()
    if not chapter_id:
        errors.append("chapter_id:missing")
    sections = chapter.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections:missing")
        sections = []
    allowed = list(
        allowed_handles
        if allowed_handles is not None
        else chapter.get("allowed_evidence_handles") or []
    )
    allowed_set = set(allowed)
    paragraphs = iter_paragraphs(chapter)
    if not paragraphs:
        errors.append("paragraphs:missing")
    seen_ids: set[str] = set()
    for para in paragraphs:
        pid = str(para.get("paragraph_id") or "").strip()
        kind = str(para.get("kind") or "").strip()
        text = str(para.get("text") or "")
        if not pid:
            errors.append("paragraph_id:missing")
        elif pid in seen_ids:
            errors.append(f"paragraph_id:duplicate:{pid}")
        seen_ids.add(pid)
        if not str(para.get("section_id") or "").strip():
            errors.append(f"{pid}:section_id:missing")
        if kind not in PARAGRAPH_KINDS:
            errors.append(f"{pid}:kind:invalid:{kind!r}")
        if not text.strip():
            errors.append(f"{pid}:text:empty")
        handles = [
            str(item).strip()
            for item in (para.get("evidence_handles") or [])
            if str(item).strip()
        ]
        if kind == PARAGRAPH_KIND_SUBSTANTIVE and not handles:
            errors.append(f"{pid}:evidence:missing")
        for handle in handles:
            if allowed_set and handle not in allowed_set:
                errors.append(f"{pid}:evidence:unknown_handle:{handle}")
            if chapter.get("synthetic") and not handle.startswith(SYNTHETIC_PREFIX):
                errors.append(f"{pid}:evidence:non_synthetic_handle_on_synthetic_chapter:{handle}")
        if kind == PARAGRAPH_KIND_CONNECTIVE:
            continue
        if kind == PARAGRAPH_KIND_SUBSTANTIVE and handles:
            continue
    ok = not errors
    return {
        "phase": PHASE,
        "ok": ok,
        "status": DECISION_PASS if ok else DECISION_BLOCK,
        "errors": errors,
        "chapter_id": chapter_id,
        "paragraph_count": len(paragraphs),
        "section_count": len(sections),
        "allowed_evidence_handles": allowed,
        "does_not_invent_evidence": True,
        "secrets_included": False,
    }


__all__ = ["iter_paragraphs", "validate_chapter_structure"]
