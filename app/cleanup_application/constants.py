"""
Vocabulaire fermé et règles versionnées de POLICY_B_PLUS_V1.

Rien ici ne recalcule une classification sémantique : ce module décrit
uniquement la politique d'APPLICATION réelle, plus prudente que POLICY_B.
"""

from __future__ import annotations

from app.cleanup_policy.constants import (  # noqa: F401
    CLASSIFICATION_NOT_TRANSLATION,
    CLASSIFICATION_TRANSLATION_AFTER,
    CLASSIFICATION_TRANSLATION_BEFORE,
    CLASSIFICATION_UNCERTAIN,
    DECISION_AUTO_REMOVE,
    DECISION_HUMAN_REVIEW,
    DECISION_KEEP,
    DECISIONS,
    ORIGIN_NO_ENGLISH_CONTEXT,
    ORIGIN_PHASE_3A1_RESOLVED,
    ORIGIN_SEMANTIC_BATCH,
    POLICY_B,
    RISK_BRIDGE_PRESENT,
    RISK_EXTRA_CONTENT_SIGNAL,
    RISK_FORMER_ALL_KEEP,
    RISK_HIGH_RISK_EXISTING,
    RISK_LONG_BLOCK,
    RISK_MULTI_SRC,
    TRANSLATION_CLASSIFICATIONS,
)
from app.language_cleanup.models import LANGUAGE_EN, LANGUAGE_FR, LANGUAGE_MIXED, LANGUAGE_UNKNOWN
from app.transcript_models import DEFAULT_TRANSCRIPT_ID, SCHEMA_VERSION

SCHEMA_VERSION_APPLICATION = "1.0"

POLICY_B_PLUS = "POLICY_B_PLUS_V1"
POLICY_B_PLUS_BASE = POLICY_B
POLICY_B_PLUS_LABEL = "CONSERVATIVE_PLUS"

POLICY_B_PLUS_MIN_CONFIDENCE = 0.90
POLICY_B_PLUS_MAX_WORDS = 30

# Convention d'index pour original_index dans l'audit : 0-based, position
# dans transcripts/transcript_data.json["segments"] original.
ORIGINAL_INDEX_CONVENTION = "0-based"
ORIGINAL_INDEX_BASIS = "transcript_data.json segments array (original, unmodified)"

DERIVATION_TYPE = "language_cleanup"
CLEAN_VIEW_NOTE = (
    "Vue après application sûre de POLICY_B_PLUS_V1. Ce n'est PAS une "
    "garantie English-only : NOT_TRANSLATION, UNCERTAIN, NO_ENGLISH_CONTEXT, "
    "HUMAN_REVIEW, legacy unresolved et traductions non sûres restent."
)

# Provenance : conservée dans cleanup_application.json, PAS dans le
# transcript_data original ni dans le contrat schema 1.0 (aucun champ
# `derivation` au schéma 1.0 — l'ajouter casserait le contrat).
PROVENANCE_LOCATION = "cleanup_application.json"
TRANSCRIPT_ID_CONVENTION = (
    f"Le transcript clean conserve {DEFAULT_TRANSCRIPT_ID} comme identité de "
    "transcription source. Il est une vue dérivée, pas un nouveau transcript_id."
)

# ---------------------------------------------------------------------------
# Raisons de décision — vocabulaire fermé, toutes conservées (jamais une seule)
# ---------------------------------------------------------------------------

REASON_AUTO_REMOVE = "POLICY_B_PLUS_CONDITIONS_SATISFIED"
REASON_LEGACY = "LEGACY_RESOLVED_REQUIRES_HUMAN_REVIEW"
REASON_NO_ENGLISH = "NO_ENGLISH_CONTEXT"
REASON_NOT_TRANSLATION = "NOT_TRANSLATION_ALWAYS_KEEP"
REASON_UNCERTAIN = "UNCERTAIN_INSUFFICIENT_EVIDENCE_ALWAYS_KEEP"
REASON_TRANSLATION_AFTER = "TRANSLATION_AFTER_REQUIRES_HUMAN_REVIEW"
REASON_LOW_CONFIDENCE = "LOW_CONFIDENCE"
REASON_WORD_COUNT = "WORD_COUNT_EXCEEDS_LIMIT"
REASON_LONG_BLOCK = "LONG_BLOCK_REQUIRES_HUMAN_REVIEW"
REASON_BRIDGE = "BRIDGE_REQUIRES_HUMAN_REVIEW"
REASON_HIGH_RISK = "HIGH_RISK_REQUIRES_HUMAN_REVIEW"
REASON_MULTI_SRC = "MULTI_SRC_REQUIRES_HUMAN_REVIEW"
REASON_EXTRA_CONTENT = "EXTRA_CONTENT_REQUIRES_HUMAN_REVIEW"
REASON_FR_SRC_COUNT = "FR_SRC_COUNT_NOT_EXACTLY_ONE"
REASON_SRC_MISSING = "SRC_NOT_IN_TRANSCRIPT"
REASON_SRC_NOT_UNIQUE = "SRC_OCCURRENCE_NOT_UNIQUE"
REASON_TEXT_MISMATCH = "TEXT_MISMATCH"
REASON_AUDIO_OWNERSHIP = "AUDIO_OWNERSHIP_MISMATCH"
REASON_LANGUAGE_NOT_FR = "LANGUAGE_NOT_FR"
REASON_ORIGIN_NOT_SEMANTIC_BATCH = "ORIGIN_NOT_SEMANTIC_BATCH"
REASON_NOT_TRANSLATION_BEFORE = "CLASSIFICATION_NOT_TRANSLATION_BEFORE"

