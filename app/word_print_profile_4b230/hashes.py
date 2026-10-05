"""Read-only hashes. STOP if book.json or chapter sources change."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_print_review_canonical_4b229.hashes import (
    file_sha256,
    snapshot as review_snapshot,
    source_snapshots_match,
)
from app.word_print_profile_4b230.constants import EXPECTED_BOOK_SHA256, PHASE
from app.word_print_profile_4b230.guard import WordPrintProfile4230Error
from app.word_print_profile_4b230.paths import production_book_path


def snapshot(*, root: Path | None = None) -> dict[str, Any]:
    snap = review_snapshot(root=root)
    book = file_sha256(production_book_path(root=root))
    snap["phase"] = PHASE
    snap["book_json"] = book
    snap["book_json_match_expected"] = (
        bool(book.get("exists")) and book.get("sha256") == EXPECTED_BOOK_SHA256
    )
    return snap


def hashes_match(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return (
        source_snapshots_match(before, after)
        and before.get("book_json") == after.get("book_json")
        and bool(after.get("book_json_match_expected"))
    )


def assert_book_hash(snap: dict[str, Any]) -> None:
    book = snap.get("book_json") or {}
    if book.get("sha256") != EXPECTED_BOOK_SHA256:
        raise WordPrintProfile4230Error(
            f"book.json SHA-256 mismatch: {book.get('sha256')}. STOP."
        )


def assert_sources_unchanged(before: dict[str, Any], after: dict[str, Any]) -> None:
    if not hashes_match(before, after):
        raise WordPrintProfile4230Error(
            "book.json or a chapter source changed during 4B.2.30. STOP."
        )


__all__ = [
    "assert_book_hash",
    "assert_sources_unchanged",
    "file_sha256",
    "hashes_match",
    "snapshot",
]
