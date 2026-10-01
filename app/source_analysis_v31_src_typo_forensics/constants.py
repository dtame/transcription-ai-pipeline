"""Constantes 3B.7.7A.32 — forensics SRC WIN007. 0 provider. 0 promotion."""

from __future__ import annotations

from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.constants import (
    CANDIDATE_PLANNER_VERSION,
    GRANULARITY_POLICY_VERSION_12_KIND_SPECIFIC,
    PROJECT_NAME,
)
from app.source_analysis_local_v3.constants import (
    SEMANTIC_TRANSPORT_VERSION_V3,
    SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
    WINDOW_ANALYSIS_PROMPT_VERSION_V140,
)
from app.source_analysis_local_v3.schema import (
    semantic_transport_v3_fingerprint,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis_v2_a15_forensics.constants import (
    A15_FORENSIC_RELATIVE,
    A15_SIGNATURE,
)
from app.source_analysis_v3_a19_forensics.constants import (
    A19_FORENSIC_RELATIVE,
    A19_HYPOTHETICAL_INTENDED_SRC,
    A19_MALFORMED_SRC,
    A19_RAW_SHA256,
    A19_RAW_SIZE,
    A19_SIGNATURE,
    A19_STATUS_UNCHANGED,
)
from app.source_analysis_v3_a22_forensics.constants import A22_SIGNATURE
from app.source_analysis_v3_a25_forensics.constants import A24_SIGNATURE
from app.source_analysis_v3_hardened_win001.constants import (
    EXPECTED_ANALYSIS_SIGNATURE as A21_SIGNATURE,
)
from app.source_analysis_v3_second_window.constants import EXPECTED_SCHEMA_HASH
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
)
from app.source_analysis_v31_final_three.constants import (
    A19_RESULT,
    A21_RESULT,
    A22_RESULT,
    A23_RESULT,
    A24_RESULT,
    A25_RESULT,
    A26_RESULT,
    A261_RESULT,
    A27_RESULT,
    A28_RESULT,
    A29_RESULT,
    A30_RESULT,
    PROTECTED_HISTORICAL as A31_PROTECTED_HISTORICAL,
    REPORT_NAME as A31_REPORT_NAME,
    WINDOW_SPECS,
)
from app.source_analysis_v31_real_win004.constants import (
    EXPECTED_ANALYSIS_SIGNATURE as A27_SIGNATURE,
)
from app.source_analysis_v31_remaining_windows.constants import (
    WINDOW_SPECS as A28_WINDOW_SPECS,
)

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.7A.32"
MODE = "WIN007_STRICT_SRC_TYPO_FORENSICS_OFFLINE"

REAL_PROVIDER_CALLS_THIS_PHASE = 0
REAL_WINDOW_CALLS = 0
WIN007_RETRY_AUTHORIZED = False
WIN007_PROMOTION_AUTHORIZED = False
CONSOLIDATION_AUTHORIZED = False
PRODUCTION_SRC_POLICY_MUTATED = False
OPTION_B_IMPLEMENTED = False

A19_STATUS = A19_RESULT
A21_STATUS = A21_RESULT
A22_STATUS = A22_RESULT
A23_STATUS = A23_RESULT
A24_STATUS = A24_RESULT
A25_STATUS = A25_RESULT
A26_STATUS = A26_RESULT
A261_STATUS = A261_RESULT
A27_STATUS = A27_RESULT
A28_STATUS = A28_RESULT
A29_STATUS = A29_RESULT
A30_STATUS = A30_RESULT
A31_STATUS_UNCHANGED = "FAIL"

READY_BEFORE = "6 / 7"
READY_BEFORE_COUNT = 6
READY_AFTER = "6 / 7"
READY_AFTER_COUNT = 6
TOTAL_WINDOWS = 7
PHASE_3B_STATUS = "INCOMPLETE"
SOURCE_MAP_STATUS = "NOT PUBLISHED"
RELATION_QUALITY_TECHNICAL_DEBT = "YES"

