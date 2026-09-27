"""Cartographie canonique IDEA.kind après local-lite. Offline."""

from __future__ import annotations

from typing import Any

from app.source_analysis.models import IDEA_KINDS, IMPORTANCE_LEVELS, SOURCE_MAP_SCHEMA_VERSION
from app.source_analysis_v31_local_lite.constants import (
    CANONICAL_IDEA_SUBTYPE,
    GLOBAL_IDEA_SUBTYPE_STRATEGY,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)


def build_canonical_mapping() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "source_map_schema_version": SOURCE_MAP_SCHEMA_VERSION,
        "field_name": "kind",
        "required": False,
        "optional": True,
        "allowed_values": list(IDEA_KINDS),
        "absence_representation": "empty string",
        "default_behavior": (
            "Local-lite reconstruction leaves kind empty. "
            "Historical V3 reconstruction still copies local m[0] kind."
        ),
        "serialization_behavior": (
            "Idea.to_dict includes kind even when empty so absence is explicit."
        ),
        "validation_behavior": (
            "Empty kind is accepted. A non-empty kind must belong to IDEA_KINDS. "
            "Invalid tokens still fail closed. Validation is not weakened for "
            "present values."
        ),
        "importance_field": "importance",
        "importance_required": True,
        "importance_values": list(IMPORTANCE_LEVELS),
        "importance_is_not_kind": True,
        "no_overlap_kind_vs_importance": not set(IDEA_KINDS) & set(IMPORTANCE_LEVELS),
        "reconstructor_v3": "copies local m[0] as kind, m[1] as importance",
        "reconstructor_local_lite": (
            "reads m[0] as importance only; sets kind='' ; "
            "refuses arity≠1 and refuses IDEA_KINDS tokens in m[0]"
        ),
        "critical_regression": (
            "local IDEA m=['central'] cannot become canonical kind='central'"
        ),
        "consolidator": (
            "MERGE-same-kind is record.kind (IDEA vs TOPIC), not IDEA subtype. "
            "Local merge identity does not use semantic subtype. "
            "Two distinct ideas do not merge merely because both lack subtype."
        ),
        "canonical_strategy": GLOBAL_IDEA_SUBTYPE_STRATEGY,
        "canonical_idea_subtype": CANONICAL_IDEA_SUBTYPE,
        "why_not_classify_globally": (
            "Canonical field is optional. Editorial Planner and Book Generator "
            "do not consume it. Do not invent a fallback category. "
            "Do not add an LLM classification task solely because the old "
            "reconstructor expected a value."
        ),
        "publication": (
            "source_map may serialize kind as empty. Publication remains "
            "NOT PUBLISHED in this phase."
        ),
        "production_llm_schema": (
            "app/source_analysis/schema.py still requires ideas[].kind ∈ "
            "IDEA_KINDS and does not admit empty string. Unchanged this "
            "phase. Empty kind is a reconstructed-map / Python-validator "
            "allowance, not a production LLM schema activation."
        ),
    }


__all__ = ["build_canonical_mapping"]
