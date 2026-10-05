"""Inventory of the existing Word stack. Read-only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.docx_export_service import (
    _FONT_CONFIGS_DOCX,
    _PAGE_MARGINS_DOCX,
    _PAGE_SIZES_DOCX,
)
from app.publication_theme import _THEMES
from app.word_renderer.constants import BODY_FONT_NAME, BODY_FONT_SOURCE

_ROOT = Path(__file__).resolve().parents[2]


def renderer_inventory() -> dict[str, Any]:
    classic = _FONT_CONFIGS_DOCX.get("classic") or {}
    book_theme = _THEMES.get("BOOK") or {}
    return {
        "exists_and_works": {
            "python_docx": True,
            "publication_docx_engine": "app/publication_docx_engine.py",
            "docx_export_service": "app/docx_export_service.py",
            "publication_theme": "app/publication_theme.py",
            "page_number_field_helper": True,
            "optional_cover_image_insertion": True,
            "six_by_nine_page_size_already_defined": "six_by_nine" in _PAGE_SIZES_DOCX,
            "georgia_already_classic_body_font": classic.get("body") == BODY_FONT_NAME,
            "book_json_data_readiness_4b229": "app/book_print_review_canonical_4b229/word.py",
            "book_models": "app/book_generation/models.py",
        },
        "must_configure": [
            "6x9 section geometry as the print-review default",
            "mirror margins and additional gutter",
            "BookBody / BookBodyFirst / BookChapterTitle / BookSectionTitle",
            "Word TOC field instead of a static heading list",
            "even/odd headers with STYLEREF",
            "front-matter half-title and title page without invented metadata",
            "chapter odd-page section starts",
            "reusable declarative print profile",
        ],
        "must_correct_for_print_book": [
            "Existing engines treat Markdown as the source; book.json is now canonical.",
            "Existing TOC helpers write static titles, not a Word TOC field.",
            "Existing headers repeat one title on every page.",
            "publication_docx_engine invents author/date fallbacks.",
            "publication_theme BOOK mode is LETTER with equal 72pt margins.",
            "Cover spacing currently uses empty paragraphs.",
        ],
        "actually_missing": [
            "app/word_renderer print profile and Book* styles",
            "Word Finalizer that refreshes fields in Microsoft Word",
            "mirror-margin + gutter application",
            "STYLEREF running chapter headers",
            "book.json to print-document mapping that suppresses technical IDs",
        ],
        "reserved_for_4b231": [
            "Generate and publish the full book DOCX",
            "Refresh TOC and PAGE fields",
            "Export the print PDF",
            "Validate rendered pagination",
            "Insert a real illustrated cover once it exists",
        ],
        "reused": {
            "dependency": "python-docx already in requirements.txt",
            "page_size_key": "six_by_nine already defined as 6x9 inches",
            "body_font": classic.get("body"),
            "body_font_source": BODY_FONT_SOURCE,
            "field_pattern": "w:fldChar / w:instrText from docx_export_service",
            "architecture": "section + style + oxml helpers, not a new file format",
        },
        "not_replaced": [
            "app/publication_docx_engine.py remains the workshop Markdown engine",
            "app/docx_export_service.py remains the legacy Markdown export",
            "book.json remains the semantic manuscript and still forbids layout fields",
        ],
        "existing_defaults": {
            "publication_theme_book_page_size": book_theme.get("page_size"),
            "publication_theme_book_margins_pt": {
                "top": book_theme.get("top_margin"),
                "left": book_theme.get("left_margin"),
            },
            "six_by_nine_legacy_equal_margin_inches": _PAGE_MARGINS_DOCX.get("six_by_nine"),
            "legacy_gutter": None,
            "legacy_mirror_margins": False,
        },
        "word_finalizer_exists": False,
        "editorial_finalizer_is_not_word": "app/editorial_finalizer.py finalizes manuscripts, not DOCX",
        "paths": {
            "repo": str(_ROOT).replace("\\", "/"),
            "profile": "app/word_renderer/profiles/print_review_6x9_v1.json",
        },
        "new_dependency_added": False,
    }


__all__ = ["renderer_inventory"]
