"""PDF existence, geometry, and canonical-paragraph correspondence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_print_review_render_4b231.constants import (
    EXPECTED_CHAPTER_COUNT,
    EXPECTED_PARAGRAPH_COUNT,
    EXPECTED_SECTION_COUNT,
    PHASE,
)
from app.book_print_review_render_4b231.pdf_text import (
    extract_pdf_geometry,
    extract_pdf_text,
    fold_for_pdf,
    normalize_for_compare,
)
from app.word_renderer.constants import DRAFT_NOTICE, PAGE_HEIGHT_INCHES, PAGE_WIDTH_INCHES
from app.word_renderer.mapping import PrintBook


def validate_pdf_export(path: Path | None) -> dict[str, Any]:
    if path is None or not Path(path).is_file():
        return {
            "phase": PHASE,
            "status": "NOT_AVAILABLE",
            "exists": False,
            "bytes": 0,
            "path": "",
            "verification": "automatic",
            "secrets_included": False,
        }
    target = Path(path)
    size = target.stat().st_size
    readable = target.read_bytes()[:5] == b"%PDF-"
    return {
        "phase": PHASE,
        "status": "PASS" if size > 0 and readable else "FAIL",
        "exists": True,
        "bytes": size,
        "readable": readable,
        "path": str(target).replace("\\", "/"),
        "verification": "automatic",
        "secrets_included": False,
    }


def validate_pdf_geometry(path: Path | None) -> dict[str, Any]:
    if path is None or not Path(path).is_file():
        return {
            "phase": PHASE,
            "status": "NOT_VERIFIED",
            "reason": "PDF was not exported.",
            "verification": "not_verified",
            "secrets_included": False,
        }
    geometry = extract_pdf_geometry(Path(path))
    expected_w = PAGE_WIDTH_INCHES * 72
    expected_h = PAGE_HEIGHT_INCHES * 72
    sizes = geometry.get("page_sizes") or []
    matches = [
        abs(item["width_pt"] - expected_w) <= 1.5 and abs(item["height_pt"] - expected_h) <= 1.5
        for item in sizes
    ]
    portrait = [
        item["height_pt"] > item["width_pt"]
        for item in sizes
    ]
    page_count = int(geometry.get("page_count") or 0)
    status = "FAIL"
    if geometry.get("readable") and page_count > 0 and matches and all(matches) and all(portrait):
        status = "PASS"
    elif geometry.get("readable") and page_count > 0:
        status = "PARTIAL"
    return {
        "phase": PHASE,
        "status": status,
        "page_count": page_count,
        "expected_width_pt": expected_w,
        "expected_height_pt": expected_h,
        "page_size": "6 × 9 inches" if status == "PASS" else "see page_sizes",
        "page_sizes": sizes[:8],
        "all_6x9": bool(matches) and all(matches),
        "all_portrait": bool(portrait) and all(portrait),
        "error": geometry.get("error") or "",
        "verification": "automatic",
        "secrets_included": False,
    }


def validate_pdf_content(path: Path | None, book: PrintBook) -> dict[str, Any]:
    if path is None or not Path(path).is_file():
        return {
            "phase": PHASE,
            "status": "NOT_VERIFIED",
            "reason": "PDF was not exported.",
            "verification": "not_verified",
            "secrets_included": False,
        }
    extracted = extract_pdf_text(Path(path))
    haystack_ws = normalize_for_compare(extracted)
    haystack = fold_for_pdf(extracted)
    missing: list[dict[str, Any]] = []
    found = 0
    cursor = 0
    for index, text in enumerate(book.paragraph_texts):
        needle = fold_for_pdf(text)
        if not needle:
            continue
        position, kind = _locate_folded(haystack, needle, cursor)
        if position < 0:
            missing.append({"index": index, "preview": normalize_for_compare(text)[:80]})
            continue
        found += 1
        cursor = position + min(len(needle), 80)
    chapter_missing = [
        chapter.title
        for chapter in book.chapters
        if fold_for_pdf(chapter.title) not in haystack
    ]
    section_missing = [
        section.title
        for chapter in book.chapters
        for section in chapter.sections
        if fold_for_pdf(section.title) not in haystack
    ]
    extractor_weak = len(haystack_ws) < 200 or found == 0
    if not missing and not chapter_missing and not section_missing:
        status = "PASS"
        verification = "automatic"
    elif extractor_weak:
        status = "NOT_VERIFIED"
        verification = "not_verified"
    else:
        status = "FAIL"
        verification = "automatic"
    return {
        "phase": PHASE,
        "status": status,
        "extracted_characters": len(haystack_ws),
        "folded_characters": len(haystack),
        "paragraphs_found": found,
        "paragraphs_expected": EXPECTED_PARAGRAPH_COUNT,
        "chapters_found": EXPECTED_CHAPTER_COUNT - len(chapter_missing),
        "sections_found": EXPECTED_SECTION_COUNT - len(section_missing),
        "missing_paragraphs": missing[:20],
        "missing_paragraph_count": len(missing),
        "missing_chapters": chapter_missing,
        "missing_sections": section_missing[:20],
        "draft_notice_present": fold_for_pdf(DRAFT_NOTICE) in haystack,
        "extractor": "stdlib_pdf_stream",
        "match_rule": "folded_alphanumerics_or_head_tail",
        "verification": verification,
        "secrets_included": False,
    }


def validate_pagination(
    *,
    finalization: dict[str, Any],
    book: PrintBook,
) -> dict[str, Any]:
    if finalization.get("status") == "NOT_AVAILABLE" or not finalization.get("executed"):
        return {
            "phase": PHASE,
            "status": "NOT_VERIFIED",
            "odd_page_chapter_starts": "NOT_VERIFIED",
            "pagination_stable": "NOT_VERIFIED",
            "reason": "Microsoft Word did not finalize the document.",
            "verification": "not_verified",
            "human_required": True,
            "secrets_included": False,
        }
    starts = list(finalization.get("chapter_starts") or [])
    toc = list(finalization.get("toc_entries") or [])
    expected_titles = [chapter.title for chapter in book.chapters]
    start_titles = [item.get("title") for item in starts]
    odd = [bool(item.get("odd")) for item in starts]
    toc_pages = [item.get("page") for item in toc if item.get("page") is not None]
    toc_titles = [str(item.get("title") or "").strip() for item in toc]
    toc_matches_starts = _toc_matches(starts, toc)
    checks = {
        "chapter_count": start_titles == expected_titles,
        "all_odd": bool(odd) and all(odd),
        "stable": bool(finalization.get("pagination_stable")),
        "toc_has_real_pages": bool(toc_pages) and all(isinstance(page, int) and page > 0 for page in toc_pages),
        "toc_titles": all(title in toc_titles for title in expected_titles) if toc_titles else False,
        "toc_page_alignment": toc_matches_starts,
    }
    if not starts:
        status = "NOT_VERIFIED"
        odd_label = "NOT_VERIFIED"
    elif all(checks.values()):
        status = "PASS"
        odd_label = "PASS"
    elif checks["all_odd"] and checks["chapter_count"]:
        status = "PARTIAL"
        odd_label = "PASS"
    else:
        status = "FAIL"
        odd_label = "PASS" if checks["all_odd"] else "FAIL"
    blanks = []
    for current, nxt in zip(starts, starts[1:], strict=False):
        page = int(current.get("page") or 0)
        following = int(nxt.get("page") or 0)
        if following > page + 1 and following % 2 == 1:
            blanks.append(following - 1)
    return {
        "phase": PHASE,
        "status": status,
        "odd_page_chapter_starts": odd_label,
        "pagination_stable": "YES" if checks["stable"] else "NO",
        "page_count": int(finalization.get("page_count") or 0),
        "chapter_starts": starts,
        "inferred_intentional_blank_pages": blanks,
        "toc_entries": toc,
        "checks": checks,
        "verification": "real_word_render",
        "human_required": status != "PASS",
        "secrets_included": False,
    }


def validate_toc(finalization: dict[str, Any], book: PrintBook) -> dict[str, Any]:
    pagination = validate_pagination(finalization=finalization, book=book)
    if not finalization.get("toc_updated"):
        return {
            "phase": PHASE,
            "status": "NOT_AVAILABLE" if finalization.get("status") == "NOT_AVAILABLE" else "FAIL",
            "updated": False,
            "reason": finalization.get("error") or "TOC was not refreshed by Microsoft Word.",
            "verification": "not_verified" if finalization.get("status") == "NOT_AVAILABLE" else "automatic",
            "human_required": True,
            "secrets_included": False,
        }
    aligned = bool(pagination.get("checks", {}).get("toc_page_alignment"))
    titles_ok = bool(pagination.get("checks", {}).get("toc_titles"))
    real_pages = bool(pagination.get("checks", {}).get("toc_has_real_pages"))
    status = "FAIL"
    if aligned and titles_ok and real_pages:
        status = "PASS"
    elif titles_ok:
        status = "PARTIAL"
    return {
        "phase": PHASE,
        "status": status,
        "updated": True,
        "entries": list(finalization.get("toc_entries") or []),
        "page_alignment": aligned,
        "verification": "real_word_render",
        "human_required": not aligned,
        "secrets_included": False,
    }


def visual_inspection_report(
    *,
    pdf_path: Path | None,
    pagination: dict[str, Any],
    pdf_content: dict[str, Any],
) -> dict[str, Any]:
    automated = {
        "first_page": "NOT_PERFORMED",
        "title_page": "NOT_PERFORMED",
        "table_of_contents": "NOT_PERFORMED",
        "first_chapter": "NOT_PERFORMED",
        "middle_chapter": "NOT_PERFORMED",
        "last_chapter": "NOT_PERFORMED",
        "section_breaks": "NOT_PERFORMED",
        "possible_blank_pages": "NOT_PERFORMED",
    }
    notes = [
        "No raster visual inspection of rendered pages was performed.",
        "Do not treat this report as a successful visual sign-off.",
    ]
    if pagination.get("verification") == "real_word_render" and pagination.get("chapter_starts"):
        automated["first_chapter"] = "PAGE_NUMBER_FROM_WORD"
        automated["last_chapter"] = "PAGE_NUMBER_FROM_WORD"
        automated["middle_chapter"] = "PAGE_NUMBER_FROM_WORD"
        notes.append("Chapter start pages were read from Microsoft Word, not from a screenshot.")
    if pdf_path is not None and pdf_content.get("status") == "PASS":
        notes.append("PDF text extraction found the canonical paragraphs; that is not a visual inspection.")
    return {
        "phase": PHASE,
        "status": "NOT_PERFORMED",
        "targets": automated,
        "inferred_blank_pages": pagination.get("inferred_intentional_blank_pages") or [],
        "notes": notes,
        "human_required": True,
        "verification": "not_verified",
        "secrets_included": False,
    }


def _locate_folded(haystack: str, needle: str, cursor: int) -> tuple[int, str]:
    if not needle:
        return cursor, "empty"
    position = haystack.find(needle, cursor)
    if position >= 0:
        return position, "exact_fold"
    position = haystack.find(needle)
    if position >= 0:
        return position, "exact_fold_reordered"
    if len(needle) < 48:
        return -1, "missing"
    head = needle[:80]
    tail = needle[-40:]
    start = haystack.find(head, cursor)
    if start < 0:
        start = haystack.find(head)
    if start < 0:
        return -1, "missing"
    end = haystack.find(tail, start)
    if end < 0:
        return -1, "missing"
    return start, "head_tail"


def _toc_matches(starts: list[dict[str, Any]], toc: list[dict[str, Any]]) -> bool:
    by_title = {
        str(item.get("title") or "").strip(): item.get("page")
        for item in toc
        if item.get("page") is not None
    }
    if not starts or not by_title:
        return False

    def _aligned(key: str) -> bool:
        return all(by_title.get(str(item.get("title") or "").strip()) == item.get(key) for item in starts)

    return _aligned("page") or _aligned("page_adjusted")


__all__ = [
    "validate_pagination",
    "validate_pdf_content",
    "validate_pdf_export",
    "validate_pdf_geometry",
    "validate_toc",
    "visual_inspection_report",
]
