"""
Phase 4A.4 — controlled EditorialPlan publication + Phase 4 freeze.

Offline only. 0 provider calls. Publishes the already-validated A.3.5
candidate by exact bytes. Does not regenerate, translate, or start the
Book Generator. Does not flip historical PUBLICATION_AUTHORIZED=False.
"""

from __future__ import annotations

from app.editorial_planner_canary_4a35.constants import (
    A3_CANDIDATE_SHA256,
    A33_CANDIDATE_SHA256,
    ADAPTED_SCHEMA_SHA256,
    EXPECTED_CANONICAL_DOCUMENT_LANGUAGE,
    EXPECTED_IDEA_COUNT,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_SOURCE_MAP_BYTES,
    EXPECTED_SOURCE_MAP_CHARS,
    EXPECTED_SOURCE_MAP_SHA256,
    LANGUAGE_POLICY,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.editorial_planning.constants import (
    EDITORIAL_PLAN_FILENAME,
    EDITORIAL_PLAN_SCHEMA_VERSION,
    PUBLICATION_AUTHORIZED as HISTORICAL_PUBLICATION_AUTHORIZED,
)
from app.editorial_planning.language_policy import DOCUMENT_LANGUAGE_POLICY
from app.source_analysis_v31_global_a47_contract_forensics.constants import (
    RELATION_QUALITY_TECHNICAL_DEBT,
)

PHASE = "4A.4"
PHASE_NAME = "EDITORIAL_PLAN_CONTROLLED_PUBLICATION_AND_PHASE_4_FREEZE"
PACKAGE_VERSION = "editorial-planner-publication-4a4-1.0"

assert HISTORICAL_PUBLICATION_AUTHORIZED is False
assert PROVIDER == "anthropic"
assert MODEL == "claude-opus-5"
assert PROMPT_VERSION == "editorial-planner-1.0.2"
assert TRANSPORT_VERSION == "editorial-plan-transport-1.0"
assert DOCUMENT_LANGUAGE_POLICY == LANGUAGE_POLICY == (
    "TRANSCRIPTION_DERIVED_PRIMARY_LANGUAGE"
)
assert EXPECTED_CANONICAL_DOCUMENT_LANGUAGE == "en"
assert PRODUCTION_MAX_OUTPUT_TOKENS == 65536
assert THINKING_MODE == "provider_default"
assert ADAPTED_SCHEMA_SHA256 == (
    "1cebcf97ed7fa5cfa4b4758d1eb1451b6770347e9508772e8287228a768ba77e"
)
assert EXPECTED_SOURCE_MAP_SHA256 == (
    "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855"
)
assert EXPECTED_SOURCE_MAP_BYTES == 202398
assert EXPECTED_SOURCE_MAP_CHARS == 202365
assert EXPECTED_IDEA_COUNT == 286
assert EXPECTED_REQUEST_SHA256 == (
    "a059adfe3b05725aabaf5df84b1d492f09090370bcc471ce985583333a718c61"
)
assert A3_CANDIDATE_SHA256 == (
    "abc87e082878e0281689ecc022ed8b40ca318510fc90d960c31795d6186bd95e"
)
assert A33_CANDIDATE_SHA256 == (
    "b4cdf2cfab53018830bc7c23f038147526ee7b605531cc4aabeb04850086838a"
)
assert RELATION_QUALITY_TECHNICAL_DEBT == "YES"
assert EDITORIAL_PLAN_SCHEMA_VERSION == "1.0"
assert EDITORIAL_PLAN_FILENAME == "editorial_plan.json"

EDITORIAL_PLAN_PUBLICATION_AUTHORIZED = True
REAL_PROVIDER_CALLS_THIS_PHASE = 0
PHASE_4A4_COST_USD = 0.0

EXPECTED_CANDIDATE_SHA256 = (
    "01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440"
)
EXPECTED_CANDIDATE_BYTES = 234637
EXPECTED_CANDIDATE_CHARS = 234625

EXPECTED_CHAPTER_COUNT = 19
EXPECTED_SECTION_COUNT = 72
EXPECTED_ASSIGNED = 286
EXPECTED_DEFERRED = 0
EXPECTED_EXCLUDED = 0
EXPECTED_SILENT_OMISSIONS = 0
EXPECTED_DUPLICATE_PRIMARY = 0
EXPECTED_REUSED = 0
EXPECTED_UNKNOWN_REFS = 0

WORKING_TITLE = "The Life You Already Inherited"
WORKING_TITLE_STATUS = "SUPPORTED_WORKING_TITLE"
FINAL_TITLE_APPROVED = False

PROVIDER_DISPLAY = "Anthropic"
REQUEST_ID = "req_011CfamLewgH5N8GFiojFCBi"
SCHEMA_HASH = ADAPTED_SCHEMA_SHA256

COVERAGE_POLICY = "EXACT_EXHAUSTIVE_IDEA_ACCOUNTABILITY"
PUBLICATION_POLICY = "VALIDATED_CANDIDATE_ONLY"
COVERAGE_CONTRACT = (
    "every input IDEA must have exactly one primary disposition: "
    "ASSIGNED, DEFERRED, or EXCLUDED. Reuse is additional and auditable. "
    "Silent omissions, duplicate primary dispositions, and unknown "
    "references are hard FAIL."
)
LANGUAGE_CONTRACT = (
    "Document generation language comes from validated transcription "
    "primary language. Planner does not choose language. Book Generator "
    "must preserve the same canonical language. Translation is a separate "
    "future downstream stage."
)
BOOK_GENERATOR_INPUT_CONTRACT = (
    "Phase 4B consumes the canonical published editorial_plan.json plus "
    "canonical SourceMap only where the frozen Book Generator design "
    "explicitly requires it. It must not read the A.3.5 audit candidate "
    "directly."
)

HISTORICAL_PROMPTS = (
    "editorial-planner-1.0",
    "editorial-planner-1.0.1",
    "editorial-planner-1.0.2",
)

PUBLICATION_MODE_NEW = "NEW_ATOMIC_WRITE"
PUBLICATION_MODE_IDENTICAL = "ALREADY_PUBLISHED_IDENTICAL"
PUBLICATION_MODE_CONFLICT = "BLOCKED_CONFLICT"
PUBLICATION_MODE_BLOCKED = "BLOCKED"
BYTE_IDENTITY_EXACT = "PASS"
BYTE_IDENTITY_FAIL = "FAIL"

AUDIT_DIRNAME = "editorial_plan_publication_4a4"
AUDIT_PREPUBLICATION = "editorial_plan_4a4_prepublication_identity.json"
AUDIT_PUBLICATION = "editorial_plan_4a4_publication_evidence.json"
AUDIT_BYTE_IDENTITY = "editorial_plan_4a4_byte_identity.json"
AUDIT_RELOAD = "editorial_plan_4a4_reload_validation.json"
AUDIT_ACCOUNTABILITY = "editorial_plan_4a4_idea_accountability.json"
AUDIT_LANGUAGE = "editorial_plan_4a4_language_validation.json"
AUDIT_FREEZE = "editorial_plan_4a4_freeze_manifest.json"
AUDIT_READINESS = "editorial_planner_post_4a4_readiness.json"
REPORT_NAME = (
    "PHASE_4A4_EDITORIAL_PLAN_CONTROLLED_PUBLICATION_AND_FREEZE_REPORT.md"
)

A35_AUDIT_RELATIVE = "audit/real/editorial_planner_4a35"
A35_CANDIDATE_NAME = "editorial_plan_candidate.json"
A35_SEMANTIC_NAME = "editorial_planner_4a35_semantic_review.json"
A35_TECHNICAL_NAME = "editorial_planner_4a35_technical_validation.json"
A35_ACCOUNTABILITY_NAME = "editorial_planner_4a35_idea_accountability.json"
A35_LANGUAGE_NAME = "editorial_planner_4a35_language_validation.json"
A35_PUBLICATION_NAME = "editorial_planner_4a35_publication_eligibility.json"
A35_EXECUTION_NAME = "editorial_planner_4a35_execution.json"
A35_PRECALL_NAME = "editorial_planner_4a35_precall_identity.json"
A35_RESPONSE_NAME = "editorial_planner_4a35_response_identity.json"
A35_READINESS_NAME = "editorial_planner_post_4a35_readiness.json"

FOCUSED_TEST_PATHS = (
    "app/tests/test_editorial_planner_publication_4a4.py",
    "app/tests/test_editorial_planner_publication_4a4_audit.py",
)
BROADER_SLICE_TEST_PATHS = FOCUSED_TEST_PATHS + (
    "app/tests/test_editorial_planning.py",
    "app/tests/test_editorial_planning_language_policy.py",
    "app/tests/test_editorial_planning_document_language.py",
)

BOOK_GENERATOR = "NOT STARTED"
NEXT_ACTION = "HUMAN REVIEW"

assert EDITORIAL_PLAN_PUBLICATION_AUTHORIZED is True
assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
assert PHASE_4A4_COST_USD == 0.0
assert FINAL_TITLE_APPROVED is False
assert BOOK_GENERATOR == "NOT STARTED"
assert EXPECTED_CANDIDATE_SHA256.startswith("01cfb86a")
