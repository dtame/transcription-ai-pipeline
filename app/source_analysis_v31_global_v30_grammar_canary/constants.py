"""Constantes 3B.7.7A.44 — tiny synthetic grammar + reuse-contract canary 3.0."""

from __future__ import annotations

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_grammar_canary.constants import (
    CANARY_CONNECT_TIMEOUT_SECONDS,
    CANARY_READ_TIMEOUT_SECONDS,
    FROZEN_GRANULARITY,
    FROZEN_PLANNER,
    FROZEN_PROMPT,
    FROZEN_SRC_POLICY,
    FROZEN_TRANSPORT,
    HANDLE_PREFIX_BY_KIND,
    MODEL,
    NODE_KINDS,
    NORMAL_FINISH_REASONS,
    PASTORAL_MARKERS,
    PRODUCTION_SRC_PATTERN,
    PROJECT_NAME,
    PROVIDER,
    THINKING_CONTRACT,
    THINKING_MODE,
)
from app.source_analysis_v31_global_output_architecture.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    DROP_REASONS_V20,
    RETIRED_DISPOSITION_OPS_V20,
    RETIRED_DROP_REASONS_V20,
    TEXT_LIMITS,
)
from app.source_analysis_v31_global_preflight.constants import (
    IDEA_DISPOSITION_COVERAGE_REQUIRED,
    IDEA_KIND_POLICY,
    READY_LABEL,
    RELATION_QUALITY_TECHNICAL_DEBT,
)
from app.source_analysis_v31_global_reuse_output.constants import (
    A39_STATUS_PRESERVED,
    A40_STATUS_PRESERVED,
    A41_STATUS_PRESERVED,
    A42_STATUS_PRESERVED,
    NEXT_PROMPT_VERSION,
    NEXT_SCHEMA_ADAPTED_BYTES,
    NEXT_SCHEMA_HASH,
    NEXT_SCHEMA_RAW_BYTES,
    NEXT_TRANSPORT_VERSION,
    PRODUCTION_MAX_OUTPUT_TOKENS as A43_MAX_OUTPUT,
    REPORT_NAME as A43_REPORT_NAME,
    SELECTED_ARCHITECTURE,
    SYNTHESIZED_IDEA_MAX_CHARS,
)
from app.source_analysis_v31_global_reuse_output.estimator import revised_reuse_budget
from app.source_analysis_v31_global_v20_grammar_canary.constants import (
    FORBIDDEN_TRANSCRIPT_IDS,
    FORBIDDEN_WINDOW_IDS,
    SYNTHETIC_NAMESPACE,
)

SCHEMA_VERSION = "1.0"
PHASE = "3B.7.7A.44"
MODE = "GLOBAL_CONSOLIDATION_3_0_REUSE_TINY_GRAMMAR_CANARY"
AUTHORIZATION_SCOPE = "GLOBAL_CONSOLIDATION_3_0_REUSE_TINY_GRAMMAR_CANARY_ONLY"

A43_STATUS_PRESERVED = "PASS"
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
assert SELECTED_ARCHITECTURE == "HARD_SINGLE_MEMBER_REUSE_SYNTHESIZE_MERGES_ONLY"
assert PROVIDER == "anthropic"
assert MODEL == "claude-sonnet-5"
assert THINKING_MODE == "disabled"
assert NEXT_PROMPT_VERSION == "global-consolidation-3.0"
assert NEXT_TRANSPORT_VERSION == "global-consolidation-transport-3.0"
assert NEXT_SCHEMA_RAW_BYTES == 1583
assert NEXT_SCHEMA_ADAPTED_BYTES == 1831
assert NEXT_SCHEMA_HASH == (
    "822397b642b0e1724e29686962caab32bff63effe18f05bff26b404bad9b2a90"
)
assert DROP_REASONS_V20 == ("transport_artifact", "non_substantive_fragment")
assert RETIRED_DROP_REASONS_V20 == ("exact_duplicate",)
assert RETIRED_DISPOSITION_OPS_V20 == ("OTHER",)
assert IDEA_KIND_POLICY == "KEEP_EMPTY_GLOBALLY"
assert IDEA_DISPOSITION_COVERAGE_REQUIRED == 100
assert READY_LABEL == "7 / 7"
assert SYNTHESIZED_IDEA_MAX_CHARS == 180

