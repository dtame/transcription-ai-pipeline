"""
Phase 4B.2.26 — CH003/CH004 acceptance and 13-chapter generation readiness.

STRICTLY OFFLINE. Isolated from production. Zero provider calls.
Does not generate remaining chapters. Does not activate the future
BOOK_GENERATION_REMAINING_13_CHAPTERS_ONE_SHOT authorization.
Does not modify accepted prose. Does not publish book.json.
Does not write the production cache. Does not change the prompt or model.
"""

from __future__ import annotations

from decimal import Decimal

from app.book_authorial_voice_4b218.constants import (
    AUTHORIAL_VOICE_POLICY_VERSION,
    FAITHFUL_PROMPT_1_0_VERSION,
    FAITHFUL_PROMPT_1_1_VERSION,
    HISTORICAL_PROMPT_V10,
    HISTORICAL_PROMPT_V101,
)
from app.book_authorial_voice_4b218.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B218_SCOPE,
)
from app.book_batch_preparation_4b222.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B222_SCOPE,
)
from app.book_ch002_offline_recovery_4b224.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B224_SCOPE,
    EMPTY_PARAGRAPH_ID,
)
from app.book_editorial_acceptance_4b219.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B219_SCOPE,
    EXPECTED_ACCEPTED_JSON_SHA256,
    EXPECTED_ACCEPTED_MD_SHA256,
    EXPECTED_LOCK_SHA256,
    EXPECTED_ORIGINAL_JSON_SHA256,
    EXPECTED_ORIGINAL_MD_SHA256,
)
from app.book_editorial_alignment_4b216.constants import (
    COVERAGE_CONTRACT_VERSION,
    EDITORIAL_POLICY_VERSION,
    HISTORICAL_SEMANTIC_CONTRACT,
)
from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION_V10,
    BOOK_GENERATOR_VALIDATOR_VERSION,
    EXPECTED_EDITORIAL_PLAN_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    HARD_MAX_OUTPUT_TOKENS,
    MIN_MAX_OUTPUT_TOKENS,
    MODEL,
    PROVIDER,
    VALIDATION_PROJECT_NAME,
)
from app.book_generation_4b217.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B217_SCOPE,
    SONNET_INPUT_COST_PER_1M,
    SONNET_OUTPUT_COST_PER_1M,
)
from app.book_generation_4b221.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B221_SCOPE,
)
from app.book_generation_4b223.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B223_SCOPE,
    EXPECTED_CH018_JSON_SHA256,
    EXPECTED_CH018_MD_SHA256,
)
from app.book_generation_4b225.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B225_SCOPE,
    EXPECTED_CH001_JSON_SHA256,
    EXPECTED_CH001_LOCK_SHA256,
    EXPECTED_CH001_MD_SHA256,
    EXPECTED_CH002_LOCK_SHA256,
    EXPECTED_CH002_ORIGINAL_JSON_SHA256,
    EXPECTED_CH002_ORIGINAL_MD_SHA256,
    EXPECTED_CH002_RECOVERED_JSON_INMEMORY_4B224_SHA256,
    EXPECTED_CH002_RECOVERED_JSON_SHA256,
    EXPECTED_CH002_RECOVERED_MD_SHA256,
)
from app.book_scale_up_preparation_4b220.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B220_SCOPE,
    EXPECTED_PROMPT_1_1_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_1_1_SHA256,
    EXPECTED_PROMPT_1_1_SYSTEM_SHA256,
    FAITHFUL_PROMPT_1_1,
    TOTAL_CHAPTER_COUNT,
)
from app.book_semantic_gate_4b23.constants import EXPECTED_CLEAN_TRANSCRIPT
from app.book_semantic_gate_4b26.constants import CANONICAL_PYTHON_EXECUTABLE

PHASE = "4B.2.26"
PHASE_NAME = "CH003_CH004_ACCEPTANCE_AND_FULL_GENERATION_PREPARATION"

PROJECT_NAME = VALIDATION_PROJECT_NAME
assert PROJECT_NAME == "pastoral_retreat_v2_validation"

AUTHORIZATION_SCOPE = (
    "BOOK_FULL_GENERATION_PREPARATION_4B226_CH003_CH004_ACCEPTANCE_"
    "AND_13_CHAPTER_READINESS_ONLY"
)

FUTURE_AUTHORIZATION_SCOPE = "BOOK_GENERATION_REMAINING_13_CHAPTERS_ONE_SHOT"
FUTURE_AUTHORIZATION_ACTIVATED = False

