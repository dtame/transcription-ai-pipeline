"""
Politique approuvée window-planner-v2.0 — Phase 3B.7.1.

Ces valeurs sont celles du design 3B.7. Elles ne sont pas des magic
numbers dispersés : toute planification production passe par
WindowPlannerConfig, qui les porte et les valide.
"""

from __future__ import annotations

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.1"
MODE = "OFFLINE_IMPLEMENTATION"

IMPLEMENTATION_ARTIFACT_NAME = "source_analysis_window_planner_v2_implementation.json"
REPORT_NAME = "PHASE_3B71_WINDOW_PLANNER_V2_AND_HYBRID_CONTRACTS_REPORT.md"

STRATEGY = "HYBRID_WINDOW_PLUS_GLOBAL_CONSOLIDATION"
PLAN_STRATEGY = "hybrid"

PLANNER_VERSION = "window-planner-v2.0"
PLANNER_NAME = "WindowPlannerV2"

TARGET_INPUT_TOKENS = 50000
HARD_MAX_INPUT_TOKENS = 60000
OVERLAP_POLICY = "NO_OWNED_OVERLAP"
RECOGNIZED_OVERLAP_POLICIES = frozenset({OVERLAP_POLICY})
BOUNDARY_CONTEXT_POLICY = "NONE"

TINY_TAIL_MIN_FRACTION_OF_TARGET = 0.15
TINY_TAIL_MIN_CONTENT_OVERHEAD_FACTOR = 2.0

WINDOW_PROMPT_VERSION = "window-analysis-1.0"
WINDOW_TRANSPORT_VERSION = "semantic-transport-v1"
CONSOLIDATION_PROMPT_VERSION = "consolidation-1.0"
CONSOLIDATION_TRANSPORT_VERSION = "consolidation-transport-v1"

CONSOLIDATION_OPERATIONS = (
    "GLOBAL_METADATA",
    "KEEP_RECORD",
    "MERGE_RECORDS",
    "RELATION",
    "REPETITION",
)
FORBIDDEN_CONSOLIDATION_OPERATIONS = ("DROP_RECORD",)

OWNERSHIP_OWNED = "OWNED"
OWNERSHIP_CONTEXT_ONLY = "CONTEXT_ONLY"

EXPECTED_PROVIDER = "anthropic"
EXPECTED_MODEL = "claude-sonnet-5"
ESTIMATION_MODEL = EXPECTED_MODEL
EXPECTED_PROMPT_VERSION = "1.3"
EXPECTED_TRANSCRIPT_ID = "TR001"
EXPECTED_INPUT_MODE = "DERIVED"

WINDOW_ID_WIDTH = 3
WINDOW_RECORD_INDEX_WIDTH = 4

PHASE_3B_STATUS = "INCOMPLETE"
NEXT_PHASE = "3B.7.2_WINDOW_ANALYSIS_PIPELINE_WITH_FAKE_AI"
NEXT_PHASE_LABEL = "3B.7.2 — WINDOW ANALYSIS PIPELINE WITH FAKE AI"

PROVIDER_CALLS = 0
SOURCE_MAP_PUBLISHED = False
PRODUCTION_ANALYZER_WIRED = False

# Comparaison descriptive au design 3B.7 — jamais utilisée comme special-case
# de planification. Le plan réel doit émerger de l'algorithme.
DESIGN_3B7_WINDOWS = (
    {
        "window_id": "WIN001",
        "owned_src_count": 2787,
        "estimated_input_tokens": 49614,
        "word_count": 12745,
        "first_owned_src_ref": "SRC000001",
        "last_owned_src_ref": "SRC002822",
    },
    {
        "window_id": "WIN002",
        "owned_src_count": 2771,
        "estimated_input_tokens": 49594,
        "word_count": 12719,
        "first_owned_src_ref": "SRC002823",
        "last_owned_src_ref": "SRC005599",
    },
    {
        "window_id": "WIN003",
        "owned_src_count": 2740,
        "estimated_input_tokens": 49589,
        "word_count": 12849,
        "first_owned_src_ref": "SRC005600",
        "last_owned_src_ref": "SRC008415",
    },
)

PHASE_3B7_NOW_HISTORICAL = (
    "audit/PHASE_3B7_HYBRID_WINDOW_PLUS_GLOBAL_CONSOLIDATION_DESIGN_REPORT.md",
    "audit/source_analysis_hybrid_window_design.json",
    "audit/source_analysis_hybrid_consolidation_design.json",
    "audit/source_analysis_window_planner_v2_simulation.json",
    "audit/source_analysis_hybrid_architecture_design.json",
)

__all__ = [
    "BOUNDARY_CONTEXT_POLICY",
    "CONSOLIDATION_OPERATIONS",
    "CONSOLIDATION_TRANSPORT_VERSION",
    "DESIGN_3B7_WINDOWS",
    "ESTIMATION_MODEL",
    "FORBIDDEN_CONSOLIDATION_OPERATIONS",
    "HARD_MAX_INPUT_TOKENS",
    "IMPLEMENTATION_ARTIFACT_NAME",
    "MODE",
    "NEXT_PHASE",
    "OVERLAP_POLICY",
    "PHASE",
    "PLANNER_VERSION",
    "PLAN_STRATEGY",
    "REPORT_NAME",
    "SCHEMA_VERSION",
    "STRATEGY",
    "TARGET_INPUT_TOKENS",
    "WINDOW_PROMPT_VERSION",
    "WINDOW_TRANSPORT_VERSION",
]
