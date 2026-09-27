"""Audit m[] + nécessité locale vs canonique. Ne mute pas V3."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from app.source_analysis.models import (
    EXAMPLE_KINDS,
    IDEA_KINDS,
    IMPORTANCE_LEVELS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    RELATION_KINDS,
    SEVERITY_LEVELS,
    UNCERTAINTY_KINDS,
)
from app.source_analysis_v3_a22_forensics.metadata_audit import audit_all_metadata as audit_m_values
from app.source_analysis_v3_a25_forensics.constants import (
    IDEA_KIND_COUNTS_EXPECTED,
    IDEA_SUBTYPE_REQUIRED_CANONICALLY,
    IDEA_SUBTYPE_REQUIRED_LOCALLY,
    MODE,
    M_OVERLOADED,
    PHASE,
    SCHEMA_VERSION,
)


def _allowed() -> dict[str, Any]:
    return {
        "TOPIC": {
            "shape": "m=[summary]",
            "m0": "free-text topic summary",
            "m1": None,
            "required": True,
            "cardinality": 1,
        },
        "IDEA": {
            "shape": "m=[kind, importance]",
            "m0": list(IDEA_KINDS),
            "m1": list(IMPORTANCE_LEVELS),
            "required": True,
            "cardinality": 2,
        },
        "RELATION": {
            "shape": "m=[] ; type lives in v",
            "m0": None,
            "m1": None,
            "required": False,
            "cardinality": 0,
            "v_allowed": list(RELATION_KINDS),
        },
        "EXAMPLE": {
            "shape": "m=[kind]",
            "m0": list(EXAMPLE_KINDS),
            "m1": None,
            "required": True,
            "cardinality": 1,
        },
        "REFERENCE": {
            "shape": "m=[kind, completeness, normalized]",
            "m0": list(REFERENCE_KINDS),
            "m1": list(REFERENCE_COMPLETENESS),
            "m2": "free-text normalized citation",
            "required": True,
            "cardinality": 3,
        },
        "UNCERTAINTY": {
            "shape": "m=[kind, severity]",
            "m0": list(UNCERTAINTY_KINDS),
            "m1": list(SEVERITY_LEVELS),
            "required": True,
            "cardinality": 2,
        },
    }


def _matrix() -> list[dict[str, Any]]:
    return [
        {
            "record_kind": "TOPIC",
            "meaning_m0": "topic summary",
            "meaning_m1": "unused",
            "allowed_values": "free text",
            "required": "required",
            "downstream_consumer": "hybrid_reconstructor TOPIC KEEP/MERGE",
            "canonical_destination": "Topic.summary",
        },
        {
            "record_kind": "IDEA",
            "meaning_m0": "semantic subtype (claim/explanation/…)",
            "meaning_m1": "importance (central/supporting/minor)",
            "allowed_values": f"m0∈{list(IDEA_KINDS)}; m1∈{list(IMPORTANCE_LEVELS)}",
            "required": "required by current V3 decoder",
            "downstream_consumer": (
                "hybrid_reconstructor._idea_raw; source_map validator; "
                "MERGE-same-kind constraint"
            ),
            "canonical_destination": "Idea.kind / Idea.importance",
        },
        {
            "record_kind": "RELATION",
            "meaning_m0": "unused (must be empty)",
            "meaning_m1": "unused",
            "allowed_values": "m must be [] ; type in v",
            "required": "m optional/empty",
            "downstream_consumer": "hybrid_reconstructor relations from v + l[]",
            "canonical_destination": "IdeaRelation.relation_type",
        },
        {
            "record_kind": "EXAMPLE",
            "meaning_m0": "example subtype",
            "meaning_m1": "unused",
            "allowed_values": list(EXAMPLE_KINDS),
            "required": "required",
            "downstream_consumer": "hybrid_reconstructor._example_kind",
            "canonical_destination": "Example.kind",
        },
        {
            "record_kind": "REFERENCE",
            "meaning_m0": "reference kind",
            "meaning_m1": "completeness",
            "allowed_values": (
                f"m0∈{list(REFERENCE_KINDS)}; m1∈{list(REFERENCE_COMPLETENESS)}"
            ),
            "required": "required",
            "downstream_consumer": "hybrid_reconstructor._reference_raw",
            "canonical_destination": "Reference.kind / completeness / normalized",
        },
        {
            "record_kind": "UNCERTAINTY",
            "meaning_m0": "uncertainty kind",
            "meaning_m1": "severity",
            "allowed_values": f"m0∈{list(UNCERTAINTY_KINDS)}; m1∈{list(SEVERITY_LEVELS)}",
            "required": "required",
            "downstream_consumer": "hybrid_reconstructor uncertainty rows",
            "canonical_destination": "Uncertainty.kind / severity",
        },
    ]


def build_metadata_necessity(
    transport: Mapping[str, Any] | None,
) -> dict[str, Any]:
    observed = audit_m_values(transport)
    observed["idea_kind_counts_expected"] = dict(IDEA_KIND_COUNTS_EXPECTED)
    observed["matches_expected_idea_counts"] = observed.get(
        "idea_kind_counts"
    ) == dict(IDEA_KIND_COUNTS_EXPECTED)
    observed["phase"] = PHASE
    observed["mode"] = MODE
    leakage = {
        "example_token_valid_for_example_invalid_for_idea": True,
        "testimony_valid_for_both_idea_and_example": True,
        "cross_kind_vocabulary_collision": ["example", "testimony"],
        "ordering_assumption": (
            "Decoder assumes positional m[0]/m[1] meaning by record kind. "
            "The provider schema cannot express that (no enum, no oneOf)."
        ),
        "duplicate_metadata": (
            "I44.m[0]=example duplicates EXAMPLE 88 kind=case_study for the "
            "same Biya/economy material."
        ),
        "unused_metadata": [
            {
                "field": "IDEA.m[0] semantic subtype at local extraction",
                "generated_by_llm": True,
                "material_effect_on_canonical_if_globalized": (
                    "None if global consolidation classifies later. "
                    "Currently copied by reconstructor."
                ),
                "dead_if_local_only": True,
            }
        ],
    }
    consumers = {
        "idea_kind": {
            "source_map_normalizer": "copies if present; does not invent",
            "canonical_source_map": "Idea.kind exists; validator requires ∈ IDEA_KINDS at publication",
            "consolidator": "does not classify; MERGE requires identical local kinds",
            "editorial_planner": "no Phase 4 consumer in this repository",
            "validator": "local decoder + source_map validator",
            "audit_only": False,
            "nobody": False,
            "book_package": "no matches",
        },
        "idea_importance": {
            "canonical_source_map": "Idea.importance",
            "consolidator": "MERGE requires identical importance",
            "editorial_planner": "no Phase 4 consumer yet",
            "local_extraction_need": "optional; useful but not the A.24 failure",
        },
    }
    idea_subtype = {
        "canonical": True,
        "required_locally": IDEA_SUBTYPE_REQUIRED_LOCALLY,
        "required_canonically": IDEA_SUBTYPE_REQUIRED_CANONICALLY,
        "used_downstream_today": (
            "Yes — reconstructor copies local m[0]; source_map validator "
            "requires a valid kind at publication. Book/Editorial Planner do not."
        ),
        "book_editorial_planning_requires_it": False,
        "could_be_derived_later": True,
        "could_be_omitted_locally_without_phase3_information_loss": True,
        "taxonomy_previously_defined_does_not_force_local_llm_classification": True,
        "q4_answer": (
            "Removing IDEA semantic subtype from LOCAL transport preserves the "
            "information Phase 3 local extraction actually needs: idea text, "
            "SRC grounding, topic association, and (optionally) importance. "
            "Canonical kind can be filled by global consolidation or omitted "
            "until a later classifier. It is not required for local source "
            "grounding."
        ),
        "q2_answer": (
            "Yes. m[] is an overloaded positional bag. The same slot means "
            "summary, kind, importance, completeness, or severity depending on "
            "k. That is an unnecessarily fragile representation for closed "
            "vocabularies that collide across kinds."
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "m_overloaded": M_OVERLOADED,
        "allowed_values": _allowed(),
        "observed_audit": observed,
        "semantics_matrix": _matrix(),
        "cross_kind_leakage": leakage,
        "downstream_consumers": consumers,
        "idea_subtype_necessity": idea_subtype,
        "dead_metadata": idea_subtype["could_be_omitted_locally_without_phase3_information_loss"],
        "q3_schema_enforcement_without_grammar_blowup": {
            "current_schema_has_no_enums": True,
            "discriminated_union_or_oneOf": (
                "Would encode kind-specific m[] but historically risks "
                "grammar-too-large. Not measured in A.25. Status would be "
                "SERVER_GRAMMAR_UNVERIFIED. Not selected."
            ),
            "compact_per_kind_keys": (
                "Same grammar risk if added to the provider schema."
            ),
            "python_validation_already_enforces": True,
            "python_cannot_stop_the_model_from_emitting_example": True,
        },
    }


__all__ = ["build_metadata_necessity"]