AUTHORIZED_ANTHROPIC_CALLS = 0
AUTHORIZED_SONNET_CALLS = 0
AUTHORIZED_REMOTE_INVOCATIONS = 0
AUTHORIZED_OPENAI_CALLS = 0
AUTHORIZED_TERRA_CALLS = 0
MAX_ENGINE_GENERATE = 0
MAX_ANTHROPIC_POST = 0
MAX_HTTP_REQUESTS = 0
RETRIES = 0
FALLBACKS = 0
SDK_MAX_RETRIES = 0

PUBLICATION_AUTHORIZED = False
TERRA_EXECUTION_AUTHORIZED = False
OPENAI_EXECUTION_AUTHORIZED = False
SONNET_EXECUTION_AUTHORIZED = False
REAL_CHAPTER_GENERATION_AUTHORIZED = False
REAL_PROVIDERS_ENABLED = False
PRODUCTION_PIPELINE_HOOK = False
PRODUCTION_CACHE_ACCEPTANCE = False
FAITHFUL_PROMPT_ACTIVATED_IN_PRODUCTION = False
FAITHFUL_PROMPT_1_1_ACTIVATED = False
EDITORIAL_POLICY_ACTIVATED_IN_PRODUCTION = False
COVERAGE_CONTROL_ACTIVATED_IN_PRODUCTION = False
SEMANTIC_GATE_202_ENABLED = False
SEMANTIC_CERTIFICATION_PERFORMED = False
BOOK_JSON_PUBLICATION = False
HISTORICAL_REMAINDER_IS_AUTHORIZATION = False

ACCEPTED_CHAPTER_IDS = ("CH001", "CH002", "CH003", "CH004", "CH012", "CH018")
REMAINING_CHAPTER_IDS = (
    "CH005",
    "CH006",
    "CH007",
    "CH008",
    "CH009",
    "CH010",
    "CH011",
    "CH013",
    "CH014",
    "CH015",
    "CH016",
    "CH017",
    "CH019",
)
ACCEPTED_CHAPTER_COUNT = 6
REMAINING_CHAPTER_COUNT = 13
assert ACCEPTED_CHAPTER_COUNT + REMAINING_CHAPTER_COUNT == TOTAL_CHAPTER_COUNT
assert TOTAL_CHAPTER_COUNT == 19
FUTURE_MAX_CALLS = 13
FUTURE_MAX_CALLS_PER_CHAPTER = 1

PROMPT_VERSION = FAITHFUL_PROMPT_1_1
TRANSPORT_VERSION = BOOK_GENERATION_TRANSPORT_VERSION
VALIDATOR_VERSION = BOOK_GENERATOR_VALIDATOR_VERSION
NARRATIVE_VOICE_CONTRACT = AUTHORIAL_VOICE_POLICY_VERSION
EDITORIAL_POLICY = EDITORIAL_POLICY_VERSION

assert PROVIDER == "anthropic"
assert MODEL == "claude-sonnet-5"
assert PROMPT_VERSION == "book-generator-faithful-restatement-1.1-candidate"
assert PROMPT_VERSION == FAITHFUL_PROMPT_1_1_VERSION
assert FAITHFUL_PROMPT_1_0_VERSION == "book-generator-faithful-restatement-1.0-candidate"
assert HISTORICAL_PROMPT_V101 == BOOK_GENERATOR_PROMPT_VERSION == "book-generator-1.0.1"
assert HISTORICAL_PROMPT_V10 == BOOK_GENERATOR_PROMPT_VERSION_V10 == "book-generator-1.0"
assert TRANSPORT_VERSION == "book-generation-transport-1.0"
assert EDITORIAL_POLICY_VERSION == "faithful-teaching-book-editorial-policy-1.0-candidate"
assert COVERAGE_CONTRACT_VERSION == "source-coverage-control-4b216-candidate"
assert HISTORICAL_SEMANTIC_CONTRACT == "book-semantic-validator-2.0.2-candidate"
assert NARRATIVE_VOICE_CONTRACT == "authorial-voice-preservation-1.0-candidate"
assert VALIDATOR_VERSION == "book-generation-validator-1.0.1"
assert CONSUMED_4B217_SCOPE == (
    "BOOK_GENERATION_4B217_CH012_FAITHFUL_REAL_PILOT_GENERATION_ONLY"
)
assert CONSUMED_4B218_SCOPE.startswith("BOOK_AUTHORIAL_VOICE_4B218_")
assert CONSUMED_4B219_SCOPE.startswith("BOOK_EDITORIAL_ACCEPTANCE_4B219_")
assert CONSUMED_4B220_SCOPE.startswith("BOOK_SCALE_UP_PREPARATION_4B220_")
assert CONSUMED_4B221_SCOPE == (
    "BOOK_GENERATION_LATER_PHASE_CH018_FIRST_REMAINING_CHAPTER_ONE_SHOT_ONLY"
)
assert CONSUMED_4B222_SCOPE.startswith("BOOK_BATCH_PREPARATION_4B222_")
assert CONSUMED_4B223_SCOPE == (
    "BOOK_GENERATION_BATCH_01_CH001_CH004_ONE_SHOT_PER_CHAPTER"
)
assert CONSUMED_4B224_SCOPE.startswith("BOOK_CH002_OFFLINE_RECOVERY_4B224_")
assert CONSUMED_4B225_SCOPE == (
    "BOOK_GENERATION_BATCH01_RESUME_CH003_CH004_ONE_SHOT_ONLY"
)

