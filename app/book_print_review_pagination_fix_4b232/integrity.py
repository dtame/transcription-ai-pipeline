"""DOCX integrity plus chapter-break policy checks."""

from __future__ import annotations

from typing import Any

from docx.enum.section import WD_SECTION

from app.book_print_review_pagination_fix_4b232.constants import (
    EXPECTED_FRONT_MATTER_PAGE_BREAKS,
    PHASE,
)
from app.book_print_review_render_4b231.integrity import (
    open_document,
    validate_docx_integrity as base_validate_docx_integrity,
)
from app.word_renderer.document import inspect_document
from app.word_renderer.headers import inspect_headers
from app.word_renderer.oxml import page_number_start
from app.word_renderer.profile import chapter_start_type_name, front_matter_section_start_name


def validate_docx_integrity(
    data: bytes,
    book,
    profile: dict[str, Any],
) -> dict[str, Any]:
    result = base_validate_docx_integrity(data, book, profile)
    result["phase"] = PHASE
    doc = open_document(data)
    inspection = inspect_document(doc, profile)
    new_page = str(WD_SECTION.NEW_PAGE)
    odd_page = str(WD_SECTION.ODD_PAGE)
    body_starts = list(inspection.get("body_start_types") or [])
    interchapter = list(inspection.get("interchapter_start_types") or [])
    headers = inspect_headers(doc.sections[1]) if len(doc.sections) > 1 else {}
    policy_checks = {
        "chapter_start_policy": chapter_start_type_name(profile) in {"next_page", "new_page"},
        "front_matter_keep_existing": front_matter_section_start_name(profile)
        == "keep_existing",
        "front_matter_not_odd_page": str(doc.sections[0].start_type) != odd_page,
        "body_starts_next_page": bool(body_starts) and all(item == new_page for item in body_starts),
        "no_interchapter_odd_page": not any(item == odd_page for item in interchapter),
        "no_double_page_break": int(inspection.get("explicit_page_breaks") or 0)
        == EXPECTED_FRONT_MATTER_PAGE_BREAKS,
        "headers_present": bool(headers.get("even_header_texts"))
        and bool(headers.get("odd_header_fields")),
        "footers_present": bool(headers.get("footer_fields")),
        "first_page_header_hidden": bool(headers.get("first_page_header_empty")),
        "pagination_restart_once": page_number_start(doc.sections[1]) == 1
        if len(doc.sections) > 1
        else False,
        "pagination_continuous": all(
            page_number_start(section) is None for section in doc.sections[2:]
        ),
    }
    checks = dict(result.get("checks") or {})
    checks.update(policy_checks)
    result["checks"] = checks
    result["chapter_start_inspection"] = inspection
    result["header_inspection"] = {
        "even_header_texts": headers.get("even_header_texts"),
        "odd_header_fields": headers.get("odd_header_fields"),
        "footer_fields": headers.get("footer_fields"),
        "first_page_header_empty": headers.get("first_page_header_empty"),
    }
    result["status"] = "PASS" if all(checks.values()) else "FAIL"
    return result


__all__ = ["validate_docx_integrity"]
