"""
Phase 4B.2 — one real small-chapter Book Generator canary.

Exactly one Anthropic Sonnet 5 call. Target CH016. Audit only.
Zero retries. Zero fallbacks. No book.json. No Phase 5.
"""

from __future__ import annotations

from app.ai.thinking import THINKING_MODE_DISABLED
from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION_V10,
    EXPECTED_EDITORIAL_PLAN_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    MODEL,
    PROVIDER,
    VALIDATION_PROJECT_NAME,
)

PHASE = "4B.2"
PHASE_NAME = "BOOK_GENERATOR_ONE_REAL_SMALL_CHAPTER_CANARY"
CANARY_VERSION = "book-generator-canary-4b2-1.0"

AUTHORIZATION_SCOPE = "BOOK_GENERATOR_4B2_ONE_REAL_SMALL_CHAPTER_CANARY_ONLY"

assert PROVIDER == "anthropic"
assert MODEL == "claude-sonnet-5"

PROMPT_VERSION = BOOK_GENERATOR_PROMPT_VERSION_V10
TRANSPORT_VERSION = BOOK_GENERATION_TRANSPORT_VERSION
assert PROMPT_VERSION == "book-generator-1.0"
assert TRANSPORT_VERSION == "book-generation-transport-1.0"

PROJECT_NAME = VALIDATION_PROJECT_NAME
assert PROJECT_NAME == "pastoral_retreat_v2_validation"

TARGET_CHAPTER_ID = "CH016"

MAX_ENGINE_GENERATE = 1
MAX_ANTHROPIC_POST = 1
MAX_ATTEMPTS = 1
RETRIES = 0
FALLBACKS = 0
AUTHORIZED_PROVIDER_CALLS = 1

THINKING_MODE = THINKING_MODE_DISABLED
assert THINKING_MODE == "disabled"

# Conservative existing Anthropic production timeouts. 4B.1 did not freeze
# a canary-specific pair; do not mutate provider infrastructure.
CONNECT_TIMEOUT_SECONDS = 30.0
READ_TIMEOUT_SECONDS = 1800.0

# Frozen 4B.1 schema identity.
PHASE_4B1_RAW_SCHEMA_BYTES = 1035
PHASE_4B1_ADAPTED_SCHEMA_BYTES = 1128
PHASE_4B1_RAW_SCHEMA_SHA256 = (
    "075455fdbf18548b3bd2c05b5c7abf35bf43d2c4cecc74f3af6963c540028273"
)
PHASE_4B1_ADAPTED_SCHEMA_SHA256 = (
    "dce904e8a1a32a700d91cdef5e5d5bc916ce3d6ce10e2b644cdfaa6f68dc6626"
)

# Frozen 4B.1 CH016 preflight identity — mismatch means inputs or path changed.
PHASE_4B1_CH016_REQUEST_SHA256 = (
    "3e1b3ab243eb17ce07186fe38853c54d903470d81391c7540b757245f92744d8"
)
PHASE_4B1_CH016_EVIDENCE_SHA256 = (
    "bc15f06b05b1160aed413720f52c104cbb63cf4c98f07ce3fb8e8d2d732a0e93"
)
PHASE_4B1_CH016_MAX_OUTPUT = 16384
PHASE_4B1_TRANSCRIPT_CONTENT_SHA256 = (
    "1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958"
)

assert EXPECTED_SOURCE_MAP_SHA256 == (
    "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855"
)
assert EXPECTED_EDITORIAL_PLAN_SHA256 == (
    "01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440"
)

STAGE_CANARY = "book_generation_canary"
CANARY_WINDOW_ID = "CANARY_BG4B2"
LOCK_NAME = "canary_real_call.lock"

AUDIT_DIRNAME = "book_generator_4b2"
AUDIT_REAL_PARENT = "real"
AUDIT_PRECALL = "book_generator_4b2_precall_identity.json"
AUDIT_EVIDENCE = "book_generator_4b2_evidence_bundle.json"
AUDIT_HYDRATION = "book_generator_4b2_hydration.json"
AUDIT_REQUEST = "book_generator_4b2_request_identity.json"
AUDIT_PROVIDER = "book_generator_4b2_provider_evidence.json"
AUDIT_RESPONSE = "book_generator_4b2_response_identity.json"
AUDIT_STRUCTURAL = "book_generator_4b2_structural_validation.json"
AUDIT_COVERAGE = "book_generator_4b2_idea_coverage.json"
AUDIT_PROVENANCE = "book_generator_4b2_paragraph_provenance.json"
AUDIT_LANGUAGE = "book_generator_4b2_language_validation.json"
AUDIT_FIDELITY = "book_generator_4b2_fidelity_review.json"
AUDIT_QUALITY = "book_generator_4b2_manuscript_quality_review.json"
AUDIT_COST = "book_generator_4b2_cost_calibration.json"
AUDIT_READINESS = "book_generator_post_4b2_readiness.json"
AUDIT_CANDIDATE = "chapter_CH016_candidate.json"
AUDIT_RAW_RESPONSE = "book_generator_4b2_raw_structured_response.json"
AUDIT_RAW_TEXT = "book_generator_4b2_raw_provider_text.txt"
AUDIT_EXECUTION = "book_generator_4b2_execution.json"
REPORT_NAME = "PHASE_4B2_BOOK_GENERATOR_ONE_REAL_SMALL_CHAPTER_CANARY_REPORT.md"

PUBLICATION_AUTHORIZED = False
BOOK_JSON = "NOT PUBLISHED"
READY_FOR_FULL_REAL_BOOK_GENERATION = False
NEXT_ACTION = "HUMAN REVIEW"

assert PUBLICATION_AUTHORIZED is False
assert RETRIES == 0
assert FALLBACKS == 0
assert MAX_ENGINE_GENERATE == 1
assert AUTHORIZED_PROVIDER_CALLS == 1
assert TARGET_CHAPTER_ID == "CH016"
assert PHASE_4B1_RAW_SCHEMA_BYTES == 1035
assert PHASE_4B1_ADAPTED_SCHEMA_BYTES == 1128
assert PHASE_4B1_CH016_MAX_OUTPUT == 16384
assert THINKING_MODE == "disabled"
assert READY_FOR_FULL_REAL_BOOK_GENERATION is False