CODE_VERSION = "app.book_full_generation_preparation_4b226"
NORMALIZER_VERSION = "empty-unprovenanced-paragraph-normalizer-4b226-1.0"
MANIFEST_VERSION = "accepted-editorial-manifest-4b226-1.0"
FUTURE_LOCK_VERSION = "remaining-13-call-lock-4b226-1.0"

CANONICAL_PYTHON = CANONICAL_PYTHON_EXECUTABLE
EXPECTED_SOURCE_MAP = EXPECTED_SOURCE_MAP_SHA256
EXPECTED_EDITORIAL_PLAN = EXPECTED_EDITORIAL_PLAN_SHA256
EXPECTED_TRANSCRIPT = EXPECTED_CLEAN_TRANSCRIPT

assert EXPECTED_SOURCE_MAP == (
    "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855"
)
assert EXPECTED_EDITORIAL_PLAN == (
    "01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440"
)
assert EXPECTED_TRANSCRIPT == (
    "1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958"
)
assert EXPECTED_PROMPT_1_1_SHA256 == (
    "e39084dc9ed3b048bfdaa2e112b380d15957085eeb613dd74c97a32b880cec50"
)
assert AUTHORIZED_ANTHROPIC_CALLS == 0
assert AUTHORIZED_OPENAI_CALLS == 0
assert AUTHORIZED_TERRA_CALLS == 0
assert FUTURE_AUTHORIZATION_ACTIVATED is False
assert PUBLICATION_AUTHORIZED is False
assert REAL_CHAPTER_GENERATION_AUTHORIZED is False
assert PRODUCTION_PIPELINE_HOOK is False
assert FAITHFUL_PROMPT_1_1_ACTIVATED is False
assert MIN_MAX_OUTPUT_TOKENS == 4096
assert HARD_MAX_OUTPUT_TOKENS == 32000
assert CANONICAL_PYTHON.endswith("python.exe")
assert SONNET_INPUT_COST_PER_1M == Decimal("2.00")
assert SONNET_OUTPUT_COST_PER_1M == Decimal("10.00")

CH001_APPROVED_JSON_REL = (
    "audit/real/book_generation_4b223_batch01/chapters/CH001/chapter_candidate.json"
)
CH001_APPROVED_MD_REL = (
    "audit/real/book_generation_4b223_batch01/chapters/CH001/chapter_candidate.md"
)
CH002_APPROVED_JSON_REL = (
    "audit/book_ch002_offline_recovery_4b224/chapter_candidate_recovered.json"
)
CH002_APPROVED_MD_REL = (
    "audit/book_ch002_offline_recovery_4b224/chapter_candidate_recovered.md"
)
CH002_ORIGINAL_JSON_REL = (
    "audit/real/book_generation_4b223_batch01/chapters/CH002/chapter_candidate.json"
)
CH002_ORIGINAL_MD_REL = (
    "audit/real/book_generation_4b223_batch01/chapters/CH002/chapter_candidate.md"
)
CH002_ORIGINAL_RAW_REL = (
    "audit/real/book_generation_4b223_batch01/chapters/CH002/provider_response_raw.json"
)
CH003_APPROVED_JSON_REL = (
    "audit/real/book_generation_4b225_batch01_resume/chapters/CH003/chapter_candidate.json"
)
CH003_APPROVED_MD_REL = (
    "audit/real/book_generation_4b225_batch01_resume/chapters/CH003/chapter_candidate.md"
)
CH004_APPROVED_JSON_REL = (
    "audit/real/book_generation_4b225_batch01_resume/chapters/CH004/chapter_candidate.json"
)
CH004_APPROVED_MD_REL = (
    "audit/real/book_generation_4b225_batch01_resume/chapters/CH004/chapter_candidate.md"
)
CH012_MANIFEST_REL = "audit/book_editorial_acceptance_4b219/ch012_accepted_editorial_manifest.json"
CH018_MANIFEST_REL = "audit/book_batch_preparation_4b222/ch018_accepted_editorial_manifest.json"
CH001_MANIFEST_REL = (
    "audit/real/book_generation_4b225_batch01_resume/ch001_accepted_editorial_manifest.json"
)
CH002_MANIFEST_REL = (
    "audit/real/book_generation_4b225_batch01_resume/ch002_accepted_editorial_manifest.json"
)