# Ordre déterministe des raisons applicables (toutes émises si vraies).
REASON_ORDER = (
    REASON_LEGACY,
    REASON_NO_ENGLISH,
    REASON_NOT_TRANSLATION,
    REASON_UNCERTAIN,
    REASON_ORIGIN_NOT_SEMANTIC_BATCH,
    REASON_NOT_TRANSLATION_BEFORE,
    REASON_TRANSLATION_AFTER,
    REASON_LOW_CONFIDENCE,
    REASON_WORD_COUNT,
    REASON_LONG_BLOCK,
    REASON_BRIDGE,
    REASON_HIGH_RISK,
    REASON_MULTI_SRC,
    REASON_EXTRA_CONTENT,
    REASON_FR_SRC_COUNT,
    REASON_SRC_MISSING,
    REASON_SRC_NOT_UNIQUE,
    REASON_TEXT_MISMATCH,
    REASON_AUDIO_OWNERSHIP,
    REASON_LANGUAGE_NOT_FR,
)

NON_FR_LANGUAGES = frozenset({LANGUAGE_EN, LANGUAGE_MIXED, LANGUAGE_UNKNOWN})

CONFIDENCE_BUCKET_090_094 = "0.90-0.94"
CONFIDENCE_BUCKET_GE_095 = ">=0.95"
CONFIDENCE_BUCKET_LT_090 = "<0.90"

WORD_BUCKETS = ("1-5", "6-10", "11-20", "21-30", ">30")

CONTROL_SAMPLE_SIZE = 10
TOP_SUPPRESSIONS_SIZE = 20

REAL_PROJECT_NAME = "pastoral_retreat_v2_validation"

POLICY_B_PLUS_RULES = {
    "policy_id": POLICY_B_PLUS,
    "base_policy": POLICY_B_PLUS_BASE,
    "label": POLICY_B_PLUS_LABEL,
    "auto_remove_requires_all": [
        "semantic_origin == SEMANTIC_BATCH",
        "classification == TRANSLATION_BEFORE",
        f"confidence >= {POLICY_B_PLUS_MIN_CONFIDENCE}",
        f"word_count <= {POLICY_B_PLUS_MAX_WORDS}",
        "bridge_source_refs is empty",
        "HIGH_RISK_EXISTING absent",
        "MULTI_SRC absent",
        "LONG_BLOCK absent",
        "EXTRA_CONTENT_SIGNAL absent",
        "fr_source_refs contains exactly 1 SRC",
        "candidate SRC exists exactly once in the original transcript",
        "candidate SRC text matches the reconstructible FR text exactly",
        "candidate SRC language is FR",
        "candidate SRC audio_id matches the block audio_id",
    ],
    "translation_after": "HUMAN_REVIEW always (TRANSLATION_AFTER_REQUIRES_HUMAN_REVIEW)",
    "not_translation": "KEEP always",
    "uncertain": "KEEP always",
    "no_english_context": "KEEP always",
    "legacy_resolved": "HUMAN_REVIEW always (LEGACY_RESOLVED_REQUIRES_HUMAN_REVIEW)",
    "min_confidence": POLICY_B_PLUS_MIN_CONFIDENCE,
    "max_words": POLICY_B_PLUS_MAX_WORDS,
    "schema_version": SCHEMA_VERSION_APPLICATION,
    "transcript_schema_version": SCHEMA_VERSION,
    "transcript_id_convention": TRANSCRIPT_ID_CONVENTION,
    "provenance_location": PROVENANCE_LOCATION,
    "original_index_convention": ORIGINAL_INDEX_CONVENTION,
    "original_index_basis": ORIGINAL_INDEX_BASIS,
    "clean_view_note": CLEAN_VIEW_NOTE,
}
