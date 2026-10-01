"""Constantes 3B.7.7A.31 — trois fenêtres finales v3.1-local-lite. 3 appels max."""

from __future__ import annotations

from app.source_analysis.models import IDEA_KINDS, IMPORTANCE_LEVELS
from app.source_analysis.window_models import (
    WINDOW_CONNECT_TIMEOUT_SECONDS,
    WINDOW_READ_TIMEOUT_SECONDS,
)
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.constants import (
    CANDIDATE_PLANNER_VERSION,
    CLEAN_SHA,
    GRANULARITY_POLICY_VERSION,
    GRANULARITY_POLICY_VERSION_12_KIND_SPECIFIC,
    MAX_OUTPUT_TOKENS_FROZEN,
    PROJECT_NAME,
)
from app.source_analysis_local_v2.granularity import (
    EXAMPLE_V_TEXT_HARD_LIMIT,
    IDEA_V_TEXT_HARD_LIMIT,
    TEXT_HARD_LIMITS,
    THEME_TEXT_HARD_LIMIT,
    V11_MINIMAL_TEXT_HARD_LIMITS,
)
from app.source_analysis_local_v3.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    SEMANTIC_TRANSPORT_VERSION_V3,
    SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
    WINDOW_ANALYSIS_PROMPT_VERSION_V132,
    WINDOW_ANALYSIS_PROMPT_VERSION_V140,
)
from app.source_analysis_local_v3.schema import (
    semantic_transport_v3_fingerprint,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis_thinking_contract.constants import (
    SELECTED_CONTRACT,
    SELECTED_EFFORT,
    SELECTED_THINKING_MODE,
)
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    A17_SCHEMA_FINGERPRINT,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
)
from app.source_analysis_v3_second_window.constants import EXPECTED_SCHEMA_HASH
from app.source_analysis_v31_kind_specific_limits.constants import (
    A28_HISTORICAL_STATUS,
    A29_STATUS,
    CURRENT_GRANULARITY_POLICY,
    READY_AFTER_COUNT_IF_PROMOTED as A30_READY_COUNT,
    READY_AFTER_IF_PROMOTED as A30_READY,
    REPORT_NAME as A30_REPORT_NAME,
    WIN003_PROMOTION_LABEL,
    WIN003_NEW_PROVIDER_CALL,
)
from app.source_analysis_v31_length_ceiling.constants import REPORT_NAME as A29_REPORT_NAME
from app.source_analysis_v31_real_win004.constants import (
    AUTHORIZATION_SCOPE as A27_AUTHORIZATION_SCOPE,
    EXPECTED_PROMPT_SHA256,
    REPORT_NAME as A27_REPORT_NAME,
    WINDOW_ID as A27_WINDOW_ID,
)
from app.source_analysis_v31_remaining_windows.constants import (
    A19_RESULT,
    A21_RESULT,
    A22_RESULT,
    A23_RESULT,
    A24_RESULT,
    A25_RESULT,
    A26_RESULT,
    A261_RESULT,
    A27_RESULT,
    AUTHORIZATION_SCOPE as A28_AUTHORIZATION_SCOPE,
    REPORT_NAME as A28_REPORT_NAME,
    WINDOW_SPECS,
)
from app.source_analysis_v31_kind_specific_limits.constants import (
    PROTECTED_HISTORICAL as A30_PROTECTED_HISTORICAL,
)
from app.source_analysis_v3_hardened_win001.constants import (
    AUTHORIZATION_SCOPE as A21_AUTHORIZATION_SCOPE,
    WINDOW_ID as A21_WINDOW_ID,
)
from app.source_analysis_v3_second_window.constants import (
    AUTHORIZATION_SCOPE as A22_AUTHORIZATION_SCOPE,
)
from app.source_analysis_v3_hardened_win004.constants import (
    AUTHORIZATION_SCOPE as A24_AUTHORIZATION_SCOPE,
)

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.7A.31"
MODE = "FINAL_THREE_REAL_LOCAL_LITE_WINDOWS"

