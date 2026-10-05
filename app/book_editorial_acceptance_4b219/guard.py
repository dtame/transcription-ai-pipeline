"""Fail-closed guards. This phase cannot call a provider or publish."""

from __future__ import annotations

from app.book_editorial_acceptance_4b219.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIAL_VOICE_POLICY_ACTIVATED,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    CONSUMED_4B217_SCOPE,
    CONSUMED_4B218_SCOPE,
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


class BookEditorialAcceptance4219Error(RuntimeError):
    """Offline editorial-acceptance phase rejected the request."""


def validate_authorization_scope(scope: str | None) -> str:
    text = str(scope or "").strip()
    if text == CONSUMED_4B217_SCOPE:
        raise BookEditorialAcceptance4219Error(
            "The 4B.2.17 Sonnet authorization has been consumed and cannot be reused."
        )
    if text == CONSUMED_4B218_SCOPE:
        raise BookEditorialAcceptance4219Error(
            "The 4B.2.18 offline voice authorization cannot authorize this phase."
        )
    if text != AUTHORIZATION_SCOPE:
        raise BookEditorialAcceptance4219Error(
            "authorization scope does not match the 4B.2.19 offline acceptance phase"
        )
    return text


def assert_offline_only() -> None:
    if AUTHORIZED_TERRA_CALLS or AUTHORIZED_OPENAI_CALLS or AUTHORIZED_ANTHROPIC_CALLS:
        raise BookEditorialAcceptance4219Error("provider calls are not authorized")
    if AUTHORIZED_SONNET_CALLS:
        raise BookEditorialAcceptance4219Error("Sonnet calls are not authorized")
    if REAL_CHAPTER_GENERATION_AUTHORIZED:
        raise BookEditorialAcceptance4219Error("chapter generation is not authorized")
    if PUBLICATION_AUTHORIZED:
        raise BookEditorialAcceptance4219Error("publication is not authorized")
    if PRODUCTION_PIPELINE_HOOK or PRODUCTION_CACHE_ACCEPTANCE:
        raise BookEditorialAcceptance4219Error("production pipeline and cache stay closed")
    if FAITHFUL_PROMPT_ACTIVATED or FAITHFUL_PROMPT_1_1_ACTIVATED:
        raise BookEditorialAcceptance4219Error("candidate prompts stay inactive")
    if EDITORIAL_POLICY_ACTIVATED or AUTHORIAL_VOICE_POLICY_ACTIVATED:
        raise BookEditorialAcceptance4219Error("candidate policies stay inactive")
    if COVERAGE_CONTROL_ACTIVATED:
        raise BookEditorialAcceptance4219Error("coverage control stays inactive")
    if SEMANTIC_GATE_202_ENABLED:
        raise BookEditorialAcceptance4219Error("semantic gate 2.0.2 stays inactive")


def reject_real_execution(token: str) -> None:
    raise BookEditorialAcceptance4219Error(
        f"{token} is rejected. This phase does not call a provider "
        "and does not regenerate CH012."
    )


__all__ = [
    "BookEditorialAcceptance4219Error",
    "assert_offline_only",
    "reject_real_execution",
    "validate_authorization_scope",
]
