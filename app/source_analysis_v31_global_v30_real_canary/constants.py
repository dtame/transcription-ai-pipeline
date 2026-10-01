"""Constantes 3B.7.7A.46 — un canary réel exact-request 3.0. 1 POST. 0 retry."""

from __future__ import annotations

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_ELAPSED_SECONDS,
    A38_STATUS_PRESERVED,
    A39_STATUS_PRESERVED,
    A40_STATUS_PRESERVED,
    A41_STATUS_PRESERVED,
    A42_STATUS_PRESERVED,
    A43_STATUS_PRESERVED,
    A44_STATUS_PRESERVED,
    CONNECT_TIMEOUT_SECONDS,
    EXPECTED_EXAMPLE,
    EXPECTED_IDEA,
    EXPECTED_REFERENCE,
    EXPECTED_RELATION,
    EXPECTED_TOPIC,
    EXPECTED_TOTAL_RECORDS,
    EXPECTED_UNCERTAINTY,
    FUTURE_AUTHORIZATION_SCOPE,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MATERIAL_BOUND_DELTA_RATIO,
    MAX_ANTHROPIC_POST,
    MAX_ATTEMPTS,
    MAX_ENGINE_GENERATE,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROTECTED_HISTORICAL as A45_PROTECTED_HISTORICAL,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    READY_COUNT,
    READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY,
    READY_LABEL,
    READY_WINDOWS,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SAFETY_70,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    THINKING_CONTRACT,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_grammar_canary.constants import NORMAL_FINISH_REASONS
from app.source_analysis_v31_global_output_architecture.constants import (
    DROP_REASONS_V20,
    TEXT_LIMITS,
)
from app.source_analysis_v31_global_reuse_output.constants import (
    SELECTED_ARCHITECTURE,
    SYNTHESIZED_IDEA_MAX_CHARS,
)

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.7A.46"
MODE = "GLOBAL_CONSOLIDATION_3_0_REAL_CANARY_EXACT_REQUEST"
AUTHORIZATION_SCOPE = FUTURE_AUTHORIZATION_SCOPE
A45_STATUS_PRESERVED = "PASS"

assert A34_STATUS_PRESERVED == "PASS"
assert A35_STATUS_PRESERVED == "FAIL"
assert A36_STATUS_PRESERVED == "PASS"
assert A37_STATUS_PRESERVED == "PASS"
assert A38_STATUS_PRESERVED == "FAIL"
assert A39_STATUS_PRESERVED == "PASS"
assert A40_STATUS_PRESERVED == "FAIL"
assert A41_STATUS_PRESERVED == "PASS"
assert A42_STATUS_PRESERVED == "PASS"
assert A43_STATUS_PRESERVED == "PASS"
assert A44_STATUS_PRESERVED == "PASS"
assert A45_STATUS_PRESERVED == "PASS"
assert AUTHORIZATION_SCOPE == "GLOBAL_CONSOLIDATION_3_0_REAL_CANARY_EXACT_REQUEST_ONLY"
assert READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY == "YES"
assert SELECTED_ARCHITECTURE == "HARD_SINGLE_MEMBER_REUSE_SYNTHESIZE_MERGES_ONLY"
assert PROVIDER == "anthropic"
assert MODEL == "claude-sonnet-5"
assert THINKING_MODE == "disabled"
assert PROMPT_VERSION == "global-consolidation-3.0"
assert TRANSPORT_VERSION == "global-consolidation-transport-3.0"
assert SCHEMA_RAW_BYTES == 1583
assert SCHEMA_ADAPTED_BYTES == 1831
assert SCHEMA_HASH == (
    "822397b642b0e1724e29686962caab32bff63effe18f05bff26b404bad9b2a90"
)
assert PRODUCTION_MAX_OUTPUT_TOKENS == 48000
assert CONNECT_TIMEOUT_SECONDS == 30.0
assert READ_TIMEOUT_SECONDS == 600.0
assert MAX_ENGINE_GENERATE == 1
assert MAX_ANTHROPIC_POST == 1
assert MAX_ATTEMPTS == 1
assert EXPECTED_IDEA == 286
assert EXPECTED_TOTAL_RECORDS == 623
assert READY_COUNT == 7
assert READY_LABEL == "7 / 7"
assert SYNTHESIZED_IDEA_MAX_CHARS == 180
assert SAFETY_70 == 33600
assert DROP_REASONS_V20 == ("transport_artifact", "non_substantive_fragment")

