"""Constantes 3B.7.7A.28 — cinq fenêtres restantes v3.1-local-lite. 5 appels max."""

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
    MAX_OUTPUT_TOKENS_FROZEN,
    PROJECT_NAME,
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
from app.source_analysis_output_ceiling_review.constants import (
    CALL1_SIGNATURE,
    CALL2_SIGNATURE,
    SMALL_SIGNATURE,
)
from app.source_analysis_small_window_hierarchy.constants import (
    CANDIDATE_CONTEXT_POLICY,
)
from app.source_analysis_small_window_readiness.constants import A7_EXPECTED_WINDOWS
from app.source_analysis_thinking_contract.constants import (
    SELECTED_CONTRACT,
    SELECTED_EFFORT,
    SELECTED_THINKING_MODE,
)
from app.source_analysis_v2_a15_forensics.constants import A15_SIGNATURE
from app.source_analysis_v2_link_semantics.constants import A13_REQUEST_IDENTITY
from app.source_analysis_v3_a19_forensics.constants import (
    A19_STATUS_UNCHANGED,
    EXAMPLE_POLICY,
    EXAMPLE_POLICY_LABEL,
    V3_HANDLE_ARCHITECTURE,
)
from app.source_analysis_v3_a22_forensics.constants import (
    A21_RESULT,
    A22_SIGNATURE,
    A22_STATUS_UNCHANGED,
    REPORT_NAME as A23_REPORT_NAME,
)
from app.source_analysis_v3_a25_forensics.constants import (
    A23_STATUS,
    A24_FORENSIC_IDENTITY,
    A24_SIGNATURE,
    A24_STATUS_UNCHANGED,
    PROTECTED_HISTORICAL as A25_PROTECTED_HISTORICAL,
    REPORT_NAME as A25_REPORT_NAME,
)
from app.source_analysis_v3_hardened_win001.constants import (
    AUTHORIZATION_SCOPE as A21_AUTHORIZATION_SCOPE,
    EXPECTED_ANALYSIS_SIGNATURE as A21_SIGNATURE,
    EXPECTED_FORENSIC_IDENTITY as A21_FORENSIC,
    WINDOW_ID as A21_WINDOW_ID,
)
from app.source_analysis_v3_real_win001.constants import (
    EXPECTED_A18_REQUEST_IDENTITY,
    EXPECTED_ANALYSIS_SIGNATURE as A19_SIGNATURE,
    EXPECTED_FORENSIC_IDENTITY as A19_FORENSIC,
)
from app.source_analysis_v3_second_window.constants import (
    AUTHORIZATION_SCOPE as A22_AUTHORIZATION_SCOPE,
    EXPECTED_SCHEMA_HASH,
    EXPECTED_WIN004_FIRST_OWNED_SRC,
    EXPECTED_WIN004_INPUT_HASH,
    EXPECTED_WIN004_LAST_OWNED_SRC,
    EXPECTED_WIN004_OWNED_SRC_COUNT,
    EXPECTED_WIN004_WORD_COUNT,
)
from app.source_analysis_v3_hardened_win004.constants import (
    AUTHORIZATION_SCOPE as A24_AUTHORIZATION_SCOPE,
)
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    A17_SCHEMA_FINGERPRINT,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
)
from app.source_analysis_v31_local_lite.constants import (
    A25_STATUS,
    FUTURE_ARTIFACT as A26_FUTURE_ARTIFACT,
    REPORT_NAME as A26_REPORT_NAME,
)
from app.source_analysis_v31_schema_boundary.constants import (
    A26_STATUS,
    REPORT_NAME as A261_REPORT_NAME,
)
from app.source_analysis_v31_real_win004.constants import (
    AUTHORIZATION_SCOPE as A27_AUTHORIZATION_SCOPE,
    EXPECTED_ANALYSIS_SIGNATURE as A27_SIGNATURE,
    EXPECTED_FORENSIC_IDENTITY as A27_FORENSIC,
    EXPECTED_LOCAL_INPUT_ESTIMATE as A27_LOCAL_INPUT,
    EXPECTED_PROMPT_FINGERPRINT as A27_PROMPT_FINGERPRINT,
    EXPECTED_PROMPT_SHA256,
    REPORT_NAME as A27_REPORT_NAME,
    WINDOW_ID as A27_WINDOW_ID,
)

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.7A.28"
MODE = "REMAINING_FIVE_REAL_LOCAL_LITE_WINDOWS"

