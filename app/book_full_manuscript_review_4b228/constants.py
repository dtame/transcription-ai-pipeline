"""
Phase 4B.2.28 — full manuscript editorial consolidation.

STRICTLY OFFLINE. Isolated from production. Zero provider calls.
Assembles the 19 already-generated chapters into one reading manuscript.
Does not regenerate, rewrite, publish book.json, or emit DOCX/PDF.
Does not spend the 4B.2.27 remainder. Does not approve pending chapters.
"""

from __future__ import annotations

from app.book_authorial_voice_4b218.constants import (
    AUTHORIAL_VOICE_POLICY_VERSION,
    FAITHFUL_PROMPT_1_1_VERSION,
)
from app.book_authorial_voice_4b218.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B218_SCOPE,
)
from app.book_batch_preparation_4b222.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B222_SCOPE,
)
from app.book_ch002_offline_recovery_4b224.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B224_SCOPE,
)
from app.book_editorial_acceptance_4b219.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B219_SCOPE,
    EXPECTED_ACCEPTED_JSON_SHA256,
    EXPECTED_ACCEPTED_MD_SHA256,
    EXPECTED_LOCK_SHA256,
    EXPECTED_ORIGINAL_JSON_SHA256,
    EXPECTED_ORIGINAL_MD_SHA256,
)
from app.book_editorial_alignment_4b216.constants import EDITORIAL_POLICY_VERSION
from app.book_full_generation_preparation_4b226.constants import (
    ACCEPTED_CHAPTER_COUNT,
    ACCEPTED_CHAPTER_IDS,
    AUTHORIZATION_SCOPE as CONSUMED_4B226_SCOPE,
    CH001_APPROVED_JSON_REL,
    CH001_APPROVED_MD_REL,
    CH001_MANIFEST_REL,
    CH002_APPROVED_JSON_REL,
    CH002_APPROVED_MD_REL,
    CH002_MANIFEST_REL,
    CH002_ORIGINAL_JSON_REL,
    CH002_ORIGINAL_MD_REL,
    CH003_APPROVED_JSON_REL,
    CH003_APPROVED_MD_REL,
    CH004_APPROVED_JSON_REL,
    CH004_APPROVED_MD_REL,
    CH012_MANIFEST_REL,
    CH018_MANIFEST_REL,
    EXPECTED_CH003_JSON_SHA256,
    EXPECTED_CH003_MD_SHA256,
    EXPECTED_CH004_JSON_SHA256,
    EXPECTED_CH004_MD_SHA256,
    HUMAN_ACCEPTANCE_STATUS,
    REMAINING_CHAPTER_COUNT,
    REMAINING_CHAPTER_IDS,
    TOTAL_CHAPTER_COUNT,
)
from app.book_generation.constants import (
    EXPECTED_EDITORIAL_PLAN_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    VALIDATION_PROJECT_NAME,
)
from app.book_generation_4b217.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B217_SCOPE,
)
from app.book_generation_4b221.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B221_SCOPE,
)
from app.book_generation_4b223.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B223_SCOPE,
    EXPECTED_CH018_JSON_SHA256,
    EXPECTED_CH018_MD_SHA256,
    REVIEW_NO_ISSUE,
    REVIEW_POTENTIAL,
    REVIEW_RECOMMENDED,
    REVIEW_UNDETERMINED,
)
from app.book_generation_4b225.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B225_SCOPE,
    EXPECTED_CH001_JSON_SHA256,
    EXPECTED_CH001_MD_SHA256,
    EXPECTED_CH002_ORIGINAL_JSON_SHA256,
    EXPECTED_CH002_ORIGINAL_MD_SHA256,
    EXPECTED_CH002_RECOVERED_JSON_SHA256,
    EXPECTED_CH002_RECOVERED_MD_SHA256,
)
from app.book_generation_4b227.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B227_SCOPE,
    EXPECTED_REMAINING_IDEAS,
    EXPECTED_REMAINING_SECTIONS,
    GENERATED_STATUS,
)
from app.book_semantic_gate_4b23.constants import EXPECTED_CLEAN_TRANSCRIPT
from app.book_semantic_gate_4b26.constants import CANONICAL_PYTHON_EXECUTABLE