A45_NORMALIZED_INPUT_HASH = (
    "0277ec07d1122a60d191577eb7a5093ddeb2eb8008a7ccfae8309c973f8448f4"
)
A45_REQUEST_HASH = (
    "fbffc38cda313aebd2fc226ecfc86cb8839db0ed4cbf3a93218f07aa8870d1cf"
)
A45_SCHEMA_HASH = SCHEMA_HASH
A45_ESTIMATED_INPUT = 67146
A45_EXPECTED_OUTPUT = 13112
A45_CONSERVATIVE_OUTPUT = 18013
A45_HARD_OUTPUT = 29435
A45_HARD_UTILIZATION_PERCENT = 61.32
A45_OUTPUT_HEADROOM = 18565
A45_EXPECTED_COST_USD = 0.265412
A45_CONSERVATIVE_COST_USD = 0.314422
A45_HARD_COST_USD = 0.428642
A45_INPUT_HEADROOM = 12854
A45_USABLE_INPUT_BUDGET = 80000
A38_ELAPSED_BEFORE_MAX_TOKENS = A38_ELAPSED_SECONDS
assert A38_ELAPSED_BEFORE_MAX_TOKENS == 219.7

AUTO_RETRY = False
AUTO_FALLBACK = False
AUTO_CONTINUE = False
EFFORT = None
JSON_REPAIR = False
CONSOLIDATION_AUTHORIZED = True
SOURCE_MAP_PUBLICATION_AUTHORIZED = False
REAL_PROVIDER_CALLS_AUTHORIZED = 1
REAL_OPENAI_CALLS = 0

CANARY_VERSION = "global-consolidation-real-canary-a46-3.0"
STAGE_CANARY = "source_analysis_v31_global_v30_real_canary"
CANARY_SUBDIR = "real/global_consolidation_v30_a46"
LOCK_NAME = "canary_real_call.lock"
CANDIDATE_SOURCE_MAP_NAME = "global_consolidation_a46_source_map_candidate.json"
PRODUCTION_SOURCE_MAP_RELATIVE = "analysis/source_map.json"
FORENSIC_WINDOW_ID = "GLOBAL_A46"

PRECALL_ARTIFACT = "global_consolidation_a46_precall_manifest.json"
RESPONSE_IDENTITY_ARTIFACT = "global_consolidation_a46_response_identity.json"
RAW_RESPONSE_ARTIFACT = "global_consolidation_a46_raw_provider_response.json"
TRANSPORT_ARTIFACT = "global_consolidation_a46_transport_validation.json"
ACCOUNTABILITY_ARTIFACT = "global_consolidation_a46_idea_accountability.json"
REUSE_ARTIFACT = "global_consolidation_a46_reuse_audit.json"
MERGE_ARTIFACT = "global_consolidation_a46_merge_semantic_review.json"
DROP_ARTIFACT = "global_consolidation_a46_drop_semantic_review.json"
METADATA_ARTIFACT = "global_consolidation_a46_metadata_semantic_review.json"
TOPIC_ARTIFACT = "global_consolidation_a46_topic_semantic_review.json"
CANONICAL_VALIDATION_ARTIFACT = "global_consolidation_a46_canonical_validation.json"
USAGE_ARTIFACT = "global_consolidation_a46_usage_cost.json"
PUBLICATION_ARTIFACT = "global_consolidation_a46_publication_eligibility.json"
READINESS_ARTIFACT = "global_consolidation_post_a46_readiness.json"
EXECUTION_ARTIFACT = "global_consolidation_a46_execution.json"
TEST_DELTA_ARTIFACT = "source_analysis_a46_test_delta.json"
BASELINE_ARTIFACT = "source_analysis_a46_test_baseline.json"
HUMAN_AUTH_ARTIFACT = "global_consolidation_a46_human_authorization.json"
REPORT_NAME = "PHASE_3B77A46_GLOBAL_CONSOLIDATION_V30_ONE_REAL_CANARY_REPORT.md"

