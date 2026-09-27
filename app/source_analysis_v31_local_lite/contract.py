"""Contrat local-lite + politique d'acceptation. Offline."""

from __future__ import annotations

from typing import Any

from app.source_analysis.models import (
    EXAMPLE_KINDS,
    IMPORTANCE_LEVELS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    RELATION_KINDS,
    SEVERITY_LEVELS,
    UNCERTAINTY_KINDS,
)
from app.source_analysis_v3_a19_forensics.constants import EXAMPLE_POLICY
from app.source_analysis_v3_a25_forensics.policy import build_acceptance_policy
from app.source_analysis_v31_local_lite.constants import (
    CANONICAL_IDEA_SUBTYPE,
    GLOBAL_IDEA_SUBTYPE_STRATEGY,
    LOCAL_IDEA_METADATA,
    LOCAL_IDEA_SUBTYPE,
    MODE,
    PHASE,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    TRANSPORT_VERSION,
)


def build_local_lite_contract() -> dict[str, Any]:
    policy = build_acceptance_policy(semantic={}, coverage={}, delta={})
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "selected_architecture": SELECTED_ARCHITECTURE,
        "prompt": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "local_idea_subtype": LOCAL_IDEA_SUBTYPE,
        "local_idea_metadata": LOCAL_IDEA_METADATA,
        "canonical_idea_subtype": CANONICAL_IDEA_SUBTYPE,
        "global_idea_subtype_strategy": GLOBAL_IDEA_SUBTYPE_STRATEGY,
        "idea_local_responsibility": [
            "idea text/content",
            "SRC grounding",
            "TOPIC association",
            "importance",
            "symbolic handle",
        ],
        "idea_local_must_not_emit": [
            "claim",
            "explanation",
            "principle",
            "instruction",
            "observation",
            "question",
            "testimony",
            "example",
        ],
        "importance_vocabulary": list(IMPORTANCE_LEVELS),
        "importance_required": True,
        "empty_idea_metadata": "REJECT",
        "unknown_importance": "REJECT",
        "old_v3_idea_metadata": "REJECT_UNDER_LOCAL_LITE",
        "other_kind_metadata_unchanged": {
            "TOPIC": "m=[summary]",
            "RELATION": "m=[] ; v=type",
            "EXAMPLE": f"m=[kind] ∈ {list(EXAMPLE_KINDS)}",
            "REFERENCE": (
                f"m=[kind, completeness, normalized] ; "
                f"kind∈{list(REFERENCE_KINDS)} ; "
                f"completeness∈{list(REFERENCE_COMPLETENESS)}"
            ),
            "UNCERTAINTY": (
                f"m=[kind, severity] ; kind∈{list(UNCERTAINTY_KINDS)} ; "
                f"severity∈{list(SEVERITY_LEVELS)}"
            ),
        },
        "m_overloaded_across_kinds": True,
        "decoder_kind_specific": True,
        "example_policy": EXAMPLE_POLICY,
        "relation_types": list(RELATION_KINDS),
        "src_contract": "strict_1.3.1+",
        "symbolic_handles": {
            "TOPIC": "Tn",
            "IDEA": "In",
            "IDEA_targets": "T",
            "RELATION_targets": "I",
            "EXAMPLE_targets": "I",
        },
        "version_aware_decoding": True,
        "heuristic_version_detection": False,
        "production_activated": False,
        "semantic_acceptance_policy": policy,
        "material_omission": policy["material_omission"],
        "local_acceptance_must_not_require": [
            "identical record counts",
            "identical SRC coverage percentage",
            "identical relation count",
            "identical wording",
            "identical stochastic extraction",
        ],
    }


__all__ = ["build_local_lite_contract"]