PHASE = "4B.2.28"
PHASE_NAME = "FULL_MANUSCRIPT_EDITORIAL_REVIEW"

PROJECT_NAME = VALIDATION_PROJECT_NAME
assert PROJECT_NAME == "pastoral_retreat_v2_validation"

AUTHORIZATION_SCOPE = (
    "BOOK_FULL_MANUSCRIPT_EDITORIAL_REVIEW_4B228_CONSOLIDATION_ONLY"
)

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

PUBLICATION_AUTHORIZED = False
TERRA_EXECUTION_AUTHORIZED = False
OPENAI_EXECUTION_AUTHORIZED = False
SONNET_EXECUTION_AUTHORIZED = False
REAL_CHAPTER_GENERATION_AUTHORIZED = False
REAL_PROVIDERS_ENABLED = False
PRODUCTION_PIPELINE_HOOK = False
PRODUCTION_CACHE_ACCEPTANCE = False
FAITHFUL_PROMPT_1_1_ACTIVATED = False
EDITORIAL_POLICY_ACTIVATED_IN_PRODUCTION = False
SEMANTIC_CERTIFICATION_PERFORMED = False
BOOK_JSON_PUBLICATION = False
DOCX_GENERATION_AUTHORIZED = False
PDF_GENERATION_AUTHORIZED = False
VISUAL_DIRECTION_AUTHORIZED = False