PROMPT_VERSION = NEXT_PROMPT_VERSION
TRANSPORT_VERSION = NEXT_TRANSPORT_VERSION
SCHEMA_RAW_BYTES = NEXT_SCHEMA_RAW_BYTES
SCHEMA_ADAPTED_BYTES = NEXT_SCHEMA_ADAPTED_BYTES
SCHEMA_HASH = NEXT_SCHEMA_HASH
A43_SCHEMA_ARTIFACT = "global_consolidation_reuse_next_schema.json"

MAX_ENGINE_GENERATE = 1
MAX_ANTHROPIC_POST = 1
MAX_ATTEMPTS = 1
AUTO_RETRY = False
AUTO_FALLBACK = False
AUTO_CONTINUE = False
EFFORT = None

CANARY_MAX_OUTPUT_TOKENS = 2048
PRODUCTION_MAX_OUTPUT_TOKENS = A43_MAX_OUTPUT
_A43_BUDGET = revised_reuse_budget()
PRODUCTION_EXPECTED_OUTPUT_TOKENS = int(_A43_BUDGET["p50_expected"])
PRODUCTION_CONSERVATIVE_OUTPUT_TOKENS = int(_A43_BUDGET["conservative"])
PRODUCTION_HARD_PLANNING_TOKENS = int(_A43_BUDGET["hard_planning"])
PRODUCTION_OUTPUT_RISK = str(_A43_BUDGET["output_risk"])
PRODUCTION_HARD_UTILIZATION = round(
    PRODUCTION_HARD_PLANNING_TOKENS / PRODUCTION_MAX_OUTPUT_TOKENS, 3
)
PRODUCTION_ABSOLUTE_HEADROOM = (
    PRODUCTION_MAX_OUTPUT_TOKENS - PRODUCTION_HARD_PLANNING_TOKENS
)
SAFETY_70 = int(PRODUCTION_MAX_OUTPUT_TOKENS * 0.70)
SAFETY_75 = int(PRODUCTION_MAX_OUTPUT_TOKENS * 0.75)
SAFETY_80 = int(PRODUCTION_MAX_OUTPUT_TOKENS * 0.80)
assert PRODUCTION_MAX_OUTPUT_TOKENS == 48000
assert PRODUCTION_EXPECTED_OUTPUT_TOKENS == 12302
assert PRODUCTION_CONSERVATIVE_OUTPUT_TOKENS == 16822
assert PRODUCTION_HARD_PLANNING_TOKENS == 25486
assert PRODUCTION_OUTPUT_RISK == "SAFE_FOR_GRAMMAR_CANARY_BUDGET"
assert PRODUCTION_HARD_UTILIZATION == 0.531
assert PRODUCTION_ABSOLUTE_HEADROOM == 22514
assert SAFETY_70 == 33600
assert SAFETY_75 == 36000
assert SAFETY_80 == 38400

CANARY_VERSION = "global-consolidation-tiny-grammar-canary-v30-1.0"
STAGE_CANARY = "source_analysis_v31_global_v30_grammar_canary"
CANARY_SUBDIR = "canary/global_consolidation_transport_v30"
CANARY_WINDOW_ID = "SYN_GLOBAL_V30"
CANARY_TRANSCRIPT_ID = "TR_CANARY_GARDEN_A44"
LOCK_NAME = "canary_real_call.lock"
RELATION_HINT_ID = "SYN:L011"

SYNTHETIC_WINDOW_IDS = ("SYN:W011", "SYN:W012")
SYNTHETIC_SRC_IDS = (
    "SRC998201",
    "SRC998202",
    "SRC998203",
    "SRC998204",
    "SRC998205",
    "SRC998206",
    "SRC998207",
    "SRC998208",
    "SRC998209",
    "SRC998210",
    "SRC998211",
    "SRC998212",
)

