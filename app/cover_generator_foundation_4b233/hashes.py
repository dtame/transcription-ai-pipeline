"""Read-only hashes for the book, the interior, and the Word profile."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_print_review_render_4b231.hashes import file_sha256
from app.cover_generator_foundation_4b233.constants import (
    EXPECTED_BOOK_SHA256,
    EXPECTED_INTERIOR_DOCX_SHA256,
    EXPECTED_INTERIOR_PDF_SHA256,
    PHASE,
)
from app.cover_generator_foundation_4b233.guard import CoverGeneratorFoundation4233Error
from app.cover_generator_foundation_4b233.paths import (
    interior_docx_path,
    interior_pdf_path,
    production_book_path,
    word_profile_path,
)
from app.word_print_profile_4b230.hashes import (
    hashes_match as profile_hashes_match,
    snapshot as profile_snapshot,
)


def snapshot(*, root: Path | None = None) -> dict[str, Any]:
    snap = profile_snapshot(root=root if root is not None else None)
    book = file_sha256(production_book_path(root=root))
    docx = file_sha256(interior_docx_path(root=root))
    pdf = file_sha256(interior_pdf_path(root=root))
    profile = file_sha256(word_profile_path())
    snap["phase"] = PHASE
    snap["book_json"] = book
    snap["book_json_match_expected"] = (
        bool(book.get("exists")) and book.get("sha256") == EXPECTED_BOOK_SHA256
    )
    snap["interior_docx"] = docx
    snap["interior_pdf"] = pdf
    snap["word_profile"] = profile
    snap["interior_match_expected"] = (
        docx.get("sha256") == EXPECTED_INTERIOR_DOCX_SHA256
        and pdf.get("sha256") == EXPECTED_INTERIOR_PDF_SHA256
    )
    return snap


def hashes_match(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return (
        profile_hashes_match(before, after)
        and before.get("interior_docx") == after.get("interior_docx")
        and before.get("interior_pdf") == after.get("interior_pdf")
        and before.get("word_profile") == after.get("word_profile")
        and bool(after.get("book_json_match_expected"))
        and bool(after.get("interior_match_expected"))
    )


def assert_protected_hashes(snap: dict[str, Any]) -> None:
    book = snap.get("book_json") or {}
    if book.get("sha256") != EXPECTED_BOOK_SHA256:
        raise CoverGeneratorFoundation4233Error(
            f"book.json SHA-256 mismatch: {book.get('sha256')}. STOP."
        )
    docx = (snap.get("interior_docx") or {}).get("sha256")
    pdf = (snap.get("interior_pdf") or {}).get("sha256")
    if docx != EXPECTED_INTERIOR_DOCX_SHA256 or pdf != EXPECTED_INTERIOR_PDF_SHA256:
        raise CoverGeneratorFoundation4233Error(
            "interior DOCX or PDF hash mismatch. STOP."
        )


def assert_sources_unchanged(before: dict[str, Any], after: dict[str, Any]) -> None:
    if not hashes_match(before, after):
        raise CoverGeneratorFoundation4233Error(
            "book.json, a chapter source, the interior, or the Word profile changed. STOP."
        )


__all__ = [
    "assert_protected_hashes",
    "assert_sources_unchanged",
    "file_sha256",
    "hashes_match",
    "snapshot",
]
