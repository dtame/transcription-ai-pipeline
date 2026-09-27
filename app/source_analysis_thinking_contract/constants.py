"""Constantes 3B.7.7A.12 — contrat thinking Anthropic. 0 appel provider."""

from __future__ import annotations

from app.source_analysis_local_v2.constants import (
    CALL_C_FINISH,
    CALL_C_OUTPUT,
    CALL_C_PROVIDER_INPUT,
    CALL_C_THINKING_TOKENS,
    CANDIDATE_PLANNER_VERSION,
    CLEAN_SHA,
    GENERATION_C_ANTHROPIC_SHA,
    GENERATION_C_RAW_SHA,
    GRANULARITY_POLICY_VERSION,
    MAX_OUTPUT_TOKENS_FROZEN,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    PROMPT_10_SHA,
    PROMPT_11_SHA,
    PROTECTED_EVIDENCE_A11,
    SEMANTIC_TRANSPORT_VERSION_V2,
    SMALL_HTTP_RAW_SHA,
    SMALL_PLANNER_STATUS,
    SMALL_RAW_TEXT_SHA,
    SMALL_SIGNATURE,
    TARGET_JSON_LOCAL_TOKENS,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
    WINDOW_ID,
)
from app.source_analysis_output_ceiling_review.constants import (
    ADAPTIVE_HIERARCHY_STATUS,
    PRIMARY_ROOT_CAUSE,
)

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.7A.12"
MODE = "OFFLINE_ANTHROPIC_THINKING_CONTRACT_AND_READINESS"

REAL_PROVIDER_CALLS_THIS_PHASE = 0
NEW_WIN001_CALLS = 0
REAL_WINDOW_CALLS = 0
REAL_PROVIDER_CALL_AUTHORIZED = False
REAL_PROVIDER_CALL_AUTHORIZED_NEXT = False

MODEL = "claude-sonnet-5"
PROVIDER = "anthropic"

SELECTED_CONTRACT = "THINKING_DISABLED"
SELECTED_THINKING_MODE = "disabled"
SELECTED_EFFORT = None
FALLBACK_CONTRACT = "ADAPTIVE_LOW"
FALLBACK_THINKING_MODE = "adaptive"
FALLBACK_EFFORT = "low"

AUTHORIZATION_SCOPE_V2_GRAMMAR_CONFIG_CANARY_ONLY = (
    "V2_GRAMMAR_CONFIG_CANARY_ONLY"
)
AUTHORIZATION_SCOPE_SMALL_V21_V2_WIN001_ONLY = "SMALL_V21_V2_WIN001_ONLY"
GRAMMAR_CANARY_EXECUTABLE = False
SEMANTIC_WIN001_EXECUTABLE = False
GRAMMAR_CANARY_MAX_GENERATE = 1
GRAMMAR_CANARY_MAX_ATTEMPTS = 1
GRAMMAR_CANARY_MAX_OUTPUT_TOKENS = 256

CALL_C_EFFECTIVE_THINKING_MODE = "adaptive"
CALL_C_EFFECTIVE_EFFORT = "high"
CALL_C_THINKING_EXPLICIT = False
CALL_C_EFFORT_EXPLICIT = False
CALL_C_ROOT_CAUSE = (
    "Sonnet 5 adaptive thinking was implicitly enabled by model default, "
    "at default high effort, sharing max_tokens=32000 with structured "
    "response. Observed thinking consumed 21911 tokens. This left "
    "insufficient room for complete JSON."
)

OFFICIAL_VERIFICATION_DATE = "2026-09-26"
OFFICIAL_SOURCE_NOTES = (
    "External verified contract facts supplied for 3B.7.7A.12 against "
    "current official Anthropic Claude Sonnet 5 documentation. "
    "No live documentation fetch was performed in this phase."
)
OFFICIAL_SOURCE_URLS = (
    "https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking",
    "https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking",
)

CONTRACT_ARTIFACT = "source_analysis_anthropic_sonnet5_thinking_contract.json"
CALL_C_ARTIFACT = "source_analysis_call_c_effective_thinking_contract.json"
OPTIONS_ARTIFACT = "source_analysis_v2_thinking_mode_options.json"
DECISION_ARTIFACT = "source_analysis_v2_thinking_mode_decision.json"
PAYLOAD_ARTIFACT = "source_analysis_v2_anthropic_payload_contract.json"
READINESS_ARTIFACT = "source_analysis_v2_grammar_canary_readiness.json"
REPORT_NAME = (
    "PHASE_3B77A12_ANTHROPIC_THINKING_CONTRACT_VERIFICATION_REAL_CALL_READINESS_REPORT.md"
)