FIXTURE_ARTIFACT = "global_consolidation_v30_synthetic_fixture.json"
REQUEST_ARTIFACT = "global_consolidation_v30_canary_request.json"
REUSE_SYNTHESIS_ARTIFACT = "global_consolidation_v30_reuse_synthesis_audit.json"
MEMBERSHIP_ARTIFACT = "global_consolidation_v30_membership_audit.json"
DERIVED_SRC_ARTIFACT = "global_consolidation_v30_derived_src_audit.json"
VALIDATOR_ARTIFACT = "global_consolidation_v30_validator_result.json"
CANONICAL_ARTIFACT = "global_consolidation_v30_canonical_reconstruction.json"
ESTIMATOR_ARTIFACT = "global_consolidation_v30_estimator_comparison.json"
USAGE_ARTIFACT = "global_consolidation_v30_usage_cost.json"
READINESS_ARTIFACT = "global_consolidation_post_a44_readiness.json"
EXECUTION_ARTIFACT = "global_consolidation_v30_canary_execution.json"
REPORT_NAME = (
    "PHASE_3B77A44_GLOBAL_CONSOLIDATION_V30_REUSE_GRAMMAR_CANARY_REPORT.md"
)
BASELINE_ARTIFACT = "source_analysis_a44_test_baseline.json"
POST_TEST_ARTIFACT = "source_analysis_a44_test_delta.json"

FOCUSED_TEST_PATHS = (
    "app/tests/test_source_analysis_v31_global_v30_grammar_canary.py",
    "app/tests/test_source_analysis_v31_global_v30_grammar_canary_audit.py",
    "app/tests/test_source_analysis_v31_global_reuse_output.py",
    "app/tests/test_source_analysis_v31_global_reuse_output_audit.py",
)
BROADER_SLICE_TEST_PATHS = FOCUSED_TEST_PATHS + (
    "app/tests/test_source_analysis_v31_global_v201_contract_canary.py",
    "app/tests/test_source_analysis_v31_global_v201_contract_canary_audit.py",
    "app/tests/test_source_analysis_v31_global_drop_domain.py",
    "app/tests/test_source_analysis_v31_global_drop_domain_audit.py",
    "app/tests/test_source_analysis_v31_global_v20_grammar_canary.py",
    "app/tests/test_source_analysis_v31_global_output_architecture.py",
)

DRY_RUN_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_v31_global_v30_grammar_canary "
    "pastoral_retreat_v2_validation "
    "--authorization-scope "
    "GLOBAL_CONSOLIDATION_3_0_REUSE_TINY_GRAMMAR_CANARY_ONLY "
    "--dry-run"
)
REAL_COMMAND = (
    r".venv\Scripts\python.exe -m app.source_analysis_v31_global_v30_grammar_canary "
    "pastoral_retreat_v2_validation "
    "--authorization-scope "
    "GLOBAL_CONSOLIDATION_3_0_REUSE_TINY_GRAMMAR_CANARY_ONLY "
    "--execute-real"
)

PHASE_3B_STATUS = "INCOMPLETE"
SOURCE_MAP_STATUS = "NOT PUBLISHED"
NEXT_ACTION = "HUMAN REVIEW"
LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN = "YES"
READY_WINDOWS = READY_LABEL
READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY = "NO"
READY_FOR_REAL_GLOBAL_CONSOLIDATION_PREFLIGHT = "NO"
CONSOLIDATION_AUTHORIZED = False
SOURCE_MAP_PUBLICATION_AUTHORIZED = False

assert not source_map_path(PROJECT_NAME).is_file() or SOURCE_MAP_STATUS == "NOT PUBLISHED"
assert RELATION_QUALITY_TECHNICAL_DEBT == "YES"
assert FROZEN_PLANNER == "window-planner-v2.1-small"
assert FROZEN_PROMPT == "window-analysis-1.4.0"
assert FROZEN_TRANSPORT == "semantic-transport-v3.1-local-lite"
assert FROZEN_GRANULARITY == "window-granularity-1.2-kind-specific"
assert FROZEN_SRC_POLICY == "src-reference-policy-1.1-narrow-canonicalization"

