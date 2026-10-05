"""Read-only hashes. STOP if book.json, chapter sources, or v1 files change."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_print_review_pagination_fix_4b232.constants import EXPECTED_BOOK_SHA256, PHASE
from app.book_print_review_pagination_fix_4b232.guard import BookPrintReviewPaginationFix4232Error
from app.book_print_review_pagination_fix_4b232.paths import (
    official_v1_docx_path,
    official_v1_pdf_path,
    production_book_path,
)
from app.book_print_review_render_4b231.hashes import file_sha256
from app.word_print_profile_4b230.hashes import (
    hashes_match as profile_hashes_match,
    snapshot as profile_snapshot,
)


def snapshot(*, root: Path | None = None) -> dict[str, Any]:
    del root
    snap = profile_snapshot(root=None)
    book = file_sha256(production_book_path())
    snap["phase"] = PHASE
    snap["book_json"] = book
    snap["book_json_match_expected"] = (
        bool(book.get("exists")) and book.get("sha256") == EXPECTED_BOOK_SHA256
    )
    return snap


def snapshot_original_publication() -> dict[str, Any]:
    return {
        "docx": file_sha256(official_v1_docx_path()),
        "pdf": file_sha256(official_v1_pdf_path()),
    }


def hashes_match(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return profile_hashes_match(before, after)


def originals_match(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return before == after


def assert_book_hash(snap: dict[str, Any]) -> None:
    book = snap.get("book_json") or {}
    if book.get("sha256") != EXPECTED_BOOK_SHA256:
        raise BookPrintReviewPaginationFix4232Error(
            f"book.json SHA-256 mismatch: {book.get('sha256')}. STOP."
        )


def assert_sources_unchanged(before: dict[str, Any], after: dict[str, Any]) -> None:
    if not hashes_match(before, after):
        raise BookPrintReviewPaginationFix4232Error(
            "book.json or a chapter source changed during 4B.2.32. STOP."
        )


def assert_originals_preserved(before: dict[str, Any], after: dict[str, Any]) -> None:
    if not originals_match(before, after):
        raise BookPrintReviewPaginationFix4232Error(
            "print-review-v1 files changed during 4B.2.32. STOP."
        )


__all__ = [
    "assert_book_hash",
    "assert_originals_preserved",
    "assert_sources_unchanged",
    "file_sha256",
    "hashes_match",
    "originals_match",
    "snapshot",
    "snapshot_original_publication",
]
