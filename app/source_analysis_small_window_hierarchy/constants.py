"""Constantes 3B.7.7A.7 — candidate path only. Production v2.0 unchanged."""

from __future__ import annotations

from app.source_analysis.consolidation_models import (
    CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
)
from app.source_analysis.window_granularity import (
    HARD_CEILINGS,
    POLICY_VERSION,
    TOTAL_HARD_CEILING,
)
from app.source_analysis.window_models import WINDOW_MAX_OUTPUT_TOKENS
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis_hybrid.constants import (
    OVERLAP_POLICY,
    PLANNER_VERSION,
    WINDOW_TRANSPORT_VERSION,
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
from app.source_analysis_post_canary_architecture.constants import (
    PROTECTED_EVIDENCE as PROTECTED_EVIDENCE_A6,
)

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.7A.7"
MODE = "OFFLINE_SMALL_WINDOW_ADAPTIVE_HIERARCHY_IMPLEMENTATION"
PROJECT_NAME = "pastoral_retreat_v2_validation"

REAL_PROVIDER_CALLS_THIS_PHASE = 0
THIRD_WIN001_CALL_AUTHORIZED = False
THIRD_WIN001_CALL = "NO"
IMPLEMENTATION_MODE = "FAKEAI ONLY"
REAL_CALL_AUTHORIZATION = False

PRODUCTION_PLANNER_VERSION = PLANNER_VERSION
CANDIDATE_PLANNER_VERSION = "window-planner-v2.1-small"
CANDIDATE_TARGET_INPUT_TOKENS = 25000
CANDIDATE_HARD_MAX_INPUT_TOKENS = 35000
CANDIDATE_OVERLAP_POLICY = OVERLAP_POLICY
CANDIDATE_CONTEXT_POLICY = "NONE"

WINDOW_PROMPT_VERSION = WINDOW_ANALYSIS_PROMPT_VERSION
WINDOW_GRANULARITY_VERSION = POLICY_VERSION
WINDOW_TRANSPORT = WINDOW_TRANSPORT_VERSION
MAX_OUTPUT_FROZEN = WINDOW_MAX_OUTPUT_TOKENS
TOTAL_RECORD_HARD_CEILING = TOTAL_HARD_CEILING
IDEA_SOFT = 40
IDEA_HARD = HARD_CEILINGS["IDEA"]
RELATION_HARD = HARD_CEILINGS["RELATION"]

CONSOLIDATION_GUARD = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS
ROUTE_DIRECT_GLOBAL = "DIRECT_GLOBAL"
ROUTE_REGIONAL_THEN_GLOBAL = "REGIONAL_THEN_GLOBAL"

REGIONAL_CONTRACT_VERSION = "regional-consolidation-1.0"
REGIONAL_REUSES_CONSOLIDATION_10_TRANSPORT = True
REGIONAL_ALLOWS_GLOBAL_METADATA = False
REGIONAL_ID_WIDTH = 3
REGIONAL_RECORD_INDEX_WIDTH = 4
MAX_HIERARCHY_DEPTH = 2
MAX_SEMANTIC_CONSOLIDATION_LEVELS = 2

EXPECTED_CLEAN_WINDOW_COUNT = 7
EXPECTED_PRESENT_SRC = 8298
EXPECTED_WORD_COUNT = 38313
EXPECTED_DURATION_SECONDS = 19954.601
EXPECTED_REMOVED_SRC = 117
EXPECTED_TRANSCRIPT_ID = "TR001"
EXPECTED_INPUT_MODE = "DERIVED"

PHASE_3B_STATUS = "INCOMPLETE"
PROJECT_STATE = "INCOMPLETE"
NEXT_ACTION = "HUMAN REVIEW"
NEXT_PHASE = "3B.7.7A.8"
NEXT_PHASE_LABEL = (
    "3B.7.7A.8 — SMALL-WINDOW PRODUCTION READINESS & STAGED REAL-CALL PLAN "
    "— OFFLINE ONLY"
)

PLAN_ARTIFACT = "source_analysis_small_window_plan_v21.json"
ROUTER_ARTIFACT = "source_analysis_adaptive_consolidation_router.json"
DIRECT_FAKEAI_ARTIFACT = "source_analysis_small_window_direct_global_fake_ai.json"
HIERARCHICAL_FAKEAI_ARTIFACT = "source_analysis_small_window_hierarchical_fake_ai.json"
TRACEABILITY_ARTIFACT = "source_analysis_hierarchical_traceability_validation.json"
PREFLIGHT_ARTIFACT = "source_analysis_small_window_real_preflight.json"
REPORT_NAME = "PHASE_3B77A7_SMALL_WINDOW_ADAPTIVE_HIERARCHY_IMPLEMENTATION_REPORT.md"

PROTECTED_EVIDENCE = PROTECTED_EVIDENCE_A6 + (
    "audit/PHASE_3B77A6_POST_CANARY_ARCHITECTURE_DECISION_REPORT.md",
    "audit/source_analysis_post_canary_architecture_decision.json",
    "audit/source_analysis_post_canary_window_size_simulations.json",
    "audit/source_analysis_post_canary_architecture_options.json",
    "audit/source_analysis_post_canary_consolidation_scaling.json",
    "audit/source_analysis_post_canary_architecture_cost_scenarios.json",
)

CALL1_COST_USD = "0.533946"
CALL2_COST = "UNKNOWN"

WINDOW_CONTENT_BINDING = (
    "window_input_hash binds planner_version + window_id + owned SRC ids "
    "+ context SRC ids + owned_content_sha256 + context_content_sha256. "
    "WindowAnalysisSignature includes window_input_hash, prompt SHA, "
    "provider/model/config. WIN001 label alone is never a cache key."
)

__all__ = [
    "CANDIDATE_CONTEXT_POLICY",
    "CANDIDATE_HARD_MAX_INPUT_TOKENS",
    "CANDIDATE_OVERLAP_POLICY",
    "CANDIDATE_PLANNER_VERSION",
    "CANDIDATE_TARGET_INPUT_TOKENS",
    "CONSOLIDATION_GUARD",
    "IMPLEMENTATION_MODE",
    "MAX_HIERARCHY_DEPTH",
    "MAX_OUTPUT_FROZEN",
    "MODE",
    "NEXT_PHASE",
    "NEXT_PHASE_LABEL",
    "PHASE",
    "PHASE_3B_STATUS",
    "PRODUCTION_PLANNER_VERSION",
    "PROJECT_NAME",
    "REGIONAL_ALLOWS_GLOBAL_METADATA",
    "REGIONAL_CONTRACT_VERSION",
    "REPORT_NAME",
    "ROUTE_DIRECT_GLOBAL",
    "ROUTE_REGIONAL_THEN_GLOBAL",
    "SCHEMA_VERSION",
    "WINDOW_CONTENT_BINDING",
    "WINDOW_PROMPT_VERSION",
]