AUTHORIZATION_SCOPE = "SMALL_V21_V31_LOCAL_LITE_REMAINING_FIVE_ONLY"
AUTHORIZED_WINDOW_IDS = ("WIN002", "WIN003", "WIN005", "WIN006", "WIN007")
EXECUTION_ORDER = AUTHORIZED_WINDOW_IDS
FORBIDDEN_WINDOW_IDS = ("WIN001", "WIN004", "WIN996")
READY_BEFORE = "2 / 7"
READY_BEFORE_COUNT = 2
TOTAL_WINDOWS = 7

PROVIDER = "anthropic"
MODEL = "claude-sonnet-5"
THINKING_CONTRACT = SELECTED_CONTRACT
THINKING_MODE = SELECTED_THINKING_MODE
EFFORT = SELECTED_EFFORT

MAX_ENGINE_GENERATE_PER_WINDOW = 1
MAX_ANTHROPIC_POST_PER_WINDOW = 1
MAX_ENGINE_GENERATE = 5
MAX_ANTHROPIC_POST = 5
MAX_ATTEMPTS = 1
AUTO_RETRY = False
AUTO_FALLBACK = False
AUTO_CONTINUE = False

MAX_OUTPUT_TOKENS = MAX_OUTPUT_TOKENS_FROZEN
CONNECT_TIMEOUT_SECONDS = WINDOW_CONNECT_TIMEOUT_SECONDS
READ_TIMEOUT_SECONDS = WINDOW_READ_TIMEOUT_SECONDS
HISTORICAL_READ_TIMEOUT_SECONDS = 7200.0

_A7 = {item["window_id"]: item for item in A7_EXPECTED_WINDOWS}

