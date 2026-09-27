"""
Classification structurelle d'un bloc FR (§15-19 du cahier des charges).

AUCUNE fonction de ce module ne juge si un bloc FR est une traduction : elle
décrit uniquement sa STRUCTURE (où est l'anglais local, si l'anglais local
existe) et agrège des décisions Phase 3A.1 déjà prises, sans jamais les
changer.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.language_blocks.combined_source import CombinedSegment
from app.language_blocks.context import (
    REASON_AUDIO_EDGE,
    REASON_BLOCKED_BY_FR,
    REASON_BLOCKED_BY_NON_EN,
    REASON_FOUND_EN,
)
from app.language_blocks.models import (
    DIRECTION_AFTER,
    DIRECTION_BEFORE,
    DIRECTION_BOTH,
    DIRECTION_NONE,
    SEMANTIC_STATUS_ALREADY_RESOLVED,
    SEMANTIC_STATUS_NEEDED,
    SEMANTIC_STATUS_NO_ENGLISH_CONTEXT,
    STATUS_ALL_KEEP,
    STATUS_ALL_REMOVE,
    STATUS_ALL_REVIEW,
    STATUS_HAS_REMOVE,
    STATUS_HAS_REVIEW,
    STATUS_MIXED_DECISIONS,
    STRUCTURE_EN_FR,
    STRUCTURE_EN_FR_EN,
    STRUCTURE_FR_EN,
    STRUCTURE_FR_ISOLATED,
    STRUCTURE_NON_EN_CONTEXT,
    STRUCTURE_OTHER,
)

LANGUAGE_FR = "FR"
LANGUAGE_EN = "EN"

DECISION_REMOVE = "REMOVE_TRANSLATION"
DECISION_REVIEW = "REVIEW"
DECISION_KEEP = "KEEP"


def classify_structure(before_reason: str, after_reason: str) -> str:
    """
    §15 : classification STRUCTURELLE uniquement (« quels contextes anglais
    locaux existent »), jamais une conclusion sur la nature du FR.
    """
    if before_reason == REASON_FOUND_EN and after_reason == REASON_FOUND_EN:
        return STRUCTURE_EN_FR_EN

    if before_reason == REASON_FOUND_EN:
        return STRUCTURE_EN_FR

    if after_reason == REASON_FOUND_EN:
        return STRUCTURE_FR_EN

    # Ni avant ni après : anglais local. Distinguer POURQUOI.
    if before_reason == REASON_BLOCKED_BY_FR or after_reason == REASON_BLOCKED_BY_FR:
        # Bordé directement par un autre bloc FR (frontière de gap, §8) :
        # configuration réelle mais ne correspondant à aucune des catégories
        # attendues — ni « isolé » (quelque chose l'entoure bel et bien), ni
        # « environné de MIXED/UNKNOWN » (c'est du FR classifié, pas ambigu).
        return STRUCTURE_OTHER

    if (
        before_reason == REASON_BLOCKED_BY_NON_EN
        or after_reason == REASON_BLOCKED_BY_NON_EN
    ):
        return STRUCTURE_NON_EN_CONTEXT

    if before_reason == REASON_AUDIO_EDGE and after_reason == REASON_AUDIO_EDGE:
        return STRUCTURE_FR_ISOLATED

    return STRUCTURE_OTHER


def classify_candidate_direction(before_reason: str, after_reason: str) -> str:
    """§16 : quels contextes anglais POURRAIENT être comparés, rien de plus."""
    before_en = before_reason == REASON_FOUND_EN
    after_en = after_reason == REASON_FOUND_EN

    if before_en and after_en:
        return DIRECTION_BOTH
    if before_en:
        return DIRECTION_BEFORE
    if after_en:
        return DIRECTION_AFTER
    return DIRECTION_NONE


@dataclass(frozen=True)
class AggregatedDecisions:
    """Agrégation en LECTURE SEULE des décisions Phase 3A.1 des SRC FR d'un bloc."""

    decisions: tuple[tuple[str, str], ...]
    remove_refs: tuple[str, ...]
    review_refs: tuple[str, ...]
    keep_refs: tuple[str, ...]
    status: str


def aggregate_phase_3a1(fr_segments: tuple[CombinedSegment, ...]) -> AggregatedDecisions:
    """
    §17 : agrège les décisions Phase 3A.1 des SRC FR d'un bloc — SEULEMENT les
    SRC classifiés FR (les ponts UNKNOWN/MIXED absorbés n'ont jamais de
    décision REMOVE_TRANSLATION possible, agréger la leur ajouterait du bruit
    sans rien apporter à la question posée par cette phase : « ce FR est-il
    déjà résolu par 3A.1 ? »).
    """
    decisions = tuple((segment.src_id, segment.decision) for segment in fr_segments)
    counts = Counter(decision for _, decision in decisions)
    total = len(decisions)

    remove_refs = tuple(ref for ref, decision in decisions if decision == DECISION_REMOVE)
    review_refs = tuple(ref for ref, decision in decisions if decision == DECISION_REVIEW)
    keep_refs = tuple(ref for ref, decision in decisions if decision == DECISION_KEEP)

    if counts.get(DECISION_REMOVE, 0) == total and total > 0:
        status = STATUS_ALL_REMOVE
    elif counts.get(DECISION_REMOVE, 0) > 0:
        status = STATUS_HAS_REMOVE
    elif counts.get(DECISION_REVIEW, 0) == total and total > 0:
        status = STATUS_ALL_REVIEW
    elif counts.get(DECISION_REVIEW, 0) > 0:
        status = STATUS_HAS_REVIEW
    elif counts.get(DECISION_KEEP, 0) == total and total > 0:
        status = STATUS_ALL_KEEP
    else:
        # Vocabulaire fermé à 3 valeurs (§17) : ce cas ne devrait jamais être
        # atteint. Conservé comme garde-fou explicite plutôt que de lever.
        status = STATUS_MIXED_DECISIONS

    return AggregatedDecisions(
        decisions=decisions,
        remove_refs=remove_refs,
        review_refs=review_refs,
        keep_refs=keep_refs,
        status=status,
    )


def compute_already_resolved(
    aggregated: AggregatedDecisions,
    fr_segments: tuple[CombinedSegment, ...],
    *,
    valid_refs: frozenset[str],
    language_by_ref: dict[str, str],
) -> bool:
    """
    §18 : `already_resolved = true` UNIQUEMENT si tous les SRC FR sont
    REMOVE_TRANSLATION et possèdent des correspondances anglaises valides
    (existantes dans le transcript ET classifiées EN — jamais recalculé,
    seulement relu depuis language_cleanup.json).
    """
    if aggregated.status != STATUS_ALL_REMOVE:
        return False

    for segment in fr_segments:
        if not segment.matched_english_source_refs:
            return False

        for ref in segment.matched_english_source_refs:
            if ref not in valid_refs:
                return False
            if language_by_ref.get(ref) != LANGUAGE_EN:
                return False

    return True


def compute_semantic_review(
    *, already_resolved: bool, before_reason: str, after_reason: str
) -> tuple[bool, str]:
    """§19 : retourne (needs_semantic_review, semantic_review_status)."""
    if already_resolved:
        return False, SEMANTIC_STATUS_ALREADY_RESOLVED

    has_english_context = (
        before_reason == REASON_FOUND_EN or after_reason == REASON_FOUND_EN
    )

    if not has_english_context:
        return False, SEMANTIC_STATUS_NO_ENGLISH_CONTEXT

    return True, SEMANTIC_STATUS_NEEDED
