"""
Canary grammar/config V2 — préparé, fail-closed, non exécutable.

Aucun engine.generate. Aucun contenu pastoral. STOP obligatoire.
"""

from __future__ import annotations

from typing import Any

from app.source_analysis_thinking_contract.constants import (
    AUTHORIZATION_SCOPE_SMALL_V21_V2_WIN001_ONLY,
    AUTHORIZATION_SCOPE_V2_GRAMMAR_CONFIG_CANARY_ONLY,
    GRAMMAR_CANARY_EXECUTABLE,
    GRAMMAR_CANARY_MAX_ATTEMPTS,
    GRAMMAR_CANARY_MAX_GENERATE,
    GRAMMAR_CANARY_MAX_OUTPUT_TOKENS,
    MODE,
    PHASE,
    REAL_PROVIDER_CALL_AUTHORIZED,
    SCHEMA_VERSION,
    SELECTED_CONTRACT,
    SELECTED_EFFORT,
    SELECTED_THINKING_MODE,
    SEMANTIC_TRANSPORT_VERSION_V2,
    SEMANTIC_WIN001_EXECUTABLE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
)


class GrammarCanaryAuthorizationError(RuntimeError):
    """Levée avant tout appel provider."""


def grammar_canary_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "authorization_scope": AUTHORIZATION_SCOPE_V2_GRAMMAR_CONFIG_CANARY_ONLY,
        "executable_this_phase": GRAMMAR_CANARY_EXECUTABLE,
        "real_provider_call_authorized": REAL_PROVIDER_CALL_AUTHORIZED,
        "purpose": (
            "Answer only: does Anthropic accept the V2 schema + selected "
            "thinking/effort payload?"
        ),
        "not_purpose": [
            "analyze real pastoral WIN001",
            "measure semantic quality",
            "start WIN002-WIN007",
        ],
        "input": "tiny synthetic — no pastoral transcript content",
        "max_engine_generate": GRAMMAR_CANARY_MAX_GENERATE,
        "max_attempts": GRAMMAR_CANARY_MAX_ATTEMPTS,
        "retry": False,
        "semantic_window": False,
        "mandatory_stop": True,
        "auto_continue_to_win001": False,
        "selected_thinking_contract": SELECTED_CONTRACT,
        "selected_thinking_mode": SELECTED_THINKING_MODE,
        "selected_effort": SELECTED_EFFORT,
        "transport": SEMANTIC_TRANSPORT_VERSION_V2,
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V12,
        "max_output_tokens_canary": GRAMMAR_CANARY_MAX_OUTPUT_TOKENS,
        "v2_server_grammar_verified": False,
    }


def semantic_win001_scope() -> dict[str, Any]:
    return {
        "authorization_scope": AUTHORIZATION_SCOPE_SMALL_V21_V2_WIN001_ONLY,
        "executable_this_phase": SEMANTIC_WIN001_EXECUTABLE,
        "enabled_because_a12_passed": False,
        "requires_separate_human_authorization_after_grammar_canary_review": True,
        "auto_start_after_grammar": False,
    }


def run_grammar_canary(
    *,
    authorization_scope: str | None = None,
    execute_real: bool = False,
) -> dict[str, Any]:
    if execute_real or not GRAMMAR_CANARY_EXECUTABLE:
        raise GrammarCanaryAuthorizationError(
            "V2 grammar/config canary is prepared but not authorized. "
            "REAL PROVIDER CALL AUTHORIZED = NO."
        )
    if authorization_scope != AUTHORIZATION_SCOPE_V2_GRAMMAR_CONFIG_CANARY_ONLY:
        raise GrammarCanaryAuthorizationError(
            "Authorization scope must be V2_GRAMMAR_CONFIG_CANARY_ONLY."
        )
    if REAL_PROVIDER_CALL_AUTHORIZED:
        raise GrammarCanaryAuthorizationError(
            "Internal contradiction: real call flag is true in a freeze phase."
        )
    raise GrammarCanaryAuthorizationError("Unreachable executable path.")


def run_semantic_win001_canary(**_kwargs: Any) -> dict[str, Any]:
    raise GrammarCanaryAuthorizationError(
        "SMALL_V21_V2_WIN001_ONLY is prepared and DISABLED. "
        "Separate human authorization is required after grammar canary review."
    )


def grammar_canary_readiness() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "v2_grammar_canary_ready": True,
        "v2_grammar_canary_executed": False,
        "v2_grammar_server_verified": False,
        "semantic_win001_ready": False,
        "semantic_win001_authorized": False,
        "real_provider_call_authorized": False,
        "grammar": grammar_canary_contract(),
        "semantic_scope": semantic_win001_scope(),
        "sequence": [
            "STEP 1: tiny V2 grammar/config canary — STOP + human review",
            "STEP 2: only if grammar/config PASS, one small WIN001 V2 "
            "semantic canary — STOP + human review",
        ],
        "do_not_combine_automatically": True,
    }


__all__ = [
    "GrammarCanaryAuthorizationError",
    "grammar_canary_contract",
    "grammar_canary_readiness",
    "run_grammar_canary",
    "run_semantic_win001_canary",
    "semantic_win001_scope",
]