EXPECTED_CH003_JSON_SHA256 = (
    "3ddc2f1298b3db9eb8646161e794b7289f4e9004f274bc1cbc427d7befc37f19"
)
EXPECTED_CH003_MD_SHA256 = (
    "7f87e86927bd0c60a7b3d5d64ba5c3fa0d8c1e8119fa26c285614a9b8999aae5"
)
EXPECTED_CH004_JSON_SHA256 = (
    "eceb00dfb019d3e6a247607143447436c7568cb230575211d4128b421ec5b012"
)
EXPECTED_CH004_MD_SHA256 = (
    "37154ea2d01c0beadc9d4cada1600f7e0f0b9a3c6012bcce7e792e4a8ee95580"
)

CH001_PRESERVED_SENTENCE = "You only did not accept it there."
CH002_REMOVED_EMPTY_PARAGRAPH = EMPTY_PARAGRAPH_ID
CH003_EX005_STATUS = "undetermined_handle_absent_is_not_omission"
CH004_REF_ABSENT_STATUS = "undetermined_handle_absent_is_not_omission"
CH004_ALWAYS_FORMULATION = "We must always remain alert"
CH004_NEVER_FORMULATION = "I have never had to look for people"
CH004_STRENGTHENED_DETAIL = "Absolute wording may strengthen a source claim."
HUMAN_ACCEPTANCE_STATUS = "HUMAN_EDITORIALLY_ACCEPTED"
DECISION_SOURCE = "explicit_user_approval"
RECORDING_DATE = "2026-10-04"

CH001_ACTUAL_COST_USD = Decimal("0.035854")
CH002_ACTUAL_COST_USD = Decimal("0.039430")
CH003_ACTUAL_COST_USD = Decimal("0.046162")
CH004_ACTUAL_COST_USD = Decimal("0.047116")
CH012_ACTUAL_COST_USD = Decimal("0.036152")
CH018_ACTUAL_COST_USD = Decimal("0.041500")

AUTHORIZED_SPEND_USD = Decimal("0")
PROPOSED_CAP_MARGIN = Decimal("0.15")
PRICING_EFFECTIVE_DATE = "2026-09-18"
PESSIMISTIC_CHARS_PER_TOKEN = Decimal("1.9365384615384615")
OBSERVED_IDEA_SCALE = Decimal("11")

LOCK_STATE_NOT_STARTED = "NOT_STARTED"
LOCK_STATE_PREFLIGHT = "PREFLIGHT_VALIDATED"
LOCK_STATE_RESERVED = "CALL_RESERVED"
LOCK_STATE_MAY_HAVE_BEEN_SENT = "CALL_MAY_HAVE_BEEN_SENT"
LOCK_STATE_RESPONSE_RECEIVED = "RESPONSE_RECEIVED"
LOCK_STATE_RESPONSE_VALIDATED = "RESPONSE_VALIDATED"
LOCK_STATE_FAILED = "FAILED"
LOCK_STATE_UNCERTAIN = "UNCERTAIN"

LOCK_CONSUMED_STATES = frozenset(
    {
        LOCK_STATE_RESERVED,
        LOCK_STATE_MAY_HAVE_BEEN_SENT,
        LOCK_STATE_RESPONSE_RECEIVED,
        LOCK_STATE_RESPONSE_VALIDATED,
        LOCK_STATE_FAILED,
        LOCK_STATE_UNCERTAIN,
    }
)
LOCK_RESUME_WITHOUT_RECALL = frozenset({LOCK_STATE_RESPONSE_VALIDATED})
LOCK_STOP_STATES = frozenset(
    {
        LOCK_STATE_RESERVED,
        LOCK_STATE_MAY_HAVE_BEEN_SENT,
        LOCK_STATE_RESPONSE_RECEIVED,
        LOCK_STATE_FAILED,
        LOCK_STATE_UNCERTAIN,
    }
)