WINDOW_SPECS = {
    "WIN001": {
        "first_owned_src": _A7["WIN001"]["first_present_src"],
        "last_owned_src": _A7["WIN001"]["last_present_src"],
        "owned_src_count": _A7["WIN001"]["owned_src_count"],
        "word_count": _A7["WIN001"]["word_count"],
        "input_hash": "0c656a1158d2ba2bdbd559bd06aa3f48f5e3e5a81caa26398db9c162b3ddbc18",
        "local_input_estimate": 23041,
        "analysis_signature": (
            "e9458ff2661061a54f388eda7d5a95221cc00ba49504b4c284e43cdb0dd8d9c9"
        ),
        "forensic_identity": (
            "183c7879dd8dcde371c820b62b0add0916699571c46780641a204578565262b2"
        ),
        "prompt_fingerprint": (
            "dd0e80ae711e7c661cc20b0c08d0f1c8c9ae2829260dcbf99f8ea69c407eb1f0"
        ),
        "authorized": False,
        "ready": True,
    },
    "WIN002": {
        "first_owned_src": _A7["WIN002"]["first_present_src"],
        "last_owned_src": _A7["WIN002"]["last_present_src"],
        "owned_src_count": _A7["WIN002"]["owned_src_count"],
        "word_count": _A7["WIN002"]["word_count"],
        "input_hash": "42a7ea9c825e9a4b07efdbdc3a33c18ec8a332c75902d54ac4352f43527cd6d8",
        "local_input_estimate": 23047,
        "analysis_signature": (
            "e9ce8ad1907964b02dc22b2e156b7112f4e1b02dc2b77e16771764434911ef65"
        ),
        "forensic_identity": (
            "224897610f252cdd5952c77ff231aad476b7577aea1cf9a1772f067bd5f3cf6f"
        ),
        "prompt_fingerprint": (
            "8e508c72fc8835635eb7928653dd5a95446db4c917a9ac375ff381d8db71bce0"
        ),
        "authorized": True,
        "ready": False,
    },
    "WIN003": {
        "first_owned_src": _A7["WIN003"]["first_present_src"],
        "last_owned_src": _A7["WIN003"]["last_present_src"],
        "owned_src_count": _A7["WIN003"]["owned_src_count"],
        "word_count": _A7["WIN003"]["word_count"],
        "input_hash": "470acd1446acdd87ff3d2b1ea75d160c8a0889e32716601e3bf71906fa93ae22",
        "local_input_estimate": 23023,
        "analysis_signature": (
            "597b2a48664392bcbcba85a12adae3c294c57ca4025dca078497a787f4d776d7"
        ),
        "forensic_identity": (
            "dc19ab1d890d3ec006f105cbb90b5b68ae8ddfd944a86bba28b35e354a81dec2"
        ),
        "prompt_fingerprint": (
            "7ac399249817ca224a3eea71fc1419c1932671ceae5f7c37795e3abfe5625d5b"
        ),
        "authorized": True,
        "ready": False,
    },
    "WIN004": {
        "first_owned_src": EXPECTED_WIN004_FIRST_OWNED_SRC,
        "last_owned_src": EXPECTED_WIN004_LAST_OWNED_SRC,
        "owned_src_count": EXPECTED_WIN004_OWNED_SRC_COUNT,
        "word_count": EXPECTED_WIN004_WORD_COUNT,
        "input_hash": EXPECTED_WIN004_INPUT_HASH,
        "local_input_estimate": A27_LOCAL_INPUT,
        "analysis_signature": A27_SIGNATURE,
        "forensic_identity": A27_FORENSIC,
        "prompt_fingerprint": A27_PROMPT_FINGERPRINT,
        "authorized": False,
        "ready": True,
    },
    "WIN005": {
        "first_owned_src": _A7["WIN005"]["first_present_src"],
        "last_owned_src": _A7["WIN005"]["last_present_src"],
        "owned_src_count": _A7["WIN005"]["owned_src_count"],
        "word_count": _A7["WIN005"]["word_count"],
        "input_hash": "b9705f4d2560f2d86bae030f3b2f2421a7f560024dd2d4ee8a2d97828e4f818e",
        "local_input_estimate": 23023,
        "analysis_signature": (
            "07c0ff44a80090d6d15c2221909222c23771a539a7d9dc9bc35d0ff8210db91c"
        ),
        "forensic_identity": (
            "1a79e974d3db9e309a3923e9051373c22d2bfedaf3e1a9240a6454e581141223"
        ),
        "prompt_fingerprint": (
            "7b20cad842751201c67a9e6b8d93586d8d65d298efdde8fa70c68c584a88a9ed"
        ),
        "authorized": True,
        "ready": False,
    },
    "WIN006": {
        "first_owned_src": _A7["WIN006"]["first_present_src"],
        "last_owned_src": _A7["WIN006"]["last_present_src"],
        "owned_src_count": _A7["WIN006"]["owned_src_count"],
        "word_count": _A7["WIN006"]["word_count"],
        "input_hash": "887d18dae76e4e04e40f5404d4264c1826ecb0dc41c334999242014e0a5ba142",
        "local_input_estimate": 23025,
        "analysis_signature": (
            "ba16f79a5e2e9949f13a2f6bc5bd214645d49d8aa25790797f9e3806a985b120"
        ),
        "forensic_identity": (
            "325f496b3360b571581f7de0af6035bf10e6ada54c0703e819b8137beb65f506"
        ),
        "prompt_fingerprint": (
            "069be49ff88f5b6af7ad93ceff1c2860d819da688eaea58c343e36232cd6ab6f"
        ),
        "authorized": True,
        "ready": False,
    },
    "WIN007": {
        "first_owned_src": _A7["WIN007"]["first_present_src"],
        "last_owned_src": _A7["WIN007"]["last_present_src"],
        "owned_src_count": _A7["WIN007"]["owned_src_count"],
        "word_count": _A7["WIN007"]["word_count"],
        "input_hash": "2aabe1f379eb443f3184d7894c08cca24a5452a30c7af16084ceb0b9d3624b08",
        "local_input_estimate": 23038,
        "analysis_signature": (
            "95b979ca7e535c9da0ca0a109fe0c2e16e312434855b9c311df684cbb8a4b4e9"
        ),
        "forensic_identity": (
            "260e863ab55cdfe9000cd609512403f2cc9d1b43ad290ffbf22f7932cc372c4e"
        ),
        "prompt_fingerprint": (
            "b812516a45dd05cf5a5e9f2bbcd172405ec97aacf9aeb76c5b5f8e2c08be4137"
        ),
        "authorized": True,
        "ready": False,
    },
}

