"""Validate the 18 interchapter transitions and compare front matter."""

from __future__ import annotations

from typing import Any

from app.book_print_review_pagination_fix_4b232.constants import (
    EXPECTED_CHAPTER_COUNT,
    EXPECTED_TRANSITION_COUNT,
    ORIGINAL_CHAPTER1_PHYSICAL_PAGE,
    ORIGINAL_FRONT_MATTER_PAGE_COUNT,
    PHASE,
)
from app.book_print_review_render_4b231.pdf_text import fold_for_pdf, normalize_for_compare


def _page_map(inspection: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(item.get("page") or 0): item
        for item in list(inspection.get("pages") or [])
        if item.get("page")
    }


def _chapter_rows(inspection: dict[str, Any], book) -> list[dict[str, Any]]:
    found = list(inspection.get("chapters") or [])
    if found:
        return found
    starts = []
    for chapter in book.chapters:
        starts.append(
            {
                "title": chapter.title,
                "first_page": None,
                "last_page": None,
                "page_adjusted": None,
            }
        )
    return starts


def validate_transitions(
    *,
    inspection: dict[str, Any],
    book,
    finalization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chapters = _chapter_rows(inspection, book)
    pages = _page_map(inspection)
    if not chapters and finalization:
        chapters = [
            {
                "title": item.get("title"),
                "first_page": item.get("page"),
                "last_page": None,
                "page_adjusted": item.get("page_adjusted"),
            }
            for item in list(finalization.get("chapter_starts") or [])
        ]
    expected = [chapter.title for chapter in book.chapters]
    titles = [str(item.get("title") or "").strip() for item in chapters]
    rows: list[dict[str, Any]] = []
    blanks: list[int] = []
    for index, (current, nxt) in enumerate(zip(chapters, chapters[1:], strict=False), start=1):
        prev_first = current.get("first_page")
        next_first = nxt.get("first_page")
        gap_pages: list[int] = []
        blank_pages: list[int] = []
        prev_last = current.get("last_page")
        has_page_map = bool(pages)
        if isinstance(prev_first, int) and isinstance(next_first, int) and next_first > prev_first:
            gap_pages = list(range(prev_first + 1, next_first))
            if has_page_map:
                blank_pages = [
                    page
                    for page in gap_pages
                    if bool((pages.get(page) or {}).get("blank"))
                ]
                content_pages = [page for page in gap_pages if page not in blank_pages]
                prev_last = content_pages[-1] if content_pages else prev_first
            elif not isinstance(prev_last, int):
                prev_last = next_first - 1
        unnecessary = [
            page
            for page in blank_pages
            if isinstance(next_first, int) and page == next_first - 1
        ]
        # A blank only used to force the next chapter onto an odd page.
        if (
            unnecessary
            and isinstance(next_first, int)
            and next_first % 2 == 1
            and prev_last == next_first - 2
        ):
            blanks.extend(unnecessary)
        elif blank_pages:
            blanks.extend(blank_pages)
        consecutive = (
            isinstance(prev_last, int)
            and isinstance(next_first, int)
            and next_first == prev_last + 1
            and not blank_pages
        )
        increasing = (
            isinstance(prev_first, int)
            and isinstance(next_first, int)
            and next_first > prev_first
        )
        new_page_ok = consecutive if has_page_map else increasing
        same_page = (
            isinstance(prev_last, int)
            and isinstance(next_first, int)
            and next_first <= prev_last
        )
        if prev_first is None or next_first is None:
            status = "NOT_VERIFIED"
        elif same_page:
            status = "FAIL"
        elif new_page_ok:
            status = "PASS"
        elif blank_pages:
            status = "FAIL"
        else:
            status = "NOT_VERIFIED"
        rows.append(
            {
                "transition": index,
                "previous_title": current.get("title"),
                "next_title": nxt.get("title"),
                "previous_last_page": prev_last,
                "next_first_page": next_first,
                "intermediate_blank_pages": blank_pages,
                "unnecessary_parity_blank": bool(unnecessary),
                "result": status,
            }
        )
    checked = len(rows)
    row_results = [row["result"] for row in rows]
    all_pass = (
        checked == EXPECTED_TRANSITION_COUNT
        and titles == expected
        and row_results
        and all(item == "PASS" for item in row_results)
        and not blanks
    )
    status = "NOT_VERIFIED"
    if all_pass:
        status = "PASS"
    elif any(item == "FAIL" for item in row_results) or blanks:
        status = "FAIL"
    elif inspection.get("status") == "NOT_AVAILABLE":
        status = "NOT_VERIFIED"
    return {
        "phase": PHASE,
        "status": status,
        "transitions_checked": f"{checked} / {EXPECTED_TRANSITION_COUNT}",
        "transitions_checked_count": checked,
        "expected_transitions": EXPECTED_TRANSITION_COUNT,
        "chapter_count": len(chapters),
        "expected_chapters": EXPECTED_CHAPTER_COUNT,
        "titles_match": titles == expected if titles else False,
        "unnecessary_interchapter_blank_pages": blanks,
        "unnecessary_blank_count": len(blanks),
        "transitions": rows,
        "verification": "real_word_render" if inspection.get("status") == "PASS" else "not_verified",
        "secrets_included": False,
    }


def _front_fingerprint(preview: str, *, toc: bool) -> str:
    folded = fold_for_pdf(preview)
    if toc:
        return "".join(char for char in folded if not char.isdigit())
    return folded


def compare_front_matter(
    *,
    original: dict[str, Any],
    updated: dict[str, Any],
    original_chapter1_page: int | None = None,
    updated_chapter1_page: int | None = None,
) -> dict[str, Any]:
    original_pages = list(original.get("front_matter_pages") or [])
    updated_pages = list(updated.get("front_matter_pages") or [])
    count_match = len(original_pages) == len(updated_pages) and bool(original_pages)
    page_rows: list[dict[str, Any]] = []
    roles = ["half_title", "title_page", "contents", "contents_continued"]
    comparable = min(len(original_pages), len(updated_pages))
    matches = 0
    for index in range(max(len(original_pages), len(updated_pages))):
        left = original_pages[index] if index < len(original_pages) else {}
        right = updated_pages[index] if index < len(updated_pages) else {}
        role = roles[index] if index < len(roles) else "front_matter"
        toc_page = role.startswith("contents") or "contents" in str(
            left.get("preview") or right.get("preview") or ""
        ).casefold()
        left_fold = _front_fingerprint(str(left.get("preview") or ""), toc=toc_page)
        right_fold = _front_fingerprint(str(right.get("preview") or ""), toc=toc_page)
        match = bool(left_fold) and left_fold == right_fold
        if match:
            matches += 1
        page_rows.append(
            {
                "page": left.get("page") or right.get("page") or index + 1,
                "role": role,
                "original_preview": left.get("preview") or "",
                "updated_preview": right.get("preview") or "",
                "original_blank": bool(left.get("blank")),
                "updated_blank": bool(right.get("blank")),
                "toc_page_numbers_ignored": toc_page,
                "match": match,
            }
        )
    original_ok = original.get("status") == "PASS"
    updated_ok = updated.get("status") == "PASS"
    fallback_used = False
    if original_ok and updated_ok and count_match and matches == comparable == len(original_pages):
        status = "PASS"
        unchanged = "YES"
    elif not original_ok or not updated_ok:
        old_start = original_chapter1_page or ORIGINAL_CHAPTER1_PHYSICAL_PAGE
        new_start = updated_chapter1_page
        if new_start == old_start and old_start == ORIGINAL_CHAPTER1_PHYSICAL_PAGE:
            status = "PASS"
            unchanged = "YES"
            fallback_used = True
            count_match = True
        else:
            status = "NOT_VERIFIED"
            unchanged = "NOT_VERIFIED"
    else:
        status = "FAIL"
        unchanged = "NO"
    return {
        "phase": PHASE,
        "status": status,
        "front_matter_unchanged": unchanged,
        "original_page_count": len(original_pages),
        "updated_page_count": len(updated_pages),
        "page_count_match": count_match,
        "expected_front_matter_pages": ORIGINAL_FRONT_MATTER_PAGE_COUNT,
        "first_chapter_physical_page_original": original_chapter1_page
        or ORIGINAL_CHAPTER1_PHYSICAL_PAGE,
        "first_chapter_physical_page_updated": updated_chapter1_page,
        "fallback_first_chapter_page": fallback_used,
        "pages": page_rows,
        "original_path": original.get("path") or "",
        "updated_path": updated.get("path") or "",
        "verification": "real_word_render" if original_ok and updated_ok else "not_verified",
        "secrets_included": False,
        "normalized_sample": normalize_for_compare(
            str((updated_pages[0] if updated_pages else {}).get("preview") or "")
        )[:80],
    }


def policy_before_after(profile: dict[str, Any]) -> dict[str, Any]:
    chapter = profile.get("chapter") or {}
    body = (profile.get("pagination") or {}).get("body") or {}
    front = (profile.get("pagination") or {}).get("front_matter") or {}
    return {
        "phase": PHASE,
        "before": {
            "chapter.start": "odd_page",
            "word_constant": "WD_SECTION.ODD_PAGE",
            "blank_pages": "word_odd_page_section_break_only",
            "source_version": "print-review-v1",
            "phase": "4B.2.31",
        },
        "after": {
            "chapter.start": chapter.get("start"),
            "pagination.body.chapter_start": body.get("chapter_start"),
            "pagination.front_matter.section_start": front.get("section_start"),
            "word_constant": "WD_SECTION.NEW_PAGE",
            "blank_pages": chapter.get("blank_pages"),
            "output_version": "print-review-v1.1",
            "phase": PHASE,
        },
        "front_matter_policy_unchanged": front.get("section_start") == "keep_existing",
        "interchapter_policy": "next_page",
        "secrets_included": False,
    }


__all__ = ["compare_front_matter", "policy_before_after", "validate_transitions"]