AUTHORIZATION_SCOPE = "FINAL_V31_LOCAL_LITE_WIN005_WIN006_WIN007_ONLY"
AUTHORIZED_WINDOW_IDS = ("WIN005", "WIN006", "WIN007")
EXECUTION_ORDER = AUTHORIZED_WINDOW_IDS
FORBIDDEN_WINDOW_IDS = ("WIN001", "WIN002", "WIN003", "WIN004", "WIN996")
READY_BEFORE = "4 / 7"
READY_BEFORE_COUNT = 4
TOTAL_WINDOWS = 7
HISTORICAL_READY_IDS = ("WIN001", "WIN002", "WIN003", "WIN004")

PROVIDER = "anthropic"
MODEL = "claude-sonnet-5"
THINKING_CONTRACT = SELECTED_CONTRACT
THINKING_MODE = SELECTED_THINKING_MODE
EFFORT = SELECTED_EFFORT

MAX_ENGINE_GENERATE_PER_WINDOW = 1
MAX_ANTHROPIC_POST_PER_WINDOW = 1
MAX_ENGINE_GENERATE = 3
MAX_ANTHROPIC_POST = 3
MAX_ATTEMPTS = 1
AUTO_RETRY = False
AUTO_FALLBACK = False
AUTO_CONTINUE = False

MAX_OUTPUT_TOKENS = MAX_OUTPUT_TOKENS_FROZEN
CONNECT_TIMEOUT_SECONDS = WINDOW_CONNECT_TIMEOUT_SECONDS
READ_TIMEOUT_SECONDS = WINDOW_READ_TIMEOUT_SECONDS
HISTORICAL_READ_TIMEOUT_SECONDS = 7200.0

A28_RESULT = A28_HISTORICAL_STATUS
A29_RESULT = A29_STATUS
A30_RESULT = "PASS"

WIN003_PROVENANCE = {
    "origin_phase": "A.28",
    "origin": "A.28 provider response",
    "revalidated_phase": "A.30",
    "revalidated_under": GRANULARITY_POLICY_VERSION_12_KIND_SPECIFIC,
    "new_a30_provider_generation": WIN003_NEW_PROVIDER_CALL,
    "label": WIN003_PROMOTION_LABEL,
}

EXPECTED_PROMPT_SHA256 = EXPECTED_PROMPT_SHA256
EXPECTED_SCHEMA_HASH = EXPECTED_SCHEMA_HASH
EXPECTED_CLEAN_SHA = CLEAN_SHA
EXPECTED_CLEAN_FILE_SHA = CLEAN_SHA
CANDIDATE_HARD_MAX_INPUT_TOKENS = CANDIDATE_HARD_MAX_INPUT_TOKENS

IMPORTANCE_VOCABULARY = IMPORTANCE_LEVELS
IDEA_SUBTYPE_TOKENS = IDEA_KINDS + ("example",)
OLD_V3_IDEA_SHAPE = ("claim", "primary")

LOCK_NAME = "a31_real_v31_local_lite_final_three.lock"
CANARY_SUBDIR = "canary/v31_local_lite_final_three"
CANDIDATE_WINDOWS_SUBDIR = "v31_windows"
CANDIDATE_CACHE_SUBDIR = "v31_cache"

BASELINE_ARTIFACT = "source_analysis_v31_a31_test_baseline.json"
PREFLIGHT_ARTIFACT = "source_analysis_v31_final_three_preflight.json"
RELATION_CROSS_ARTIFACT = "source_analysis_v31_relation_quality_ready_windows.json"
READY_STATE_ARTIFACT = "source_analysis_ready_windows_after_a31.json"
POST_TEST_ARTIFACT = "source_analysis_v31_a31_test_delta.json"
INVENTORY_ARTIFACT = "source_analysis_global_consolidation_input_inventory.json"
REPORT_NAME = "PHASE_3B77A31_FINAL_THREE_REAL_LOCAL_LITE_WINDOWS_REPORT.md"

SEMANTIC_REVIEW_STATUS = (
    "FORENSIC_SEMANTIC_REVIEW_OF_VALID_V31_LOCAL_LITE_FINAL_WINDOW"
)
SEMANTIC_REVIEW_INVALID = "FORENSIC_SEMANTIC_REVIEW_OF_INVALID_V31_LOCAL_LITE_TRANSPORT"
SERVER_GRAMMAR_STATUS = "A18_PROOF_APPLICABLE"
SUBTYPE_FAILURE_CLASS_IF_PASS = "ELIMINATED_BY_ARCHITECTURE"
RELATION_QUALITY_TECHNICAL_DEBT = "YES"