EXPECTED_PROMPT_SHA256 = EXPECTED_PROMPT_SHA256
EXPECTED_SCHEMA_HASH = EXPECTED_SCHEMA_HASH
EXPECTED_CLEAN_SHA = CLEAN_SHA
EXPECTED_CLEAN_FILE_SHA = CLEAN_SHA
EXPECTED_CONTEXT_COUNT = 0
EXPECTED_CONTEXT_POLICY = CANDIDATE_CONTEXT_POLICY

A13_SYNTHETIC_IDENTITY = A13_REQUEST_IDENTITY
A15_V2_SIGNATURE = A15_SIGNATURE
A18_REQUEST_IDENTITY = EXPECTED_A18_REQUEST_IDENTITY
A19_V3_SIGNATURE = A19_SIGNATURE
A19_V3_FORENSIC = A19_FORENSIC
A19_RESULT = A19_STATUS_UNCHANGED
A21_V3_SIGNATURE = A21_SIGNATURE
A21_V3_FORENSIC = A21_FORENSIC
A21_RESULT = A21_RESULT
A22_V3_SIGNATURE = A22_SIGNATURE
A22_RESULT = A22_STATUS_UNCHANGED
A23_RESULT = A23_STATUS
A24_V3_SIGNATURE = A24_SIGNATURE
A24_V3_FORENSIC = A24_FORENSIC_IDENTITY
A24_RESULT = A24_STATUS_UNCHANGED
A25_RESULT = A25_STATUS
A26_RESULT = A26_STATUS
A261_RESULT = "PASS"
A27_RESULT = "PASS"
A27_V31_SIGNATURE = A27_SIGNATURE
A27_V31_FORENSIC = A27_FORENSIC

IMPORTANCE_VOCABULARY = IMPORTANCE_LEVELS
IDEA_SUBTYPE_TOKENS = IDEA_KINDS + ("example",)
OLD_V3_IDEA_SHAPE = ("claim", "primary")
A24_INVALID_IDEA_SHAPE = ("example", "supporting")

LOCK_NAME = "a28_real_v31_local_lite_remaining.lock"
CANARY_SUBDIR = "canary/v31_local_lite_remaining"
CANDIDATE_WINDOWS_SUBDIR = "v31_windows"
CANDIDATE_CACHE_SUBDIR = "v31_cache"

BASELINE_ARTIFACT = "source_analysis_v31_remaining_windows_test_baseline.json"
PREFLIGHT_ARTIFACT = "source_analysis_v31_remaining_windows_preflight.json"
RELATION_CROSS_ARTIFACT = "source_analysis_v31_relation_quality_cross_window.json"
READY_STATE_ARTIFACT = "source_analysis_v31_ready_windows_state.json"
POST_TEST_ARTIFACT = "source_analysis_v31_remaining_windows_test_delta.json"
REPORT_NAME = "PHASE_3B77A28_REMAINING_FIVE_REAL_LOCAL_LITE_WINDOWS_REPORT.md"

SEMANTIC_REVIEW_STATUS = (
    "FORENSIC_SEMANTIC_REVIEW_OF_VALID_V31_LOCAL_LITE_REMAINING_WINDOW"
)
SEMANTIC_REVIEW_INVALID = "FORENSIC_SEMANTIC_REVIEW_OF_INVALID_V31_LOCAL_LITE_TRANSPORT"
EXAMPLE_POLICY = EXAMPLE_POLICY
EXAMPLE_POLICY_LABEL = EXAMPLE_POLICY_LABEL
SERVER_GRAMMAR_STATUS = "A18_PROOF_APPLICABLE"
SUBTYPE_FAILURE_CLASS_IF_PASS = "ELIMINATED_BY_ARCHITECTURE"

