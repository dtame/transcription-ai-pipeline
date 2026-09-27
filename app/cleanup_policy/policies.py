"""
Couche DÉCISION D'APPLICATION (§2, §8) — trois politiques hypothétiques,
simulées, jamais choisies automatiquement.

Chaque fonction `decide_policy_*` est PURE : `BlockRecord` + `risk_flags`
déjà calculés en entrée, `(decision, reason)` en sortie — jamais un accès
disque, jamais un état partagé, jamais un appel réseau.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.cleanup_policy.constants import (
    CLASSIFICATION_NOT_TRANSLATION,
    CLASSIFICATION_UNCERTAIN,
    DECISION_AUTO_REMOVE,
    DECISION_HUMAN_REVIEW,
    DECISION_KEEP,
    LEGACY_REASON_CODE,
    NO_ENGLISH_CONTEXT_REASON_CODE,
    NOT_TRANSLATION_REASON_CODE,
    ORIGIN_NO_ENGLISH_CONTEXT,
    ORIGIN_PHASE_3A1_RESOLVED,
    POLICY_A,
    POLICY_A_MAX_WORDS,
    POLICY_A_MIN_CONFIDENCE,
    POLICY_B,
    POLICY_B_MAX_WORDS,
    POLICY_B_MIN_CONFIDENCE,
    POLICY_C,
    POLICY_C_MAX_WORDS,
    POLICY_C_MIN_CONFIDENCE,
    POLICY_IDS,
    RISK_EXTRA_CONTENT_SIGNAL,
    RISK_HIGH_RISK_EXISTING,
    UNCERTAIN_REASON_CODE,
)
from app.cleanup_policy.population import BlockRecord


@dataclass(frozen=True)
class PolicyDecision:
    """Une décision simulée pour un bloc, sous une politique donnée (§20-21)."""

    decision: str
    reason: str
    candidate_removed_source_refs: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "candidate_removed_source_refs": list(self.candidate_removed_source_refs),
        }


def _fixed_origin_decision(record: BlockRecord) -> PolicyDecision | None:
    """
    Décisions communes aux trois politiques, indépendantes des conditions
    A/B/C (§15-18) : ALREADY_RESOLVED -> HUMAN_REVIEW, NO_ENGLISH_CONTEXT ->
    KEEP. Retourne None si le bloc doit être évalué par les conditions de la
    politique (SEMANTIC_BATCH).
    """
    if record.semantic_origin == ORIGIN_PHASE_3A1_RESOLVED:
        return PolicyDecision(
            decision=DECISION_HUMAN_REVIEW,
            reason=(
                f"{LEGACY_REASON_CODE} : bloc résolu par la Phase 3A.1 "
                f"(phase_3a1_status={record.phase_3a1_status!r}) — aucune politique de "
                "cette simulation ne l'AUTO_REMOVE (§15)."
            ),
            candidate_removed_source_refs=(),
        )

    if record.semantic_origin == ORIGIN_NO_ENGLISH_CONTEXT:
        return PolicyDecision(
            decision=DECISION_KEEP,
            reason=(
                f"{NO_ENGLISH_CONTEXT_REASON_CODE} : aucun contexte anglais adjacent, "
                "aucun appel au modèle — conservation dans les trois politiques (§16)."
            ),
            candidate_removed_source_refs=(),
        )

    return None


def _classification_gate_decision(record: BlockRecord) -> PolicyDecision | None:
    """
    §17-18 : NOT_TRANSLATION et UNCERTAIN sont toujours KEEP, sans exception,
    dans les trois politiques. Retourne None si `classification` est
    TRANSLATION_BEFORE/TRANSLATION_AFTER (à évaluer par les seuils propres à
    la politique).
    """
    if record.classification == CLASSIFICATION_NOT_TRANSLATION:
        return PolicyDecision(
            decision=DECISION_KEEP,
            reason=(
                f"{NOT_TRANSLATION_REASON_CODE} : classification=NOT_TRANSLATION — "
                "toujours KEEP, aucune exception (§17)."
            ),
            candidate_removed_source_refs=(),
        )

    if record.classification == CLASSIFICATION_UNCERTAIN:
        return PolicyDecision(
            decision=DECISION_KEEP,
            reason=(
                f"{UNCERTAIN_REASON_CODE} : classification=UNCERTAIN — absence de "
                "preuve suffisante de traduction = conservation (§18), jamais un "
                "HUMAN_REVIEW dans cette simulation principale."
            ),
            candidate_removed_source_refs=(),
        )

    return None


def _evaluate_translation_conditions(
    record: BlockRecord,
    risk_flags: tuple[str, ...],
    *,
    policy_id: str,
    min_confidence: float,
    max_words: int,
    forbid_high_risk: bool,
    forbid_bridge: bool,
    forbid_extra_content_signal: bool,
    forbid_requires_human_review: bool = False,
) -> PolicyDecision:
    """
    Évalue un bloc TRANSLATION_BEFORE/TRANSLATION_AFTER contre les
    conditions d'une politique donnée. Toutes les conditions activées
    doivent être satisfaites pour AUTO_REMOVE ; sinon HUMAN_REVIEW avec la
    liste explicite des conditions non satisfaites (§11 : raisons
    explicables, jamais un score opaque).
    """
    checks: list[tuple[str, bool]] = [
        (
            f"confidence={record.confidence} >= {min_confidence}",
            record.confidence is not None and record.confidence >= min_confidence,
        ),
        (
            f"word_count={record.word_count} <= {max_words}",
            record.word_count <= max_words,
        ),
    ]

    if forbid_bridge:
        checks.append(
            (
                f"bridge_source_refs vide (actuel={list(record.bridge_source_refs)})",
                not record.bridge_source_refs,
            )
        )

    if forbid_high_risk:
        checks.append(
            (
                "block_id absent de high_risk_for_deletion_review",
                RISK_HIGH_RISK_EXISTING not in risk_flags,
            )
        )

    if forbid_extra_content_signal:
        checks.append(
            (
                "aucun EXTRA_CONTENT_SIGNAL",
                RISK_EXTRA_CONTENT_SIGNAL not in risk_flags,
            )
        )

    if forbid_requires_human_review:
        checks.append(
            (
                "bloc non marqué long/complexe (requires_human_review)",
                not record.requires_human_review_flag,
            )
        )

    failed = [description for description, passed in checks if not passed]

    if not failed:
        satisfied = ", ".join(description for description, _ in checks)
        return PolicyDecision(
            decision=DECISION_AUTO_REMOVE,
            reason=(
                f"{policy_id} : AUTO_REMOVE — classification={record.classification}, "
                f"toutes les conditions satisfaites ({satisfied})."
            ),
            candidate_removed_source_refs=record.fr_source_refs,
        )

    return PolicyDecision(
        decision=DECISION_HUMAN_REVIEW,
        reason=(
            f"{policy_id} : HUMAN_REVIEW — classification={record.classification} "
            f"ne satisfait pas : {'; '.join(failed)}."
        ),
        candidate_removed_source_refs=(),
    )


def decide_policy_a(record: BlockRecord, risk_flags: tuple[str, ...]) -> PolicyDecision:
    """POLICY_A — ULTRA_CONSERVATIVE (§8)."""
    fixed = _fixed_origin_decision(record)
    if fixed is not None:
        return fixed

    gated = _classification_gate_decision(record)
    if gated is not None:
        return gated

    return _evaluate_translation_conditions(
        record,
        risk_flags,
        policy_id=POLICY_A,
        min_confidence=POLICY_A_MIN_CONFIDENCE,
        max_words=POLICY_A_MAX_WORDS,
        forbid_high_risk=True,
        forbid_bridge=True,
        forbid_extra_content_signal=False,
    )


def decide_policy_b(record: BlockRecord, risk_flags: tuple[str, ...]) -> PolicyDecision:
    """POLICY_B — CONSERVATIVE (§8). high_risk n'est jamais bloquant ici."""
    fixed = _fixed_origin_decision(record)
    if fixed is not None:
        return fixed

    gated = _classification_gate_decision(record)
    if gated is not None:
        return gated

    return _evaluate_translation_conditions(
        record,
        risk_flags,
        policy_id=POLICY_B,
        min_confidence=POLICY_B_MIN_CONFIDENCE,
        max_words=POLICY_B_MAX_WORDS,
        forbid_high_risk=False,
        forbid_bridge=True,
        forbid_extra_content_signal=False,
        forbid_requires_human_review=True,
    )


def decide_policy_c(record: BlockRecord, risk_flags: tuple[str, ...]) -> PolicyDecision:
    """POLICY_C — BROADER (§8-10). Bridges non bloquants ; EXTRA_CONTENT_SIGNAL bloquant."""
    fixed = _fixed_origin_decision(record)
    if fixed is not None:
        return fixed

    gated = _classification_gate_decision(record)
    if gated is not None:
        return gated

    return _evaluate_translation_conditions(
        record,
        risk_flags,
        policy_id=POLICY_C,
        min_confidence=POLICY_C_MIN_CONFIDENCE,
        max_words=POLICY_C_MAX_WORDS,
        forbid_high_risk=False,
        forbid_bridge=False,
        forbid_extra_content_signal=True,
    )


DECISION_FUNCTIONS = {
    POLICY_A: decide_policy_a,
    POLICY_B: decide_policy_b,
    POLICY_C: decide_policy_c,
}


def decide_all_policies(
    record: BlockRecord, risk_flags: tuple[str, ...]
) -> dict[str, PolicyDecision]:
    """Applique les trois politiques à un bloc, dans l'ordre déterministe §8."""
    return {policy_id: DECISION_FUNCTIONS[policy_id](record, risk_flags) for policy_id in POLICY_IDS}