CANONICAL_CHAPTER_IDS = tuple(f"CH{index:03d}" for index in range(1, 20))
assert CANONICAL_CHAPTER_IDS[0] == "CH001"
assert CANONICAL_CHAPTER_IDS[-1] == "CH019"
assert len(CANONICAL_CHAPTER_IDS) == TOTAL_CHAPTER_COUNT == 19
assert ACCEPTED_CHAPTER_IDS == ("CH001", "CH002", "CH003", "CH004", "CH012", "CH018")
assert REMAINING_CHAPTER_IDS == (
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
assert ACCEPTED_CHAPTER_COUNT + REMAINING_CHAPTER_COUNT == TOTAL_CHAPTER_COUNT

PENDING_CHAPTER_IDS = REMAINING_CHAPTER_IDS
STRENGTHENED_CLAIM_CHAPTER_IDS = (
    "CH005",
    "CH006",
    "CH008",
    "CH009",
    "CH010",
    "CH013",
    "CH014",
    "CH017",
)

EXPECTED_SECTION_COUNT = 72
EXPECTED_IDEA_COUNT = 286
EXPECTED_ACCEPTED_SECTIONS = EXPECTED_SECTION_COUNT - EXPECTED_REMAINING_SECTIONS
EXPECTED_ACCEPTED_IDEAS = EXPECTED_IDEA_COUNT - EXPECTED_REMAINING_IDEAS
assert EXPECTED_REMAINING_SECTIONS == 47
assert EXPECTED_REMAINING_IDEAS == 204
assert EXPECTED_ACCEPTED_SECTIONS == 25
assert EXPECTED_ACCEPTED_IDEAS == 82

HUMAN_REVIEW_PENDING_STATUS = "HUMAN_REVIEW_PENDING"
GENERATED_STRUCTURALLY_VALID = GENERATED_STATUS
assert GENERATED_STRUCTURALLY_VALID == "GENERATED_STRUCTURALLY_VALID"
assert HUMAN_ACCEPTANCE_STATUS == "HUMAN_EDITORIALLY_ACCEPTED"

NARRATIVE_VOICE_CONTRACT = AUTHORIAL_VOICE_POLICY_VERSION
EDITORIAL_POLICY = EDITORIAL_POLICY_VERSION
PROMPT_VERSION = FAITHFUL_PROMPT_1_1_VERSION
CODE_VERSION = "app.book_full_manuscript_review_4b228"
MANIFEST_VERSION = "manuscript-provenance-manifest-4b228-1.0"
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
assert AUTHORIZED_ANTHROPIC_CALLS == 0
assert AUTHORIZED_OPENAI_CALLS == 0
assert AUTHORIZED_TERRA_CALLS == 0
assert PUBLICATION_AUTHORIZED is False
assert REAL_CHAPTER_GENERATION_AUTHORIZED is False
assert BOOK_JSON_PUBLICATION is False
assert DOCX_GENERATION_AUTHORIZED is False
assert PDF_GENERATION_AUTHORIZED is False
assert SEMANTIC_CERTIFICATION_PERFORMED is False
assert CANONICAL_PYTHON.endswith("python.exe")
assert CONSUMED_4B217_SCOPE == (
    "BOOK_GENERATION_4B217_CH012_FAITHFUL_REAL_PILOT_GENERATION_ONLY"
)
assert CONSUMED_4B218_SCOPE.startswith("BOOK_AUTHORIAL_VOICE_4B218_")
assert CONSUMED_4B219_SCOPE.startswith("BOOK_EDITORIAL_ACCEPTANCE_4B219_")
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
assert CONSUMED_4B226_SCOPE.startswith("BOOK_FULL_GENERATION_PREPARATION_4B226_")
assert CONSUMED_4B227_SCOPE == "BOOK_GENERATION_REMAINING_13_CHAPTERS_ONE_SHOT"
assert NARRATIVE_VOICE_CONTRACT == "authorial-voice-preservation-1.0-candidate"
assert EDITORIAL_POLICY == "faithful-teaching-book-editorial-policy-1.0-candidate"
assert PROMPT_VERSION == "book-generator-faithful-restatement-1.1-candidate"

CH003_MANIFEST_REL = (
    "audit/book_full_generation_preparation_4b226/ch003_accepted_editorial_manifest.json"
)
CH004_MANIFEST_REL = (
    "audit/book_full_generation_preparation_4b226/ch004_accepted_editorial_manifest.json"
)
CH012_ACCEPTED_JSON_REL = (
    "audit/book_authorial_voice_4b218/chapter_candidate_authorial_v2.json"
)
CH012_ACCEPTED_MD_REL = (
    "audit/book_authorial_voice_4b218/chapter_candidate_authorial_v2.md"
)
CH012_ORIGINAL_JSON_REL = (
    "audit/real/book_generation_4b217_ch012/chapter_candidate.json"
)
CH012_ORIGINAL_MD_REL = "audit/real/book_generation_4b217_ch012/chapter_candidate.md"
CH018_APPROVED_JSON_REL = (
    "audit/real/book_generation_4b221_ch018/chapter_candidate.json"
)
CH018_APPROVED_MD_REL = "audit/real/book_generation_4b221_ch018/chapter_candidate.md"
REMAINING13_CHAPTER_REL = (
    "audit/real/book_generation_4b227_remaining13/chapters/{chapter_id}"
)
CH002_IDEA_REVIEW_REL = (
    "audit/real/book_generation_4b223_batch01/chapters/CH002/idea_traceability_review.json"
)
CH012_IDEA_MAPPING_REL = (
    "audit/book_editorial_acceptance_4b219/idea_content_mapping_review.json"
)

TECHNICAL_TITLE_FALLBACK = (
    "[PROVISIONAL TECHNICAL DESIGNATION] pastoral_retreat_v2_validation "
    "reading manuscript"
)
MANUSCRIPT_NOTE = (
    "Technical reading assembly produced by Phase 4B.2.28. "
    "Chapter titles and paragraphs are unchanged. Heading levels were "
    "adjusted only to place chapters under one book document. "
    "IDEA/SRC identifiers are kept in annex manifests, not in the reading body."
)
CHAPTER_SEPARATOR = "---"

HISTORICAL_EX_REF_OBSERVATIONS = (
    {
        "chapter_id": "CH003",
        "kind": "EX",
        "id": "EX005",
        "historical_note": "EX005 without an explicit handle.",
    },
    {
        "chapter_id": "CH004",
        "kind": "REF",
        "id": "REF011",
        "historical_note": (
            "REF011 without an explicit handle, but the reference is present in the prose."
        ),
    },
    {
        "chapter_id": "CH004",
        "kind": "REF",
        "id": "REF012",
        "historical_note": (
            "REF012 without an explicit handle, but the reference is present in the prose."
        ),
    },
    {
        "chapter_id": "CH004",
        "kind": "REF",
        "id": "REF013",
        "historical_note": (
            "REF013 without an explicit handle, but the reference is present in the prose."
        ),
    },
    {
        "chapter_id": "CH012",
        "kind": "EX",
        "id": "EX030",
        "historical_note": "EX030, historically documented partial coverage.",
    },
    {
        "chapter_id": "CH018",
        "kind": "EX",
        "id": "EX046",
        "historical_note": "EX046 present in the text without an explicit handle.",
    },
)

AUDIT_DIRNAME = "book_full_manuscript_review_4b228"
AUDIT_MANUSCRIPT = "manuscript_reading_draft.md"
AUDIT_PROVENANCE = "manuscript_provenance_manifest.json"
AUDIT_INVENTORY = "chapters_inventory.json"
AUDIT_INTEGRITY = "manuscript_integrity_validation.json"
AUDIT_EDITORIAL_MD = "editorial_global_review.md"
AUDIT_EDITORIAL_JSON = "editorial_global_review.json"
AUDIT_STRENGTHENED = "strengthened_claims_review.json"
AUDIT_REFERENCES = "references_examples_review.json"
AUDIT_CONTINUITY = "continuity_review.json"
AUDIT_HUMAN_GUIDE = "human_review_guide.md"
AUDIT_HUMAN_CHECKLIST = "human_review_checklist.json"
AUDIT_HASHES_PRE = "canonical_hashes_pre.json"
AUDIT_HASHES_POST = "canonical_hashes_post.json"
AUDIT_HASHES_PRE_POST = "canonical_hashes_pre_post.json"
AUDIT_READINESS = "readiness.json"
AUDIT_PREFLIGHT = "preflight.json"
AUDIT_TESTS = "offline_regression_tests.json"
AUDIT_TRACEABILITY = "paragraph_traceability.json"
AUDIT_ASSEMBLY_SPEC = "manuscript_assembly_spec.json"
REPORT_NAME = "PHASE_4B228_FULL_MANUSCRIPT_EDITORIAL_REVIEW_REPORT.md"

NEXT_ACTION = (
    "WAIT FOR HUMAN EXAMINATION AND APPROVAL OF THE ASSEMBLED MANUSCRIPT. "
    "DO NOT CORRECT CHAPTERS. DO NOT REGENERATE. DO NOT CALL ANTHROPIC. "
    "DO NOT CALL OPENAI. DO NOT CALL TERRA. DO NOT GENERATE DOCX OR PDF. "
    "DO NOT PUBLISH book.json. DO NOT LAUNCH VISUAL DIRECTION. "
    "DO NOT SPEND THE 4B.2.27 BUDGET REMAINDER."
)

__all__ = [
    "ACCEPTED_CHAPTER_IDS",
    "AUTHORIZATION_SCOPE",
    "CANONICAL_CHAPTER_IDS",
    "CANONICAL_PYTHON",
    "EXPECTED_EDITORIAL_PLAN",
    "EXPECTED_IDEA_COUNT",
    "EXPECTED_SECTION_COUNT",
    "EXPECTED_SOURCE_MAP",
    "EXPECTED_TRANSCRIPT",
    "HUMAN_ACCEPTANCE_STATUS",
    "HUMAN_REVIEW_PENDING_STATUS",
    "PENDING_CHAPTER_IDS",
    "PHASE",
    "PROJECT_NAME",
    "REMAINING_CHAPTER_IDS",
    "REPORT_NAME",
]