PROTECTED_A27 = (
    f"audit/{A27_REPORT_NAME}",
    "audit/source_analysis_v31_win004_real_execution.json",
    "audit/source_analysis_v31_win004_real_preflight.json",
    "audit/source_analysis_v31_win004_semantic_review.json",
    "audit/source_analysis_v31_win004_canonical_reconstruction.json",
    "audit/source_analysis_v31_win004_src_analysis.json",
    "audit/source_analysis_v31_win004_handle_analysis.json",
    "audit/source_analysis_v31_future_win004_readiness.json",
    f"audit/{A26_REPORT_NAME}",
    f"audit/{A26_FUTURE_ARTIFACT}",
    f"audit/{A261_REPORT_NAME}",
    f"audit/{A25_REPORT_NAME}",
)
PROTECTED_HISTORICAL = tuple(A25_PROTECTED_HISTORICAL) + PROTECTED_A27

DRY_RUN_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_v31_remaining_windows "
    "pastoral_retreat_v2_validation "
    "--authorization-scope SMALL_V21_V31_LOCAL_LITE_REMAINING_FIVE_ONLY "
    "--dry-run"
)
REAL_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_v31_remaining_windows "
    "pastoral_retreat_v2_validation "
    "--authorization-scope SMALL_V21_V31_LOCAL_LITE_REMAINING_FIVE_ONLY "
    "--execute-real"
)

NEXT_ACTION = "HUMAN REVIEW"
NEXT_PHASE = "3B.7.7A.29_REAL_GLOBAL_CONSOLIDATION_PREFLIGHT"
NEXT_PHASE_LABEL = (
    "3B.7.7A.29 — REAL GLOBAL CONSOLIDATION PREFLIGHT "
    "(offline first; NOT authorized here)"
)
PHASE_3B_STATUS = "INCOMPLETE"
PRODUCTION_PLANNER_VERSION = PLANNER_VERSION
CANDIDATE_PLANNER = CANDIDATE_PLANNER_VERSION
PROMPT_VERSION = WINDOW_ANALYSIS_PROMPT_VERSION_V140
TRANSPORT_VERSION = SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE
SELECTED_ARCHITECTURE = "GLOBALIZE_IDEA_SUBTYPE"


def window_artifact(window_id: str, kind: str) -> str:
    return f"source_analysis_v31_{window_id}_{kind}.json"


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
assert AUTHORIZATION_SCOPE == "SMALL_V21_V31_LOCAL_LITE_REMAINING_FIVE_ONLY"
assert AUTHORIZATION_SCOPE != A21_AUTHORIZATION_SCOPE
assert AUTHORIZATION_SCOPE != A22_AUTHORIZATION_SCOPE
assert AUTHORIZATION_SCOPE != A24_AUTHORIZATION_SCOPE
assert AUTHORIZATION_SCOPE != A27_AUTHORIZATION_SCOPE
assert A27_WINDOW_ID == "WIN004"
assert A21_WINDOW_ID == "WIN001"
assert WINDOW_SPECS["WIN004"]["analysis_signature"] == A27_SIGNATURE
assert WINDOW_SPECS["WIN004"]["owned_src_count"] == 1180
assert WINDOW_SPECS["WIN004"]["word_count"] == 5662
assert WINDOW_SPECS["WIN004"]["local_input_estimate"] == 23046
assert WINDOW_SPECS["WIN002"]["local_input_estimate"] == 23047
assert WINDOW_SPECS["WIN003"]["local_input_estimate"] == 23023
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
assert PROMPT_VERSION == "window-analysis-1.4.0"
assert TRANSPORT_VERSION == "semantic-transport-v3.1-local-lite"
assert WINDOW_ANALYSIS_PROMPT_VERSION_V13 == "window-analysis-1.3"
assert WINDOW_ANALYSIS_PROMPT_VERSION_V131 == "window-analysis-1.3.1"
assert WINDOW_ANALYSIS_PROMPT_VERSION_V132 == "window-analysis-1.3.2"
assert not set(IDEA_KINDS) & set(IMPORTANCE_LEVELS)
assert EXECUTION_ORDER == ("WIN002", "WIN003", "WIN005", "WIN006", "WIN007")

