"""Architecture options A/B/C. None is activated. None is declared validated."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b212.constants import PHASE


def architecture_options() -> dict[str, Any]:
    strategies = {
        "A_full_semantic_gate_20": {
            "name": "Semantic Gate 2.0 complete",
            "method": "Validate every unit of every paragraph with the IA auditor.",
            "advantages": [
                "Broad coverage of inventions, not only pre-tagged risk classes.",
                "Stable unit identifiers already exist from conservative segmentation.",
                "4B.2.11 showed Terra can accept a faithful paraphrase when the units are supplied.",
            ],
            "limits": [
                "Cost scales with unit count across 19 chapters.",
                "One positive h01 case does not validate negative families h02/h11.",
                "Contract fragility can still BLOCK a semantically acceptable paragraph.",
                "False rejections would stall production even after 2.0.2 consolidation.",
                "Validation load is high: every paragraph waits on a remote JSON object.",
            ],
            "validated": False,
            "cost_is_not_the_decision_criterion": True,
        },
        "B_targeted_high_risk": {
            "name": "Targeted high-risk validation",
            "method": (
                "Run IA only on propositions that look like causality, implication, "
                "guarantee, example, reference, attribution, or strengthening."
            ),
            "advantages": [
                "Fewer paid calls.",
                "Attention stays on the invention families that historically mattered.",
                "Deterministic detectors can pre-filter candidates.",
            ],
            "limits": [
                "An invention outside the detector categories can pass unseen.",
                "Detectors themselves can miss a lightly worded causal or universal claim.",
                "Targeting does not remove the need for a strict response contract.",
                "h01-style paraphrase risk sits outside those high-risk tags, so targeting alone would not have produced the 4B.2.11 observation.",
            ],
            "missed_invention_risk": "HIGH_IF_DETECTORS_ARE_INCOMPLETE",
            "validated": False,
            "cost_is_not_the_decision_criterion": True,
        },
        "C_hybrid_supervised": {
            "name": "Hybrid supervised validation",
            "method": (
                "Deterministic preparation and coverage, IA semantic classification "
                "on prepared units or on high-risk subset, Python operational "
                "PASS/BLOCK/REVIEW, human review of REVIEW and BLOCK, independent "
                "Book Validator in Phase 5."
            ),
            "advantages": [
                "Separates semantic, operational, and technical duties as 2.0.2 now requires.",
                "REVIEW is a real state, not a silent pass into the production cache.",
                "A blocked chapter can be isolated without regenerating the whole book.",
                "The independent Book Validator remains a second line after the gate.",
                "Human review stays on ambiguities rather than on every paraphrase.",
            ],
            "limits": [
                "Still unproven on negative Terra cases.",
                "Human bandwidth is part of the control system, not an afterthought.",
                "Requires the 2.0.2 contract to be used on a later authorized call before production trust.",
                "Not sufficient by itself to publish book.json.",
            ],
            "conditions_for_first_book": [
                "Canonical SourceMap, EditorialPlan, and transcript remain frozen.",
                "Each generated chapter keeps source-to-unit traceability.",
                "Semantic Gate 2.0.2 stays fail-closed and inactive until a later authorization.",
                "REVIEW never writes the production cache.",
                "BLOCK isolates the chapter; no automatic full-book retry.",
                "Phase 5 Book Validator stays independent.",
                "Human review of REVIEW, BLOCK, and any residual high-risk claims.",
            ],
            "validated": False,
            "cost_is_not_the_decision_criterion": True,
        },
    }
    return {
        "phase": PHASE,
        "strategies": strategies,
        "comparison": {
            "coverage": {"A": "highest", "B": "category-limited", "C": "layered"},
            "false_reject_exposure": {"A": "high_if_contract_or_model_strict", "B": "lower_volume_higher_miss", "C": "absorbed_by_REVIEW"},
            "missed_invention_exposure": {"A": "lowest_in_principle", "B": "highest", "C": "medium_with_human_backstop"},
            "production_block_risk": {"A": "high", "B": "medium", "C": "controlled"},
            "human_load": {"A": "low_until_block_storm", "B": "low", "C": "explicit"},
        },
        "proposed_integration_strategy": "C_HYBRID_SUPERVISED_CANDIDATE_FOR_HUMAN_REVIEW",
        "proposed_not_activated": True,
        "proposed_not_validated": True,
        "why_not_cost_alone": (
            "A cheaper targeted gate that misses an invented causality would "
            "violate low semantic freedom. A full gate that still confuses "
            "PASS with SUPPORTED would stall a faithful book. Hybrid keeps "
            "the fidelity boundary while refusing to treat one PARTIAL canary "
            "as production proof."
        ),
        "evidence_used": [
            "4B.2.11: five SUPPORTED units, target paraphrase recognized, contract FAIL.",
            "Historical h01/h02/h11 remain PARTIAL under the old architecture.",
            "FakeAI exercises the validator, not Terra.",
        ],
        "none_activated": True,
        "secrets_included": False,
    }


__all__ = ["architecture_options"]
