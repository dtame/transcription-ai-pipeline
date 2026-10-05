"""Offline segmentation replay on exact h01/h02/h11 paragraphs. No Terra call."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b28.canaries import load_canary_bundle
from app.book_semantic_gate_4b28.constants import (
    DISPUTED_CAUSAL_CLAUSE,
    H01_DISPUTED_CLAUSE,
    H11_DISPUTED_CLAUSE,
    PHASE,
)
from app.book_semantic_gate_4b28.segmentation import (
    prepare_semantic_validation_units,
    spans_preserved,
)


def _replay_one(handle: str, text: str, preserved: list[tuple[int, int, str]]) -> dict[str, Any]:
    first = prepare_semantic_validation_units(text)
    second = prepare_semantic_validation_units(text)
    first_units = [
        {
            "id": unit["id"],
            "start_offset": unit["start_offset"],
            "end_offset": unit["end_offset"],
            "text": unit["text"],
            "boundary_type": unit["boundary_type"],
            "ambiguous": unit["ambiguous"],
        }
        for unit in first.get("units") or []
    ]
    second_units = [
        {
            "id": unit["id"],
            "start_offset": unit["start_offset"],
            "end_offset": unit["end_offset"],
            "text": unit["text"],
            "boundary_type": unit["boundary_type"],
            "ambiguous": unit["ambiguous"],
        }
        for unit in second.get("units") or []
    ]
    return {
        "handle": handle,
        "paragraph_chars": len(text),
        "unit_count": first.get("unit_count"),
        "ambiguous_unit_count": first.get("ambiguous_unit_count"),
        "conservative_fallback": first.get("conservative_fallback"),
        "coverage": first.get("coverage"),
        "units": first_units,
        "preserved_propositions": spans_preserved(first, preserved),
        "offset_stability": first_units == second_units,
        "deterministic_replay": first_units == second_units,
        "paragraph_unchanged": first.get("paragraph_unchanged"),
        "not_a_terra_verdict": True,
        "evidence_level": "DETERMINISTICALLY_VERIFIED",
    }


def segmentation_offline_replay(*, root=None) -> dict[str, Any]:
    bundle = load_canary_bundle(root=root)
    h01_text = str(bundle["h01"].get("text") or "")
    h02_text = str(bundle["h02"].get("text") or "")
    h11_text = str(bundle["h11"].get("text") or "")
    h01_start = h01_text.find(H01_DISPUTED_CLAUSE)
    h02_start = h02_text.find(DISPUTED_CAUSAL_CLAUSE)
    h11_start = h11_text.find(H11_DISPUTED_CLAUSE)
    h01 = _replay_one(
        "h01",
        h01_text,
        [
            (h01_start, h01_start + len(H01_DISPUTED_CLAUSE), "bargain_clause"),
        ]
        if h01_start >= 0
        else [],
    )
    h02 = _replay_one(
        "h02",
        h02_text,
        [
            (h02_start, h02_start + len(DISPUTED_CAUSAL_CLAUSE), "because_clause"),
            (
                h02_text.find("an abuse to your very person"),
                h02_text.find("an abuse to your very person")
                + len("an abuse to your very person"),
                "very_person",
            ),
            (
                h02_text.find("The devil has used it since the beginning"),
                h02_text.find("The devil has used it since the beginning")
                + len("The devil has used it since the beginning"),
                "since_the_beginning",
            ),
        ]
        if h02_start >= 0
        else [],
    )
    h11 = _replay_one(
        "h11",
        h11_text,
        [
            (h11_start, h11_start + len(H11_DISPUTED_CLAUSE), "universal_guarantee"),
            (
                h11_text.find("It is not mind over matter"),
                h11_text.find("It is not mind over matter") + len("It is not mind over matter"),
                "mind_over_matter",
            ),
            (
                h11_text.find("not a trick of positive thinking applied to a frightening subject"),
                h11_text.find("not a trick of positive thinking applied to a frightening subject")
                + len("not a trick of positive thinking applied to a frightening subject"),
                "positive_thinking",
            ),
        ]
        if h11_start >= 0
        else [],
    )
    return {
        "phase": PHASE,
        "provider_calls": 0,
        "historical_terra_verdicts_not_reissued": True,
        "old_responses_not_treated_as_new_architecture_answers": True,
        "h01": h01,
        "h02": h02,
        "h11": h11,
        "all_complete_char_coverage": all(
            (item.get("coverage") or {}).get("complete_chars") for item in (h01, h02, h11)
        ),
        "all_offset_stable": all(
            item.get("offset_stability") for item in (h01, h02, h11)
        ),
        "evidence_level": "DETERMINISTICALLY_VERIFIED",
        "secrets_included": False,
    }


def segmentation_design() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "prototype": "prepare_semantic_validation_units",
        "strategy": "hybrid_conservative",
        "sentence_segmentation": True,
        "clause_segmentation": (
            "Only on em dash, semicolon, and selected clause-initial connectives "
            "(because, which means, unless, although, and so)."
        ),
        "not_split": [
            "every comma",
            "coordinating and/or",
            "relative that-clauses",
            "not because",
            "negation particles",
        ],
        "context": "Each unit retains the full paragraph as context.",
        "stable_ids": "u00, u01, ... in left-to-right order",
        "unicode_offsets": "python3_str_half_open",
        "full_coverage_required": True,
        "punctuation_retained": True,
        "connectives_retained_with_following_clause": True,
        "negations_not_detached": True,
        "ambiguity_status": "Units may be marked ambiguous; unsafe paragraphs fall back to one unit.",
        "not_a_perfect_semantic_analysis": True,
        "does_not_judge_fidelity": True,
        "risks": [
            "Bad split of distributed causality",
            "False precision if units look like gold claims",
            "Insufficient context if the model ignores the context field",
        ],
        "evidence_level": "HYPOTHESIS",
        "feasibility_offline": "DETERMINISTICALLY_VERIFIED",
        "secrets_included": False,
    }


__all__ = ["segmentation_design", "segmentation_offline_replay"]
