"""Half-title, title page, draft notice, and Word TOC field."""

from __future__ import annotations

from typing import Any, Mapping

from app.word_renderer.constants import (
    DRAFT_NOTICE,
    STYLE_DRAFT_NOTICE,
    STYLE_HALF_TITLE,
    STYLE_TITLE_PAGE_SUBTITLE,
    STYLE_TITLE_PAGE_TITLE,
    STYLE_TOC_TITLE,
)
from app.word_renderer.mapping import PrintBook, visible_metadata
from app.word_renderer.oxml import add_toc_field, field_instructions
from app.word_renderer.profile import include_sections_in_toc


def add_front_matter(
    doc,
    book: PrintBook,
    profile: Mapping[str, Any],
    *,
    include_sections: bool | None = None,
) -> dict[str, Any]:
    metadata = visible_metadata(book)
    invented = [
        key
        for key in ("author", "publisher", "isbn", "copyright", "publication_date", "logo")
        if metadata.get(key)
    ]
    if invented:
        raise ValueError(f"refusing to invent editorial fields: {invented}")

    doc.add_paragraph(book.title, style=STYLE_HALF_TITLE)
    doc.add_page_break()
    doc.add_paragraph(book.title, style=STYLE_TITLE_PAGE_TITLE)
    subtitle_written = False
    if book.subtitle:
        doc.add_paragraph(book.subtitle, style=STYLE_TITLE_PAGE_SUBTITLE)
        subtitle_written = True
    doc.add_paragraph(DRAFT_NOTICE, style=STYLE_DRAFT_NOTICE)
    version_line = version_notice(book)
    if version_line:
        doc.add_paragraph(version_line, style=STYLE_DRAFT_NOTICE)
    doc.add_page_break()

    toc_title = str(profile.get("front_matter", {}).get("toc_page", {}).get("title") or "Contents")
    doc.add_paragraph(toc_title, style=STYLE_TOC_TITLE)
    toc_paragraph = doc.add_paragraph()
    sections = include_sections_in_toc(profile, include_sections=include_sections)
    add_toc_field(toc_paragraph, include_sections=sections)
    return {
        "half_title": book.title,
        "title_page_title": book.title,
        "subtitle_written": subtitle_written,
        "subtitle": book.subtitle or None,
        "draft_notice": DRAFT_NOTICE,
        "version_notice": version_line,
        "invented_fields": invented,
        "toc_include_sections": sections,
        "toc_fields": field_instructions(toc_paragraph._element),
    }


def version_notice(book: PrintBook) -> str | None:
    version = str(book.version or "").strip()
    if not version:
        return None
    return f"Version {version}"


def inspect_front_matter(doc) -> dict[str, Any]:
    texts = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
    styles = [paragraph.style.name for paragraph in doc.paragraphs if paragraph.text.strip()]
    fields = field_instructions(doc.element)
    return {
        "paragraphs": texts,
        "styles": styles,
        "toc_fields": tuple(item for item in fields if item.startswith("TOC")),
        "has_half_title": STYLE_HALF_TITLE in styles,
        "has_title_page": STYLE_TITLE_PAGE_TITLE in styles,
        "has_draft_notice": DRAFT_NOTICE in texts,
        "has_author_line": any(style == "Author" for style in styles),
    }


__all__ = ["add_front_matter", "inspect_front_matter", "version_notice"]
