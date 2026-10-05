"""Reusable Word print-renderer constants. Book-agnostic."""

from __future__ import annotations

PROFILE_NAME = "print_review_6x9_v1"
PROFILE_FILENAME = "print_review_6x9_v1.json"

STYLE_BODY = "BookBody"
STYLE_BODY_FIRST = "BookBodyFirst"
STYLE_CHAPTER_TITLE = "BookChapterTitle"
STYLE_CHAPTER_NUMBER = "BookChapterNumber"
STYLE_SECTION_TITLE = "BookSectionTitle"
STYLE_HALF_TITLE = "BookHalfTitle"
STYLE_TITLE_PAGE_TITLE = "BookTitlePageTitle"
STYLE_TITLE_PAGE_SUBTITLE = "BookTitlePageSubtitle"
STYLE_DRAFT_NOTICE = "BookDraftNotice"
STYLE_TOC_TITLE = "BookTocTitle"
STYLE_RUNNING_HEADER = "BookRunningHeader"
STYLE_PAGE_NUMBER = "BookPageNumber"

DRAFT_NOTICE = "Print Review Draft — Not for Publication"

PAGE_WIDTH_INCHES = 6.0
PAGE_HEIGHT_INCHES = 9.0
PAGE_WIDTH_CM = 15.24
PAGE_HEIGHT_CM = 22.86

INSIDE_MARGIN_INCHES = 0.85
OUTSIDE_MARGIN_INCHES = 0.65
TOP_MARGIN_INCHES = 0.75
BOTTOM_MARGIN_INCHES = 0.75
GUTTER_INCHES = 0.15
TOTAL_BINDING_EDGE_INCHES = INSIDE_MARGIN_INCHES + GUTTER_INCHES

BODY_FONT_NAME = "Georgia"
BODY_FONT_SOURCE = (
    "Retained from app/docx_export_service.py classic publication body font. "
    "Georgia is a Windows system face already used by this project. "
    "The renderer does not embed a font file."
)

TECHNICAL_ID_PATTERNS = (
    r"\bCH\d{3}\b",
    r"\bSEC\d{3}\b",
    r"\bIDEA\d{3,}\b",
    r"\bSRC\d{6}\b",
    r"\bP\d{6}\b",
)

TECHNICAL_STATUS_TOKENS = (
    "HUMAN_EDITORIALLY_ACCEPTED",
    "GENERATED_STRUCTURALLY_VALID",
    "HUMAN_REVIEW_PENDING",
    "DRAFT_FOR_PRINT_REVIEW",
)

ABSENT_EDITORIAL_FIELDS = (
    "author",
    "publisher",
    "isbn",
    "copyright",
    "preface",
    "dedication",
    "biography",
    "acknowledgements",
)

__all__ = [
    "ABSENT_EDITORIAL_FIELDS",
    "BODY_FONT_NAME",
    "DRAFT_NOTICE",
    "GUTTER_INCHES",
    "INSIDE_MARGIN_INCHES",
    "OUTSIDE_MARGIN_INCHES",
    "PAGE_HEIGHT_INCHES",
    "PAGE_WIDTH_INCHES",
    "PROFILE_NAME",
    "STYLE_BODY",
    "STYLE_BODY_FIRST",
    "STYLE_CHAPTER_TITLE",
    "STYLE_SECTION_TITLE",
    "TECHNICAL_ID_PATTERNS",
    "TECHNICAL_STATUS_TOKENS",
]
