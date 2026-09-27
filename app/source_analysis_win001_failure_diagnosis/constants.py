"""Constantes 3B.7.7A.1 — diagnostic offline WIN001. Aucun réglage de production."""

from __future__ import annotations

from app.source_analysis.window_models import (
    STAGE_WINDOW,
    TARGET_MODEL,
    TARGET_PROVIDER,
    WINDOW_MAX_OUTPUT_TOKENS,
)
from app.source_analysis_hybrid.constants import (
    HARD_MAX_INPUT_TOKENS,
    TARGET_INPUT_TOKENS,
)

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.7A.1"
MODE = "OFFLINE_FORENSIC_DIAGNOSIS"

FAILURE_DIAGNOSIS_ARTIFACT = "source_analysis_win001_structured_failure_diagnosis.json"
TOKEN_ACCOUNTING_ARTIFACT = "source_analysis_win001_token_accounting_diagnosis.json"
OBSERVABILITY_ARTIFACT = "source_analysis_structured_output_observability_review.json"
REPORT_NAME = (
    "PHASE_3B77A1_WIN001_STRUCTURED_OUTPUT_FAILURE_TOKEN_DIAGNOSIS_REPORT.md"
)

PROJECT_NAME = "pastoral_retreat_v2_validation"
WINDOW_ID = "WIN001"

OBSERVED_LOCAL_ESTIMATE = 49617
OBSERVED_PROVIDER_INPUT = 106973
OBSERVED_PROVIDER_OUTPUT = 32000
OBSERVED_COST_USD = "0.533946"
OBSERVED_INPUT_COST_USD = "0.213946"
OBSERVED_OUTPUT_COST_USD = "0.32"
OBSERVED_ERROR_TYPE = "AIStructuredOutputError"
OBSERVED_MAX_OUTPUT = WINDOW_MAX_OUTPUT_TOKENS

INPUT_COST_PER_1M = "2.00"
OUTPUT_COST_PER_1M = "10.00"

LONG_CONTEXT_THRESHOLD_PROTOCOL = 272000
LONG_CONTEXT_THRESHOLD_IN_REPO = False

HISTORICAL_3B_GLOBAL_MALFORMED = {
    "label": "3B global malformed JSON attempt",
    "input_tokens": 311362,
    "output_tokens": 14494,
    "evidence": (
        "Documented in app/tests/test_ai_providers.py "
        "(test_json_invalide_reste_rejete_localement_avec_output_config_envoye). "
        "Not located as a persisted pastoral audit usage object."
    ),
    "persisted_audit_usage": False,
}

PROTECTED_EVIDENCE = (
    "audit/PHASE_3B77A_REAL_WIN001_CANARY_REPORT.md",
    "audit/source_analysis_real_win001_canary_execution.json",
    "audit/PHASE_3B76_HYBRID_PRODUCTION_EXECUTION_READINESS_REAL_CALL_PLAN_REPORT.md",
    "audit/source_analysis_hybrid_win001_dry_run.json",
    "audit/source_analysis_hybrid_failure_matrix.json",
    "audit/source_analysis_hybrid_real_call_plan.json",
    "audit/source_analysis_hybrid_production_readiness.json",
    "audit/source_analysis_ultra_compact_canary_result.json",
    "audit/source_analysis_vocabulary_compliance_canary_result.json",
)

PRIMARY_CLASSIFICATION = "MULTIPLE_CONTRIBUTING_FACTORS"
PROXIMATE_FAILURE = (
    "AIStructuredOutputError raised by parse_structured_output() inside "
    "BaseAIEngine.generate() after a successful Anthropic HTTP body and "
    "text-block extraction; AIResponse.parsed never attached."
)
NEXT_PHASE = "3B.7.7A.2_WINDOW_OUTPUT_BOUNDING_GRANULARITY_REDESIGN"
NEXT_PHASE_LABEL = (
    "3B.7.7A.2 — WINDOW OUTPUT BOUNDING / GRANULARITY REDESIGN — OFFLINE ONLY"
)
NEXT_ACTION = (
    "Human review. Do not retry WIN001. Redesign output bounding / "
    "granularity offline before any future real call."
)

REAL_PROVIDER_CALLS_THIS_PHASE = 0
WIN001_RETRIED = False

STAGE = STAGE_WINDOW
EXPECTED_PROVIDER = TARGET_PROVIDER
EXPECTED_MODEL = TARGET_MODEL

__all__ = [
    "EXPECTED_MODEL",
    "EXPECTED_PROVIDER",
    "FAILURE_DIAGNOSIS_ARTIFACT",
    "HARD_MAX_INPUT_TOKENS",
    "HISTORICAL_3B_GLOBAL_MALFORMED",
    "INPUT_COST_PER_1M",
    "LONG_CONTEXT_THRESHOLD_IN_REPO",
    "LONG_CONTEXT_THRESHOLD_PROTOCOL",
    "MODE",
    "NEXT_ACTION",
    "NEXT_PHASE",
    "NEXT_PHASE_LABEL",
    "OBSERVED_COST_USD",
    "OBSERVED_ERROR_TYPE",
    "OBSERVED_INPUT_COST_USD",
    "OBSERVED_LOCAL_ESTIMATE",
    "OBSERVED_MAX_OUTPUT",
    "OBSERVED_OUTPUT_COST_USD",
    "OBSERVED_PROVIDER_INPUT",
    "OBSERVED_PROVIDER_OUTPUT",
    "OBSERVABILITY_ARTIFACT",
    "OUTPUT_COST_PER_1M",
    "PHASE",
    "PRIMARY_CLASSIFICATION",
    "PROJECT_NAME",
    "PROTECTED_EVIDENCE",
    "PROXIMATE_FAILURE",
    "REAL_PROVIDER_CALLS_THIS_PHASE",
    "REPORT_NAME",
    "SCHEMA_VERSION",
    "STAGE",
    "TARGET_INPUT_TOKENS",
    "TOKEN_ACCOUNTING_ARTIFACT",
    "WINDOW_ID",
    "WIN001_RETRIED",
    "WINDOW_MAX_OUTPUT_TOKENS",
]
