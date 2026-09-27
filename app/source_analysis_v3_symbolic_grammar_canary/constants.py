"""Constantes 3B.7.7A.18 — canary V3 symbolic-handle grammar. Isolé."""

from __future__ import annotations

from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.constants import (
    DEFERRED_KINDS,
    LOCAL_KINDS,
    MAX_OUTPUT_TOKENS_FROZEN,
    PROJECT_NAME,
    SEMANTIC_TRANSPORT_VERSION_V2,
)
from app.source_analysis_local_v3.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_PLANNER_VERSION,
    SEMANTIC_TRANSPORT_VERSION_V3,
    TARGET_JSON_LOCAL_TOKENS,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
)
from app.source_analysis_local_v3.schema import semantic_transport_v3_fingerprint
from app.source_analysis_thinking_contract.constants import (
    SELECTED_CONTRACT,
    SELECTED_EFFORT,
    SELECTED_THINKING_MODE,
)
from app.source_analysis_v2_link_semantics.constants import A13_REQUEST_IDENTITY
from app.source_analysis_v3_symbolic_handles.constants import (
    CANARY_WINDOW_ID as A17_PREPARED_WINDOW_ID,
)

assert A17_PREPARED_WINDOW_ID == "WIN996"

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.7A.18"
MODE = "V3_SYMBOLIC_HANDLE_TINY_GRAMMAR_CANARY"

CANARY_VERSION = "v3-symbolic-handle-grammar-canary-1.0"
WRAPPER_VERSION = "v3-symbolic-handle-grammar-canary-wrapper-1.0"
PROVIDER = "anthropic"
MODEL = "claude-sonnet-5"
THINKING_CONTRACT = SELECTED_CONTRACT
THINKING_MODE = SELECTED_THINKING_MODE
EFFORT = SELECTED_EFFORT

AUTHORIZATION_SCOPE = "V3_SYMBOLIC_HANDLE_GRAMMAR_CANARY_ONLY"
WIN001_SCOPE = "SMALL_V21_V2_WIN001_ONLY"

MAX_ENGINE_GENERATE = 1
MAX_ANTHROPIC_POST = 1
MAX_ATTEMPTS = 1
AUTO_RETRY = False
AUTO_FALLBACK = False
AUTO_CONTINUE = False

# Tiny canary only. Production semantic max_output remains 32000.
# A.13 used 512 for 3 records (236 output tokens). This fixture requires
# 2 TOPIC + 3 IDEA + 1 RELATION + 1 EXAMPLE with symbolic handles.
CANARY_MAX_OUTPUT_TOKENS = 1024
PRODUCTION_MAX_OUTPUT_TOKENS = MAX_OUTPUT_TOKENS_FROZEN

CANARY_CONNECT_TIMEOUT_SECONDS = 30.0
CANARY_READ_TIMEOUT_SECONDS = 120.0

EXPECTED_RAW_SCHEMA_BYTES = 588
EXPECTED_ADAPTED_SCHEMA_BYTES = 650
A17_RAW_SCHEMA_BYTES = 588
A17_ADAPTED_SCHEMA_BYTES = 650
A17_SCHEMA_FINGERPRINT = semantic_transport_v3_fingerprint()

SYNTHETIC_WORST_CASE_LOCAL_TOKENS = 12185
TARGET_12000_EXCEEDED_BY = 364
HEADROOM_TO_32000 = 19815

CANARY_WINDOW_ID = "WIN996"
CANARY_TRANSCRIPT_ID = "TR_CANARY_H"
SYNTHETIC_SRC_IDS = ("SRC998001", "SRC998002", "SRC998003", "SRC998004")
SYNTHETIC_TEXTS = (
    "Planning reduces avoidable mistakes.",
    "Reviewing a plan can reveal missing steps.",
    "The speaker gives checking a checklist twice as an example.",
    "Planning and review support careful execution.",
)

FORBIDDEN_WINDOW_IDS = (
    "WIN001",
    "WIN002",
    "WIN003",
    "WIN004",
    "WIN005",
    "WIN006",
    "WIN007",
)
FORBIDDEN_TRANSCRIPT_IDS = ("TR001",)
PRODUCTION_SRC_PATTERN = r"^SRC0\d{5}$"
PASTORAL_MARKERS = (
    "pastoral_retreat",
    "pastoral retreat",
    "WIN001",
    "WIN002",
    "WIN003",
    "WIN004",
    "WIN005",
    "WIN006",
    "WIN007",
    "SRC000001",
    "TR001",
)

