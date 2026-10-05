"""Fail-closed guards. This phase cannot call a provider or generate."""

from __future__ import annotations

from app.book_scale_up_preparation_4b220.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIAL_VOICE_POLICY_ACTIVATED,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    CONSUMED_4B217_SCOPE,
    CONSUMED_4B218_SCOPE,
    CONSUMED_4B219_SCOPE,
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


class BookScaleUpPreparation4220Error(RuntimeError):
    """Offline scale-up preparation rejected the request."""


def validate_authorization_scope(scope: str | None) -> str:
    text = str(scope or "").strip()
    if text == CONSUMED_4B217_SCOPE:
        raise BookScaleUpPreparation4220Error(
            "The 4B.2.17 Sonnet authorization has been consumed and cannot be reused."
        )
    if text == CONSUMED_4B218_SCOPE:
        raise BookScaleUpPreparation4220Error(
            "The 4B.2.18 offline voice authorization cannot authorize this phase."
        )
    if text == CONSUMED_4B219_SCOPE:
        raise BookScaleUpPreparation4220Error(
            "The 4B.2.19 editorial-acceptance authorization cannot authorize generation."
        )
    if text != AUTHORIZATION_SCOPE:
        raise BookScaleUpPreparation4220Error(
            "authorization scope does not match the 4B.2.20 offline preparation phase"
        )
    return text


def assert_offline_only() -> None:
    if AUTHORIZED_TERRA_CALLS or AUTHORIZED_OPENAI_CALLS or AUTHORIZED_ANTHROPIC_CALLS:
        raise BookScaleUpPreparation4220Error("provider calls are not authorized")
    if AUTHORIZED_SONNET_CALLS:
        raise BookScaleUpPreparation4220Error("Sonnet calls are not authorized")
    if REAL_CHAPTER_GENERATION_AUTHORIZED:
        raise BookScaleUpPreparation4220Error("chapter generation is not authorized")
    if PUBLICATION_AUTHORIZED:
        raise BookScaleUpPreparation4220Error("publication is not authorized")
    if PRODUCTION_PIPELINE_HOOK or PRODUCTION_CACHE_ACCEPTANCE:
        raise BookScaleUpPreparation4220Error("production pipeline and cache stay closed")
    if FAITHFUL_PROMPT_ACTIVATED or FAITHFUL_PROMPT_1_1_ACTIVATED:
        raise BookScaleUpPreparation4220Error("candidate prompts stay inactive")
    if EDITORIAL_POLICY_ACTIVATED or AUTHORIAL_VOICE_POLICY_ACTIVATED:
        raise BookScaleUpPreparation4220Error("candidate policies stay inactive")
    if COVERAGE_CONTROL_ACTIVATED:
        raise BookScaleUpPreparation4220Error("coverage control stays inactive")
    if SEMANTIC_GATE_202_ENABLED:
        raise BookScaleUpPreparation4220Error("semantic gate 2.0.2 stays inactive")


def reject_real_execution(token: str) -> None:
    raise BookScaleUpPreparation4220Error(
        f"{token} is rejected. This phase prepares remaining-chapter "
        "generation and does not call a provider."
    )


def reject_unknown_cost() -> None:
    raise BookScaleUpPreparation4220Error(
        "COST_MAXIMUM_UNKNOWN. Unknown cost is never treated as zero."
    )


def reject_cap_exceeded() -> None:
    raise BookScaleUpPreparation4220Error(
        "COST_MAXIMUM_EXCEEDS_CAP. The theoretical maximum exceeds the authorized cap."
    )


def reject_missing_authorization() -> None:
    raise BookScaleUpPreparation4220Error(
        "No remaining-chapter generation authorization exists. STOP."
    )


def reject_automatic_paid_retry() -> None:
    raise BookScaleUpPreparation4220Error(
        "Automatic paid retry is forbidden. A human decision is required."
    )


def reject_prompt_fallback(requested: str, fallback: str) -> None:
    raise BookScaleUpPreparation4220Error(
        f"Prompt {requested!r} is unavailable. Fallback to {fallback!r} is forbidden."
    )


__all__ = [
    "BookScaleUpPreparation4220Error",
    "assert_offline_only",
    "reject_automatic_paid_retry",
    "reject_cap_exceeded",
    "reject_missing_authorization",
    "reject_prompt_fallback",
    "reject_real_execution",
    "reject_unknown_cost",
    "validate_authorization_scope",
]
