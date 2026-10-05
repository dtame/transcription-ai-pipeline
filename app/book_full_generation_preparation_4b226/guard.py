"""Fail-closed 4B.2.26 guards. This phase cannot call a provider or generate."""

from __future__ import annotations

from pathlib import Path

from app.book_full_generation_preparation_4b226.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    CONSUMED_4B217_SCOPE,
    CONSUMED_4B218_SCOPE,
    CONSUMED_4B219_SCOPE,
    CONSUMED_4B220_SCOPE,
    CONSUMED_4B221_SCOPE,
    CONSUMED_4B222_SCOPE,
    CONSUMED_4B223_SCOPE,
    CONSUMED_4B224_SCOPE,
    CONSUMED_4B225_SCOPE,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    FUTURE_AUTHORIZATION_ACTIVATED,
    FUTURE_AUTHORIZATION_SCOPE,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PUBLICATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
)
from app.book_generation.writer import production_book_absent
from app.book_full_generation_preparation_4b226.constants import PROJECT_NAME


class BookFullGenerationPreparation4226Error(RuntimeError):
    """Offline full-generation preparation request rejected."""


def validate_authorization_scope(scope: str | None) -> str:
    text = str(scope or "").strip()
    consumed = {
        CONSUMED_4B217_SCOPE: "The 4B.2.17 Sonnet authorization has been consumed.",
        CONSUMED_4B218_SCOPE: "The 4B.2.18 offline voice authorization cannot authorize this phase.",
        CONSUMED_4B219_SCOPE: "The 4B.2.19 editorial-acceptance authorization cannot authorize generation.",
        CONSUMED_4B220_SCOPE: "The 4B.2.20 scale-up preparation authorization cannot authorize generation.",
        CONSUMED_4B221_SCOPE: "The 4B.2.21 CH018 one-shot authorization has been consumed.",
        CONSUMED_4B222_SCOPE: "The 4B.2.22 batch-preparation authorization cannot authorize generation.",
        CONSUMED_4B223_SCOPE: "The 4B.2.23 BATCH-01 authorization has been consumed.",
        CONSUMED_4B224_SCOPE: "The 4B.2.24 offline recovery authorization cannot authorize generation.",
        CONSUMED_4B225_SCOPE: "The 4B.2.25 CH003–CH004 resume authorization has been consumed.",
        FUTURE_AUTHORIZATION_SCOPE: (
            "BOOK_GENERATION_REMAINING_13_CHAPTERS_ONE_SHOT is a future "
            "proposal and is not activated in Phase 4B.2.26."
        ),
    }
    if text in consumed:
        raise BookFullGenerationPreparation4226Error(consumed[text])
    if text != AUTHORIZATION_SCOPE:
        raise BookFullGenerationPreparation4226Error(
            "authorization scope does not match the 4B.2.26 offline preparation phase"
        )
    return text


def assert_offline_only() -> None:
    if AUTHORIZED_TERRA_CALLS or AUTHORIZED_OPENAI_CALLS or AUTHORIZED_ANTHROPIC_CALLS:
        raise BookFullGenerationPreparation4226Error("provider calls are not authorized")
    if AUTHORIZED_SONNET_CALLS:
        raise BookFullGenerationPreparation4226Error("Sonnet calls are not authorized")
    if REAL_CHAPTER_GENERATION_AUTHORIZED:
        raise BookFullGenerationPreparation4226Error("chapter generation is not authorized")
    if PUBLICATION_AUTHORIZED:
        raise BookFullGenerationPreparation4226Error("publication is not authorized")
    if FUTURE_AUTHORIZATION_ACTIVATED:
        raise BookFullGenerationPreparation4226Error(
            "the 13-chapter authorization must stay inactive in this phase"
        )
    if PRODUCTION_PIPELINE_HOOK or PRODUCTION_CACHE_ACCEPTANCE:
        raise BookFullGenerationPreparation4226Error("production pipeline and cache stay closed")
    if FAITHFUL_PROMPT_1_1_ACTIVATED:
        raise BookFullGenerationPreparation4226Error("candidate prompt 1.1 stays inactive")


def assert_no_publication(path: Path) -> None:
    if path.is_file():
        raise BookFullGenerationPreparation4226Error(
            f"Production book.json already present at {path}. "
            "4B.2.26 must not publish and must not overwrite."
        )
    if not production_book_absent(PROJECT_NAME):
        raise BookFullGenerationPreparation4226Error("book.json must remain unpublished")


def reject_real_execution(token: str) -> None:
    raise BookFullGenerationPreparation4226Error(
        f"{token} is rejected. This phase records CH003/CH004 acceptance and "
        "prepares the remaining 13 chapters. It does not call a provider."
    )


def reject_replay() -> None:
    raise BookFullGenerationPreparation4226Error(
        "A consumed or uncertain call must never be replayed automatically."
    )


__all__ = [
    "BookFullGenerationPreparation4226Error",
    "assert_no_publication",
    "assert_offline_only",
    "reject_real_execution",
    "reject_replay",
    "validate_authorization_scope",
]
