"""Fail-closed guards. This phase cannot call a provider or generate."""

from __future__ import annotations

from app.book_ch002_offline_recovery_4b224.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_SPEND_USD,
    AUTHORIZED_TERRA_CALLS,
    BATCH02_AUTHORIZED,
    BOOK_JSON_PUBLICATION,
    CONSUMED_4B217_SCOPE,
    CONSUMED_4B218_SCOPE,
    CONSUMED_4B219_SCOPE,
    CONSUMED_4B220_SCOPE,
    CONSUMED_4B221_SCOPE,
    CONSUMED_4B222_SCOPE,
    CONSUMED_4B223_SCOPE,
    COVERAGE_CONTROL_ACTIVATED,
    EDITORIAL_POLICY_ACTIVATED,
    EDITORIAL_REWRITE_AUTHORIZED,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    FAITHFUL_PROMPT_ACTIVATED,
    LOCK_RESET_AUTHORIZED,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PUBLICATION_AUTHORIZED,
    RAW_RESPONSE_MUTATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    SEMANTIC_GATE_202_ENABLED,
)


class BookCh002OfflineRecovery4224Error(RuntimeError):
    """Offline CH002 recovery request rejected."""


def validate_authorization_scope(scope: str | None) -> str:
    text = str(scope or "").strip()
    consumed = {
        CONSUMED_4B217_SCOPE: "The 4B.2.17 Sonnet authorization has been consumed.",
        CONSUMED_4B218_SCOPE: "The 4B.2.18 offline voice authorization cannot authorize this phase.",
        CONSUMED_4B219_SCOPE: "The 4B.2.19 editorial-acceptance authorization cannot authorize generation.",
        CONSUMED_4B220_SCOPE: "The 4B.2.20 scale-up preparation authorization cannot authorize generation.",
        CONSUMED_4B221_SCOPE: "The 4B.2.21 CH018 one-shot authorization has been consumed.",
        CONSUMED_4B222_SCOPE: "The 4B.2.22 batch-preparation authorization cannot authorize generation.",
        CONSUMED_4B223_SCOPE: (
            "The 4B.2.23 BATCH-01 authorization has been consumed and cannot be reused."
        ),
    }
    if text in consumed:
        raise BookCh002OfflineRecovery4224Error(consumed[text])
    if text != AUTHORIZATION_SCOPE:
        raise BookCh002OfflineRecovery4224Error(
            "authorization scope does not match the 4B.2.24 offline recovery phase"
        )
    return text


def assert_offline_only() -> None:
    if AUTHORIZED_TERRA_CALLS or AUTHORIZED_OPENAI_CALLS or AUTHORIZED_ANTHROPIC_CALLS:
        raise BookCh002OfflineRecovery4224Error("provider calls are not authorized")
    if AUTHORIZED_SONNET_CALLS:
        raise BookCh002OfflineRecovery4224Error("Sonnet calls are not authorized")
    if AUTHORIZED_SPEND_USD:
        raise BookCh002OfflineRecovery4224Error("authorized spend must remain 0 USD")
    if REAL_CHAPTER_GENERATION_AUTHORIZED:
        raise BookCh002OfflineRecovery4224Error("chapter generation is not authorized")
    if PUBLICATION_AUTHORIZED or BOOK_JSON_PUBLICATION:
        raise BookCh002OfflineRecovery4224Error("publication is not authorized")
    if PRODUCTION_PIPELINE_HOOK or PRODUCTION_CACHE_ACCEPTANCE:
        raise BookCh002OfflineRecovery4224Error("production pipeline and cache stay closed")
    if FAITHFUL_PROMPT_ACTIVATED or FAITHFUL_PROMPT_1_1_ACTIVATED:
        raise BookCh002OfflineRecovery4224Error("candidate prompts stay inactive")
    if EDITORIAL_POLICY_ACTIVATED or COVERAGE_CONTROL_ACTIVATED:
        raise BookCh002OfflineRecovery4224Error("candidate policies stay inactive")
    if SEMANTIC_GATE_202_ENABLED:
        raise BookCh002OfflineRecovery4224Error("semantic gate 2.0.2 stays inactive")
    if EDITORIAL_REWRITE_AUTHORIZED:
        raise BookCh002OfflineRecovery4224Error("editorial rewrite is not authorized")
    if LOCK_RESET_AUTHORIZED:
        raise BookCh002OfflineRecovery4224Error("lock reset is not authorized")
    if RAW_RESPONSE_MUTATION_AUTHORIZED:
        raise BookCh002OfflineRecovery4224Error("raw provider responses are immutable")
    if BATCH02_AUTHORIZED:
        raise BookCh002OfflineRecovery4224Error("BATCH-02 is not authorized")


def reject_real_execution(token: str) -> None:
    raise BookCh002OfflineRecovery4224Error(
        f"{token} is rejected. This phase recovers CH002 offline and prepares "
        "CH001 human review. It does not call a provider."
    )


def reject_consumed_lock() -> None:
    raise BookCh002OfflineRecovery4224Error(
        "Call lock already consumed. Authorization is not reusable. NO RETRY."
    )


def reject_editorial_rewrite() -> None:
    raise BookCh002OfflineRecovery4224Error(
        "Automatic editorial rewrite is forbidden. Propose only. Human decision required."
    )


__all__ = [
    "BookCh002OfflineRecovery4224Error",
    "assert_offline_only",
    "reject_consumed_lock",
    "reject_editorial_rewrite",
    "reject_real_execution",
    "validate_authorization_scope",
]
