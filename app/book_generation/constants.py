"""
Book Generator — Phase 4B.1 constants.

Generic implementation must not treat pastoral inventory counts or English
as code defaults. Production identity values below are gate/audit data only.
"""

from __future__ import annotations

PHASE = "4B.1"
PHASE_NAME = "BOOK_GENERATOR_ARCHITECTURE_AND_OFFLINE_FOUNDATION"

BOOK_SCHEMA_VERSION = "1.0"
BOOK_GENERATOR_PROMPT_VERSION_V10 = "book-generator-1.0"
BOOK_GENERATOR_PROMPT_VERSION = "book-generator-1.0.1"
BOOK_GENERATION_TRANSPORT_VERSION = "book-generation-transport-1.0"
BOOK_GENERATOR_VALIDATOR_VERSION_V10 = "book-generation-validator-1.0"
BOOK_GENERATOR_VALIDATOR_VERSION = "book-generation-validator-1.0.1"
BOOK_GENERATOR_SETTINGS_VERSION = "book-generator-settings-1.0"
IDEA_ACCOUNTABILITY_POLICY_VERSION = "book-idea-accountability-1.0"
TRACEABILITY_CONTRACT_VERSION = "book-traceability-1.0"
EVIDENCE_BUNDLE_VERSION = "book-evidence-bundle-1.0"
HYDRATION_POLICY_VERSION = "book-src-hydration-1.0"

STAGE_BOOK_GENERATION = "book_generation"
STRATEGY_CHAPTER = "one_chapter_per_call"
FALLBACK_SECTION = "one_section_per_call"

PROVIDER = "anthropic"
MODEL = "claude-sonnet-5"

PUBLICATION_AUTHORIZED = False
BOOK_FILENAME = "book.json"

PARAGRAPH_KIND_SUBSTANTIVE = "substantive"
PARAGRAPH_KIND_CONNECTIVE = "connective"
PARAGRAPH_KINDS = (PARAGRAPH_KIND_SUBSTANTIVE, PARAGRAPH_KIND_CONNECTIVE)

TRANSPORT_KIND_SUBSTANTIVE = "sub"
TRANSPORT_KIND_CONNECTIVE = "con"
TRANSPORT_KINDS = (TRANSPORT_KIND_SUBSTANTIVE, TRANSPORT_KIND_CONNECTIVE)

TITLE_STATUS_WORKING = "working"
TITLE_STATUS_FINAL_APPROVED = "final_approved"

EVIDENCE_STRATEGY_SOURCE_MAP_ONLY = "SOURCE_MAP_ONLY"
EVIDENCE_STRATEGY_HYDRATED = "SOURCE_MAP_PLUS_TARGETED_TRANSCRIPT_HYDRATION"

GENERATION_UNIT_CHAPTER = "CHAPTER"
GENERATION_UNIT_SECTION = "SECTION"

VALIDATION_PASS = "PASS"
VALIDATION_REVIEW = "REVIEW"
VALIDATION_FAIL = "FAIL"
VALIDATION_BLOCKED = "BLOCKED"

LANGUAGE_POLICY = "TRANSCRIPTION_DERIVED_PRIMARY_LANGUAGE"

# Safety bounds only — not style targets.
MAX_PARAGRAPH_CHARS = 4000
MAX_CONNECTIVE_CHARS = 400
MIN_SUBSTANTIVE_CHARS = 1

# Output budget derived from chapter evidence, not Planner 65536.
MIN_MAX_OUTPUT_TOKENS = 4096
DEFAULT_MAX_OUTPUT_TOKENS = 16384
CONSERVATIVE_MAX_OUTPUT_TOKENS = 24000
HARD_MAX_OUTPUT_TOKENS = 32000
MODEL_MAX_OUTPUT_TOKENS = 128_000

# Fallback triggers (deterministic, not dynamic improvisation).
FALLBACK_UTILIZATION_TRIGGER = 0.85
FALLBACK_OUTPUT_TRIGGER = HARD_MAX_OUTPUT_TOKENS

RETRY_POLICY = "one_real_call_per_generation_unit"
CANARY_AUTOMATIC_RETRIES = 0

# Production identity gate — not generic defaults.
VALIDATION_PROJECT_NAME = "pastoral_retreat_v2_validation"
EXPECTED_SOURCE_MAP_SHA256 = (
    "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855"
)
EXPECTED_EDITORIAL_PLAN_SHA256 = (
    "01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440"
)
EXPECTED_SOURCE_MAP_BYTES = 202398
EXPECTED_EDITORIAL_PLAN_BYTES = 234637
EXPECTED_WORKING_TITLE = "The Life You Already Inherited"

AUDIT_DIRNAME = "book_generator_4b1"
AUDIT_ARCHITECTURE = "book_generator_4b1_architecture.json"
AUDIT_INPUT_CONTRACT = "book_generator_4b1_input_contract.json"
AUDIT_OUTPUT_CONTRACT = "book_generator_4b1_output_contract.json"
AUDIT_TRACEABILITY = "book_generator_4b1_traceability_contract.json"
AUDIT_EVIDENCE = "book_generator_4b1_evidence_strategy.json"
AUDIT_HYDRATION = "book_generator_4b1_transcript_hydration_analysis.json"
AUDIT_GENERATION = "book_generator_4b1_generation_strategy.json"
AUDIT_SCHEMA = "book_generator_4b1_schema_identity.json"
AUDIT_PROMPT = "book_generator_4b1_prompt_identity.json"
AUDIT_TRANSPORT = "book_generator_4b1_transport_identity.json"
AUDIT_BUDGET = "book_generator_4b1_real_corpus_budget.json"
AUDIT_DISTRIBUTION = "book_generator_4b1_chapter_distribution.json"
AUDIT_COST = "book_generator_4b1_cost_estimate.json"
AUDIT_FAKEAI = "book_generator_4b1_fakeai_validation.json"
AUDIT_PREFLIGHT = "book_generator_4b1_request_preflight.json"
AUDIT_READINESS = "book_generator_post_4b1_readiness.json"
AUDIT_REPORT = "PHASE_4B1_BOOK_GENERATOR_ARCHITECTURE_AND_OFFLINE_FOUNDATION_REPORT.md"

REAL_PROVIDER_CALLS_THIS_PHASE = 0
BOOK_GENERATOR_THINKING_VALIDATED = False
READY_FOR_REAL_BOOK_GENERATION = False

assert PUBLICATION_AUTHORIZED is False
assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
assert BOOK_SCHEMA_VERSION == "1.0"
assert PROVIDER == "anthropic"
assert MODEL == "claude-sonnet-5"
assert BOOK_GENERATOR_PROMPT_VERSION_V10 == "book-generator-1.0"
assert BOOK_GENERATOR_PROMPT_VERSION == "book-generator-1.0.1"
assert BOOK_GENERATION_TRANSPORT_VERSION == "book-generation-transport-1.0"
assert BOOK_GENERATOR_VALIDATOR_VERSION_V10 == "book-generation-validator-1.0"
assert BOOK_GENERATOR_VALIDATOR_VERSION == "book-generation-validator-1.0.1"
assert CANARY_AUTOMATIC_RETRIES == 0
assert READY_FOR_REAL_BOOK_GENERATION is False