WINDOW_ID = "WIN007"
WIN007_SIGNATURE = WINDOW_SPECS["WIN007"]["analysis_signature"]
WIN007_FORENSIC = WINDOW_SPECS["WIN007"]["forensic_identity"]
WIN007_RAW_SHA256 = (
    "0eac2ca0c0cfb9c2ca9564f9f087fa2126d6791d5792d08e8d2e3d4001968f36"
)
WIN007_RAW_SIZE = 19947
WIN007_REQUEST_ID = "req_011CfVDkmr5jkE7chHzsafTc"
WIN007_HTTP = 200
WIN007_FINISH = "end_turn"
WIN007_THINKING = "disabled"
WIN007_INPUT_TOKENS = 49546
WIN007_OUTPUT_TOKENS = 7778
WIN007_ELAPSED_MS = 68827
WIN007_COST_USD = 0.176872
WIN007_OWNED_SRC_COUNT = WINDOW_SPECS["WIN007"]["owned_src_count"]
WIN007_FIRST_OWNED = WINDOW_SPECS["WIN007"]["first_owned_src"]
WIN007_LAST_OWNED = WINDOW_SPECS["WIN007"]["last_owned_src"]
WIN007_WORD_COUNT = WINDOW_SPECS["WIN007"]["word_count"]
WIN007_FORENSIC_RELATIVE = (
    "audit/canary/v31_local_lite_final_three/provider_forensics/WIN007/"
    + WIN007_SIGNATURE
)

A31_VALIDATOR_ERROR = "records[13].s[1] : source_ref mal formé « SRec007337 »"
MALFORMED_TOKEN = "SRec007337"
EXPECTED_CANONICAL = "SRC007337"
NUMERIC_PAYLOAD = "007337"
RECORD_INDEX = 13
RECORD_S_POSITION = 1
A19_MALFORMED = A19_MALFORMED_SRC
A19_CANONICAL = A19_HYPOTHETICAL_INTENDED_SRC

PROMPT_VERSION = WINDOW_ANALYSIS_PROMPT_VERSION_V140
TRANSPORT_VERSION = SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE
GRANULARITY_POLICY = GRANULARITY_POLICY_VERSION_12_KIND_SPECIFIC
PRODUCTION_PLANNER_VERSION = PLANNER_VERSION
CANDIDATE_PLANNER = CANDIDATE_PLANNER_VERSION

A18_PROOF_STILL_APPLIES = True
SCHEMA_CHANGE_REQUIRED = False
PROMPT_CHANGE_REQUIRED = False
TRANSPORT_CHANGE_REQUIRED = False

ROOT_FAILURE_ARTIFACT = "source_analysis_win007_src_root_failure.json"
HISTORY_ARTIFACT = "source_analysis_real_provider_src_error_history.json"
OPTIONS_ARTIFACT = "source_analysis_src_identifier_policy_options.json"
COUNTERFACTUAL_ARTIFACT = "source_analysis_win007_single_src_counterfactual.json"
SEMANTIC_ARTIFACT = "source_analysis_win007_counterfactual_semantic_review.json"
CANONICAL_ARTIFACT = "source_analysis_win007_counterfactual_canonical.json"
DECISION_ARTIFACT = "source_analysis_src_identifier_policy_decision.json"
REPORT_NAME = "PHASE_3B77A32_WIN007_STRICT_SRC_TYPO_FORENSICS_REPORT.md"

