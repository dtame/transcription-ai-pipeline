"""Constantes 3B.7.7A.2 — bounding de sortie / granularité. Offline only."""

from __future__ import annotations

from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_models import WINDOW_MAX_OUTPUT_TOKENS
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis_hybrid.constants import WINDOW_TRANSPORT_VERSION

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.7A.2"
MODE = "OFFLINE_OUTPUT_BOUNDING_DESIGN"

POLICY_ARTIFACT = "source_analysis_window_granularity_policy.json"
SIZE_STUDY_ARTIFACT = "source_analysis_window_output_size_study.json"
PREFLIGHT_ARTIFACT = "source_analysis_win001_bounded_prompt_preflight.json"
IMPLEMENTATION_ARTIFACT = "source_analysis_window_output_bounding_implementation.json"
REPORT_NAME = "PHASE_3B77A2_WINDOW_OUTPUT_BOUNDING_GRANULARITY_REDESIGN_REPORT.md"

PROJECT_NAME = "pastoral_retreat_v2_validation"
WINDOW_ID = "WIN001"

HISTORICAL_PROMPT = WINDOW_ANALYSIS_PROMPT_VERSION_V10
SUCCESSOR_PROMPT = WINDOW_ANALYSIS_PROMPT_VERSION
TRANSPORT_VERSION = WINDOW_TRANSPORT_VERSION
GRANULARITY_POLICY_VERSION = POLICY_VERSION

NEXT_PHASE = "3B.7.7A.3_BOUNDED_WIN001_RETRY_READINESS_COST_RISK_REVIEW"
NEXT_PHASE_LABEL = (
    "3B.7.7A.3 — BOUNDED WIN001 RETRY READINESS & COST/RISK REVIEW — OFFLINE ONLY"
)
NEXT_ACTION = (
    "Human review. Do not retry WIN001. Next offline phase decides whether "
    "a second paid WIN001 canary is justified under the bounded contract."
)

REAL_PROVIDER_CALLS_THIS_PHASE = 0
WIN001_RETRIED = False

PROTECTED_EVIDENCE = (
    "audit/PHASE_3B77A_REAL_WIN001_CANARY_REPORT.md",
    "audit/source_analysis_real_win001_canary_execution.json",
    "audit/PHASE_3B77A1_WIN001_STRUCTURED_OUTPUT_FAILURE_TOKEN_DIAGNOSIS_REPORT.md",
    "audit/source_analysis_win001_structured_failure_diagnosis.json",
    "audit/source_analysis_win001_token_accounting_diagnosis.json",
    "audit/source_analysis_structured_output_observability_review.json",
    "audit/PHASE_3B76_HYBRID_PRODUCTION_EXECUTION_READINESS_REAL_CALL_PLAN_REPORT.md",
    "audit/source_analysis_hybrid_win001_dry_run.json",
    "audit/source_analysis_hybrid_failure_matrix.json",
    "audit/source_analysis_hybrid_real_call_plan.json",
    "audit/source_analysis_hybrid_production_readiness.json",
    "audit/source_analysis_ultra_compact_canary_result.json",
    "audit/source_analysis_vocabulary_compliance_canary_result.json",
)

__all__ = [
    "GRANULARITY_POLICY_VERSION",
    "HISTORICAL_PROMPT",
    "IMPLEMENTATION_ARTIFACT",
    "MODE",
    "NEXT_ACTION",
    "NEXT_PHASE",
    "NEXT_PHASE_LABEL",
    "PHASE",
    "POLICY_ARTIFACT",
    "PREFLIGHT_ARTIFACT",
    "PROJECT_NAME",
    "PROTECTED_EVIDENCE",
    "REAL_PROVIDER_CALLS_THIS_PHASE",
    "REPORT_NAME",
    "SCHEMA_VERSION",
    "SIZE_STUDY_ARTIFACT",
    "SUCCESSOR_PROMPT",
    "TRANSPORT_VERSION",
    "WINDOW_ID",
    "WINDOW_MAX_OUTPUT_TOKENS",
    "WIN001_RETRIED",
]