NEXT_PHASE = "3B.7.7A.13_V2_TINY_GRAMMAR_THINKING_CONFIG_CANARY"
NEXT_PHASE_LABEL = (
    "3B.7.7A.13 — V2 TINY GRAMMAR + THINKING-CONFIG CANARY — "
    "ONE tiny synthetic Anthropic call maximum. NO pastoral transcript. "
    "NO WIN001. max_attempts=1. NO retry. Mandatory STOP."
)
NEXT_ACTION = "HUMAN REVIEW"

PROTECTED_EVIDENCE_A12 = PROTECTED_EVIDENCE_A11 + (
    "audit/PHASE_3B77A11_OUTPUT_BOUNDED_LOCAL_SEMANTIC_EXTRACTION_IMPLEMENTATION_REPORT.md",
    "audit/source_analysis_semantic_transport_v2_design.json",
    "audit/source_analysis_local_v2_output_budget.json",
    "audit/source_analysis_anthropic_thinking_budget_capability.json",
    "audit/source_analysis_local_v2_subdivision_policy.json",
    "audit/source_analysis_local_v2_fake_ai_e2e.json",
    "audit/source_analysis_local_v2_canonical_compatibility.json",
)

__all__ = [
    "ADAPTIVE_HIERARCHY_STATUS",
    "AUTHORIZATION_SCOPE_SMALL_V21_V2_WIN001_ONLY",
    "AUTHORIZATION_SCOPE_V2_GRAMMAR_CONFIG_CANARY_ONLY",
    "CALL_C_ARTIFACT",
    "CALL_C_EFFECTIVE_EFFORT",
    "CALL_C_EFFECTIVE_THINKING_MODE",
    "CALL_C_EFFORT_EXPLICIT",
    "CALL_C_FINISH",
    "CALL_C_OUTPUT",
    "CALL_C_PROVIDER_INPUT",
    "CALL_C_ROOT_CAUSE",
    "CALL_C_THINKING_EXPLICIT",
    "CALL_C_THINKING_TOKENS",
    "CANDIDATE_PLANNER_VERSION",
    "CLEAN_SHA",
    "CONTRACT_ARTIFACT",
    "DECISION_ARTIFACT",
    "FALLBACK_CONTRACT",
    "FALLBACK_EFFORT",
    "FALLBACK_THINKING_MODE",
    "GENERATION_C_ANTHROPIC_SHA",
    "GENERATION_C_RAW_SHA",
    "GRAMMAR_CANARY_EXECUTABLE",
    "GRAMMAR_CANARY_MAX_ATTEMPTS",
    "GRAMMAR_CANARY_MAX_GENERATE",
    "GRAMMAR_CANARY_MAX_OUTPUT_TOKENS",
    "GRANULARITY_POLICY_VERSION",
    "MAX_OUTPUT_TOKENS_FROZEN",
    "MODE",
    "MODEL",
    "NEW_WIN001_CALLS",
    "NEXT_ACTION",
    "NEXT_PHASE",
    "NEXT_PHASE_LABEL",
    "OFFICIAL_SOURCE_NOTES",
    "OFFICIAL_SOURCE_URLS",
    "OFFICIAL_VERIFICATION_DATE",
    "OPTIONS_ARTIFACT",
    "PAYLOAD_ARTIFACT",
    "PHASE",
    "PRIMARY_ROOT_CAUSE",
    "PRODUCTION_PLANNER_VERSION",
    "PROJECT_NAME",
    "PROMPT_10_SHA",
    "PROMPT_11_SHA",
    "PROTECTED_EVIDENCE_A12",
    "PROVIDER",
    "READINESS_ARTIFACT",
    "REAL_PROVIDER_CALL_AUTHORIZED",
    "REAL_PROVIDER_CALL_AUTHORIZED_NEXT",
    "REAL_PROVIDER_CALLS_THIS_PHASE",
    "REAL_WINDOW_CALLS",
    "REPORT_NAME",
    "SCHEMA_VERSION",
    "SELECTED_CONTRACT",
    "SELECTED_EFFORT",
    "SELECTED_THINKING_MODE",
    "SEMANTIC_TRANSPORT_VERSION_V2",
    "SEMANTIC_WIN001_EXECUTABLE",
    "SMALL_HTTP_RAW_SHA",
    "SMALL_PLANNER_STATUS",
    "SMALL_RAW_TEXT_SHA",
    "SMALL_SIGNATURE",
    "TARGET_JSON_LOCAL_TOKENS",
    "WINDOW_ANALYSIS_PROMPT_VERSION_V12",
    "WINDOW_ID",
]
