"""
Décision POLICY_B_PLUS_V1 — fonction PURE.

Entrée : BlockRecord + risk_flags déjà calculés + contexte transcript/langue.
Sortie : ApplicationDecision (décision + TOUTES les raisons applicables).

Aucun accès disque, aucun état partagé, aucun appel réseau.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.cleanup_application.constants import (
    CLASSIFICATION_NOT_TRANSLATION,
    CLASSIFICATION_TRANSLATION_AFTER,
    CLASSIFICATION_TRANSLATION_BEFORE,
    CLASSIFICATION_UNCERTAIN,
    DECISION_AUTO_REMOVE,
    DECISION_HUMAN_REVIEW,
    DECISION_KEEP,
    LANGUAGE_FR,
    ORIGIN_NO_ENGLISH_CONTEXT,
    ORIGIN_PHASE_3A1_RESOLVED,
    ORIGIN_SEMANTIC_BATCH,
    POLICY_B_PLUS_MAX_WORDS,
    POLICY_B_PLUS_MIN_CONFIDENCE,
    REASON_AUDIO_OWNERSHIP,
    REASON_AUTO_REMOVE,
    REASON_BRIDGE,
    REASON_EXTRA_CONTENT,
    REASON_FR_SRC_COUNT,
    REASON_HIGH_RISK,
    REASON_LANGUAGE_NOT_FR,
    REASON_LEGACY,
    REASON_LONG_BLOCK,
    REASON_LOW_CONFIDENCE,
    REASON_MULTI_SRC,
    REASON_NO_ENGLISH,
    REASON_NOT_TRANSLATION,
    REASON_NOT_TRANSLATION_BEFORE,
    REASON_ORDER,
    REASON_ORIGIN_NOT_SEMANTIC_BATCH,
    REASON_SRC_MISSING,
    REASON_SRC_NOT_UNIQUE,
    REASON_TEXT_MISMATCH,
    REASON_TRANSLATION_AFTER,
    REASON_UNCERTAIN,
    REASON_WORD_COUNT,
    RISK_EXTRA_CONTENT_SIGNAL,
    RISK_HIGH_RISK_EXISTING,
    RISK_LONG_BLOCK,
    RISK_MULTI_SRC,
    TRANSLATION_CLASSIFICATIONS,
)
from app.cleanup_application.models import ApplicationDecision
from app.cleanup_policy.population import BlockRecord
from app.transcript_models import TranscriptSegment


@dataclass(frozen=True)
class PolicyContext:
    """Contexte lecture-seule nécessaire aux conditions 11-12 et à la langue."""

    segments_by_id: dict[str, TranscriptSegment]
    occurrence_count: dict[str, int]
    language_by_src: dict[str, str]


def _ordered_reasons(flags: dict[str, bool]) -> tuple[str, ...]:
    return tuple(reason for reason in REASON_ORDER if flags.get(reason))


def decide_policy_b_plus(
    record: BlockRecord,
    risk_flags: tuple[str, ...],
    context: PolicyContext,
) -> ApplicationDecision:
    """
    Applique POLICY_B_PLUS_V1 à un bloc.

    AUTO_REMOVE uniquement si TOUTES les conditions du cahier sont vraies.
    Sinon KEEP (NOT_TRANSLATION / UNCERTAIN / NO_ENGLISH_CONTEXT) ou
    HUMAN_REVIEW. Toutes les raisons applicables sont conservées.
    """
    flags: dict[str, bool] = {reason: False for reason in REASON_ORDER}

    if record.semantic_origin == ORIGIN_PHASE_3A1_RESOLVED:
        flags[REASON_LEGACY] = True
        return ApplicationDecision(
            decision=DECISION_HUMAN_REVIEW,
            reasons=_ordered_reasons(flags),
            candidate_removed_source_refs=(),
        )

    if record.semantic_origin == ORIGIN_NO_ENGLISH_CONTEXT:
        flags[REASON_NO_ENGLISH] = True
        return ApplicationDecision(
            decision=DECISION_KEEP,
            reasons=_ordered_reasons(flags),
            candidate_removed_source_refs=(),
        )

    if record.classification == CLASSIFICATION_NOT_TRANSLATION:
        flags[REASON_NOT_TRANSLATION] = True
        return ApplicationDecision(
            decision=DECISION_KEEP,
            reasons=_ordered_reasons(flags),
            candidate_removed_source_refs=(),
        )

    if record.classification == CLASSIFICATION_UNCERTAIN:
        flags[REASON_UNCERTAIN] = True
        return ApplicationDecision(
            decision=DECISION_KEEP,
            reasons=_ordered_reasons(flags),
            candidate_removed_source_refs=(),
        )

    if record.semantic_origin != ORIGIN_SEMANTIC_BATCH:
        flags[REASON_ORIGIN_NOT_SEMANTIC_BATCH] = True

    if record.classification != CLASSIFICATION_TRANSLATION_BEFORE:
        flags[REASON_NOT_TRANSLATION_BEFORE] = True

    is_translation = record.classification in TRANSLATION_CLASSIFICATIONS

    if record.classification == CLASSIFICATION_TRANSLATION_AFTER:
        flags[REASON_TRANSLATION_AFTER] = True

    if is_translation:
        if record.confidence is None or record.confidence < POLICY_B_PLUS_MIN_CONFIDENCE:
            flags[REASON_LOW_CONFIDENCE] = True
        if record.word_count > POLICY_B_PLUS_MAX_WORDS:
            flags[REASON_WORD_COUNT] = True
        if RISK_LONG_BLOCK in risk_flags:
            flags[REASON_LONG_BLOCK] = True
        if record.bridge_source_refs:
            flags[REASON_BRIDGE] = True
        if RISK_HIGH_RISK_EXISTING in risk_flags:
            flags[REASON_HIGH_RISK] = True
        if RISK_MULTI_SRC in risk_flags or len(record.fr_source_refs) > 1:
            flags[REASON_MULTI_SRC] = True
        if RISK_EXTRA_CONTENT_SIGNAL in risk_flags:
            flags[REASON_EXTRA_CONTENT] = True

    if len(record.fr_source_refs) != 1:
        flags[REASON_FR_SRC_COUNT] = True
    else:
        src = record.fr_source_refs[0]
        count = context.occurrence_count.get(src, 0)
        if count == 0:
            flags[REASON_SRC_MISSING] = True
        elif count != 1:
            flags[REASON_SRC_NOT_UNIQUE] = True
        else:
            segment = context.segments_by_id[src]
            if segment.text != record.text:
                flags[REASON_TEXT_MISMATCH] = True
            if segment.source_id != record.audio_id:
                flags[REASON_AUDIO_OWNERSHIP] = True
            language = context.language_by_src.get(src)
            if language != LANGUAGE_FR:
                flags[REASON_LANGUAGE_NOT_FR] = True

    reasons = _ordered_reasons(flags)
    if reasons:
        return ApplicationDecision(
            decision=DECISION_HUMAN_REVIEW,
            reasons=reasons,
            candidate_removed_source_refs=(),
        )

    return ApplicationDecision(
        decision=DECISION_AUTO_REMOVE,
        reasons=(REASON_AUTO_REMOVE,),
        candidate_removed_source_refs=record.fr_source_refs,
    )