PROTECTED_A30 = (
    f"audit/{A30_REPORT_NAME}",
    "audit/source_analysis_ready_windows_after_a30.json",
    "audit/source_analysis_kind_specific_length_policy.json",
    "audit/source_analysis_a30_schema_identity.json",
    "audit/source_analysis_win003_saved_response_revalidation.json",
    "audit/source_analysis_win003_revalidation_provenance.json",
    "audit/source_analysis_win005_007_post_policy_preflight.json",
    f"audit/{A29_REPORT_NAME}",
    f"audit/{A28_REPORT_NAME}",
    "audit/source_analysis_v31_WIN002_execution.json",
    "audit/source_analysis_v31_WIN003_execution.json",
    "audit/source_analysis_v31_relation_quality_cross_window.json",
    "audit/source_analysis_v31_ready_windows_state.json",
)
PROTECTED_HISTORICAL = tuple(A30_PROTECTED_HISTORICAL) + PROTECTED_A30

DRY_RUN_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_v31_final_three "
    "pastoral_retreat_v2_validation "
    "--authorization-scope FINAL_V31_LOCAL_LITE_WIN005_WIN006_WIN007_ONLY "
    "--dry-run"
)
REAL_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_v31_final_three "
    "pastoral_retreat_v2_validation "
    "--authorization-scope FINAL_V31_LOCAL_LITE_WIN005_WIN006_WIN007_ONLY "
    "--execute-real"
)

FOCUSED_TEST_PATHS = (
    "app/tests/test_source_analysis_v31_kind_specific_limits.py",
    "app/tests/test_source_analysis_v31_kind_specific_limits_audit.py",
    "app/tests/test_source_analysis_v31_length_ceiling.py",
    "app/tests/test_source_analysis_v31_length_ceiling_audit.py",
    "app/tests/test_source_analysis_v31_remaining_windows.py",
    "app/tests/test_source_analysis_v31_remaining_windows_audit.py",
    "app/tests/test_source_analysis_v31_real_win004.py",
    "app/tests/test_source_analysis_v31_real_win004_audit.py",
    "app/tests/test_source_analysis_v31_local_lite.py",
    "app/tests/test_source_analysis_v31_final_three.py",
    "app/tests/test_source_analysis_v31_final_three_audit.py",
)

NEXT_ACTION = "HUMAN REVIEW"
NEXT_PHASE = "3B.7.7A.32_OFFLINE_GLOBAL_CONSOLIDATION_PREFLIGHT_DESIGN"
NEXT_PHASE_LABEL = (
    "OFFLINE GLOBAL CONSOLIDATION PREFLIGHT / DESIGN VALIDATION "
    "(not real consolidation; not authorized here)"
)
PHASE_3B_STATUS = "INCOMPLETE"
PRODUCTION_PLANNER_VERSION = PLANNER_VERSION
CANDIDATE_PLANNER = CANDIDATE_PLANNER_VERSION
PROMPT_VERSION = WINDOW_ANALYSIS_PROMPT_VERSION_V140
TRANSPORT_VERSION = SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE
GRANULARITY_POLICY = GRANULARITY_POLICY_VERSION_12_KIND_SPECIFIC
SELECTED_ARCHITECTURE = "GLOBALIZE_IDEA_SUBTYPE"


def window_artifact(window_id: str, kind: str) -> str:
    if kind == "length_policy":
        return f"source_analysis_v31_{window_id}_length_policy.json"
    return f"source_analysis_v31_{window_id}_a31_{kind}.json"


