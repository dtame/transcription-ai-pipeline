"""Constantes 3B.7.7A.8 — readiness small WIN001. Offline only."""

from __future__ import annotations

from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_models import WINDOW_MAX_OUTPUT_TOKENS
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis_hybrid.constants import WINDOW_TRANSPORT_VERSION
from app.source_analysis_hybrid_readiness.constants import (
    AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY,
    MAX_ATTEMPTS,
    MAX_NEW_CALLS_WIN001,
)
from app.source_analysis_provider_boundary.constants import (
    CALL1_SIGNATURE,
    CALL2_SIGNATURE,
    CLEAN_SHA,
    GENERATION_C_ANTHROPIC_SHA,
    GENERATION_C_RAW_SHA,
    PROMPT_10_SHA,
    PROMPT_11_SHA,
)
from app.source_analysis_small_window_hierarchy.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_PLANNER_VERSION,
    CANDIDATE_TARGET_INPUT_TOKENS,
    EXPECTED_DURATION_SECONDS,
    EXPECTED_PRESENT_SRC,
    EXPECTED_REMOVED_SRC,
    EXPECTED_TRANSCRIPT_ID,
    EXPECTED_WORD_COUNT,
    PROTECTED_EVIDENCE as PROTECTED_EVIDENCE_A7,
)
from app.source_analysis_win001_failure_diagnosis.constants import (
    LONG_CONTEXT_THRESHOLD_PROTOCOL,
    OBSERVED_COST_USD,
    OBSERVED_LOCAL_ESTIMATE,
    OBSERVED_PROVIDER_INPUT,
)

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.7A.8"
MODE = "OFFLINE_SMALL_WINDOW_PRODUCTION_READINESS"

READINESS_ARTIFACT = "source_analysis_small_win001_readiness.json"
COST_RISK_ARTIFACT = "source_analysis_small_win001_cost_risk.json"
EXECUTION_CONTRACT_ARTIFACT = "source_analysis_small_win001_execution_contract.json"
BOUNDARY_ARTIFACT = "source_analysis_small_window_boundary_review.json"
DRY_RUN_ARTIFACT = "source_analysis_small_win001_dry_run.json"
CACHE_ARTIFACT = "source_analysis_small_window_real_cache_status.json"
REPORT_NAME = (
    "PHASE_3B77A8_SMALL_WINDOW_PRODUCTION_READINESS_STAGED_REAL_CALL_PLAN_REPORT.md"
)

PROJECT_NAME = "pastoral_retreat_v2_validation"
WINDOW_ID = "WIN001"
AUTHORIZATION_SCOPE = AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY
PLANNER_VERSION_REQUIRED = CANDIDATE_PLANNER_VERSION
PRODUCTION_PLANNER_VERSION = "window-planner-v2.0"
PROMPT_VERSION_REQUIRED = WINDOW_ANALYSIS_PROMPT_VERSION
GRANULARITY_POLICY_VERSION = POLICY_VERSION
TRANSPORT_VERSION = WINDOW_TRANSPORT_VERSION
MAX_OUTPUT = WINDOW_MAX_OUTPUT_TOKENS
HARD_MAX_LOCAL_ESTIMATE = CANDIDATE_HARD_MAX_INPUT_TOKENS
TARGET_LOCAL_ESTIMATE = CANDIDATE_TARGET_INPUT_TOKENS
LONG_CONTEXT_THRESHOLD = LONG_CONTEXT_THRESHOLD_PROTOCOL

HISTORICAL_SPEND_USD = OBSERVED_COST_USD
HISTORICAL_CALL2_COST = "UNKNOWN"
HISTORICAL_LOCAL_ESTIMATE = OBSERVED_LOCAL_ESTIMATE
HISTORICAL_PROVIDER_INPUT = OBSERVED_PROVIDER_INPUT
HISTORICAL_RATIO_LABEL = "2.155975"
HISTORICAL_CALL1_SIGNATURE = CALL1_SIGNATURE
HISTORICAL_CALL2_SIGNATURE = CALL2_SIGNATURE

EXPECTED_WINDOW_COUNT = 7
A7_WIN001_INPUT_HASH = (
    "0c656a1158d2ba2bdbd559bd06aa3f48f5e3e5a81caa26398db9c162b3ddbc18"
)
A7_EXPECTED_WINDOWS = (
    {
        "window_id": "WIN001",
        "first_present_src": "SRC000001",
        "last_present_src": "SRC001201",
        "owned_src_count": 1195,
        "word_count": 5447,
        "local_request_estimate": 23618,
    },
    {
        "window_id": "WIN002",
        "first_present_src": "SRC001202",
        "last_present_src": "SRC002416",
        "owned_src_count": 1214,
        "word_count": 5320,
        "local_request_estimate": 23624,
    },
    {
        "window_id": "WIN003",
        "first_present_src": "SRC002417",
        "last_present_src": "SRC003606",
        "owned_src_count": 1156,
        "word_count": 5716,
        "local_request_estimate": 23600,
    },
    {
        "window_id": "WIN004",
        "first_present_src": "SRC003607",
        "last_present_src": "SRC004786",
        "owned_src_count": 1180,
        "word_count": 5662,
        "local_request_estimate": 23623,
    },
    {
        "window_id": "WIN005",
        "first_present_src": "SRC004787",
        "last_present_src": "SRC006022",
        "owned_src_count": 1227,
        "word_count": 5131,
        "local_request_estimate": 23601,
    },
    {
        "window_id": "WIN006",
        "first_present_src": "SRC006023",
        "last_present_src": "SRC007206",
        "owned_src_count": 1142,
        "word_count": 5721,
        "local_request_estimate": 23602,
    },
    {
        "window_id": "WIN007",
        "first_present_src": "SRC007207",
        "last_present_src": "SRC008415",
        "owned_src_count": 1184,
        "word_count": 5316,
        "local_request_estimate": 23615,
    },
)

