"""Fail-closed 4B.2.32 guards. Offline only. Never overwrite print-review-v1."""

from __future__ import annotations

from pathlib import Path

from app.book_print_review_canonical_4b229.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B229_SCOPE,
)
from app.book_print_review_pagination_fix_4b232.constants import (
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
from app.book_print_review_pagination_fix_4b232.paths import is_v1_publication_path
from app.book_print_review_render_4b231.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B231_SCOPE,
)
from app.word_print_profile_4b230.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B230_SCOPE,
)


class BookPrintReviewPaginationFix4232Error(RuntimeError):
    """Offline interchapter pagination correction rejected."""


def validate_authorization_scope(scope: str | None) -> str:
    text = str(scope or "").strip()
    if text == CONSUMED_4B229_SCOPE:
        raise BookPrintReviewPaginationFix4232Error(
            "The 4B.2.29 book-constitution authorization cannot correct pagination."
        )
    if text == CONSUMED_4B230_SCOPE:
        raise BookPrintReviewPaginationFix4232Error(
            "The 4B.2.30 print-profile authorization cannot generate DOCX/PDF."
        )
    if text == CONSUMED_4B231_SCOPE:
        raise BookPrintReviewPaginationFix4232Error(
            "The 4B.2.31 render authorization cannot overwrite or replace v1."
        )
    if text != AUTHORIZATION_SCOPE:
        raise BookPrintReviewPaginationFix4232Error(
            "authorization scope does not match the 4B.2.32 pagination-fix phase"
        )
    return text


def assert_offline_only() -> None:
    if AUTHORIZED_TERRA_CALLS or AUTHORIZED_OPENAI_CALLS or AUTHORIZED_ANTHROPIC_CALLS:
        raise BookPrintReviewPaginationFix4232Error("provider calls are not authorized")
    if AUTHORIZED_SONNET_CALLS:
        raise BookPrintReviewPaginationFix4232Error("Sonnet calls are not authorized")
    if REAL_CHAPTER_GENERATION_AUTHORIZED:
        raise BookPrintReviewPaginationFix4232Error("chapter generation is not authorized")
    if COVER_GENERATION_AUTHORIZED:
        raise BookPrintReviewPaginationFix4232Error("cover generation is not authorized")
    if VISUAL_DIRECTION_AUTHORIZED:
        raise BookPrintReviewPaginationFix4232Error("visual direction is not authorized")
    if FINAL_PUBLICATION_AUTHORIZED:
        raise BookPrintReviewPaginationFix4232Error("final publication is not authorized")
    if BOOK_JSON_MUTATION_AUTHORIZED:
        raise BookPrintReviewPaginationFix4232Error("book.json mutation is not authorized")


def assert_not_v1_target(path: Path) -> None:
    if is_v1_publication_path(path):
        raise BookPrintReviewPaginationFix4232Error(
            f"refusing to write into print-review-v1: {path}. STOP."
        )


def assert_publication_target_allowed(path: Path, *, allow_official: bool) -> None:
    assert_not_v1_target(path)
    if not allow_official:
        from app.book_print_review_pagination_fix_4b232.paths import publication_dir, repo_root

        official = publication_dir(root=repo_root()).resolve()
        resolved = Path(path).resolve()
        if resolved == official or official in resolved.parents or resolved.parent == official:
            raise BookPrintReviewPaginationFix4232Error(
                "refusing to publish test artifacts into the official v1.1 directory"
            )


def reject_real_execution(token: str) -> None:
    raise BookPrintReviewPaginationFix4232Error(
        f"{token} is rejected. This phase is offline pagination correction only."
    )


__all__ = [
    "BookPrintReviewPaginationFix4232Error",
    "assert_not_v1_target",
    "assert_offline_only",
    "assert_publication_target_allowed",
    "reject_real_execution",
    "validate_authorization_scope",
]