STRUCTURAL_PARAGRAPH_KEYS = frozenset(
    {
        "text",
        "t",
        "kind",
        "k",
        "paragraph_id",
        "provider_handle",
        "h",
        "evidence_handles",
        "e",
        "source_refs",
        "idea_refs",
        "example_refs",
        "reference_refs",
        "uncertainty_refs",
        "u",
    }
)
ATTRIBUTION_KEYS = frozenset(
    {"attribution", "speaker", "attributed_to", "voice", "narrator"}
)
CITATION_KEYS = frozenset(
    {"citation", "quote", "quoted", "quotation", "quoted_text", "quoted_source"}
)
PROVENANCE_FIELDS = (
    "evidence_handles",
    "e",
    "source_refs",
    "idea_refs",
    "example_refs",
    "reference_refs",
    "uncertainty_refs",
    "u",
)

FORBIDDEN_PROMPT_CLAUSES = (
    "High stylistic freedom",
    "Stylistic expansion is allowed",
)
FORBIDDEN_PROMPTS = (
    "book-generator-1.0",
    "book-generator-1.0.1",
    "book-generator-faithful-restatement-1.0-candidate",
)

AUDIT_DIRNAME = "book_full_generation_preparation_4b226"
AUDIT_CH003_MANIFEST = "ch003_accepted_editorial_manifest.json"
AUDIT_CH004_MANIFEST = "ch004_accepted_editorial_manifest.json"
AUDIT_ACCEPTED_INVENTORY = "accepted_chapters_inventory.json"
AUDIT_NORMALIZER_SPEC = "empty_paragraph_normalization_spec.json"
AUDIT_NORMALIZER_TESTS = "empty_paragraph_normalization_tests.json"
AUDIT_REMAINING_INVENTORY = "remaining_chapters_inventory.json"
AUDIT_PLAN = "remaining_chapters_generation_plan.json"
AUDIT_COST = "remaining_chapters_budget_forecast.json"
AUDIT_AUTHORIZATION = "global_authorization_proposal.json"
AUDIT_SIMULATION = "full_batch_offline_simulation.json"
AUDIT_RESUME = "resume_and_lock_validation.json"
AUDIT_HASHES_PRE = "canonical_hashes_pre.json"
AUDIT_HASHES_POST = "canonical_hashes_post.json"
AUDIT_HASHES_PRE_POST = "canonical_hashes_pre_post.json"
AUDIT_READINESS = "readiness.json"
AUDIT_PREFLIGHT = "preflight.json"
AUDIT_TESTS = "offline_regression_tests.json"
REPORT_NAME = "PHASE_4B226_FULL_GENERATION_PREPARATION_REPORT.md"

NEXT_ACTION = (
    "WAIT FOR THE USER'S EXPLICIT SINGLE AUTHORIZATION OF THE REMAINING "
    "13 CHAPTERS UNDER BOOK_GENERATION_REMAINING_13_CHAPTERS_ONE_SHOT, "
    "WITH ITS GLOBAL FINANCIAL CAP. DO NOT CALL ANTHROPIC. DO NOT CALL "
    "OPENAI. DO NOT GENERATE CH005-CH019. DO NOT REUSE A HISTORICAL "
    "REMAINING BUDGET. DO NOT REQUEST CHAPTER-BY-CHAPTER AUTHORIZATION."
)

__all__ = [
    "ACCEPTED_CHAPTER_IDS",
    "AUTHORIZATION_SCOPE",
    "CANONICAL_PYTHON",
    "EXPECTED_CH003_JSON_SHA256",
    "EXPECTED_CH003_MD_SHA256",
    "EXPECTED_CH004_JSON_SHA256",
    "EXPECTED_CH004_MD_SHA256",
    "EXPECTED_EDITORIAL_PLAN",
    "EXPECTED_PROMPT_1_1_SHA256",
    "EXPECTED_SOURCE_MAP",
    "EXPECTED_TRANSCRIPT",
    "FUTURE_AUTHORIZATION_SCOPE",
    "HUMAN_ACCEPTANCE_STATUS",
    "PHASE",
    "PROMPT_VERSION",
    "REMAINING_CHAPTER_IDS",
    "VALIDATOR_VERSION",
]