DRY_RUN_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_hybrid_readiness.canary_cli "
    "pastoral_retreat_v2_validation --window WIN001 "
    "--authorization-scope SMALL_V21_WIN001_ONLY "
    "--planner-version window-planner-v2.1-small "
    "--prompt-version window-analysis-1.1 --dry-run"
)
FUTURE_REAL_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_hybrid_readiness.canary_cli "
    "pastoral_retreat_v2_validation --window WIN001 "
    "--authorization-scope SMALL_V21_WIN001_ONLY "
    "--planner-version window-planner-v2.1-small "
    "--prompt-version window-analysis-1.1 --execute-real"
)

NEXT_PHASE = "3B.7.7A.9_REAL_SMALL_WIN001_CANARY"
NEXT_PHASE_LABEL = (
    "3B.7.7A.9 — REAL SMALL WIN001 CANARY — 1 Anthropic semantic call maximum"
)
NEXT_ACTION = (
    "HUMAN DECISION. Do not execute. A new explicit human authorization is "
    "required for one small WIN001 canary under window-planner-v2.1-small."
)

REAL_PROVIDER_CALLS_THIS_PHASE = 0
REAL_WINDOWS_EXECUTED = 0
PRODUCTION_DEFAULT_CHANGED = False
MAX_NEW_CALLS = MAX_NEW_CALLS_WIN001
MAX_ATTEMPTS_REQUIRED = MAX_ATTEMPTS
PHASE_3B_STATUS = "INCOMPLETE"

PROTECTED_EVIDENCE = PROTECTED_EVIDENCE_A7 + (
    "audit/PHASE_3B77A7_SMALL_WINDOW_ADAPTIVE_HIERARCHY_IMPLEMENTATION_REPORT.md",
    "audit/source_analysis_small_window_plan_v21.json",
    "audit/source_analysis_adaptive_consolidation_router.json",
    "audit/source_analysis_small_window_direct_global_fake_ai.json",
    "audit/source_analysis_small_window_hierarchical_fake_ai.json",
    "audit/source_analysis_hierarchical_traceability_validation.json",
    "audit/source_analysis_small_window_real_preflight.json",
)

__all__ = [
    "A7_EXPECTED_WINDOWS",
    "A7_WIN001_INPUT_HASH",
    "AUTHORIZATION_SCOPE",
    "BOUNDARY_ARTIFACT",
    "CACHE_ARTIFACT",
    "COST_RISK_ARTIFACT",
    "DRY_RUN_ARTIFACT",
    "DRY_RUN_COMMAND",
    "EXECUTION_CONTRACT_ARTIFACT",
    "FUTURE_REAL_COMMAND",
    "GRANULARITY_POLICY_VERSION",
    "HARD_MAX_LOCAL_ESTIMATE",
    "HISTORICAL_CALL1_SIGNATURE",
    "HISTORICAL_CALL2_COST",
    "HISTORICAL_CALL2_SIGNATURE",
    "HISTORICAL_RATIO_LABEL",
    "HISTORICAL_SPEND_USD",
    "LONG_CONTEXT_THRESHOLD",
    "MAX_ATTEMPTS_REQUIRED",
    "MAX_NEW_CALLS",
    "MAX_OUTPUT",
    "MODE",
    "NEXT_ACTION",
    "NEXT_PHASE",
    "NEXT_PHASE_LABEL",
    "PHASE",
    "PHASE_3B_STATUS",
    "PLANNER_VERSION_REQUIRED",
    "PRODUCTION_DEFAULT_CHANGED",
    "PRODUCTION_PLANNER_VERSION",
    "PROJECT_NAME",
    "PROMPT_10_SHA",
    "PROMPT_11_SHA",
    "PROMPT_VERSION_REQUIRED",
    "PROTECTED_EVIDENCE",
    "READINESS_ARTIFACT",
    "REAL_PROVIDER_CALLS_THIS_PHASE",
    "REAL_WINDOWS_EXECUTED",
    "REPORT_NAME",
    "SCHEMA_VERSION",
    "TRANSPORT_VERSION",
    "WINDOW_ID",
    "CLEAN_SHA",
    "EXPECTED_DURATION_SECONDS",
    "EXPECTED_PRESENT_SRC",
    "EXPECTED_REMOVED_SRC",
    "EXPECTED_TRANSCRIPT_ID",
    "EXPECTED_WINDOW_COUNT",
    "EXPECTED_WORD_COUNT",
    "GENERATION_C_ANTHROPIC_SHA",
    "GENERATION_C_RAW_SHA",
]