STAGE_CANARY = "source_analysis_v3_symbolic_grammar_canary"
CANARY_SUBDIR = "canary/v3_symbolic_handle_grammar"
LOCK_NAME = "canary_real_call.lock"

PAYLOAD_ARTIFACT = "source_analysis_v3_symbolic_grammar_canary_payload.json"
EXECUTION_ARTIFACT = "source_analysis_v3_symbolic_grammar_canary_execution.json"
HANDLES_ARTIFACT = "source_analysis_v3_symbolic_grammar_canary_handles.json"
REPORT_NAME = "PHASE_3B77A18_SYMBOLIC_HANDLE_TINY_GRAMMAR_CANARY_REPORT.md"

DRY_RUN_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_v3_symbolic_grammar_canary "
    "pastoral_retreat_v2_validation "
    "--authorization-scope V3_SYMBOLIC_HANDLE_GRAMMAR_CANARY_ONLY "
    "--dry-run"
)
REAL_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_v3_symbolic_grammar_canary "
    "pastoral_retreat_v2_validation "
    "--authorization-scope V3_SYMBOLIC_HANDLE_GRAMMAR_CANARY_ONLY "
    "--execute-real"
)

NEXT_ACTION = "HUMAN REVIEW"
NEXT_PHASE = "3B.7.7A.19_REAL_V3_SMALL_WIN001_SYMBOLIC_HANDLE_CANARY"
NEXT_PHASE_LABEL = (
    "3B.7.7A.19 — REAL V3 SMALL WIN001 SYMBOLIC-HANDLE CANARY "
    "(ONE real WIN001 call maximum; not authorized here)"
)
PHASE_3B_STATUS = "INCOMPLETE"
PRODUCTION_PLANNER_VERSION = PLANNER_VERSION
A13_IDENTITY = A13_REQUEST_IDENTITY

__all__ = [
    "A13_IDENTITY",
    "A17_ADAPTED_SCHEMA_BYTES",
    "A17_RAW_SCHEMA_BYTES",
    "A17_SCHEMA_FINGERPRINT",
    "AUTHORIZATION_SCOPE",
    "AUTO_CONTINUE",
    "AUTO_FALLBACK",
    "AUTO_RETRY",
    "CANARY_CONNECT_TIMEOUT_SECONDS",
    "CANARY_MAX_OUTPUT_TOKENS",
    "CANARY_READ_TIMEOUT_SECONDS",
    "CANARY_SUBDIR",
    "CANARY_TRANSCRIPT_ID",
    "CANARY_VERSION",
    "CANARY_WINDOW_ID",
    "CANDIDATE_HARD_MAX_INPUT_TOKENS",
    "CANDIDATE_PLANNER_VERSION",
    "DEFERRED_KINDS",
    "DRY_RUN_COMMAND",
    "EFFORT",
    "EXECUTION_ARTIFACT",
    "EXPECTED_ADAPTED_SCHEMA_BYTES",
    "EXPECTED_RAW_SCHEMA_BYTES",
    "FORBIDDEN_TRANSCRIPT_IDS",
    "FORBIDDEN_WINDOW_IDS",
    "HANDLES_ARTIFACT",
    "HEADROOM_TO_32000",
    "LOCAL_KINDS",
    "LOCK_NAME",
    "MAX_ANTHROPIC_POST",
    "MAX_ATTEMPTS",
    "MAX_ENGINE_GENERATE",
    "MODE",
    "MODEL",
    "NEXT_ACTION",
    "NEXT_PHASE",
    "NEXT_PHASE_LABEL",
    "PASTORAL_MARKERS",
    "PAYLOAD_ARTIFACT",
    "PHASE",
    "PHASE_3B_STATUS",
    "PRODUCTION_MAX_OUTPUT_TOKENS",
    "PRODUCTION_PLANNER_VERSION",
    "PRODUCTION_SRC_PATTERN",
    "PROJECT_NAME",
    "PROVIDER",
    "REAL_COMMAND",
    "REPORT_NAME",
    "SCHEMA_VERSION",
    "SEMANTIC_TRANSPORT_VERSION_V2",
    "SEMANTIC_TRANSPORT_VERSION_V3",
    "STAGE_CANARY",
    "SYNTHETIC_SRC_IDS",
    "SYNTHETIC_TEXTS",
    "SYNTHETIC_WORST_CASE_LOCAL_TOKENS",
    "TARGET_12000_EXCEEDED_BY",
    "TARGET_JSON_LOCAL_TOKENS",
    "THINKING_CONTRACT",
    "THINKING_MODE",
    "WINDOW_ANALYSIS_PROMPT_VERSION_V13",
    "WIN001_SCOPE",
    "WRAPPER_VERSION",
]