__all__ = [
    "A34_STATUS_PRESERVED",
    "A35_STATUS_PRESERVED",
    "A36_STATUS_PRESERVED",
    "A37_STATUS_PRESERVED",
    "A38_STATUS_PRESERVED",
    "A39_STATUS_PRESERVED",
    "A40_STATUS_PRESERVED",
    "A41_STATUS_PRESERVED",
    "A42_STATUS_PRESERVED",
    "A43_REPORT_NAME",
    "A43_SCHEMA_ARTIFACT",
    "A43_STATUS_PRESERVED",
    "AUTHORIZATION_SCOPE",
    "AUTO_CONTINUE",
    "AUTO_FALLBACK",
    "AUTO_RETRY",
    "BASELINE_ARTIFACT",
    "BROADER_SLICE_TEST_PATHS",
    "CANARY_CONNECT_TIMEOUT_SECONDS",
    "CANARY_MAX_OUTPUT_TOKENS",
    "CANARY_READ_TIMEOUT_SECONDS",
    "CANARY_SUBDIR",
    "CANARY_TRANSCRIPT_ID",
    "CANARY_VERSION",
    "CANARY_WINDOW_ID",
    "CANONICAL_ARTIFACT",
    "CONSOLIDATION_AUTHORIZED",
    "DERIVED_SRC_ARTIFACT",
    "DROP_REASONS_V20",
    "DRY_RUN_COMMAND",
    "EFFORT",
    "ESTIMATOR_ARTIFACT",
    "EXECUTION_ARTIFACT",
    "FIXTURE_ARTIFACT",
    "FOCUSED_TEST_PATHS",
    "FORBIDDEN_TRANSCRIPT_IDS",
    "FORBIDDEN_WINDOW_IDS",
    "FROZEN_GRANULARITY",
    "FROZEN_PLANNER",
    "FROZEN_PROMPT",
    "FROZEN_SRC_POLICY",
    "FROZEN_TRANSPORT",
    "HANDLE_PREFIX_BY_KIND",
    "IDEA_DISPOSITION_COVERAGE_REQUIRED",
    "IDEA_KIND_POLICY",
    "LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN",
    "LOCK_NAME",
    "MAX_ANTHROPIC_POST",
    "MAX_ATTEMPTS",
    "MAX_ENGINE_GENERATE",
    "MEMBERSHIP_ARTIFACT",
    "MODE",
    "MODEL",
    "NEXT_ACTION",
    "NODE_KINDS",
    "NORMAL_FINISH_REASONS",
    "PASTORAL_MARKERS",
    "PHASE",
    "PHASE_3B_STATUS",
    "POST_TEST_ARTIFACT",
    "PRODUCTION_ABSOLUTE_HEADROOM",
    "PRODUCTION_CONSERVATIVE_OUTPUT_TOKENS",
    "PRODUCTION_EXPECTED_OUTPUT_TOKENS",
    "PRODUCTION_HARD_PLANNING_TOKENS",
    "PRODUCTION_HARD_UTILIZATION",
    "PRODUCTION_MAX_OUTPUT_TOKENS",
    "PRODUCTION_OUTPUT_RISK",
    "PRODUCTION_SRC_PATTERN",
    "PROJECT_NAME",
    "PROMPT_VERSION",
    "PROVIDER",
    "READINESS_ARTIFACT",
    "READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY",
    "READY_FOR_REAL_GLOBAL_CONSOLIDATION_PREFLIGHT",
    "READY_WINDOWS",
    "REAL_COMMAND",
    "RELATION_HINT_ID",
    "RELATION_QUALITY_TECHNICAL_DEBT",
    "REPORT_NAME",
    "REQUEST_ARTIFACT",
    "RETIRED_DISPOSITION_OPS_V20",
    "RETIRED_DROP_REASONS_V20",
    "REUSE_SYNTHESIS_ARTIFACT",
    "SAFETY_70",
    "SAFETY_75",
    "SAFETY_80",
    "SCHEMA_ADAPTED_BYTES",
    "SCHEMA_HASH",
    "SCHEMA_RAW_BYTES",
    "SCHEMA_VERSION",
    "SELECTED_ARCHITECTURE",
    "SOURCE_MAP_PUBLICATION_AUTHORIZED",
    "SOURCE_MAP_STATUS",
    "STAGE_CANARY",
    "SYNTHESIZED_IDEA_MAX_CHARS",
    "SYNTHETIC_NAMESPACE",
    "SYNTHETIC_SRC_IDS",
    "SYNTHETIC_WINDOW_IDS",
    "TEXT_LIMITS",
    "THINKING_CONTRACT",
    "THINKING_MODE",
    "TRANSPORT_VERSION",
    "USAGE_ARTIFACT",
    "VALIDATOR_ARTIFACT",
]
