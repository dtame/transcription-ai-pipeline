"""Constantes du run 3B Final — pas des règles métier du Source Analyzer."""

from __future__ import annotations

from app.source_analysis.canonical_vocabulary import (
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
)
from app.source_analysis_vocabulary_compliance_canary.constants import (
    REFERENCE_3B44_PROMPT_SHA256,
)

SCHEMA_VERSION = "1.0"
STAGE = "source_analysis"
PURPOSE = "global_clean_source_analysis"

EXPECTED_PROVIDER = "anthropic"
EXPECTED_MODEL = "claude-sonnet-5"
TRANSPORT_VERSION = "semantic-transport-v1"
EXPECTED_PROMPT_VERSION = "1.3"

MAX_REAL_CALLS = 1
MAX_ATTEMPTS = 1
# HISTORIQUE 3B Final — n'est PLUS la source effective du timeout.
# Conservé à 3600.0 pour que l'audit 3B.5 reste un témoin du run échoué.
# Le runner global utilise désormais resolve_timeouts() (connect/read,
# configuration par étape / env). Ne pas remplacer par 7200.
REAL_CALL_TIMEOUT_SECONDS = 3600.0
EXPECTED_MODEL_MAX_OUTPUT = 128_000

DRY_RUN_ARTIFACT_NAME = "source_analysis_global_clean_dry_run.json"
TRANSPORT_ARTIFACT_NAME = "source_analysis_global_clean_transport.json"
RESULT_ARTIFACT_NAME = "source_analysis_global_clean_result.json"
FAILED_RAW_NAME = "source_analysis_global_clean_failed_canonical_raw.json"
FAILED_NORMALIZED_NAME = "source_analysis_global_clean_failed_normalized.json"
REPORT_NAME = "PHASE_3B_FINAL_GLOBAL_CLEAN_SOURCE_ANALYZER_REPORT.md"

OUTCOME_PASS = "PASS"
OUTCOME_PARTIAL = "PARTIAL"
OUTCOME_FAIL = "FAIL"

STOP_PRE_CALL = "PRE_CALL_FAILURE"
STOP_AFTER_CALL = "POST_CALL_FAILURE"
STOP_EXISTING_MAP = "EXISTING_SOURCE_MAP"
STOP_CACHE_HIT = "UNEXPECTED_CACHE_HIT"
STOP_TRUNCATED = "OUTPUT_TRUNCATED"
STOP_TRANSPORT_WRITE = "TRANSPORT_PRESERVE_FAILURE"

CLASS_PRE_CALL_SCHEMA_DRIFT = "PRE_CALL_SCHEMA_DRIFT"
CLASS_PRE_CALL_CREDENTIAL_MISSING = "PRE_CALL_CREDENTIAL_MISSING"
CLASS_PRE_CALL_EXISTING_MAP = "PRE_CALL_EXISTING_SOURCE_MAP"
CLASS_PRE_CALL_UNEXPECTED_CACHE = "PRE_CALL_UNEXPECTED_CACHE"
CLASS_PRE_CALL_NOT_GLOBAL = "PRE_CALL_NOT_GLOBAL"
CLASS_PRE_CALL_OUTPUT_CAPACITY = "PRE_CALL_OUTPUT_CAPACITY"
CLASS_PRE_CALL_PARITY = "PRE_CALL_VOCABULARY_PARITY"

CANARY_SIGNATURE_MARKS = (
    "ultra-compact-canary-3b43",
    "vocabulary-compliance-canary-3b45",
    "schema-canary-3b41",
)

PHASE4_FORBIDDEN_MARKERS = (
    "editorial_plan.json",
    "Editorial Planner",
    "editorial_planning",
    "book_generation",
    "book_validation",
    "visual_design",
    "image_generation",
    "run_editorial",
    "create_editorial_plan",
)

__all__ = [
    "EXPECTED_MODEL",
    "EXPECTED_MODEL_MAX_OUTPUT",
    "EXPECTED_PROMPT_VERSION",
    "EXPECTED_PROVIDER",
    "GENERATION_C_ANTHROPIC_SHA256_3B43",
    "GENERATION_C_RAW_SHA256_3B43",
    "REFERENCE_3B44_PROMPT_SHA256",
    "STAGE",
    "TRANSPORT_VERSION",
]
