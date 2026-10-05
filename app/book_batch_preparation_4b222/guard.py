"""Fail-closed guards. This phase cannot call a provider or generate."""

from __future__ import annotations

from app.book_batch_preparation_4b222.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIAL_VOICE_POLICY_ACTIVATED,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    CONSUMED_4B217_SCOPE,
    CONSUMED_4B218_SCOPE,
    CONSUMED_4B219_SCOPE,
    CONSUMED_4B220_SCOPE,
    CONSUMED_4B221_SCOPE,
    COVERAGE_CONTROL_ACTIVATED,
    EDITORIAL_POLICY_ACTIVATED,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    FAITHFUL_PROMPT_ACTIVATED,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PUBLICATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    SEMANTIC_GATE_202_ENABLED,
)


class BookBatchPreparation4222Error(RuntimeError):
    """Offline batch-preparation request rejected."""


def validate_authorization_scope(scope: str | None) -> str:
    text = str(scope or "").strip()
    consumed = {
        CONSUMED_4B217_SCOPE: "The 4B.2.17 Sonnet authorization has been consumed and cannot be reused.",
        CONSUMED_4B218_SCOPE: "The 4B.2.18 offline voice authorization cannot authorize this phase.",
        CONSUMED_4B219_SCOPE: "The 4B.2.19 editorial-acceptance authorization cannot authorize generation.",
        CONSUMED_4B220_SCOPE: "The 4B.2.20 scale-up preparation authorization cannot authorize generation.",
        CONSUMED_4B221_SCOPE: "The 4B.2.21 CH018 one-shot authorization has been consumed and cannot be reused.",
    }
    if text in consumed:
        raise BookBatchPreparation4222Error(consumed[text])
    if text != AUTHORIZATION_SCOPE:
        raise BookBatchPreparation4222Error(
            "authorization scope does not match the 4B.2.22 offline preparation phase"
        )
    return text


def assert_offline_only() -> None:
    if AUTHORIZED_TERRA_CALLS or AUTHORIZED_OPENAI_CALLS or AUTHORIZED_ANTHROPIC_CALLS:
        raise BookBatchPreparation4222Error("provider calls are not authorized")
    if AUTHORIZED_SONNET_CALLS:
        raise BookBatchPreparation4222Error("Sonnet calls are not authorized")
    if REAL_CHAPTER_GENERATION_AUTHORIZED:
        raise BookBatchPreparation4222Error("chapter generation is not authorized")
    if PUBLICATION_AUTHORIZED:
        raise BookBatchPreparation4222Error("publication is not authorized")
    if PRODUCTION_PIPELINE_HOOK or PRODUCTION_CACHE_ACCEPTANCE:
        raise BookBatchPreparation4222Error("production pipeline and cache stay closed")
    if FAITHFUL_PROMPT_ACTIVATED or FAITHFUL_PROMPT_1_1_ACTIVATED:
        raise BookBatchPreparation4222Error("candidate prompts stay inactive")
    if EDITORIAL_POLICY_ACTIVATED or AUTHORIAL_VOICE_POLICY_ACTIVATED:
        raise BookBatchPreparation4222Error("candidate policies stay inactive")
    if COVERAGE_CONTROL_ACTIVATED:
        raise BookBatchPreparation4222Error("coverage control stays inactive")
    if SEMANTIC_GATE_202_ENABLED:
        raise BookBatchPreparation4222Error("semantic gate 2.0.2 stays inactive")


def reject_real_execution(token: str) -> None:
    raise BookBatchPreparation4222Error(
        f"{token} is rejected. This phase records CH018 acceptance and "
        "prepares the remaining 17 chapters. It does not call a provider."
    )


def reject_unknown_cost() -> None:
    raise BookBatchPreparation4222Error(
        "COST_MAXIMUM_UNKNOWN. Unknown cost is never treated as zero."
    )


def reject_cap_exceeded() -> None:
    raise BookBatchPreparation4222Error(
        "COST_MAXIMUM_EXCEEDS_CAP. The theoretical maximum exceeds the authorized cap."
    )


def reject_missing_authorization() -> None:
    raise BookBatchPreparation4222Error(
        "No remaining-chapter batch authorization exists. STOP."
    )


def reject_automatic_paid_retry() -> None:
    raise BookBatchPreparation4222Error(
        "Automatic paid retry is forbidden. A human decision is required."
    )


def reject_prompt_fallback(requested: str, fallback: str) -> None:
    raise BookBatchPreparation4222Error(
        f"Prompt {requested!r} is unavailable. Fallback to {fallback!r} is forbidden."
    )


def reject_consumed_lock() -> None:
    raise BookBatchPreparation4222Error(
        "Call lock already consumed. Authorization is not reusable. NO RETRY."
    )


def reject_uncertain_lock() -> None:
    raise BookBatchPreparation4222Error(
        "Call lock is UNCERTAIN. Do not repeat the paid call automatically."
    )


def reject_multi_chapter_call() -> None:
    raise BookBatchPreparation4222Error(
        "A provider call may contain exactly one chapter. Multi-chapter calls are forbidden."
    )


__all__ = [
    "BookBatchPreparation4222Error",
    "assert_offline_only",
    "reject_automatic_paid_retry",
    "reject_cap_exceeded",
    "reject_consumed_lock",
    "reject_missing_authorization",
    "reject_multi_chapter_call",
    "reject_prompt_fallback",
    "reject_real_execution",
    "reject_uncertain_lock",
    "reject_unknown_cost",
    "validate_authorization_scope",
]
