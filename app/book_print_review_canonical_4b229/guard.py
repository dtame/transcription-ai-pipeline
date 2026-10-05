"""Fail-closed 4B.2.29 guards. Offline only. Provisional book.json only."""

from __future__ import annotations

from app.book_full_manuscript_review_4b228.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B228_SCOPE,
)
from app.book_full_generation_preparation_4b226.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B226_SCOPE,
)
from app.book_generation_4b227.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B227_SCOPE,
)
from app.book_print_review_canonical_4b229.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    COMMERCIAL_PUBLICATION_AUTHORIZED,
    DOCX_GENERATION_AUTHORIZED,
    FINAL_PUBLICATION_AUTHORIZED,
    PDF_GENERATION_AUTHORIZED,
    PRODUCTION_CACHE_ACCEPTANCE,
    PUBLIC_PUBLICATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    VISUAL_DIRECTION_AUTHORIZED,
)


class BookPrintReviewCanonical4229Error(RuntimeError):
    """Offline print-review book constitution rejected."""


def validate_authorization_scope(scope: str | None) -> str:
    text = str(scope or "").strip()
    consumed = {
        CONSUMED_4B226_SCOPE: "The 4B.2.26 preparation authorization cannot authorize publication.",
        CONSUMED_4B227_SCOPE: "The 4B.2.27 remaining-13 authorization has been consumed.",
        CONSUMED_4B228_SCOPE: (
            "The 4B.2.28 manuscript-review authorization cannot authorize book.json."
        ),
    }
    if text in consumed:
        raise BookPrintReviewCanonical4229Error(consumed[text])
    if text != AUTHORIZATION_SCOPE:
        raise BookPrintReviewCanonical4229Error(
            "authorization scope does not match the 4B.2.29 print-review "
            "canonical constitution phase"
        )
    return text


def assert_offline_only() -> None:
    if AUTHORIZED_TERRA_CALLS or AUTHORIZED_OPENAI_CALLS or AUTHORIZED_ANTHROPIC_CALLS:
        raise BookPrintReviewCanonical4229Error("provider calls are not authorized")
    if AUTHORIZED_SONNET_CALLS:
        raise BookPrintReviewCanonical4229Error("Sonnet calls are not authorized")
    if REAL_CHAPTER_GENERATION_AUTHORIZED:
        raise BookPrintReviewCanonical4229Error("chapter generation is not authorized")
    if DOCX_GENERATION_AUTHORIZED or PDF_GENERATION_AUTHORIZED:
        raise BookPrintReviewCanonical4229Error("DOCX/PDF generation is not authorized")
    if VISUAL_DIRECTION_AUTHORIZED:
        raise BookPrintReviewCanonical4229Error("visual direction is not authorized")
    if FINAL_PUBLICATION_AUTHORIZED or COMMERCIAL_PUBLICATION_AUTHORIZED:
        raise BookPrintReviewCanonical4229Error("final/commercial publication is not authorized")
    if PUBLIC_PUBLICATION_AUTHORIZED:
        raise BookPrintReviewCanonical4229Error("public publication is not authorized")
    if PRODUCTION_CACHE_ACCEPTANCE:
        raise BookPrintReviewCanonical4229Error("production cache stays closed")


def reject_real_execution(token: str) -> None:
    raise BookPrintReviewCanonical4229Error(
        f"{token} is rejected. This phase consolidates existing chapters offline. "
        "It does not call a provider and does not rewrite prose."
    )


__all__ = [
    "BookPrintReviewCanonical4229Error",
    "assert_offline_only",
    "reject_real_execution",
    "validate_authorization_scope",
]