PROTECTED_A31 = (
    f"audit/{A31_REPORT_NAME}",
    "audit/source_analysis_ready_windows_after_a31.json",
    "audit/source_analysis_v31_WIN007_a31_execution.json",
    "audit/source_analysis_v31_WIN007_a31_src.json",
    "audit/source_analysis_v31_WIN007_a31_contract.json",
    "audit/source_analysis_v31_WIN007_a31_handles.json",
    "audit/source_analysis_v31_WIN007_a31_semantic_review.json",
    "audit/source_analysis_v31_WIN005_a31_execution.json",
    "audit/source_analysis_v31_WIN006_a31_execution.json",
    f"{WIN007_FORENSIC_RELATIVE}/provider_raw_response.bin",
    f"{WIN007_FORENSIC_RELATIVE}/provider_http_envelope.json",
    "audit/canary/v31_local_lite_final_three/a31_real_v31_local_lite_final_three.lock",
)
PROTECTED_HISTORICAL = tuple(A31_PROTECTED_HISTORICAL) + PROTECTED_A31

HISTORICAL_RESPONSES = (
    {
        "phase": "A.15",
        "window_id": "WIN001",
        "generation": "pre-hardening",
        "prompt": "window-analysis-1.2.1",
        "transport": "semantic-transport-v2",
        "relative": A15_FORENSIC_RELATIVE,
        "signature": A15_SIGNATURE,
    },
    {
        "phase": "A.19",
        "window_id": "WIN001",
        "generation": "pre-hardening",
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V13,
        "transport": SEMANTIC_TRANSPORT_VERSION_V3,
        "relative": A19_FORENSIC_RELATIVE,
        "signature": A19_SIGNATURE,
    },
    {
        "phase": "A.21",
        "window_id": "WIN001",
        "generation": "window-analysis-1.3.1",
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V131,
        "transport": SEMANTIC_TRANSPORT_VERSION_V3,
        "relative": (
            "audit/canary/v3_hardened_win001/provider_forensics/WIN001/"
            + A21_SIGNATURE
        ),
        "signature": A21_SIGNATURE,
    },
    {
        "phase": "A.22",
        "window_id": "WIN004",
        "generation": "window-analysis-1.3.1",
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V131,
        "transport": SEMANTIC_TRANSPORT_VERSION_V3,
        "relative": (
            "audit/canary/v3_second_window/provider_forensics/WIN004/"
            + A22_SIGNATURE
        ),
        "signature": A22_SIGNATURE,
    },
    {
        "phase": "A.24",
        "window_id": "WIN004",
        "generation": "window-analysis-1.3.1",
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V131,
        "transport": SEMANTIC_TRANSPORT_VERSION_V3,
        "relative": (
            "audit/canary/v3_hardened_win004/provider_forensics/WIN004/"
            + A24_SIGNATURE
        ),
        "signature": A24_SIGNATURE,
    },
    {
        "phase": "A.27",
        "window_id": "WIN004",
        "generation": "window-analysis-1.4.0 / v3.1-local-lite",
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V140,
        "transport": SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
        "relative": (
            "audit/canary/v31_local_lite_win004/provider_forensics/WIN004/"
            + A27_SIGNATURE
        ),
        "signature": A27_SIGNATURE,
    },
    {
        "phase": "A.28",
        "window_id": "WIN002",
        "generation": "window-analysis-1.4.0 / v3.1-local-lite",
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V140,
        "transport": SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
        "relative": (
            "audit/canary/v31_local_lite_remaining/provider_forensics/WIN002/"
            + A28_WINDOW_SPECS["WIN002"]["analysis_signature"]
        ),
        "signature": A28_WINDOW_SPECS["WIN002"]["analysis_signature"],
    },
    {
        "phase": "A.28",
        "window_id": "WIN003",
        "generation": "window-analysis-1.4.0 / v3.1-local-lite",
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V140,
        "transport": SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
        "relative": (
            "audit/canary/v31_local_lite_remaining/provider_forensics/WIN003/"
            + A28_WINDOW_SPECS["WIN003"]["analysis_signature"]
        ),
        "signature": A28_WINDOW_SPECS["WIN003"]["analysis_signature"],
    },
    {
        "phase": "A.31",
        "window_id": "WIN005",
        "generation": "window-analysis-1.4.0 / v3.1-local-lite",
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V140,
        "transport": SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
        "relative": (
            "audit/canary/v31_local_lite_final_three/provider_forensics/WIN005/"
            + WINDOW_SPECS["WIN005"]["analysis_signature"]
        ),
        "signature": WINDOW_SPECS["WIN005"]["analysis_signature"],
    },
    {
        "phase": "A.31",
        "window_id": "WIN006",
        "generation": "window-analysis-1.4.0 / v3.1-local-lite",
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V140,
        "transport": SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
        "relative": (
            "audit/canary/v31_local_lite_final_three/provider_forensics/WIN006/"
            + WINDOW_SPECS["WIN006"]["analysis_signature"]
        ),
        "signature": WINDOW_SPECS["WIN006"]["analysis_signature"],
    },
    {
        "phase": "A.31",
        "window_id": "WIN007",
        "generation": "window-analysis-1.4.0 / v3.1-local-lite",
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V140,
        "transport": SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
        "relative": WIN007_FORENSIC_RELATIVE,
        "signature": WIN007_SIGNATURE,
    },
)

