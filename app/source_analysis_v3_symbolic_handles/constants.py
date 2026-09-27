"""Constantes 3B.7.7A.17 — redesign transport handles. 0 provider."""

from __future__ import annotations

from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v3.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_PLANNER_VERSION,
    MAX_OUTPUT_TOKENS_FROZEN,
    MODE,
    NEXT_ACTION,
    NEXT_PHASE,
    NEXT_PHASE_LABEL,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    SEMANTIC_TRANSPORT_VERSION_V2,
    SEMANTIC_TRANSPORT_VERSION_V3,
    TARGET_JSON_LOCAL_TOKENS,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WIN001_RETRY_AUTHORIZED,
)
from app.source_analysis_output_ceiling_review.constants import (
    CALL1_SIGNATURE,
    CALL2_SIGNATURE,
    SMALL_SIGNATURE,
)
from app.source_analysis_thinking_contract.constants import (
    SELECTED_CONTRACT,
    SELECTED_EFFORT,
    SELECTED_THINKING_MODE,
)
from app.source_analysis_v2_a15_forensics.constants import (
    A15_SIGNATURE,
    SEMANTIC_CONTENT_CLASSIFICATION,
)
from app.source_analysis_v2_link_semantics.constants import A13_REQUEST_IDENTITY
from app.source_analysis_v2_real_win001.constants import WINDOW_ID

PROVIDER = "anthropic"
MODEL = "claude-sonnet-5"
THINKING_CONTRACT = SELECTED_CONTRACT
THINKING_MODE = SELECTED_THINKING_MODE
EFFORT = SELECTED_EFFORT

DESIGN_ARTIFACT = "source_analysis_symbolic_handle_transport_design.json"
SCHEMA_ARTIFACT = "source_analysis_symbolic_handle_schema_analysis.json"
RESOLUTION_ARTIFACT = "source_analysis_symbolic_handle_resolution_contract.json"
FAKEAI_ARTIFACT = "source_analysis_symbolic_handle_fakeai_e2e.json"
PREFLIGHT_ARTIFACT = "source_analysis_symbolic_handle_real_window_preflight.json"
CANARY_ARTIFACT = "source_analysis_symbolic_handle_grammar_canary_readiness.json"
REPORT_NAME = "PHASE_3B77A17_LOCAL_SYMBOLIC_HANDLES_TRANSPORT_REDESIGN_REPORT.md"

CANARY_WINDOW_ID = "WIN996"
CANARY_TRANSCRIPT_ID = "TR_CANARY_H"
CANARY_SRC_IDS = ("SRC997001", "SRC997002")
CANARY_TEXTS = (
    "The speaker says careful planning reduces avoidable mistakes.",
    "The speaker gives checking the plan twice as an example.",
)
CANARY_MAX_OUTPUT_TOKENS = 512
CANARY_EXECUTED = False

A15_SEMANTIC_CONTENT = SEMANTIC_CONTENT_CLASSIFICATION

__all__ = [
    "A13_REQUEST_IDENTITY",
    "A15_SEMANTIC_CONTENT",
    "A15_SIGNATURE",
    "CALL1_SIGNATURE",
    "CALL2_SIGNATURE",
    "CANARY_ARTIFACT",
    "CANARY_EXECUTED",
    "CANARY_MAX_OUTPUT_TOKENS",
    "CANARY_SRC_IDS",
    "CANARY_TEXTS",
    "CANARY_TRANSCRIPT_ID",
    "CANARY_WINDOW_ID",
    "CANDIDATE_HARD_MAX_INPUT_TOKENS",
    "CANDIDATE_PLANNER_VERSION",
    "DESIGN_ARTIFACT",
    "EFFORT",
    "FAKEAI_ARTIFACT",
    "MAX_OUTPUT_TOKENS_FROZEN",
    "MODE",
    "MODEL",
    "NEXT_ACTION",
    "NEXT_PHASE",
    "NEXT_PHASE_LABEL",
    "PHASE",
    "PHASE_3B_STATUS",
    "PLANNER_VERSION",
    "PREFLIGHT_ARTIFACT",
    "PRODUCTION_PLANNER_VERSION",
    "PROJECT_NAME",
    "PROVIDER",
    "REAL_PROVIDER_CALLS_THIS_PHASE",
    "REAL_WINDOW_CALLS",
    "REPORT_NAME",
    "RESOLUTION_ARTIFACT",
    "SCHEMA_ARTIFACT",
    "SCHEMA_VERSION",
    "SELECTED_ARCHITECTURE",
    "SEMANTIC_TRANSPORT_VERSION_V2",
    "SEMANTIC_TRANSPORT_VERSION_V3",
    "SMALL_SIGNATURE",
    "TARGET_JSON_LOCAL_TOKENS",
    "THINKING_CONTRACT",
    "THINKING_MODE",
    "WINDOW_ANALYSIS_PROMPT_VERSION_V13",
    "WINDOW_ID",
    "WIN001_RETRY_AUTHORIZED",
]
