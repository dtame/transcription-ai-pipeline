"""
Modèles internes de l'application POLICY_B_PLUS_V1.

Ces dataclasses ne sont pas le contrat JSON publié : elles portent le plan
déterministe (décisions + snapshots) dont l'audit et le transformer dérivent.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.cleanup_policy.population import BlockRecord


@dataclass(frozen=True)
class ApplicationDecision:
    """Décision POLICY_B+ pour un bloc, avec TOUTES les raisons applicables."""

    decision: str
    reasons: tuple[str, ...]
    candidate_removed_source_refs: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "decision_reasons": list(self.reasons),
            "candidate_removed_source_refs": list(self.candidate_removed_source_refs),
        }


@dataclass(frozen=True)
class RemovalSnapshot:
    """
    Preuve d'une suppression : assez d'information pour expliquer ET
    restaurer le SRC retiré (réversibilité).
    """

    source_ref: str
    audio_id: str
    source_order: int
    start: float
    end: float
    text: str
    word_count: int
    original_index: int
    block_id: str
    classification: str | None
    matched_direction: str | None
    confidence: float | None
    semantic_reason: str | None
    risk_flags: tuple[str, ...]
    matched_english_before_source_refs: tuple[str, ...]
    matched_english_before_text: str | None
    policy_decision: str
    decision_reasons: tuple[str, ...]

    @property
    def duration_seconds(self) -> float:
        return round(self.end - self.start, 6)

    def to_dict(self) -> dict:
        return {
            "source_ref": self.source_ref,
            "audio_id": self.audio_id,
            "source_order": self.source_order,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "word_count": self.word_count,
            "duration_seconds": self.duration_seconds,
            "original_index": self.original_index,
            "block_id": self.block_id,
            "classification": self.classification,
            "matched_direction": self.matched_direction,
            "confidence": self.confidence,
            "semantic_reason": self.semantic_reason,
            "risk_flags": list(self.risk_flags),
            "matched_english_before_source_refs": list(
                self.matched_english_before_source_refs
            ),
            "matched_english_before_text": self.matched_english_before_text,
            "policy_decision": self.policy_decision,
            "decision_reasons": list(self.decision_reasons),
        }


@dataclass(frozen=True)
class PlannedBlock:
    """Un bloc FR après application de POLICY_B_PLUS_V1."""

    record: BlockRecord
    risk_flags: tuple[str, ...]
    decision: ApplicationDecision
    english_before_source_refs: tuple[str, ...]
    english_after_source_refs: tuple[str, ...]
    english_after_text: str | None

    @property
    def block_id(self) -> str:
        return self.record.block_id


@dataclass(frozen=True)
class ApplicationPlan:
    """Plan complet, validable avant toute écriture."""

    project_name: str
    blocks: tuple[PlannedBlock, ...]
    removal_snapshots: tuple[RemovalSnapshot, ...]
    removal_set: frozenset[str]

    def blocks_with(self, decision: str) -> tuple[PlannedBlock, ...]:
        return tuple(block for block in self.blocks if block.decision.decision == decision)
