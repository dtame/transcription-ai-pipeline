"""
Comparaison locale post-réponse (§22-25) — jamais envoyée au modèle.

Ce module compare les classifications du modèle aux catégories cachées lors
de la sélection (§15) : phase_3a1_status / semantic_review_status. Il ne
modifie AUCUNE décision de language_cleanup.json ou language_blocks.json
(§21, §22) — c'est un rapport de lecture, rien d'autre.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.semantic_canary.models import (
    CLASSIFICATIONS,
    GROUP_CONTROL_RESOLVED,
    CanaryClassification,
    SelectedBlock,
)

# Pour un bloc ALREADY_RESOLVED (Phase 3A.1 avait conclu REMOVE_TRANSLATION),
# l'accord attendu du canary est une classification TRANSLATION_* (peu
# importe la direction précise — le contrôle positif porte sur « le modèle
# retrouve-t-il une relation de traduction », pas sur laquelle exactement,
# §15 : la catégorie de sélection n'a jamais dicté BEFORE vs AFTER au modèle).
_TRANSLATION_CLASSIFICATIONS = frozenset({"TRANSLATION_BEFORE", "TRANSLATION_AFTER"})


@dataclass(frozen=True)
class CaseReport:
    """Un cas complet (§25) : sélection locale + réponse du modèle."""

    selected: SelectedBlock
    result: CanaryClassification
    agreement: bool | None  # None si le groupe n'est pas un contrôle positif

    def to_dict(self) -> dict:
        return {
            "block_id": self.selected.block_id,
            "selection_group": self.selected.selection_group,
            "selection_reason": self.selected.selection_reason,
            "audio_id": self.selected.audio_id,
            "structure": self.selected.structure,
            "candidate_direction": self.selected.candidate_direction,
            "fr_source_refs": self.selected.fr_source_refs,
            "fr_text": self.selected.raw_block.get("text", ""),
            "english_before": self.selected.english_before,
            "english_after": self.selected.english_after,
            "classification": self.result.classification,
            "matched_direction": self.result.matched_direction,
            "confidence": self.result.confidence,
            "reason": self.result.reason,
            "previous_local_category": {
                "phase_3a1_status": self.selected.raw_block.get("phase_3a1_status"),
                "semantic_review_status": self.selected.semantic_review_status,
            },
            "positive_control_agreement": self.agreement,
        }


def build_case_reports(
    selected_blocks: list[SelectedBlock],
    results: list[CanaryClassification],
) -> list[CaseReport]:
    """Associe chaque bloc sélectionné à son résultat, dans l'ordre de sélection."""
    results_by_id = {result.block_id: result for result in results}
    cases: list[CaseReport] = []

    for selected in selected_blocks:
        result = results_by_id[selected.block_id]

        agreement: bool | None = None
        if selected.selection_group == GROUP_CONTROL_RESOLVED:
            agreement = result.classification in _TRANSLATION_CLASSIFICATIONS

        cases.append(CaseReport(selected=selected, result=result, agreement=agreement))

    return cases


def classification_distribution(results: list[CanaryClassification]) -> dict[str, int]:
    """Distribution globale des classifications (§11, §23)."""
    counts = {label: 0 for label in CLASSIFICATIONS}
    for result in results:
        counts[result.classification] = counts.get(result.classification, 0) + 1
    return counts


def distribution_by_group(cases: list[CaseReport]) -> dict[str, dict[str, int]]:
    """Distribution des classifications, par groupe de sélection (§23)."""
    by_group: dict[str, dict[str, int]] = {}

    for case in cases:
        group_counts = by_group.setdefault(
            case.selected.selection_group, {label: 0 for label in CLASSIFICATIONS}
        )
        group_counts[case.result.classification] += 1

    return by_group


def positive_control_summary(cases: list[CaseReport]) -> dict:
    """`positive_control_agreement_rate` (§24) — jamais forcé à 100 %."""
    controls = [case for case in cases if case.agreement is not None]
    agreed = sum(1 for case in controls if case.agreement)

    return {
        "total": len(controls),
        "agreed": agreed,
        "disagreed": len(controls) - agreed,
        "agreement_rate": (agreed / len(controls)) if controls else None,
        "disagreements": [
            case.selected.block_id for case in controls if not case.agreement
        ],
    }