A45_REPORT_NAME = (
    "PHASE_3B77A45_GLOBAL_CONSOLIDATION_V30_EXACT_PRODUCTION_PREFLIGHT_REPORT.md"
)
A45_REQUEST_IDENTITY_ARTIFACT = "global_consolidation_a45_request_identity.json"
A45_INVENTORY_ARTIFACT = "global_consolidation_a45_exact_inventory.json"
A45_WINDOW_MANIFEST_ARTIFACT = "global_consolidation_a45_window_manifest.json"

PROTECTED_HISTORICAL = A45_PROTECTED_HISTORICAL

FOCUSED_TEST_PATHS = (
    "app/tests/test_source_analysis_v31_global_v30_exact_preflight.py",
    "app/tests/test_source_analysis_v31_global_v30_exact_preflight_audit.py",
    "app/tests/test_source_analysis_v31_global_v30_real_canary.py",
    "app/tests/test_source_analysis_v31_global_v30_real_canary_audit.py",
)
BROADER_SLICE_TEST_PATHS = FOCUSED_TEST_PATHS + (
    "app/tests/test_source_analysis_v31_global_v30_grammar_canary.py",
    "app/tests/test_source_analysis_v31_global_v30_grammar_canary_audit.py",
    "app/tests/test_source_analysis_v31_global_reuse_output.py",
    "app/tests/test_source_analysis_v31_global_reuse_output_audit.py",
    "app/tests/test_source_analysis_v31_global_v201_contract_canary.py",
    "app/tests/test_source_analysis_v31_global_v201_contract_canary_audit.py",
    "app/tests/test_source_analysis_v31_global_drop_domain.py",
    "app/tests/test_source_analysis_v31_global_drop_domain_audit.py",
    "app/tests/test_source_analysis_v31_global_v20_grammar_canary.py",
    "app/tests/test_source_analysis_v31_global_output_architecture.py",
)

PHASE_3B_STATUS = "INCOMPLETE"
SOURCE_MAP_STATUS = "NOT PUBLISHED"
NEXT_ACTION = "HUMAN REVIEW"
EDITORIAL_MARKERS = (
    "chapter",
    "chapters",
    "book section",
    "book title",
    "editorial plan",
    "editorial structure",
    "publication prose",
    "table of contents",
)

DRY_RUN_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_v31_global_v30_real_canary "
    "pastoral_retreat_v2_validation "
    "--authorization-scope GLOBAL_CONSOLIDATION_3_0_REAL_CANARY_EXACT_REQUEST_ONLY "
    "--dry-run"
)
REAL_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_v31_global_v30_real_canary "
    "pastoral_retreat_v2_validation "
    "--authorization-scope GLOBAL_CONSOLIDATION_3_0_REAL_CANARY_EXACT_REQUEST_ONLY "
    "--execute-real"
)

assert not source_map_path(PROJECT_NAME).is_file() or SOURCE_MAP_STATUS == "NOT PUBLISHED"
assert SOURCE_MAP_PUBLICATION_AUTHORIZED is False
assert CONSOLIDATION_AUTHORIZED is True
assert RELATION_QUALITY_TECHNICAL_DEBT == "YES"
assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"

