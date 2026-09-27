"""Constantes du canary 3B.4.1 — pas des règles métier du Source Analyzer."""

from __future__ import annotations

CANARY_SCHEMA_VERSION = "1.0"
CANARY_PROMPT_ADDENDUM_VERSION = "1.0"
STAGE = "source_analysis_schema_canary"

EXPECTED_PROVIDER = "anthropic"
EXPECTED_MODEL = "claude-sonnet-5"

MAX_REAL_CALLS = 1
MAX_ATTEMPTS = 1
REAL_CALL_TIMEOUT_SECONDS = 600.0

# Fenêtre de sélection : on réduit l'INPUT, jamais le schéma de réponse.
MIN_SRC = 8
PREFERRED_MAX_SRC = 15
MAX_SRC = 80
MIN_WORDS = 200
TARGET_WORDS = 500
MAX_WORDS = 1200
MIN_SEGMENT_WORDS = 8

# Le canary doit rester clairement plus petit que ~141919 tokens du run global.
MAX_ESTIMATED_INPUT_TOKENS = 20_000
GLOBAL_ESTIMATED_TOKENS_REFERENCE = 141_919

SELECTION_RULE = (
    "first_contiguous_clean_english_window : première fenêtre contiguë de "
    "SRC survivants du transcript clean classés EN par language_detector "
    "local (aucun appel IA), en écartant silence / fragments courts / "
    "UNKNOWN / FR ; 8–15 SRC si la fenêtre est déjà substantielle, sinon "
    "extension jusqu'à 500–1200 mots (plafond 1200 mots / 80 SRC)."
)

INPUT_ARTIFACT_NAME = "source_analysis_schema_canary_input.json"
DRY_RUN_ARTIFACT_NAME = "source_analysis_schema_canary_dry_run.json"
RESULT_ARTIFACT_NAME = "source_analysis_schema_canary_result.json"
CANARY_SOURCEMAP_NAME = "source_analysis_schema_canary_sourcemap.json"
REPORT_NAME = "PHASE_3B41_SERVER_GRAMMAR_CANARY_REPORT.md"

GRAMMAR_ACCEPTANCE_VERIFIED = "VERIFIED"
GRAMMAR_ACCEPTANCE_REJECTED = "REJECTED"
GRAMMAR_ACCEPTANCE_UNKNOWN = "UNKNOWN"

CLASS_SERVER_GRAMMAR_REJECTED = "SERVER_GRAMMAR_REJECTED"
CLASS_SERVER_REQUEST_REJECTED = "SERVER_REQUEST_REJECTED"

OUTCOME_PASS = "PASS"
OUTCOME_PARTIAL = "PARTIAL"
OUTCOME_FAIL = "FAIL"
STOP_PRE_CALL = "PRE_CALL_FAILURE"
