"""Even/odd headers, chapter first-page suppression, and PAGE footers."""

from __future__ import annotations

from typing import Any, Mapping

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from app.word_renderer.constants import DRAFT_NOTICE, STYLE_CHAPTER_TITLE
from app.word_renderer.oxml import add_page_field, add_styleref_field, field_instructions


def unlink_headers_footers(section) -> None:
    for part in (
        section.header,
        section.footer,
        section.even_page_header,
        section.even_page_footer,
        section.first_page_header,
        section.first_page_footer,
    ):
        part.is_linked_to_previous = False


def _clear(container) -> None:
    paragraph = container.paragraphs[0] if container.paragraphs else container.add_paragraph()
    paragraph.clear()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return paragraph


def _set_run(paragraph, text: str, *, size_pt: float = 9, italic: bool = False) -> None:
    run = paragraph.add_run(text)
    run.font.name = "Georgia"
    run.font.size = Pt(size_pt)
    run.italic = italic


def apply_front_matter_headers(section, profile: Mapping[str, Any]) -> None:
    del profile
    unlink_headers_footers(section)
    _clear(section.first_page_header)
    _clear(section.first_page_footer)
    _clear(section.header)
    footer = _clear(section.footer)
    _set_run(footer, DRAFT_NOTICE, size_pt=8, italic=True)
    _clear(section.even_page_header)
    even_footer = _clear(section.even_page_footer)
    _set_run(even_footer, DRAFT_NOTICE, size_pt=8, italic=True)


def apply_body_headers(section, book_title: str, profile: Mapping[str, Any]) -> None:
    headers = profile.get("headers") or {}
    style_ref = str((headers.get("odd_page") or {}).get("style_ref") or STYLE_CHAPTER_TITLE)
    unlink_headers_footers(section)
    _clear(section.first_page_header)
    first_footer = _clear(section.first_page_footer)
    first_footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_page_field(first_footer)

    odd_header = _clear(section.header)
    add_styleref_field(odd_header, style_ref)
    odd_footer = _clear(section.footer)
    add_page_field(odd_footer)

    even_header = _clear(section.even_page_header)
    _set_run(even_header, book_title, size_pt=9)
    even_footer = _clear(section.even_page_footer)
    add_page_field(even_footer)


def inspect_headers(section) -> dict[str, Any]:
    return {
        "different_first_page": bool(section.different_first_page_header_footer),
        "first_page_header_empty": not any(iter_header_text(section.first_page_header)),
        "even_header_texts": iter_header_text(section.even_page_header),
        "odd_header_fields": field_instructions(section.header._element),
        "footer_fields": field_instructions(section.footer._element),
        "first_footer_fields": field_instructions(section.first_page_footer._element),
        "even_footer_fields": field_instructions(section.even_page_footer._element),
    }


def iter_header_text(container) -> tuple[str, ...]:
    texts: list[str] = []
    for paragraph in container.paragraphs:
        text = paragraph.text.strip()
        if text:
            texts.append(text)
    return tuple(texts)


__all__ = [
    "apply_body_headers",
    "apply_front_matter_headers",
    "inspect_headers",
    "unlink_headers_footers",
]
