"""
Évaluation d'un bloc : calcule UNE FOIS `risk_flags` et les trois décisions
(POLICY_A/B/C), réutilisées ensuite à la fois par `simulation.py`
(entrées `blocks[]`) et par `aggregator.py` (statistiques) — jamais
recalculées deux fois, jamais divergentes entre l'artefact et son rapport.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.cleanup_policy.policies import PolicyDecision, decide_all_policies
from app.cleanup_policy.population import BlockRecord
from app.cleanup_policy.risk import compute_risk_flags


@dataclass(frozen=True)
class BlockEvaluation:
    record: BlockRecord
    risk_flags: tuple[str, ...]
    decisions: dict[str, PolicyDecision]

    def decision_for(self, policy_id: str) -> PolicyDecision:
        return self.decisions[policy_id]


def evaluate_block(record: BlockRecord) -> BlockEvaluation:
    risk_flags = compute_risk_flags(record)
    decisions = decide_all_policies(record, risk_flags)
    return BlockEvaluation(record=record, risk_flags=risk_flags, decisions=decisions)


def evaluate_population(records: list[BlockRecord]) -> list[BlockEvaluation]:
    """§22 : ordre déterministe, toujours par block_id."""
    return [
        evaluate_block(record)
        for record in sorted(records, key=lambda r: r.block_id)
    ]
