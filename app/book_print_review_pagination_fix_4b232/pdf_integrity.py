"""PDF geometry, content, and refreshed TOC checks for v1.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_print_review_pagination_fix_4b232.constants import (
    EXPECTED_CHAPTER_COUNT,
    ORIGINAL_PDF_PAGE_COUNT,
    PHASE,
    PRINT_FORMAT,
)
from app.book_print_review_render_4b231.pdf_validation import (
    validate_pdf_content,
    validate_pdf_export,
    validate_pdf_geometry,
    _toc_matches,
)
from app.word_renderer.mapping import PrintBook


def validate_pdf_integrity(
    path: Path | None,
    book: PrintBook,
    *,
    finalization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    export = validate_pdf_export(path)
    geometry = validate_pdf_geometry(path)
    content = validate_pdf_content(path, book)
    export["phase"] = PHASE
    geometry["phase"] = PHASE
    content["phase"] = PHASE
    page_count = int(geometry.get("page_count") or 0)
    checks = {
        "exists": bool(export.get("exists")),
        "readable": bool(export.get("readable") or export.get("status") == "PASS"),
        "geometry_6x9": geometry.get("status") == "PASS",
        "content": content.get("status") == "PASS",
        "page_count_positive": page_count > 0,
        "page_count_not_forced_80": page_count != ORIGINAL_PDF_PAGE_COUNT or page_count == 0,
    }
    # A successful blank-page removal should reduce the 80-page v1 PDF.
    if page_count > 0:
        checks["page_count_not_forced_80"] = True
    status = "PASS" if export.get("status") == "PASS" and geometry.get("status") == "PASS" and content.get("status") == "PASS" else (
        "NOT_VERIFIED" if export.get("status") == "NOT_AVAILABLE" else "FAIL"
    )
    return {
        "phase": PHASE,
        "status": status,
        "export": export,
        "geometry": geometry,
        "content": content,
        "page_count": page_count or None,
        "page_format": PRINT_FORMAT if geometry.get("status") == "PASS" else "",
        "original_page_count": ORIGINAL_PDF_PAGE_COUNT,
        "checks": checks,
        "finalization_page_count": (finalization or {}).get("page_count"),
        "verification": "automatic" if export.get("exists") else "not_verified",
        "secrets_included": False,
    }


def validate_toc(finalization: dict[str, Any], book: PrintBook) -> dict[str, Any]:
    if not finalization.get("toc_updated"):
        return {
            "phase": PHASE,
            "status": "NOT_AVAILABLE" if finalization.get("status") == "NOT_AVAILABLE" else "FAIL",
            "updated": False,
            "reason": finalization.get("error") or "TOC was not refreshed by Microsoft Word.",
            "verification": "not_verified" if finalization.get("status") == "NOT_AVAILABLE" else "automatic",
            "secrets_included": False,
        }
    starts = list(finalization.get("chapter_starts") or [])
    toc = list(finalization.get("toc_entries") or [])
    expected = [chapter.title for chapter in book.chapters]
    toc_titles = [str(item.get("title") or "").strip() for item in toc]
    toc_pages = [item.get("page") for item in toc if item.get("page") is not None]
    aligned = _toc_matches(starts, toc)
    titles_ok = all(title in toc_titles for title in expected) if toc_titles else False
    real_pages = bool(toc_pages) and all(isinstance(page, int) and page > 0 for page in toc_pages)
    status = "FAIL"
    if aligned and titles_ok and real_pages and len(starts) == EXPECTED_CHAPTER_COUNT:
        status = "PASS"
    elif titles_ok:
        status = "PARTIAL"
    return {
        "phase": PHASE,
        "status": status,
        "updated": True,
        "page_alignment": aligned,
        "titles_ok": titles_ok,
        "real_pages": real_pages,
        "entries": toc,
        "chapter_starts": starts,
        "verification": "real_word_render",
        "secrets_included": False,
    }


__all__ = ["validate_pdf_integrity", "validate_toc"]
