"""Matrice d'options A.43 et architecture retenue."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v31_global_reuse_output.constants import (
    PRODUCTION_MAX_OUTPUT_TOKENS,
    SELECTED_ARCHITECTURE,
    SELECTED_OPTION,
    V20_HARD_OUTPUT,
)
from app.source_analysis_v31_global_reuse_output.estimator import revised_reuse_budget


def architecture_options(budget: dict[str, Any] | None = None) -> dict[str, Any]:
    live = budget or revised_reuse_budget()
    hard_b = live.get("hard_planning")
    return {
        "do_not_solve_by_max_output_alone": True,
        "options": {
            "A": {
                "name": "transport 2.0 unchanged, max_output 48000",
                "fidelity": "HIGH",
                "boundedness": "WEAK",
                "output_tokens_hard": V20_HARD_OUTPUT,
                "calls": 1,
                "cost": "current production estimate",
                "latency": "ONE_CALL",
                "auditability": "HIGH",
                "determinism": "HIGH",
                "implementation_complexity": "NONE",
                "failure_blast_radius": "OUTPUT_CAP_AGAIN",
                "rejected_because": "hard 41430 / 48000 = 86.3% remains NEEDS_OUTPUT_REDESIGN",
            },
            "B": {
                "name": "hard single-member REUSE; synthesize merges only",
                "fidelity": "HIGHEST",
                "boundedness": "STRONG",
                "output_tokens_hard": hard_b,
                "calls": 1,
                "cost": "lower output than A",
                "latency": "ONE_CALL",
                "auditability": "HIGHEST",
                "determinism": "HIGHEST",
                "implementation_complexity": "LOW",
                "failure_blast_radius": "SMALL_SCHEMA_BUMP",
                "selected": True,
            },
            "C": {
                "name": "reuse + bounded single-member rewrite exceptions",
                "fidelity": "HIGH",
                "boundedness": "MEDIUM",
                "output_tokens_hard": "B plus exception text; cap required or bound collapses",
                "calls": 1,
                "cost": "higher than B if exceptions are common",
                "latency": "ONE_CALL",
                "auditability": "MEDIUM",
                "determinism": "MEDIUM",
                "implementation_complexity": "MEDIUM",
                "failure_blast_radius": "EXCEPTION_LEAK_RESTORES_V20_VOLUME",
                "rejected_because": (
                    "Local IDEA quality is high; an exception channel would "
                    "re-open unconstrained single-member text."
                ),
            },
            "D": {
                "name": "compact edit-script",
                "fidelity": "HIGH_IF_OPS_NARROW",
                "boundedness": "MEDIUM",
                "output_tokens_hard": "depends on op vocabulary",
                "calls": 1,
                "cost": "uncertain",
                "latency": "ONE_CALL",
                "auditability": "LOWER",
                "determinism": "LOWER",
                "implementation_complexity": "HIGH",
                "failure_blast_radius": "NEW_OP_LANGUAGE",
                "rejected_because": "More complex than B with no fidelity gain on this corpus.",
            },
            "E": {
                "name": "two-stage membership then selective normalization",
                "fidelity": "HIGH",
                "boundedness": "STRONG_PER_CALL",
                "output_tokens_hard": "each stage bounded",
                "calls": 2,
                "cost": "extra input tokens and latency",
                "latency": "TWO_CALLS",
                "auditability": "HIGH",
                "determinism": "HIGH",
                "implementation_complexity": "HIGH",
                "failure_blast_radius": "SECOND_CALL_DRIFT",
                "rejected_because": (
                    "Unnecessary extra provider call when hard reuse already bounds output."
                ),
            },
        },
        "selected": SELECTED_OPTION,
        "selected_architecture": SELECTED_ARCHITECTURE,
        "max_output_comparison_only": PRODUCTION_MAX_OUTPUT_TOKENS,
    }


def selected_architecture(quality: dict[str, Any], budget: dict[str, Any]) -> dict[str, Any]:
    high_quality = bool(quality.get("high_reuse_quality"))
    return {
        "option": SELECTED_OPTION,
        "architecture": SELECTED_ARCHITECTURE,
        "reason": (
            "Local IDEA texts are self-contained propositions. A.38 prefix ideas "
            "were near-copies. A.34 found almost no true duplicates. Hard "
            "single-member REUSE preserves fidelity, removes the v20 idea-text "
            "bottleneck, and needs no extra provider call."
        ),
        "single_member_policy": "DETERMINISTIC_REUSE",
        "multi_member_policy": "SYNTHESIZE",
        "rewrite_exception_policy": "FORBIDDEN",
        "provider_idea_text_required_for": "MULTI_MEMBER_MERGES_ONLY",
        "wire_mode_field": "NONE_DERIVED_FROM_MEMBERSHIP_AND_V_PRESENCE",
        "local_quality_supports_hard_rule": high_quality,
        "needs_alternative_output_architecture": (not high_quality),
        "hard_output": budget.get("hard_planning"),
        "output_risk": budget.get("output_risk"),
        "new_prompt": "global-consolidation-3.0",
        "new_transport": "global-consolidation-transport-3.0",
        "mutate_2_0": False,
        "mutate_2_0_1": False,
    }


__all__ = ["architecture_options", "selected_architecture"]
