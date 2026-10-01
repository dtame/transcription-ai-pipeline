"""Plan de revue sémantique offline d'une future consolidation réelle."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_global_preflight.constants import (
    MODE,
    PHASE,
    SCHEMA_VERSION,
)


def build_semantic_review_plan(
    normalized: Mapping[str, Any],
    duplicates: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    idea_ids = list(normalized.get("idea_input_ids") or [])
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "executed": False,
        "against": [
            "normalized local candidates",
            "exact CLEAN SRC excerpts where necessary",
        ],
        "no_drop_review": {
            "every_substantive_local_idea_checked_against_declared_disposition": True,
            "idea_input_ids": len(idea_ids),
        },
        "merge_review": {
            "for_every_MERGE_EQUIVALENT": [
                "semantic equivalence",
                "no proposition broadening",
                "union of source refs",
                "no loss of qualifiers",
            ],
            "high_confidence_duplicate_pairs_to_inspect": len(
                (duplicates or {}).get("high_confidence") or []
            ),
        },
        "relation_review": {
            "audit_every_global_relation": True,
            "do_not_accept_merely_because_provider_emitted_them": True,
            "RELATION_QUALITY_TECHNICAL_DEBT": "YES",
        },
        "repetition_review": {
            "must_be_actual_source_recurrence": True,
            "related_ideas_are_not_repetitions": True,
        },
        "voice_review": {
            "must_describe_observable_source_characteristics": True,
            "must_not_become_stylistic_invention": True,
        },
        "sample_protocol": {
            "KEEP": "spot-check SRC excerpts vs global wording",
            "MERGE_EQUIVALENT": "review 100% of merges",
            "LINK_RELATED": "confirm distinctness",
            "DROP": "review 100% of drops against allowed reasons",
            "OTHER": "review 100%",
        },
    }


__all__ = ["build_semantic_review_plan"]
