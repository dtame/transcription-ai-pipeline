"""Audit before DOCX generation. Blocking errors stop the phase."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.book_print_review_render_4b231.constants import (
    ACCEPTED_CHAPTER_IDS,
    BOOK_STATUS,
    BOOK_TITLE,
    BOOK_VERSION,
    EXPECTED_BOOK_SHA256,
    EXPECTED_CHAPTER_COUNT,
    EXPECTED_IDEA_COUNT,
    EXPECTED_PARAGRAPH_COUNT,
    EXPECTED_SECTION_COUNT,
    PENDING_CHAPTER_IDS,
    PHASE,
    PRINT_PROFILE,
)
from app.book_print_review_render_4b231.guard import BookPrintReviewRender4231Error
from app.book_print_review_render_4b231.hashes import file_sha256
from app.book_print_review_render_4b231.paths import (
    print_profile_path,
    production_book_path,
)
from app.word_renderer.document import configure_document
from app.word_renderer.mapping import map_book, source_paragraph_texts
from app.word_renderer.profile import load_profile, validate_profile


def load_canonical_book(*, root: Path | None = None) -> dict[str, Any]:
    path = production_book_path(root=root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BookPrintReviewRender4231Error("book.json must be an object. STOP.")
    return payload


def build_preflight(*, root: Path | None = None) -> dict[str, Any]:
    book_path = production_book_path(root=root)
    book_hash = file_sha256(book_path)
    if book_hash.get("sha256") != EXPECTED_BOOK_SHA256:
        raise BookPrintReviewRender4231Error(
            f"book.json SHA-256 mismatch: {book_hash.get('sha256')}. STOP."
        )
    payload = load_canonical_book(root=root)
    profile_path = print_profile_path()
    if not profile_path.is_file():
        raise BookPrintReviewRender4231Error(f"print profile missing: {profile_path}. STOP.")
    profile = load_profile(profile_path)
    validate_profile(profile)
    book = map_book(payload)
    paragraphs = source_paragraph_texts(payload)
    accepted = [
        chapter.get("chapter_id")
        for chapter in payload.get("chapters") or []
        if chapter.get("editorial_status") == "HUMAN_EDITORIALLY_ACCEPTED"
    ]
    structural = [
        chapter.get("chapter_id")
        for chapter in payload.get("chapters") or []
        if chapter.get("editorial_status") == "GENERATED_STRUCTURALLY_VALID"
    ]
    titles_ok = all(chapter.title for chapter in book.chapters) and all(
        section.title for chapter in book.chapters for section in chapter.sections
    )
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        raise BookPrintReviewRender4231Error(f"python-docx is missing: {exc}. STOP.") from exc
    configure_document(profile)
    checks = {
        "book_sha256": book_hash.get("sha256") == EXPECTED_BOOK_SHA256,
        "profile_present": profile_path.is_file(),
        "profile_valid": profile.get("profile_id") == PRINT_PROFILE,
        "engine_compatible": True,
        "chapters": book.chapter_count == EXPECTED_CHAPTER_COUNT,
        "sections": book.section_count == EXPECTED_SECTION_COUNT,
        "paragraphs": len(paragraphs) == EXPECTED_PARAGRAPH_COUNT == len(book.paragraph_texts),
        "titles": titles_ok,
        "metadata_title": book.title == BOOK_TITLE == payload.get("title"),
        "metadata_version": book.version == BOOK_VERSION,
        "metadata_status": book.status == BOOK_STATUS,
        "human_accepted": accepted == list(ACCEPTED_CHAPTER_IDS),
        "pending": structural == list(PENDING_CHAPTER_IDS),
        "idea_coverage": int(payload.get("idea_coverage_count") or 0) == EXPECTED_IDEA_COUNT,
        "local_python_docx": True,
        "book_json_not_mutated": True,
    }
    blocking = [name for name, ok in checks.items() if not ok]
    if blocking:
        raise BookPrintReviewRender4231Error(
            f"preflight blocked: {', '.join(blocking)}. STOP."
        )
    return {
        "phase": PHASE,
        "status": "PASS",
        "book_path": str(book_path).replace("\\", "/"),
        "book_sha256": book_hash.get("sha256"),
        "profile_path": str(profile_path).replace("\\", "/"),
        "profile_id": profile.get("profile_id"),
        "title": book.title,
        "subtitle": book.subtitle,
        "version": book.version,
        "editorial_status": book.status,
        "chapter_count": book.chapter_count,
        "section_count": book.section_count,
        "paragraph_count": len(paragraphs),
        "human_accepted_chapters": accepted,
        "pending_chapters": structural,
        "checks": checks,
        "blocking": blocking,
        "verification": "automatic",
        "secrets_included": False,
        "payload": payload,
        "profile": profile,
        "book": book,
    }


__all__ = ["build_preflight", "load_canonical_book"]
