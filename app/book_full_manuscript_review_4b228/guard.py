"""Fail-closed 4B.2.28 guards. This phase cannot call a provider or rewrite."""

from __future__ import annotations

import json
from pathlib import Path

from app.book_full_manuscript_review_4b228.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BOOK_JSON_PUBLICATION,
    CONSUMED_4B217_SCOPE,
    CONSUMED_4B218_SCOPE,
    CONSUMED_4B219_SCOPE,
    CONSUMED_4B221_SCOPE,
    CONSUMED_4B222_SCOPE,
    CONSUMED_4B223_SCOPE,
    CONSUMED_4B224_SCOPE,
    CONSUMED_4B225_SCOPE,
    CONSUMED_4B226_SCOPE,
    CONSUMED_4B227_SCOPE,
    DOCX_GENERATION_AUTHORIZED,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    PDF_GENERATION_AUTHORIZED,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PROJECT_NAME,
    PUBLICATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    VISUAL_DIRECTION_AUTHORIZED,
)
from app.book_generation.writer import production_book_absent


class BookFullManuscriptReview4228Error(RuntimeError):
    """Offline manuscript consolidation request rejected."""


def _is_later_print_review_draft(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    return (
        payload.get("editorial_status") == "DRAFT_FOR_PRINT_REVIEW"
        and payload.get("document_version") == "print-review-v1"
        and payload.get("phase") == "4B.2.29"
    )


def validate_authorization_scope(scope: str | None) -> str:
    text = str(scope or "").strip()
    consumed = {
        CONSUMED_4B217_SCOPE: "The 4B.2.17 Sonnet authorization has been consumed.",
        CONSUMED_4B218_SCOPE: "The 4B.2.18 offline voice authorization cannot authorize this phase.",
        CONSUMED_4B219_SCOPE: "The 4B.2.19 editorial-acceptance authorization cannot authorize generation.",
        CONSUMED_4B221_SCOPE: "The 4B.2.21 CH018 one-shot authorization has been consumed.",
        CONSUMED_4B222_SCOPE: "The 4B.2.22 batch-preparation authorization cannot authorize generation.",
        CONSUMED_4B223_SCOPE: "The 4B.2.23 BATCH-01 authorization has been consumed.",
        CONSUMED_4B224_SCOPE: "The 4B.2.24 offline recovery authorization cannot authorize generation.",
        CONSUMED_4B225_SCOPE: "The 4B.2.25 CH003–CH004 resume authorization has been consumed.",
        CONSUMED_4B226_SCOPE: "The 4B.2.26 preparation authorization cannot authorize generation.",
        CONSUMED_4B227_SCOPE: (
            "The 4B.2.27 remaining-13 authorization has been consumed and "
            "cannot authorize a new generation or a rewrite."
        ),
    }
    if text in consumed:
        raise BookFullManuscriptReview4228Error(consumed[text])
    if text != AUTHORIZATION_SCOPE:
        raise BookFullManuscriptReview4228Error(
            "authorization scope does not match the 4B.2.28 offline consolidation phase"
        )
    return text


def assert_offline_only() -> None:
    if AUTHORIZED_TERRA_CALLS or AUTHORIZED_OPENAI_CALLS or AUTHORIZED_ANTHROPIC_CALLS:
        raise BookFullManuscriptReview4228Error("provider calls are not authorized")
    if AUTHORIZED_SONNET_CALLS:
        raise BookFullManuscriptReview4228Error("Sonnet calls are not authorized")
    if REAL_CHAPTER_GENERATION_AUTHORIZED:
        raise BookFullManuscriptReview4228Error("chapter generation is not authorized")
    if PUBLICATION_AUTHORIZED or BOOK_JSON_PUBLICATION:
        raise BookFullManuscriptReview4228Error("publication is not authorized")
    if DOCX_GENERATION_AUTHORIZED or PDF_GENERATION_AUTHORIZED:
        raise BookFullManuscriptReview4228Error("DOCX/PDF generation is not authorized")
    if VISUAL_DIRECTION_AUTHORIZED:
        raise BookFullManuscriptReview4228Error("visual direction is not authorized")
    if PRODUCTION_PIPELINE_HOOK or PRODUCTION_CACHE_ACCEPTANCE:
        raise BookFullManuscriptReview4228Error("production pipeline and cache stay closed")
    if FAITHFUL_PROMPT_1_1_ACTIVATED:
        raise BookFullManuscriptReview4228Error("candidate prompt 1.1 stays inactive")


def assert_no_publication(path: Path) -> None:
    if _is_later_print_review_draft(path):
        return
    if path.is_file():
        raise BookFullManuscriptReview4228Error(
            f"Production book.json already present at {path}. "
            "4B.2.28 must not publish and must not overwrite."
        )
    if not production_book_absent(PROJECT_NAME):
        raise BookFullManuscriptReview4228Error("book.json must remain unpublished")


def reject_real_execution(token: str) -> None:
    raise BookFullManuscriptReview4228Error(
        f"{token} is rejected. This phase assembles existing chapters offline. "
        "It does not call a provider and does not rewrite prose."
    )


__all__ = [
    "BookFullManuscriptReview4228Error",
    "assert_no_publication",
    "assert_offline_only",
    "reject_real_execution",
    "validate_authorization_scope",
    "_is_later_print_review_draft",
]
