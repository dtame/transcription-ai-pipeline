"""
Assemblage des entrées `blocks[]` de l'artefact final (§20-21) : un bloc =
sa traçabilité complète + ses trois décisions simulées (POLICY_A/B/C).

Aucun tri aléatoire, aucun horodatage : `build_block_entries` trie toujours
par `block_id` (§22, déterminisme).
"""

from __future__ import annotations

from app.cleanup_policy.constants import (
    POLICY_A,
    POLICY_A_MAX_WORDS,
    POLICY_A_MIN_CONFIDENCE,
    POLICY_B,
    POLICY_B_MAX_WORDS,
    POLICY_B_MIN_CONFIDENCE,
    POLICY_C,
    POLICY_C_DISCLAIMER,
    POLICY_C_MAX_WORDS,
    POLICY_C_MIN_CONFIDENCE,
    POLICY_IDS,
    POLICY_LABELS,
)
from app.cleanup_policy.evaluation import BlockEvaluation


def build_policy_definitions() -> dict:
    """§21 : bloc `policies` statique — définitions/seuils, jamais un choix."""
    return {
        POLICY_A: {
            "label": POLICY_LABELS[POLICY_A],
            "description": (
                "AUTO_REMOVE seulement si TRANSLATION_BEFORE/AFTER, confidence "
                f">= {POLICY_A_MIN_CONFIDENCE}, hors high_risk_for_deletion_review, "
                f"word_count <= {POLICY_A_MAX_WORDS}, aucun bridge_source_refs. "
                "Les 15 ALREADY_RESOLVED restent HUMAN_REVIEW (mesure séparée)."
            ),
            "min_confidence": POLICY_A_MIN_CONFIDENCE,
            "max_words": POLICY_A_MAX_WORDS,
            "forbid_high_risk": True,
            "forbid_bridge": True,
            "forbid_extra_content_signal": False,
            "is_recommended": False,
        },
        POLICY_B: {
            "label": POLICY_LABELS[POLICY_B],
            "description": (
                "AUTO_REMOVE si TRANSLATION_BEFORE/AFTER, confidence >= "
                f"{POLICY_B_MIN_CONFIDENCE}, word_count <= {POLICY_B_MAX_WORDS}, aucun "
                "bridge_source_refs, et le bloc n'est pas marqué long/complexe "
                "(requires_human_review). high_risk_for_deletion_review ne bloque "
                "pas automatiquement, mais reste tracé dans risk_flags."
            ),
            "min_confidence": POLICY_B_MIN_CONFIDENCE,
            "max_words": POLICY_B_MAX_WORDS,
            "forbid_high_risk": False,
            "forbid_bridge": True,
            "forbid_extra_content_signal": False,
            "forbid_requires_human_review": True,
            "is_recommended": False,
        },
        POLICY_C: {
            "label": POLICY_LABELS[POLICY_C],
            "description": (
                "AUTO_REMOVE si TRANSLATION_BEFORE/AFTER, confidence >= "
                f"{POLICY_C_MIN_CONFIDENCE}, word_count <= {POLICY_C_MAX_WORDS}, aucun "
                "EXTRA_CONTENT_SIGNAL détecté. Bridges non bloquants."
            ),
            "min_confidence": POLICY_C_MIN_CONFIDENCE,
            "max_words": POLICY_C_MAX_WORDS,
            "forbid_high_risk": False,
            "forbid_bridge": False,
            "forbid_extra_content_signal": True,
            "is_recommended": False,
            "disclaimer": POLICY_C_DISCLAIMER,
        },
    }


def build_block_entry(evaluation: BlockEvaluation) -> dict:
    """Une entrée complète de `blocks[]` (§20-21) pour UN bloc FR."""
    record = evaluation.record
    risk_flags = evaluation.risk_flags
    decisions = evaluation.decisions

    return {
        "block_id": record.block_id,
        "source": {
            "audio_id": record.audio_id,
            "start_seconds": record.start_seconds,
            "end_seconds": record.end_seconds,
            "fr_source_refs": list(record.fr_source_refs),
            "bridge_source_refs": list(record.bridge_source_refs),
            "word_count": record.word_count,
            "segment_count": record.segment_count,
            "fr_segment_count": record.fr_segment_count,
            "structure": record.structure,
            "phase_3a1_status": record.phase_3a1_status,
            "text": record.text,
        },
        "semantic": {
            "semantic_origin": record.semantic_origin,
            "classification": record.classification,
            "matched_direction": record.matched_direction,
            "confidence": record.confidence,
            "confidence_range": record.confidence_range,
            "reason": record.reason,
            "requires_human_review_flag": record.requires_human_review_flag,
            "english_before_text": record.english_before_text,
            "english_after_text": record.english_after_text,
            "matched_english_text": record.matched_english_text(),
        },
        "risk_flags": list(risk_flags),
        "simulations": {
            policy_id: decisions[policy_id].to_dict() for policy_id in POLICY_IDS
        },
    }


def build_block_entries(evaluations: list[BlockEvaluation]) -> list[dict]:
    """§22 : ordre déterministe — `evaluations` est déjà triée par block_id."""
    return [build_block_entry(evaluation) for evaluation in evaluations]