ALLOWED_DECISIONS = (
    "KEEP_STRICT_AND_RETRY_WIN007",
    "IMPLEMENT_NARROW_SRC_CANONICALIZATION_THEN_REVALIDATE_SAVED_WIN007",
    "REDESIGN_SRC_REFERENCE_TRANSPORT_BEFORE_CONTINUING",
    "HUMAN_SEMANTIC_REVIEW_REQUIRED",
    "OTHER_EXPLICITLY_JUSTIFIED",
)

NEXT_ACTION = "HUMAN REVIEW"
NEXT_PHASE = "HUMAN_REVIEW_WIN007_SRC_POLICY"
FAILURE_CLASS = "PROVIDER_SRC_LITERAL_COPY_ERROR"

assert EXPECTED_SCHEMA_HASH == (
    "de42ce0f3c271e67b902a94d2f528eae56f82b1a2a5740e65161987038849425"
)
assert semantic_transport_v31_local_lite_fingerprint() == EXPECTED_SCHEMA_HASH
assert semantic_transport_v3_fingerprint() == EXPECTED_SCHEMA_HASH
assert EXPECTED_RAW_SCHEMA_BYTES == 588
assert EXPECTED_ADAPTED_SCHEMA_BYTES == 650
assert A19_STATUS == "FAIL"
assert A21_STATUS == "PASS"
assert A22_STATUS == "FAIL"
assert A23_STATUS == "PASS"
assert A24_STATUS == "FAIL"
assert A25_STATUS == "PARTIAL"
assert A26_STATUS == "PASS"
assert A261_STATUS == "PASS"
assert A27_STATUS == "PASS"
assert A28_STATUS == "FAIL"
assert A29_STATUS == "PASS"
assert A30_STATUS == "PASS"
assert A31_STATUS_UNCHANGED == "FAIL"
assert PROMPT_VERSION == "window-analysis-1.4.0"
assert TRANSPORT_VERSION == "semantic-transport-v3.1-local-lite"
assert GRANULARITY_POLICY == "window-granularity-1.2-kind-specific"
assert WIN007_SIGNATURE == (
    "95b979ca7e535c9da0ca0a109fe0c2e16e312434855b9c311df684cbb8a4b4e9"
)
assert MALFORMED_TOKEN == "SRec007337"
assert EXPECTED_CANONICAL == "SRC007337"
assert A19_MALFORMED == "SRc000609"
assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
assert OPTION_B_IMPLEMENTED is False
assert WIN007_PROMOTION_AUTHORIZED is False
assert not source_map_path(PROJECT_NAME).is_file() or SOURCE_MAP_STATUS == "NOT PUBLISHED"
assert A19_RAW_SIZE == 28161
assert A19_RAW_SHA256

