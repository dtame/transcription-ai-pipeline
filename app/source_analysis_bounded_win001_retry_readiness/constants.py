"""Constantes 3B.7.7A.3 — readiness bornée WIN001. Offline only."""

from __future__ import annotations

from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_models import WINDOW_MAX_OUTPUT_TOKENS
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis_hybrid.constants import (
    HARD_MAX_INPUT_TOKENS,
    WINDOW_TRANSPORT_VERSION,
)
from app.source_analysis_hybrid_readiness.constants import (
    AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY,
    MAX_ATTEMPTS,
    MAX_NEW_CALLS_WIN001,
)
from app.source_analysis_win001_failure_diagnosis.constants import (
    LONG_CONTEXT_THRESHOLD_PROTOCOL,
    OBSERVED_COST_USD,
    OBSERVED_LOCAL_ESTIMATE,
    OBSERVED_PROVIDER_INPUT,
    OBSERVED_PROVIDER_OUTPUT,
)

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.7A.3"
MODE = "OFFLINE_BOUNDED_WIN001_RETRY_READINESS"

READINESS_ARTIFACT = "source_analysis_bounded_win001_retry_readiness.json"
COST_RISK_ARTIFACT = "source_analysis_bounded_win001_cost_risk.json"
EXECUTION_CONTRACT_ARTIFACT = "source_analysis_bounded_win001_execution_contract.json"
DRY_RUN_ARTIFACT = "source_analysis_bounded_win001_dry_run.json"
REPORT_NAME = "PHASE_3B77A3_BOUNDED_WIN001_RETRY_READINESS_COST_RISK_REPORT.md"

PROJECT_NAME = "pastoral_retreat_v2_validation"
WINDOW_ID = "WIN001"

HISTORICAL_PROMPT = WINDOW_ANALYSIS_PROMPT_VERSION_V10
SUCCESSOR_PROMPT = WINDOW_ANALYSIS_PROMPT_VERSION
TRANSPORT_VERSION = WINDOW_TRANSPORT_VERSION
GRANULARITY_POLICY_VERSION = POLICY_VERSION
AUTHORIZATION_SCOPE = AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY

HISTORICAL_SPEND_USD = OBSERVED_COST_USD
HISTORICAL_LOCAL_ESTIMATE = OBSERVED_LOCAL_ESTIMATE
HISTORICAL_PROVIDER_INPUT = OBSERVED_PROVIDER_INPUT
HISTORICAL_PROVIDER_OUTPUT = OBSERVED_PROVIDER_OUTPUT
HISTORICAL_RATIO_LABEL = "2.155975"

HARD_MAX_LOCAL_ESTIMATE = HARD_MAX_INPUT_TOKENS
MAX_OUTPUT = WINDOW_MAX_OUTPUT_TOKENS
LONG_CONTEXT_THRESHOLD = LONG_CONTEXT_THRESHOLD_PROTOCOL

DRY_RUN_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_hybrid_readiness.canary_cli "
    "pastoral_retreat_v2_validation --window WIN001 "
    "--authorization-scope BOUNDED_WIN001_ONLY "
    "--prompt-version window-analysis-1.1 --dry-run"
)
FUTURE_REAL_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_hybrid_readiness.canary_cli "
    "pastoral_retreat_v2_validation --window WIN001 "
    "--authorization-scope BOUNDED_WIN001_ONLY "
    "--prompt-version window-analysis-1.1 --execute-real"
)

NEXT_PHASE = "3B.7.7A.4_REAL_BOUNDED_WIN001_CANARY"
NEXT_PHASE_LABEL = (
    "3B.7.7A.4 — REAL BOUNDED WIN001 CANARY — 1 Anthropic call maximum"
)
NEXT_ACTION = (
    "HUMAN DECISION. Do not execute. A new explicit human authorization is "
    "required for one bounded WIN001 canary under window-analysis-1.1."
)

REAL_PROVIDER_CALLS_THIS_PHASE = 0
WIN001_RETRIED = False
MAX_NEW_CALLS = MAX_NEW_CALLS_WIN001
MAX_ATTEMPTS_REQUIRED = MAX_ATTEMPTS

PROTECTED_EVIDENCE = (
    "audit/PHASE_3B77A_REAL_WIN001_CANARY_REPORT.md",
    "audit/source_analysis_real_win001_canary_execution.json",
    "audit/PHASE_3B77A1_WIN001_STRUCTURED_OUTPUT_FAILURE_TOKEN_DIAGNOSIS_REPORT.md",
    "audit/source_analysis_win001_structured_failure_diagnosis.json",
    "audit/source_analysis_win001_token_accounting_diagnosis.json",
    "audit/source_analysis_structured_output_observability_review.json",
    "audit/PHASE_3B77A2_WINDOW_OUTPUT_BOUNDING_GRANULARITY_REDESIGN_REPORT.md",
    "audit/source_analysis_window_granularity_policy.json",
    "audit/source_analysis_window_output_size_study.json",
    "audit/source_analysis_win001_bounded_prompt_preflight.json",
    "audit/source_analysis_window_output_bounding_implementation.json",
    "audit/PHASE_3B76_HYBRID_PRODUCTION_EXECUTION_READINESS_REAL_CALL_PLAN_REPORT.md",
    "audit/source_analysis_hybrid_win001_dry_run.json",
    "audit/source_analysis_hybrid_failure_matrix.json",
    "audit/source_analysis_hybrid_real_call_plan.json",
    "audit/source_analysis_hybrid_production_readiness.json",
    "audit/source_analysis_ultra_compact_canary_result.json",
    "audit/source_analysis_vocabulary_compliance_canary_result.json",
)

__all__ = [
    "AUTHORIZATION_SCOPE",
    "COST_RISK_ARTIFACT",
    "DRY_RUN_ARTIFACT",
    "DRY_RUN_COMMAND",
    "EXECUTION_CONTRACT_ARTIFACT",
    "FUTURE_REAL_COMMAND",
    "GRANULARITY_POLICY_VERSION",
    "HARD_MAX_LOCAL_ESTIMATE",
    "HISTORICAL_PROMPT",
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
    "PROJECT_NAME",
    "PROTECTED_EVIDENCE",
    "READINESS_ARTIFACT",
    "REAL_PROVIDER_CALLS_THIS_PHASE",
    "REPORT_NAME",
    "SCHEMA_VERSION",
    "SUCCESSOR_PROMPT",
    "TRANSPORT_VERSION",
    "WINDOW_ID",
    "WIN001_RETRIED",
]
