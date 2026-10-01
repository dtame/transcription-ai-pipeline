"""book-generator-1.0.1 sufficiency given an independent semantic gate."""

from __future__ import annotations

from typing import Any


def sufficiency_assessment() -> dict[str, Any]:
    return {
        "prompt": "book-generator-1.0.1",
        "do_not_automatically_reject": True,
        "current_evidence": {
            "major_improvement": True,
            "technical_pass_4b22": True,
            "historical_4b2_defects_eliminated": [
                "empty paragraph",
                "invented funeral illustration",
                "unsupported connective closer",
            ],
            "residual_semantic_extensions": 2,
            "residual_cases": [
                "4B.2.2 p3 NEW_CAUSAL_LINK / NEW_IMPLICATION",
                "4B.2.2 p8 REFERENCE_COMPLETION / REFERENCE_EXPANSION",
            ],
            "real_ch016_generations": 2,
        },
        "classification": "SUFFICIENT_WITH_SEMANTIC_GATE",
        "why": (
            "The remaining 4B.2.2 defects are unsupported semantic extensions "
            "inside an otherwise technically valid chapter. They are exactly "
            "the class of error the independent semantic gate is designed to "
            "block before cache acceptance. Architecture does not require a "
            "perfect generator. It requires a pipeline that refuses "
            "QUESTIONABLE and UNSUPPORTED content."
        ),
        "not": [
            "INSUFFICIENT_EVEN_WITH_GATE",
            "NEEDS_MORE_EVIDENCE",
        ],
        "sample_limitation": {
            "real_generations": 2,
            "do_not_infer_production_failure_rate": True,
            "rejection_rate": "UNKNOWN",
            "unknown_is_not_zero": True,
        },
        "acceptable_future_rejection_policy": {
            "occasional_rejected_chapter": "acceptable if gate blocks cache",
            "automatic_regeneration_loop": "forbidden until explicitly designed",
            "chronic_high_rejection": (
                "not a license for an unreliable generator; investigate prompt, "
                "evidence, or model if rejection becomes routine"
            ),
            "human_review_of_questionable": True,
            "do_not_seek_perfect_ch016_sample": True,
        },
        "4b22_candidate_production_cache": "NOT ACCEPTED",
        "next_useful_experiment": (
            "ONE REAL TERRA SEMANTIC-GATE BENCHMARK CANARY on frozen "
            "historical human-labeled cases. Not another Sonnet CH016."
        ),
    }


__all__ = ["sufficiency_assessment"]