__all__ = [
    "A15_FORENSIC_RELATIVE",
    "A15_SIGNATURE",
    "A18_PROOF_STILL_APPLIES",
    "A19_CANONICAL",
    "A19_MALFORMED",
    "A19_RAW_SHA256",
    "A19_RAW_SIZE",
    "A19_SIGNATURE",
    "A19_STATUS",
    "A19_STATUS_UNCHANGED",
    "A21_SIGNATURE",
    "A21_STATUS",
    "A22_SIGNATURE",
    "A22_STATUS",
    "A23_STATUS",
    "A24_SIGNATURE",
    "A24_STATUS",
    "A25_STATUS",
    "A26_STATUS",
    "A261_STATUS",
    "A27_SIGNATURE",
    "A27_STATUS",
    "A28_STATUS",
    "A28_WINDOW_SPECS",
    "A29_STATUS",
    "A30_STATUS",
    "A31_REPORT_NAME",
    "A31_STATUS_UNCHANGED",
    "A31_VALIDATOR_ERROR",
    "ALLOWED_DECISIONS",
    "CANDIDATE_PLANNER",
    "CANONICAL_ARTIFACT",
    "CONSOLIDATION_AUTHORIZED",
    "COUNTERFACTUAL_ARTIFACT",
    "DECISION_ARTIFACT",
    "EXPECTED_ADAPTED_SCHEMA_BYTES",
    "EXPECTED_CANONICAL",
    "EXPECTED_RAW_SCHEMA_BYTES",
    "EXPECTED_SCHEMA_HASH",
    "FAILURE_CLASS",
    "GRANULARITY_POLICY",
    "HISTORICAL_RESPONSES",
    "HISTORY_ARTIFACT",
    "MALFORMED_TOKEN",
    "MODE",
    "NEXT_ACTION",
    "NEXT_PHASE",
    "NUMERIC_PAYLOAD",
    "OPTION_B_IMPLEMENTED",
    "OPTIONS_ARTIFACT",
    "PHASE",
    "PHASE_3B_STATUS",
    "PRODUCTION_PLANNER_VERSION",
    "PRODUCTION_SRC_POLICY_MUTATED",
    "PROJECT_NAME",
    "PROMPT_CHANGE_REQUIRED",
    "PROMPT_VERSION",
    "PROTECTED_HISTORICAL",
    "READY_AFTER",
    "READY_AFTER_COUNT",
    "READY_BEFORE",
    "READY_BEFORE_COUNT",
    "REAL_PROVIDER_CALLS_THIS_PHASE",
    "REAL_WINDOW_CALLS",
    "RECORD_INDEX",
    "RECORD_S_POSITION",
    "RELATION_QUALITY_TECHNICAL_DEBT",
    "REPORT_NAME",
    "ROOT_FAILURE_ARTIFACT",
    "SCHEMA_CHANGE_REQUIRED",
    "SCHEMA_VERSION",
    "SEMANTIC_ARTIFACT",
    "SOURCE_MAP_STATUS",
    "TOTAL_WINDOWS",
    "TRANSPORT_CHANGE_REQUIRED",
    "TRANSPORT_VERSION",
    "WIN007_COST_USD",
    "WIN007_ELAPSED_MS",
    "WIN007_FINISH",
    "WIN007_FIRST_OWNED",
    "WIN007_FORENSIC",
    "WIN007_FORENSIC_RELATIVE",
    "WIN007_HTTP",
    "WIN007_INPUT_TOKENS",
    "WIN007_LAST_OWNED",
    "WIN007_OUTPUT_TOKENS",
    "WIN007_OWNED_SRC_COUNT",
    "WIN007_PROMOTION_AUTHORIZED",
    "WIN007_RAW_SHA256",
    "WIN007_RAW_SIZE",
    "WIN007_REQUEST_ID",
    "WIN007_RETRY_AUTHORIZED",
    "WIN007_SIGNATURE",
    "WIN007_THINKING",
    "WIN007_WORD_COUNT",
    "WINDOW_ID",
    "WINDOW_SPECS",
]
