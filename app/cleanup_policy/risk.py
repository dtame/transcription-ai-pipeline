"""
Risk flags déterministes (§11-14, §28) — raisons explicables, jamais un
score opaque.

`compute_risk_flags` est une fonction PURE d'un `BlockRecord` isolé : aucune
dépendance à l'ordre de traitement, aucun état partagé — deux exécutions
produisent toujours exactement la même liste, dans le même ordre (§22,
déterminisme).
"""

from __future__ import annotations

from app.cleanup_policy.constants import (
    EXTRA_CONTENT_SIGNAL_TERMS,
    FORMER_REVIEW_STATUSES,
    KNOWN_BILINGUAL_STRUCTURES,
    LONG_BLOCK_WORD_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    MEDIUM_BLOCK_MAX_WORDS,
    MEDIUM_BLOCK_MIN_WORDS,
    ORIGIN_NO_ENGLISH_CONTEXT,
    ORIGIN_PHASE_3A1_RESOLVED,
    PHASE_3A1_ALL_KEEP,
    RISK_BRIDGE_PRESENT,
    RISK_EXTRA_CONTENT_SIGNAL,
    RISK_FORMER_ALL_KEEP,
    RISK_FORMER_REVIEW,
    RISK_HIGH_RISK_EXISTING,
    RISK_LEGACY_RESOLVED,
    RISK_LONG_BLOCK,
    RISK_LOW_CONFIDENCE,
    RISK_MEDIUM_BLOCK,
    RISK_MULTI_SRC,
    RISK_NO_ENGLISH_CONTEXT,
    RISK_OTHER_STRUCTURE,
    RISK_TRANSLATION_AFTER,
    TRANSLATION_CLASSIFICATIONS,
    CLASSIFICATION_TRANSLATION_AFTER,
)
from app.cleanup_policy.population import BlockRecord


def has_extra_content_signal(reason: str | None) -> bool:
    """
    §10 : signal de prudence extrait de `reason` — jamais une nouvelle
    classification. Recherche en sous-chaîne, insensible à la casse, sur la
    liste documentée dans app.cleanup_policy.constants.EXTRA_CONTENT_SIGNAL_TERMS.
    """
    if not reason:
        return False

    lowered = reason.lower()
    return any(term in lowered for term in EXTRA_CONTENT_SIGNAL_TERMS)


def compute_risk_flags(record: BlockRecord) -> tuple[str, ...]:
    """
    Construit la liste ordonnée et déterministe des risk_flags d'un bloc
    (§11). L'ordre suit celui de la déclaration du vocabulaire (§11), pas un
    tri alphabétique arbitraire — stable et lisible pour une revue humaine.
    """
    flags: list[str] = []

    if record.is_high_risk_existing:
        flags.append(RISK_HIGH_RISK_EXISTING)

    if (
        record.classification in TRANSLATION_CLASSIFICATIONS
        and record.confidence is not None
        and record.confidence < LOW_CONFIDENCE_THRESHOLD
    ):
        flags.append(RISK_LOW_CONFIDENCE)

    if len(record.fr_source_refs) > 1:
        flags.append(RISK_MULTI_SRC)

    if record.word_count > LONG_BLOCK_WORD_THRESHOLD:
        flags.append(RISK_LONG_BLOCK)
    elif MEDIUM_BLOCK_MIN_WORDS <= record.word_count <= MEDIUM_BLOCK_MAX_WORDS:
        flags.append(RISK_MEDIUM_BLOCK)

    if record.bridge_source_refs:
        flags.append(RISK_BRIDGE_PRESENT)

    if has_extra_content_signal(record.reason):
        flags.append(RISK_EXTRA_CONTENT_SIGNAL)

    if record.semantic_origin == ORIGIN_PHASE_3A1_RESOLVED:
        flags.append(RISK_LEGACY_RESOLVED)

    if record.semantic_origin == ORIGIN_NO_ENGLISH_CONTEXT:
        flags.append(RISK_NO_ENGLISH_CONTEXT)

    if (
        record.phase_3a1_status == PHASE_3A1_ALL_KEEP
        and record.classification in TRANSLATION_CLASSIFICATIONS
    ):
        flags.append(RISK_FORMER_ALL_KEEP)

    if record.phase_3a1_status in FORMER_REVIEW_STATUSES:
        flags.append(RISK_FORMER_REVIEW)

    if record.classification == CLASSIFICATION_TRANSLATION_AFTER:
        flags.append(RISK_TRANSLATION_AFTER)

    if record.structure not in KNOWN_BILINGUAL_STRUCTURES:
        flags.append(RISK_OTHER_STRUCTURE)

    return tuple(flags)