assert EXPECTED_SCHEMA_HASH == (
    "de42ce0f3c271e67b902a94d2f528eae56f82b1a2a5740e65161987038849425"
)
assert semantic_transport_v31_local_lite_fingerprint() == EXPECTED_SCHEMA_HASH
assert semantic_transport_v3_fingerprint() == EXPECTED_SCHEMA_HASH
assert A17_SCHEMA_FINGERPRINT == EXPECTED_SCHEMA_HASH
assert EXPECTED_RAW_SCHEMA_BYTES == 588
assert EXPECTED_ADAPTED_SCHEMA_BYTES == 650
assert MAX_OUTPUT_TOKENS == 32000
assert THINKING_MODE == "disabled"
assert EFFORT is None
assert AUTHORIZATION_SCOPE == "FINAL_V31_LOCAL_LITE_WIN005_WIN006_WIN007_ONLY"
assert AUTHORIZATION_SCOPE != A21_AUTHORIZATION_SCOPE
assert AUTHORIZATION_SCOPE != A22_AUTHORIZATION_SCOPE
assert AUTHORIZATION_SCOPE != A24_AUTHORIZATION_SCOPE
assert AUTHORIZATION_SCOPE != A27_AUTHORIZATION_SCOPE
assert AUTHORIZATION_SCOPE != A28_AUTHORIZATION_SCOPE
assert A27_WINDOW_ID == "WIN004"
assert A21_WINDOW_ID == "WIN001"
assert READY_BEFORE_COUNT == A30_READY_COUNT == 4
assert READY_BEFORE == A30_READY == "4 / 7"
assert WINDOW_SPECS["WIN005"]["local_input_estimate"] == 23023
assert WINDOW_SPECS["WIN006"]["local_input_estimate"] == 23025
assert WINDOW_SPECS["WIN007"]["local_input_estimate"] == 23038
assert A19_RESULT == "FAIL"
assert A21_RESULT == "PASS"
assert A22_RESULT == "FAIL"
assert A23_RESULT == "PASS"
assert A24_RESULT == "FAIL"
assert A25_RESULT == "PARTIAL"
assert A26_RESULT == "PASS"
assert A261_RESULT == "PASS"
assert A27_RESULT == "PASS"
assert A28_RESULT == "FAIL"
assert A29_RESULT == "PASS"
assert A30_RESULT == "PASS"
assert WIN003_NEW_PROVIDER_CALL is False
assert PROMPT_VERSION == "window-analysis-1.4.0"
assert TRANSPORT_VERSION == "semantic-transport-v3.1-local-lite"
assert GRANULARITY_POLICY == "window-granularity-1.2-kind-specific"
assert GRANULARITY_POLICY_VERSION == "window-granularity-1.1-minimal"
assert CURRENT_GRANULARITY_POLICY == GRANULARITY_POLICY
assert THEME_TEXT_HARD_LIMIT == 225
assert EXAMPLE_V_TEXT_HARD_LIMIT == 225
assert IDEA_V_TEXT_HARD_LIMIT == 280
assert TEXT_HARD_LIMITS["theme"] == 225
assert TEXT_HARD_LIMITS["TOPIC.v"] == 80
assert TEXT_HARD_LIMITS["IDEA.v"] == 280
assert TEXT_HARD_LIMITS["RELATION.v"] == 40
assert TEXT_HARD_LIMITS["EXAMPLE.v"] == 225
assert TEXT_HARD_LIMITS["REFERENCE.v"] == 220
assert TEXT_HARD_LIMITS["UNCERTAINTY.v"] == 280
assert V11_MINIMAL_TEXT_HARD_LIMITS["theme"] == 200
assert V11_MINIMAL_TEXT_HARD_LIMITS["EXAMPLE.v"] == 200
assert WINDOW_ANALYSIS_PROMPT_VERSION_V13 == "window-analysis-1.3"
assert WINDOW_ANALYSIS_PROMPT_VERSION_V131 == "window-analysis-1.3.1"
assert WINDOW_ANALYSIS_PROMPT_VERSION_V132 == "window-analysis-1.3.2"
assert not set(IDEA_KINDS) & set(IMPORTANCE_LEVELS)
assert EXECUTION_ORDER == ("WIN005", "WIN006", "WIN007")
assert SEMANTIC_TRANSPORT_VERSION_V3 == "semantic-transport-v3"

