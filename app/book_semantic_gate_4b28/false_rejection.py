"""False-rejection analysis against offline presegmentation. No new Terra verdicts."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b28.constants import PHASE
from app.book_semantic_gate_4b28.replay import segmentation_offline_replay


def _unit_note(replay: dict[str, Any], label: str) -> dict[str, Any]:
    rows = list(replay.get("preserved_propositions") or [])
    match = next((item for item in rows if item.get("label") == label), None)
    return match or {"label": label, "preserved_in_one_unit": False}


def false_rejection_analysis(*, root=None) -> dict[str, Any]:
    replay = segmentation_offline_replay(root=root)
    h01 = replay.get("h01") or {}
    h02 = replay.get("h02") or {}
    h11 = replay.get("h11") or {}
    return {
        "phase": PHASE,
        "does_not_claim_false_rejections_corrected": True,
        "does_not_issue_new_terra_verdicts": True,
        "better_segmentation_is_not_better_understanding": True,
        "h01": {
            "false_rejection": "that fear can calculate or bargain with",
            "unit": _unit_note(h01, "bargain_clause"),
            "evidence_available": "IDEA224 no set time remains the relevant support.",
            "context_preserved": True,
            "presegmentation_effect": (
                "The relative clause stays inside its sentence. Local units do not "
                "isolate 'bargain with' as its own proposition."
            ),
            "false_rejection_risk_remaining": (
                "High. The disagreement is lexical vs entailment, not offset ownership."
            ),
            "structural_load_reduced": False,
            "semantic_load_unchanged": True,
            "evidence_level": "HYPOTHESIS",
            "observed_unit_preservation_level": "DETERMINISTICALLY_VERIFIED",
        },
        "h02": {
            "false_rejections": [
                "an abuse to your very person",
                "The devil has used it since the beginning",
            ],
            "invented_causality_unit": _unit_note(h02, "because_clause"),
            "very_person_unit": _unit_note(h02, "very_person"),
            "since_beginning_unit": _unit_note(h02, "since_the_beginning"),
            "context_preserved": True,
            "presegmentation_effect": (
                "The because-clause can be a local unit, reducing the chance that "
                "causality is mixed into a neighboring span. Stylistic intensifiers "
                "and continuity paraphrases still require model judgment."
            ),
            "false_rejection_risk_remaining": (
                "Remaining. Isolation is not acceptance."
            ),
            "structural_load_reduced": True,
            "semantic_load_unchanged": True,
            "evidence_level": "HYPOTHESIS",
            "observed_unit_preservation_level": "DETERMINISTICALLY_VERIFIED",
        },
        "h11": {
            "false_rejections": [
                "mental technique",
                "positive thinking",
                "sermon illustration",
            ],
            "guarantee_unit": _unit_note(h11, "universal_guarantee"),
            "mind_over_matter_unit": _unit_note(h11, "mind_over_matter"),
            "positive_thinking_unit": _unit_note(h11, "positive_thinking"),
            "context_preserved": True,
            "presegmentation_effect": (
                "Local offsets would cover 'subject', 'reality', 'aside', 'ending', "
                "and 'death.' fully. The guarantee can be a local implicative unit. "
                "Prefix false rejections remain a semantic question."
            ),
            "coverage_gaps_would_be_locally_owned": True,
            "false_rejection_risk_remaining": (
                "Remaining for the three supported-prefix disagreements."
            ),
            "structural_load_reduced": True,
            "semantic_load_unchanged": True,
            "evidence_level": "HYPOTHESIS",
            "observed_unit_preservation_level": "DETERMINISTICALLY_VERIFIED",
        },
        "summary": (
            "Presegmentation can reduce structural load (offsets, coverage, identifiers). "
            "It has not been shown to reduce semantic false rejections. Architecture C "
            "must not be described as a Terra-validated fix."
        ),
        "evidence_level": "HYPOTHESIS",
        "secrets_included": False,
    }


__all__ = ["false_rejection_analysis"]
