"""Word-renderer data readiness. No layout decisions. No DOCX generation."""

from __future__ import annotations

from typing import Any

from app.book_generation.models import scan_forbidden_book_structure
from app.book_print_review_canonical_4b229.constants import (
    ABSENT_EDITORIAL_FIELDS,
    BOOK_TITLE,
    PHASE,
)


def assess_word_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    chapters = list(payload.get("chapters") or [])
    sections = [
        section
        for chapter in chapters
        for section in chapter.get("sections") or []
    ]
    paragraphs = [
        paragraph
        for section in sections
        for paragraph in section.get("paragraphs") or []
    ]
    title_page = bool(payload.get("title") == BOOK_TITLE)
    toc = all(
        str(chapter.get("title") or "").strip() and int(chapter.get("order") or 0) > 0
        for chapter in chapters
    ) and all(str(section.get("title") or "").strip() for section in sections)
    chapter_titles = all(str(chapter.get("title") or "").strip() for chapter in chapters)
    section_titles = all(str(section.get("title") or "").strip() for section in sections)
    body = all(str(paragraph.get("text") or "") for paragraph in paragraphs)
    chapter_breaks = [chapter.get("chapter_id") for chapter in chapters] == [
        f"CH{index:03d}" for index in range(1, 20)
    ]
    leaked = scan_forbidden_book_structure(payload)
    invented = [
        field
        for field in ABSENT_EDITORIAL_FIELDS
        if payload.get(field) not in (None, "", [], {}, payload.get("absent_editorial_fields", {}).get(field))
        and field in payload
    ]
    data_ready = all(
        (
            title_page,
            toc,
            chapter_titles,
            section_titles,
            body,
            chapter_breaks,
            not leaked,
            not invented,
        )
    )
    return {
        "phase": PHASE,
        "status": "PASS" if data_ready else "PARTIAL",
        "title_page": "READY" if title_page else "BLOCKED",
        "table_of_contents": "READY" if toc else "BLOCKED",
        "chapter_titles": "READY" if chapter_titles else "BLOCKED",
        "section_titles": "READY" if section_titles else "BLOCKED",
        "paragraphs": "READY" if body else "BLOCKED",
        "pagination": "WORD_RESPONSIBILITY",
        "headers_and_footers": "WORD_RESPONSIBILITY",
        "chapter_breaks": "READY" if chapter_breaks else "BLOCKED",
        "layout_fields_in_book_json": list(leaked),
        "invented_editorial_fields": invented,
        "docx_generated": False,
        "existing_markdown_docx_engine_invoked": False,
        "graphic_decisions_in_content": False,
        "notes": (
            "book.json carries title, ordered chapters, ordered sections, and "
            "paragraph text. Word remains responsible for presentation. "
            "Author, publisher, ISBN, copyright, preface, dedication, "
            "biography, and acknowledgements are explicitly absent."
        ),
        "secrets_included": False,
    }


__all__ = ["assess_word_readiness"]
