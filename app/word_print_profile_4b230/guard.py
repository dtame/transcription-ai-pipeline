"""Fail-closed 4B.2.30 guards. Offline only. No DOCX/PDF publication."""

from __future__ import annotations

from app.book_print_review_canonical_4b229.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B229_SCOPE,
)
from app.word_print_profile_4b230.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BOOK_JSON_MUTATION_AUTHORIZED,
    COVER_GENERATION_AUTHORIZED,
    DOCX_GENERATION_AUTHORIZED,
    FINAL_PUBLICATION_AUTHORIZED,
    PDF_GENERATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    VISUAL_DIRECTION_AUTHORIZED,
)


class WordPrintProfile4230Error(RuntimeError):
    """Offline Word print-profile preparation rejected."""


def validate_authorization_scope(scope: str | None) -> str:
    text = str(scope or "").strip()
    if text == CONSUMED_4B229_SCOPE:
        raise WordPrintProfile4230Error(
            "The 4B.2.29 book-constitution authorization cannot configure Word."
        )
    if text != AUTHORIZATION_SCOPE:
        raise WordPrintProfile4230Error(
            "authorization scope does not match the 4B.2.30 Word print-profile phase"
        )
    return text


def assert_offline_only() -> None:
    if AUTHORIZED_TERRA_CALLS or AUTHORIZED_OPENAI_CALLS or AUTHORIZED_ANTHROPIC_CALLS:
        raise WordPrintProfile4230Error("provider calls are not authorized")
    if AUTHORIZED_SONNET_CALLS:
        raise WordPrintProfile4230Error("Sonnet calls are not authorized")
    if REAL_CHAPTER_GENERATION_AUTHORIZED:
        raise WordPrintProfile4230Error("chapter generation is not authorized")
    if DOCX_GENERATION_AUTHORIZED or PDF_GENERATION_AUTHORIZED:
        raise WordPrintProfile4230Error("DOCX/PDF generation is not authorized")
    if COVER_GENERATION_AUTHORIZED:
        raise WordPrintProfile4230Error("cover generation is not authorized")
    if VISUAL_DIRECTION_AUTHORIZED:
        raise WordPrintProfile4230Error("visual direction is not authorized")
    if FINAL_PUBLICATION_AUTHORIZED:
        raise WordPrintProfile4230Error("final publication is not authorized")
    if BOOK_JSON_MUTATION_AUTHORIZED:
        raise WordPrintProfile4230Error("book.json mutation is not authorized")


def reject_real_execution(token: str) -> None:
    raise WordPrintProfile4230Error(
        f"{token} is rejected. This phase prepares the Word print profile offline."
    )


__all__ = [
    "WordPrintProfile4230Error",
    "assert_offline_only",
    "reject_real_execution",
    "validate_authorization_scope",
]