__all__ = [
    "A13_SYNTHETIC_IDENTITY",
    "A15_V2_SIGNATURE",
    "A17_SCHEMA_FINGERPRINT",
    "A18_REQUEST_IDENTITY",
    "A19_RESULT",
    "A19_V3_FORENSIC",
    "A19_V3_SIGNATURE",
    "A21_AUTHORIZATION_SCOPE",
    "A21_RESULT",
    "A21_V3_FORENSIC",
    "A21_V3_SIGNATURE",
    "A21_WINDOW_ID",
    "A22_AUTHORIZATION_SCOPE",
    "A22_RESULT",
    "A22_V3_SIGNATURE",
    "A23_REPORT_NAME",
    "A23_RESULT",
    "A24_AUTHORIZATION_SCOPE",
    "A24_INVALID_IDEA_SHAPE",
    "A24_RESULT",
    "A24_V3_FORENSIC",
    "A24_V3_SIGNATURE",
    "A25_RESULT",
    "A26_RESULT",
    "A261_RESULT",
    "A27_AUTHORIZATION_SCOPE",
    "A27_FORENSIC",
    "A27_LOCAL_INPUT",
    "A27_PROMPT_FINGERPRINT",
    "A27_REPORT_NAME",
    "A27_RESULT",
    "A27_SIGNATURE",
    "A27_V31_FORENSIC",
    "A27_V31_SIGNATURE",
    "A27_WINDOW_ID",
    "AUTHORIZATION_SCOPE",
    "AUTHORIZED_WINDOW_IDS",
    "AUTO_CONTINUE",
    "AUTO_FALLBACK",
    "AUTO_RETRY",
    "BASELINE_ARTIFACT",
    "CALL1_SIGNATURE",
    "CALL2_SIGNATURE",
    "CANARY_SUBDIR",
    "CANDIDATE_CACHE_SUBDIR",
    "CANDIDATE_HARD_MAX_INPUT_TOKENS",
    "CANDIDATE_PLANNER",
    "CANDIDATE_WINDOWS_SUBDIR",
    "CONNECT_TIMEOUT_SECONDS",
    "DRY_RUN_COMMAND",
    "EFFORT",
    "EXAMPLE_POLICY",
    "EXAMPLE_POLICY_LABEL",
    "EXECUTION_ORDER",
    "EXPECTED_ADAPTED_SCHEMA_BYTES",
    "EXPECTED_CLEAN_FILE_SHA",
    "EXPECTED_CLEAN_SHA",
    "EXPECTED_CONTEXT_COUNT",
    "EXPECTED_CONTEXT_POLICY",
    "EXPECTED_PROMPT_SHA256",
    "EXPECTED_RAW_SCHEMA_BYTES",
    "EXPECTED_SCHEMA_HASH",
    "FORBIDDEN_WINDOW_IDS",
    "HISTORICAL_READ_TIMEOUT_SECONDS",
    "IDEA_SUBTYPE_TOKENS",
    "IMPORTANCE_VOCABULARY",
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
    "REPORT_NAME",
    "SCHEMA_VERSION",
    "SELECTED_ARCHITECTURE",
    "SEMANTIC_REVIEW_INVALID",
    "SEMANTIC_REVIEW_STATUS",
    "SEMANTIC_TRANSPORT_VERSION_V3",
    "SERVER_GRAMMAR_STATUS",
    "SMALL_SIGNATURE",
    "SUBTYPE_FAILURE_CLASS_IF_PASS",
    "THINKING_CONTRACT",
    "THINKING_MODE",
    "TOTAL_WINDOWS",
    "TRANSPORT_VERSION",
    "V3_HANDLE_ARCHITECTURE",
    "WINDOW_ANALYSIS_PROMPT_VERSION_V13",
    "WINDOW_ANALYSIS_PROMPT_VERSION_V131",
    "WINDOW_ANALYSIS_PROMPT_VERSION_V132",
    "WINDOW_ANALYSIS_PROMPT_VERSION_V140",
    "WINDOW_SPECS",
    "window_artifact",
]
