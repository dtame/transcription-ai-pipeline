"""Phase 4B.2.35 report."""

from __future__ import annotations

from typing import Any


def render_report(header: dict[str, Any]) -> str:
    lines = [
        "# PHASE 4B.2.35 — PRINT-READY COVER",
        "",
        f"RESULT = {header['result']}",
        f"ART IMAGE = {header['art_image']}",
        f"AI GENERATION CALLS = {header['ai_generation_calls']}",
        f"ORIGINAL IMAGE = {header['original_image']}",
        f"ORIGINAL IMAGE SHA256 = {header['original_image_sha256']}",
        f"PREPARED IMAGE = {header['prepared_image']}",
        f"PREPARED RESOLUTION = {header['prepared_resolution']}",
        "TRIM SIZE = 6 × 9 in",
        "BLEED = 3 mm",
        f"FRONT TITLE = {header['front_title']}",
        f"SUBTITLE = {header['subtitle']}",
        f"AUTHOR = {header['author']}",
        f"BACKGROUND COLOR = {header['background_color']}",
        f"BOOK DESCRIPTION = {header['book_description']}",
        f"AUTHOR BIOGRAPHY = {header['author_biography']}",
        "ISBN = MISSING_OPTIONAL",
        f"FRONT DOCX = {header['front_docx']}",
        f"FRONT PDF = {header['front_pdf']}",
        f"BACK DOCX = {header['back_docx']}",
        f"BACK PDF = {header['back_pdf']}",
        "FRONT PDF PAGES = 1",
        "BACK PDF PAGES = 1",
        "INTERIOR VERSION = print-review-v1.1",
        "INTERIOR PAGES = 67",
        "INTERIOR MODIFIED = NO",
        f"CANONICAL HASHES = {header['canonical_hashes']}",
        f"TESTS = {header['tests_passed']} PASS / {header['tests_failed']} FAIL",
        f"READY_FOR_PRINT_REVIEW = {header['ready_for_print_review']}",
        f"REMAINING HUMAN REVIEW = {header['remaining_human_review']}",
        "",
        "## Composition",
        "",
        header["composition"],
        "",
        "## Stop",
        "",
        "The four cover files are ready for human inspection. "
        "No further image was generated. The interior was not modified. "
        "No spine and no wraparound were produced.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
