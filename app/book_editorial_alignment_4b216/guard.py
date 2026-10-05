"""Fail-closed guards. This phase cannot call a provider or publish."""

from __future__ import annotations

from app.book_editorial_alignment_4b216.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    COVERAGE_CONTROL_ACTIVATED,
    EDITORIAL_POLICY_ACTIVATED,
    FAITHFUL_PROMPT_ACTIVATED,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PUBLICATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    SEMANTIC_GATE_202_ENABLED,
)


class BookEditorialAlignment4216Error(RuntimeError):
    """Offline alignment phase rejected the request."""


def validate_authorization_scope(scope: str | None) -> None:
    if scope != AUTHORIZATION_SCOPE:
        raise BookEditorialAlignment4216Error(
            "authorization scope does not match the 4B.2.16 offline alignment phase"
        )


def assert_offline_only() -> None:
    if AUTHORIZED_TERRA_CALLS or AUTHORIZED_OPENAI_CALLS or AUTHORIZED_ANTHROPIC_CALLS:
        raise BookEditorialAlignment4216Error("provider calls are not authorized")
    if AUTHORIZED_SONNET_CALLS:
        raise BookEditorialAlignment4216Error("Sonnet calls are not authorized")
    if REAL_CHAPTER_GENERATION_AUTHORIZED:
        raise BookEditorialAlignment4216Error("chapter generation is not authorized")
    if PUBLICATION_AUTHORIZED:
        raise BookEditorialAlignment4216Error("publication is not authorized")
    if PRODUCTION_PIPELINE_HOOK or PRODUCTION_CACHE_ACCEPTANCE:
        raise BookEditorialAlignment4216Error("production pipeline and cache stay closed")
    if FAITHFUL_PROMPT_ACTIVATED or EDITORIAL_POLICY_ACTIVATED:
        raise BookEditorialAlignment4216Error("candidate policy and prompt stay inactive")
    if COVERAGE_CONTROL_ACTIVATED:
        raise BookEditorialAlignment4216Error("coverage control stays inactive")
    if SEMANTIC_GATE_202_ENABLED:
        raise BookEditorialAlignment4216Error("semantic gate 2.0.2 stays inactive")


def reject_real_execution(token: str) -> None:
    raise BookEditorialAlignment4216Error(
        f"{token} is rejected. This phase does not call Terra or Sonnet."
    )


__all__ = [
    "BookEditorialAlignment4216Error",
    "assert_offline_only",
    "reject_real_execution",
    "validate_authorization_scope",
]