__all__ = [
    "A34_STATUS_PRESERVED",
    "A35_STATUS_PRESERVED",
    "A36_STATUS_PRESERVED",
    "A37_STATUS_PRESERVED",
    "A38_ELAPSED_BEFORE_MAX_TOKENS",
    "A38_STATUS_PRESERVED",
    "A39_STATUS_PRESERVED",
    "A40_STATUS_PRESERVED",
    "A41_STATUS_PRESERVED",
    "A42_STATUS_PRESERVED",
    "A43_STATUS_PRESERVED",
    "A44_STATUS_PRESERVED",
    "A45_CONSERVATIVE_COST_USD",
    "A45_CONSERVATIVE_OUTPUT",
    "A45_ESTIMATED_INPUT",
    "A45_EXPECTED_COST_USD",
    "A45_EXPECTED_OUTPUT",
    "A45_HARD_COST_USD",
    "A45_HARD_OUTPUT",
    "A45_HARD_UTILIZATION_PERCENT",
    "A45_INPUT_HEADROOM",
    "A45_INVENTORY_ARTIFACT",
    "A45_NORMALIZED_INPUT_HASH",
    "A45_OUTPUT_HEADROOM",
    "A45_REPORT_NAME",
    "A45_REQUEST_HASH",
    "A45_REQUEST_IDENTITY_ARTIFACT",
    "A45_SCHEMA_HASH",
    "A45_STATUS_PRESERVED",
    "A45_USABLE_INPUT_BUDGET",
    "A45_WINDOW_MANIFEST_ARTIFACT",
    "ACCOUNTABILITY_ARTIFACT",
    "AUTHORIZATION_SCOPE",
    "AUTO_CONTINUE",
    "AUTO_FALLBACK",
    "AUTO_RETRY",
    "BASELINE_ARTIFACT",
    "BROADER_SLICE_TEST_PATHS",
    "CANARY_SUBDIR",
    "CANARY_VERSION",
    "CANONICAL_VALIDATION_ARTIFACT",
    "CANDIDATE_SOURCE_MAP_NAME",
    "CONSOLIDATION_AUTHORIZED",
    "CONNECT_TIMEOUT_SECONDS",
    "DROP_ARTIFACT",
    "DROP_REASONS_V20",
    "DRY_RUN_COMMAND",
    "EDITORIAL_MARKERS",
    "EFFORT",
    "EXECUTION_ARTIFACT",
    "EXPECTED_EXAMPLE",
    "EXPECTED_IDEA",
    "EXPECTED_REFERENCE",
    "EXPECTED_RELATION",
    "EXPECTED_TOPIC",
    "EXPECTED_TOTAL_RECORDS",
    "EXPECTED_UNCERTAINTY",
    "FOCUSED_TEST_PATHS",
    "FORENSIC_WINDOW_ID",
    "HUMAN_AUTH_ARTIFACT",
    "JSON_REPAIR",
    "LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN",
    "LOCK_NAME",
    "MATERIAL_BOUND_DELTA_RATIO",
    "MAX_ANTHROPIC_POST",
    "MAX_ATTEMPTS",
    "MAX_ENGINE_GENERATE",
    "MERGE_ARTIFACT",
    "METADATA_ARTIFACT",
    "MODE",
    "MODEL",
    "NEXT_ACTION",
    "NORMAL_FINISH_REASONS",
    "PHASE",
    "PHASE_3B_STATUS",
    "PRECALL_ARTIFACT",
    "PRODUCTION_MAX_OUTPUT_TOKENS",
    "PRODUCTION_SOURCE_MAP_RELATIVE",
    "PROJECT_NAME",
    "PROMPT_VERSION",
    "PROTECTED_HISTORICAL",
    "PROVIDER",
    "PUBLICATION_ARTIFACT",
    "RAW_RESPONSE_ARTIFACT",
    "READINESS_ARTIFACT",
    "READY_COUNT",
    "READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY",
    "READY_LABEL",
    "READY_WINDOWS",
    "READ_TIMEOUT_SECONDS",
    "REAL_COMMAND",
    "REAL_OPENAI_CALLS",
    "REAL_PROVIDER_CALLS_AUTHORIZED",
    "RELATION_QUALITY_TECHNICAL_DEBT",
    "REPORT_NAME",
    "RESPONSE_IDENTITY_ARTIFACT",
    "REUSE_ARTIFACT",
    "SAFETY_70",
    "SCHEMA_ADAPTED_BYTES",
    "SCHEMA_HASH",
    "SCHEMA_RAW_BYTES",
    "SCHEMA_VERSION",
    "SELECTED_ARCHITECTURE",
    "SOURCE_MAP_PUBLICATION_AUTHORIZED",
    "SOURCE_MAP_STATUS",
    "STAGE_CANARY",
    "SYNTHESIZED_IDEA_MAX_CHARS",
    "TEST_DELTA_ARTIFACT",
    "TEXT_LIMITS",
    "THINKING_CONTRACT",
    "THINKING_MODE",
    "TOPIC_ARTIFACT",
    "TRANSPORT_ARTIFACT",
    "TRANSPORT_VERSION",
    "USAGE_ARTIFACT",
]
