"""Architecture A/B/C analysis and comparison. No architecture declared superior without evidence."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b28.constants import (
    PHASE,
    PROMPT_VERSION_113,
    TARGET_ARCHITECTURE,
    TRANSPORT_VERSION_11,
)


def architecture_a_analysis() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "id": "A",
        "name": "Current Semantic Gate",
        "status": "DEPLOYED_AS_CANDIDATE_NOT_PRODUCTION_PROMOTED",
        "contract": PROMPT_VERSION_113,
        "transport": TRANSPORT_VERSION_11,
        "model_responsibilities": [
            "Segment the paragraph",
            "Identify spans and offsets",
            "Associate evidence handles",
            "Judge propositions",
            "Emit verdicts and reason codes",
            "Cover the paragraph",
            "Respect the JSON contract",
        ],
        "local_responsibilities": [
            "Validate JSON",
            "Validate catalog membership",
            "Validate spans and coverage",
            "Block acceptance on FAIL/REVIEW",
        ],
        "advantages": [
            "Single call, no extra local linguistic component.",
            "Model sees the paragraph as a whole, which can preserve distributed causality.",
            "Observed true positives: h02 invented causality; h11 universal guarantee.",
        ],
        "observed_limits": [
            "h01 false rejection of supported paraphrase.",
            "h02 two false rejections plus unknown reason codes.",
            "h11 three supported-prefix false rejections.",
            "h11 coverage gaps are word endings, not separators.",
            "Offsets and coverage are a structural burden on the model.",
        ],
        "complexity": "High prompt complexity; mixed structural and semantic tasks.",
        "cost_observed": "See cost_comparison.json. Not projected here as a prediction.",
        "risks": [
            "Structural errors fail an otherwise useful semantic judgment.",
            "Prompt growth (1.1 → 1.1.3) increases input tokens without proving fewer false rejections.",
        ],
        "terra_validated_for_this_phase": False,
        "evidence_level": "OBSERVED",
        "secrets_included": False,
    }


def architecture_b_analysis() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "id": "B",
        "name": "Deterministic presegmentation",
        "status": "EXPERIMENTAL_PROTOTYPE_ONLY",
        "model_responsibilities": [
            "Evaluate fidelity of pre-identified units",
            "Associate authorized evidence",
            "Emit verdicts and catalog reason codes",
        ],
        "local_responsibilities": [
            "Offsets",
            "Coverage",
            "Stable identifiers",
            "Structural compliance",
            "Conservative segmentation",
        ],
        "advantages": [
            "Removes offset arithmetic from the model.",
            "Makes coverage a local invariant.",
            "Can isolate a because-clause or which-means clause as a unit.",
        ],
        "limits": [
            "A better split does not prove better semantic understanding.",
            "Not tested with real Terra.",
            "False rejections of paraphrase may persist.",
        ],
        "risks": [
            "Bad segmentation",
            "Detached negation",
            "Detached condition",
            "Causality split across units",
            "Insufficient context if the model ignores context",
            "False sense of precision",
        ],
        "mitigations_in_prototype": [
            "Do not split 'not because'.",
            "Keep connectives with the following clause.",
            "Retain full paragraph as context.",
            "Ambiguity flag and conservative whole-paragraph fallback.",
        ],
        "complexity": "Adds a local linguistic component. Reduces prompt structural instructions.",
        "cost": "Hypothetical only. Output JSON can omit s/e/t copies. Reasoning tokens are unknown.",
        "terra_validated_for_this_phase": False,
        "evidence_level": "HYPOTHESIS",
        "offline_prototype_evidence_level": "DETERMINISTICALLY_VERIFIED",
        "secrets_included": False,
    }


def architecture_c_analysis() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "id": "C",
        "name": "Hybrid two-level validation",
        "status": "PROPOSED_TARGET_NOT_ACTIVATED",
        "level_1_deterministic": [
            "Integrity and schema",
            "Identifiers",
            "Coverage from local units",
            "Evidence handle membership",
            "Unknown reason codes",
            "Missing codes on reservations",
            "Structural anomalies",
        ],
        "level_2_model": [
            "Paraphrase",
            "Implication",
            "Causality",
            "Strengthening",
            "Generalization",
            "Source fidelity",
        ],
        "final_decision": (
            "Blocking rules remain: QUESTIONABLE/UNSUPPORTED block production PASS. "
            "Unknown codes FAIL. Coverage FAIL is local and does not require the model "
            "to recount characters."
        ),
        "presegmentation_in_c": (
            "Relevant. Architecture C can consume B's units so the model never emits offsets."
        ),
        "does_not_automatically_fix_false_rejections": True,
        "advantages": [
            "Separates what code can guarantee from what only a model can judge.",
            "Preserves observed true positives as model tasks.",
            "Makes h11-style word-ending gaps locally impossible on new calls.",
        ],
        "limits": [
            "Semantic false rejections remain untested under C.",
            "Two-level design can still over-trust isolated units.",
            "Migration requires a new contract and a later authorized Terra canary.",
        ],
        "complexity": "Highest local complexity; lowest model structural load.",
        "cost": "Hypothetical. Fewer output fields; unknown reasoning-token effect.",
        "terra_validated_for_this_phase": False,
        "evidence_level": "HYPOTHESIS",
        "secrets_included": False,
    }


def _cell(observation: str, hypothesis: str, limitation: str, level: str) -> dict[str, str]:
    return {
        "observation": observation,
        "hypothesis": hypothesis,
        "limitation": limitation,
        "evidence_level": level,
    }


def architecture_comparison() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "scoring_scale_not_used": True,
        "no_numeric_scores": True,
        "no_architecture_declared_terra_validated": True,
        "proposed_target": TARGET_ARCHITECTURE,
        "proposed_target_is_not_proven_superior": True,
        "why_c_is_proposed": (
            "Observed failures split into (1) structural duties the model performed "
            "unreliably and (2) semantic judgments that were sometimes correct and "
            "sometimes false rejections. C assigns (1) to local code, including "
            "conservative presegmentation from B, and leaves (2) to the model. "
            "This is an evidential partition, not a Terra result."
        ),
        "matrix": {
            "implementation_complexity": {
                "A": _cell(
                    "Already implemented as 1.1.3-candidate plus local validators.",
                    "Further prompt patches remain cheap to write.",
                    "Prompt patches have not removed false rejections.",
                    "OBSERVED",
                ),
                "B": _cell(
                    "Offline prototype exists in this phase.",
                    "Wiring units into a request is straightforward after authorization.",
                    "Linguistic edge cases remain.",
                    "DETERMINISTICALLY_VERIFIED",
                ),
                "C": _cell(
                    "Combines B plus existing local validators.",
                    "Largest local change; smallest change to model structural duties.",
                    "Not integrated with production.",
                    "HYPOTHESIS",
                ),
            },
            "prompt_complexity": {
                "A": _cell(
                    "1.1.3 still instructs segmentation, coverage, and catalog.",
                    "Further instructions may still grow the prompt.",
                    "h11 input 2562 tokens > h01 1654 despite one paragraph.",
                    "OBSERVED",
                ),
                "B": _cell(
                    "Coverage/offset instructions can be removed.",
                    "Shorter prompt may follow.",
                    "Not measured on Terra.",
                    "HYPOTHESIS",
                ),
                "C": _cell(
                    "Model prompt can be fidelity-only.",
                    "Deterministic layer absorbs schema text locally.",
                    "Not measured on Terra.",
                    "HYPOTHESIS",
                ),
            },
            "model_structural_load": {
                "A": _cell(
                    "Model emits s/e and must cover the paragraph.",
                    "Load contributes to coverage failures.",
                    "Causal link from load to false rejection is unproven.",
                    "OBSERVED",
                ),
                "B": _cell(
                    "Prototype owns offsets and coverage.",
                    "Model load falls.",
                    "Not tested remotely.",
                    "HYPOTHESIS",
                ),
                "C": _cell(
                    "Same as B for structure, plus local blocking.",
                    "Model load is semantic only.",
                    "Not tested remotely.",
                    "HYPOTHESIS",
                ),
            },
            "deterministic_reliability": {
                "A": _cell(
                    "Local validators catch unknown codes and coverage after the fact.",
                    "They cannot prevent the model from emitting bad spans.",
                    "Historical JSON stays invalid under 1.1.3 for h02/h11.",
                    "OBSERVED",
                ),
                "B": _cell(
                    "Offline replay covers all characters of h01/h02/h11.",
                    "New calls would inherit that coverage.",
                    "Segmentation bugs would become systematic.",
                    "DETERMINISTICALLY_VERIFIED",
                ),
                "C": _cell(
                    "Level 1 can reuse B coverage and existing catalog checks.",
                    "Reliability of structure becomes local.",
                    "Semantic reliability remains untested.",
                    "HYPOTHESIS",
                ),
            },
            "false_rejection_risk": {
                "A": _cell(
                    "Observed on h01, h02 (2), h11 (3).",
                    "May persist under any architecture.",
                    "No architecture tested to reduce it.",
                    "OBSERVED",
                ),
                "B": _cell(
                    "Units preserve disputed clauses offline.",
                    "Isolation might help the model focus.",
                    "May also fragment supportive context.",
                    "HYPOTHESIS",
                ),
                "C": _cell(
                    "Does not automatically fix false rejections.",
                    "Removing structural noise might help calibration.",
                    "Requires a later authorized canary.",
                    "HYPOTHESIS",
                ),
            },
            "false_acceptance_risk": {
                "A": _cell(
                    "No false acceptance on the three canaries.",
                    "A less loaded model might become more lenient.",
                    "Absence of false acceptance is not proof of safety.",
                    "OBSERVED",
                ),
                "B": _cell(
                    "Not tested.",
                    "Detached negation could hide a denial.",
                    "Conservative prototype refuses unsafe splits.",
                    "NOT_TESTED",
                ),
                "C": _cell(
                    "Blocking rules stay in local code.",
                    "Risk remains in level 2 judgments.",
                    "Not tested.",
                    "NOT_TESTED",
                ),
            },
            "coverage": {
                "A": _cell(
                    "h01 periods; h02 separators historically; h11 word endings.",
                    "Model will keep making offset errors.",
                    "Policy patches cannot restore omitted letters in saved JSON.",
                    "DETERMINISTICALLY_VERIFIED",
                ),
                "B": _cell(
                    "Offline full-character coverage on the three paragraphs.",
                    "Would hold on new calls if the prototype is used.",
                    "Only three paragraphs replayed.",
                    "DETERMINISTICALLY_VERIFIED",
                ),
                "C": _cell(
                    "Coverage becomes a level-1 invariant.",
                    "h11-class gaps would not reach semantic review as contract FAIL.",
                    "Not tested remotely.",
                    "HYPOTHESIS",
                ),
            },
            "traceability": {
                "A": _cell(
                    "Claims have indices and offsets; notes are visible.",
                    "Empty reason codes on h01 reduce traceability.",
                    "Offsets can be wrong and still look precise.",
                    "OBSERVED",
                ),
                "B": _cell(
                    "Stable unit ids and exact slices.",
                    "Traceability of structure improves.",
                    "Semantic rationale still depends on model notes.",
                    "DETERMINISTICALLY_VERIFIED",
                ),
                "C": _cell(
                    "Can join local units to model verdicts by id.",
                    "Best of both if implemented.",
                    "Not implemented in production.",
                    "HYPOTHESIS",
                ),
            },
            "estimated_cost": {
                "A": _cell(
                    "h01 0.018812; h02 0.066036; h11 0.029556 USD calculated.",
                    "Status quo cost continues.",
                    "Not an invoice.",
                    "OBSERVED",
                ),
                "B": _cell(
                    "No new provider spend in this phase.",
                    "Output tokens may fall if s/e/t are omitted; reasoning unknown.",
                    "Must not claim reasoning will fall.",
                    "HYPOTHESIS",
                ),
                "C": _cell(
                    "No new provider spend.",
                    "Similar to B; local CPU is negligible vs Terra.",
                    "Not measured.",
                    "HYPOTHESIS",
                ),
            },
            "maintainability": {
                "A": _cell(
                    "Contract versions 1.1 → 1.1.3 accumulated instructions.",
                    "Further patches will keep growing the prompt.",
                    "Overfit risk on canary wording.",
                    "OBSERVED",
                ),
                "B": _cell(
                    "Segmentation is local Python with tests.",
                    "Easier to extend than prompt prose.",
                    "Linguistic rules can rot.",
                    "HYPOTHESIS",
                ),
                "C": _cell(
                    "Clearer ownership boundary.",
                    "Two components to maintain.",
                    "Not in production.",
                    "HYPOTHESIS",
                ),
            },
            "pipeline_compatibility": {
                "A": _cell(
                    "Fits current gate call.",
                    "No pipeline change.",
                    "Still not production-promoted.",
                    "OBSERVED",
                ),
                "B": _cell(
                    "Requires a new request shape.",
                    "Can sit beside A until a canary.",
                    "Must not auto-connect.",
                    "HYPOTHESIS",
                ),
                "C": _cell(
                    "Requires contract 2.0 and local orchestration.",
                    "Compatible if the gate remains a canary stage.",
                    "Migration stop points required.",
                    "HYPOTHESIS",
                ),
            },
            "migration_risks": {
                "A": _cell(
                    "Staying on A preserves known PARTIAL canaries.",
                    "Repeating Terra calls without architectural change repeats cost.",
                    "Calibration-only path is unproven.",
                    "OBSERVED",
                ),
                "B": _cell(
                    "Prototype is isolated.",
                    "Connecting it too early could change Terra behavior opaquely.",
                    "No remote test.",
                    "HYPOTHESIS",
                ),
                "C": _cell(
                    "Largest design change.",
                    "Needs human review, offline tests, then one authorized canary.",
                    "Stop points in migration_plan.json.",
                    "HYPOTHESIS",
                ),
            },
        },
        "secrets_included": False,
    }


__all__ = [
    "architecture_a_analysis",
    "architecture_b_analysis",
    "architecture_c_analysis",
    "architecture_comparison",
]