__all__ = [
    "A19_RESULT",
    "A21_AUTHORIZATION_SCOPE",
    "A21_RESULT",
    "A21_WINDOW_ID",
    "A22_AUTHORIZATION_SCOPE",
    "A22_RESULT",
    "A23_RESULT",
    "A24_AUTHORIZATION_SCOPE",
    "A24_RESULT",
    "A25_RESULT",
    "A26_RESULT",
    "A261_RESULT",
    "A27_AUTHORIZATION_SCOPE",
    "A27_REPORT_NAME",
    "A27_RESULT",
    "A27_WINDOW_ID",
    "A28_AUTHORIZATION_SCOPE",
    "A28_REPORT_NAME",
    "A28_RESULT",
    "A29_REPORT_NAME",
    "A29_RESULT",
    "A30_REPORT_NAME",
    "A30_RESULT",
    "AUTHORIZATION_SCOPE",
    "AUTHORIZED_WINDOW_IDS",
    "AUTO_CONTINUE",
    "AUTO_FALLBACK",
    "AUTO_RETRY",
    "BASELINE_ARTIFACT",
    "CANARY_SUBDIR",
    "CANDIDATE_CACHE_SUBDIR",
    "CANDIDATE_HARD_MAX_INPUT_TOKENS",
    "CANDIDATE_PLANNER",
    "CANDIDATE_WINDOWS_SUBDIR",
    "CONNECT_TIMEOUT_SECONDS",
    "DRY_RUN_COMMAND",
    "EFFORT",
    "EXAMPLE_V_TEXT_HARD_LIMIT",
    "EXECUTION_ORDER",
    "EXPECTED_ADAPTED_SCHEMA_BYTES",
    "EXPECTED_CLEAN_FILE_SHA",
    "EXPECTED_CLEAN_SHA",
    "EXPECTED_PROMPT_SHA256",
    "EXPECTED_RAW_SCHEMA_BYTES",
    "EXPECTED_SCHEMA_HASH",
    "FOCUSED_TEST_PATHS",
    "FORBIDDEN_WINDOW_IDS",
    "GRANULARITY_POLICY",
    "GRANULARITY_POLICY_VERSION",
    "HISTORICAL_READY_IDS",
    "HISTORICAL_READ_TIMEOUT_SECONDS",
    "IDEA_SUBTYPE_TOKENS",
    "IDEA_V_TEXT_HARD_LIMIT",
    "IMPORTANCE_VOCABULARY",
    "INVENTORY_ARTIFACT",
    "LOCK_NAME",
    "MAX_ANTHROPIC_POST",
    "MAX_ANTHROPIC_POST_PER_WINDOW",
    "MAX_ATTEMPTS",
    "MAX_ENGINE_GENERATE",
    "MAX_ENGINE_GENERATE_PER_WINDOW",
    "MAX_OUTPUT_TOKENS",
    "MODE",
    "MODEL",
    "NEXT_ACTION",
    "NEXT_PHASE",
    "NEXT_PHASE_LABEL",
    "OLD_V3_IDEA_SHAPE",
    "PHASE",
    "PHASE_3B_STATUS",
    "POST_TEST_ARTIFACT",
    "PREFLIGHT_ARTIFACT",
    "PRODUCTION_PLANNER_VERSION",
    "PROJECT_NAME",
    "PROMPT_VERSION",
    "PROTECTED_HISTORICAL",
    "PROVIDER",
    "READ_TIMEOUT_SECONDS",
    "READY_BEFORE",
    "READY_BEFORE_COUNT",
    "READY_STATE_ARTIFACT",
    "REAL_COMMAND",
    "RELATION_CROSS_ARTIFACT",
    "RELATION_QUALITY_TECHNICAL_DEBT",
    "REPORT_NAME",
    "SCHEMA_VERSION",
    "SELECTED_ARCHITECTURE",
    "SEMANTIC_REVIEW_INVALID",
    "SEMANTIC_REVIEW_STATUS",
    "SEMANTIC_TRANSPORT_VERSION_V3",
    "SERVER_GRAMMAR_STATUS",
    "SUBTYPE_FAILURE_CLASS_IF_PASS",
    "TEXT_HARD_LIMITS",
    "THEME_TEXT_HARD_LIMIT",
    "THINKING_CONTRACT",
    "THINKING_MODE",
    "TOTAL_WINDOWS",
    "TRANSPORT_VERSION",
    "V11_MINIMAL_TEXT_HARD_LIMITS",
    "WIN003_PROVENANCE",
    "WINDOW_ANALYSIS_PROMPT_VERSION_V140",
    "WINDOW_SPECS",
    "window_artifact",
]
