"""Matrice des options d'architecture de sortie. Analyse seulement."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v31_global_output_architecture.constants import (
    A38_INPUT_TOKENS,
    NEXT_MAX_OUTPUT_TOKENS,
)
from app.source_analysis_v31_global_output_architecture.costing import estimate_cost
from app.source_analysis_v31_global_output_architecture.estimator import estimate_output


def architecture_options(
    *,
    compact_expected: int,
    compact_hard: int,
    transport11_expected: int,
    transport11_high: int,
) -> dict[str, Any]:
    compact_cost = estimate_cost(
        input_tokens=A38_INPUT_TOKENS, output_tokens=compact_expected
    )
    same_64k = estimate_cost(input_tokens=A38_INPUT_TOKENS, output_tokens=64000)
    two_stage = estimate_cost(
        input_tokens=A38_INPUT_TOKENS + 8000, output_tokens=compact_expected + 4000
    )
    return {
        "A": {
            "name": "same transport 1.1 + larger max_output",
            "semantic_fidelity": "UNCHANGED",
            "output_boundedness": "EMPIRICAL_ONLY",
            "input_tokens": A38_INPUT_TOKENS,
            "output_tokens_planning": transport11_expected,
            "provider_calls": 1,
            "cost": same_64k,
            "failure_blast_radius": "HIGH — entire verbose JSON lost on truncation",
            "auditability": "SAME_AS_1_1",
            "determinism": "PROVIDER_HEAVY",
            "implementation_complexity": "LOW",
            "relation_quality": "UNCHANGED_DEBT",
            "source_map_compatibility": "YES",
            "selected": False,
            "why_not": (
                "Fits only at 64K+ and still unbounded. A.38 already proved "
                "verbosity and almost no merge. Raising the cap repeats the "
                "same blast radius at higher cost."
            ),
        },
        "B": {
            "name": "inverse-membership compact transport + one global call",
            "semantic_fidelity": "PRESERVED",
            "output_boundedness": "CALCULABLE",
            "input_tokens": A38_INPUT_TOKENS,
            "output_tokens_planning": compact_expected,
            "hard_output_tokens": compact_hard,
            "provider_calls": 1,
            "cost": compact_cost,
            "failure_blast_radius": "MEDIUM — one bounded call",
            "auditability": "STRONGER — membership + derived SRC",
            "determinism": "HIGHER — dispositions and SRC derived",
            "implementation_complexity": "MEDIUM",
            "relation_quality": "DEFERRED_WITH_DEBT_PRESERVED",
            "source_map_compatibility": "YES via reconstruction",
            "selected": True,
            "why": (
                "Smallest redesign that makes output bounded by construction "
                "without dropping 286-IDEA accountability or forcing merges."
            ),
        },
        "C": {
            "name": "inverse-membership + separate relation stage",
            "semantic_fidelity": "PRESERVED",
            "output_boundedness": "CALCULABLE_PER_STAGE",
            "provider_calls": 2,
            "cost": two_stage,
            "failure_blast_radius": "LOWER_PER_CALL",
            "auditability": "STRONG",
            "determinism": "HIGH",
            "implementation_complexity": "HIGH",
            "relation_quality": "POTENTIALLY_BETTER_FOCUS",
            "source_map_compatibility": "YES",
            "selected": False,
            "why_not": (
                "Useful later. Extra call and cross-stage complexity are not "
                "required once relations are deferred from SourceMap completion."
            ),
        },
        "D": {
            "name": "hierarchical / thematic consolidation",
            "semantic_fidelity": "RISK_OF_THEME_LOSS",
            "output_boundedness": "PER_THEME",
            "provider_calls": "3+",
            "failure_blast_radius": "DISTRIBUTED",
            "implementation_complexity": "HIGH",
            "source_map_compatibility": "YES_AFTER_MERGE",
            "selected": False,
            "why_not": "More calls and merge-loss risk without a proven need.",
        },
        "E": {
            "name": "deterministic pre-clustering + one consolidation",
            "semantic_fidelity": "RISK_IF_CLUSTER_WRONG",
            "output_boundedness": "HELPFUL_HINT_ONLY",
            "provider_calls": 1,
            "implementation_complexity": "MEDIUM",
            "selected": False,
            "why_not": (
                "A.34 found 0 high-confidence duplicates. Pre-clustering is a "
                "hint generator, not a bound."
            ),
        },
        "F": {
            "name": "multiple bounded consolidation calls + deterministic merge",
            "semantic_fidelity": "CROSS_CALL_MERGE_RISK",
            "output_boundedness": "PER_CALL",
            "provider_calls": "2+",
            "implementation_complexity": "HIGH",
            "selected": False,
            "why_not": (
                "Reject one-call only if compact 2.0 cannot meet its bound. "
                "It can, at 48000 with a calculable hard cap."
            ),
        },
        "preferred_principle": (
            "Smallest redesign that makes output bounded and auditable "
            "without lowering semantic fidelity."
        ),
        "selected": "B",
        "next_max_output": NEXT_MAX_OUTPUT_TOKENS,
        "compact_estimate": estimate_output(),
    }


__all__ = ["architecture_options"]
