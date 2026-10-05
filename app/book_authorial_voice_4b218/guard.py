"""Fail-closed guards. This phase cannot call a provider or publish."""

from __future__ import annotations

from app.book_authorial_voice_4b218.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIAL_VOICE_POLICY_ACTIVATED,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    CONSUMED_4B217_SCOPE,
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


class BookAuthorialVoice4218Error(RuntimeError):
    """Offline voice-preservation phase rejected the request."""


def validate_authorization_scope(scope: str | None) -> str:
    text = str(scope or "").strip()
    if text == CONSUMED_4B217_SCOPE:
        raise BookAuthorialVoice4218Error(
            "The 4B.2.17 Sonnet authorization has been consumed and cannot be reused."
        )
    if text != AUTHORIZATION_SCOPE:
        raise BookAuthorialVoice4218Error(
            "authorization scope does not match the 4B.2.18 offline voice phase"
        )
    return text


def assert_offline_only() -> None:
    if AUTHORIZED_TERRA_CALLS or AUTHORIZED_OPENAI_CALLS or AUTHORIZED_ANTHROPIC_CALLS:
        raise BookAuthorialVoice4218Error("provider calls are not authorized")
    if AUTHORIZED_SONNET_CALLS:
        raise BookAuthorialVoice4218Error("Sonnet calls are not authorized")
    if REAL_CHAPTER_GENERATION_AUTHORIZED:
        raise BookAuthorialVoice4218Error("chapter generation is not authorized")
    if PUBLICATION_AUTHORIZED:
        raise BookAuthorialVoice4218Error("publication is not authorized")
    if PRODUCTION_PIPELINE_HOOK or PRODUCTION_CACHE_ACCEPTANCE:
        raise BookAuthorialVoice4218Error("production pipeline and cache stay closed")
    if FAITHFUL_PROMPT_ACTIVATED or FAITHFUL_PROMPT_1_1_ACTIVATED:
        raise BookAuthorialVoice4218Error("candidate prompts stay inactive")
    if EDITORIAL_POLICY_ACTIVATED or AUTHORIAL_VOICE_POLICY_ACTIVATED:
        raise BookAuthorialVoice4218Error("candidate policies stay inactive")
    if COVERAGE_CONTROL_ACTIVATED:
        raise BookAuthorialVoice4218Error("coverage control stays inactive")
    if SEMANTIC_GATE_202_ENABLED:
        raise BookAuthorialVoice4218Error("semantic gate 2.0.2 stays inactive")


def reject_real_execution(token: str) -> None:
    raise BookAuthorialVoice4218Error(
        f"{token} is rejected. This phase does not call a provider "
        "and does not regenerate CH012."
    )


__all__ = [
    "BookAuthorialVoice4218Error",
    "assert_offline_only",
    "reject_real_execution",
    "validate_authorization_scope",
]
