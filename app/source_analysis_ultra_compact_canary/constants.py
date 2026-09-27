"""Constantes du canary 3B.4.3 — pas des règles métier du Source Analyzer."""

from __future__ import annotations

CANARY_SCHEMA_VERSION = "1.0"
CANARY_PROMPT_ADDENDUM_VERSION = "1.0"
STAGE = "source_analysis_ultra_compact_canary"
CACHE_NAMESPACE = "ultra-compact-canary-3b43"
SIGNATURE_MARK = "ultra-compact-canary-3b43"

EXPECTED_PROVIDER = "anthropic"
EXPECTED_MODEL = "claude-sonnet-5"
TRANSPORT_VERSION = "semantic-transport-v1"

MAX_REAL_CALLS = 1
MAX_ATTEMPTS = 1
REAL_CALL_TIMEOUT_SECONDS = 600.0

# Budget de sortie du canary uniquement — ne change PAS la config globale.
CANARY_MAX_OUTPUT_TOKENS = 8192

MIN_SRC = 8
PREFERRED_MAX_SRC = 15
MAX_SRC = 15
MIN_WORDS = 100
TARGET_WORDS = 500
MAX_WORDS = 500
MIN_SEGMENT_WORDS = 8

MAX_ESTIMATED_INPUT_TOKENS = 20_000
GLOBAL_ESTIMATED_TOKENS_REFERENCE = 141_775

# Passage 3B.4.1 — à réutiliser s'il est encore présent et cohérent.
HISTORICAL_SRC_IDS = (
    "SRC003799",
    "SRC003800",
    "SRC003801",
    "SRC003802",
    "SRC003803",
    "SRC003804",
    "SRC003805",
    "SRC003806",
    "SRC003807",
    "SRC003808",
)

SELECTION_RULE_HISTORICAL = (
    "historical_3b41_window : SRC003799–SRC003808 tels que sélectionnés "
    "par la Phase 3B.4.1, réutilisés parce que ces SRC restent présents "
    "dans le transcript clean DERIVED et forment encore un extrait contigu."
)

SELECTION_RULE_FALLBACK = (
    "first_contiguous_clean_english_window : première fenêtre contiguë de "
    "SRC survivants du transcript clean classés EN par language_detector "
    "local (aucun appel IA), en écartant silence / fragments courts / "
    "UNKNOWN / FR ; 8–15 SRC, 100–500 mots."
)

INPUT_ARTIFACT_NAME = "source_analysis_ultra_compact_canary_input.json"
DRY_RUN_ARTIFACT_NAME = "source_analysis_ultra_compact_canary_dry_run.json"
RESULT_ARTIFACT_NAME = "source_analysis_ultra_compact_canary_result.json"
TRANSPORT_ARTIFACT_NAME = "source_analysis_ultra_compact_canary_transport.json"
CANARY_SOURCEMAP_NAME = "source_analysis_ultra_compact_canary_source_map.json"
REPORT_NAME = "PHASE_3B43_ULTRA_COMPACT_SERVER_CANARY_REPORT.md"

GRAMMAR_ACCEPTED = "ACCEPTED"
GRAMMAR_REJECTED = "REJECTED"
GRAMMAR_UNKNOWN = "UNKNOWN"

GRAMMAR_ACCEPTANCE_VERIFIED = "VERIFIED"
GRAMMAR_ACCEPTANCE_REJECTED = "REJECTED"
GRAMMAR_ACCEPTANCE_UNKNOWN = "UNKNOWN"

CLASS_SERVER_GRAMMAR_REJECTED = "SERVER_GRAMMAR_REJECTED"
CLASS_SERVER_SCHEMA_REJECTED = "SERVER_SCHEMA_REJECTED"
CLASS_SERVER_REQUEST_REJECTED = "SERVER_REQUEST_REJECTED"

OUTCOME_PASS = "PASS"
OUTCOME_PARTIAL = "PARTIAL"
OUTCOME_FAIL = "FAIL"
STOP_PRE_CALL = "PRE_CALL_FAILURE"

# Référence 3B.4.2 — comparée, jamais utilisée comme schéma de production.
REFERENCE_3B42_RAW_SHA256 = (
    "90885d692bf56695e33f6205013a7f81d21b6b520e90b59338f43113fc17b0f9"
)
REFERENCE_3B42_ANTHROPIC_SHA256 = (
    "5e54bc73257ee7d6c68ac74818974973bc7ece506556a8e975c56ef3ada18ae1"
)
REFERENCE_3B42_RAW_BYTES = 559
REFERENCE_3B42_ANTHROPIC_BYTES = 621
