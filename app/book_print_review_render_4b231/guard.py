"""Fail-closed 4B.2.31 guards. Offline only. Print-review publication only."""

from __future__ import annotations

from pathlib import Path

from app.book_print_review_canonical_4b229.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B229_SCOPE,
)
from app.word_print_profile_4b230.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B230_SCOPE,
)
from app.book_print_review_render_4b231.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BOOK_JSON_MUTATION_AUTHORIZED,
    COVER_GENERATION_AUTHORIZED,
    FINAL_PUBLICATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    VISUAL_DIRECTION_AUTHORIZED,
)
from app.book_print_review_render_4b231.paths import is_official_publication_path


class BookPrintReviewRender4231Error(RuntimeError):
    """Offline print-review DOCX/PDF generation rejected."""


def validate_authorization_scope(scope: str | None) -> str:
    text = str(scope or "").strip()
    if text == CONSUMED_4B229_SCOPE:
        raise BookPrintReviewRender4231Error(
            "The 4B.2.29 book-constitution authorization cannot generate DOCX/PDF."
        )
    if text == CONSUMED_4B230_SCOPE:
        raise BookPrintReviewRender4231Error(
            "The 4B.2.30 print-profile authorization cannot generate DOCX/PDF."
        )
    if text != AUTHORIZATION_SCOPE:
        raise BookPrintReviewRender4231Error(
            "authorization scope does not match the 4B.2.31 print-review render phase"
        )
    return text


def assert_offline_only() -> None:
    if AUTHORIZED_TERRA_CALLS or AUTHORIZED_OPENAI_CALLS or AUTHORIZED_ANTHROPIC_CALLS:
        raise BookPrintReviewRender4231Error("provider calls are not authorized")
    if AUTHORIZED_SONNET_CALLS:
        raise BookPrintReviewRender4231Error("Sonnet calls are not authorized")
    if REAL_CHAPTER_GENERATION_AUTHORIZED:
        raise BookPrintReviewRender4231Error("chapter generation is not authorized")
    if COVER_GENERATION_AUTHORIZED:
        raise BookPrintReviewRender4231Error("cover generation is not authorized")
    if VISUAL_DIRECTION_AUTHORIZED:
        raise BookPrintReviewRender4231Error("visual direction is not authorized")
    if FINAL_PUBLICATION_AUTHORIZED:
        raise BookPrintReviewRender4231Error("final publication is not authorized")
    if BOOK_JSON_MUTATION_AUTHORIZED:
        raise BookPrintReviewRender4231Error("book.json mutation is not authorized")


def assert_publication_target_allowed(path: Path, *, allow_official: bool) -> None:
    if is_official_publication_path(path) and not allow_official:
        raise BookPrintReviewRender4231Error(
            "refusing to publish test or unofficial artifacts into the "
            "official print-review directory"
        )


def reject_real_execution(token: str) -> None:
    raise BookPrintReviewRender4231Error(
        f"{token} is rejected. This phase is offline print-review rendering only."
    )


__all__ = [
    "BookPrintReviewRender4231Error",
    "assert_offline_only",
    "assert_publication_target_allowed",
    "reject_real_execution",
    "validate_authorization_scope",
]
