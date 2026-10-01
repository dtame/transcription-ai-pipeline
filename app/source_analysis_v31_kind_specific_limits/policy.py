"""Politique kind-specific A.30. Plafonds nommés. Pas de plafond universel."""

from __future__ import annotations

from typing import Any

from app.source_analysis_local_v2.constants import (
    GRANULARITY_POLICY_VERSION,
    GRANULARITY_POLICY_VERSION_12_KIND_SPECIFIC,
)
from app.source_analysis_local_v2.granularity import (
    AUD_TEXT_HARD_LIMIT,
    EXAMPLE_V_TEXT_HARD_LIMIT,
    IDEA_V_TEXT_HARD_LIMIT,
    INTENT_TEXT_HARD_LIMIT,
    METADATA_ITEM_TEXT_HARD_LIMIT,
    REFERENCE_V_TEXT_HARD_LIMIT,
    RELATION_V_TEXT_HARD_LIMIT,
    TEXT_HARD_LIMITS,
    THEME_TEXT_HARD_LIMIT,
    TOPIC_M0_TEXT_HARD_LIMIT,
    TOPIC_V_TEXT_HARD_LIMIT,
    UNCERTAINTY_V_TEXT_HARD_LIMIT,
    V11_MINIMAL_TEXT_HARD_LIMITS,
    granularity_policy,
)
from app.source_analysis.window_granularity import (
    POLICY_VERSION as V10_POLICY_VERSION,
    TEXT_HARD_LIMITS as V10_TEXT_HARD_LIMITS,
)
from app.source_analysis_v31_kind_specific_limits.constants import (
    MODE,
    PHASE,
    SCHEMA_VERSION,
    SELECTED_POLICY,
    SIGNATURE_DECISION,
    SIGNATURE_INCLUDES_GRANULARITY_POLICY,
)


def approved_limits() -> dict[str, int]:
    return {
        "theme": THEME_TEXT_HARD_LIMIT,
        "TOPIC.v": TOPIC_V_TEXT_HARD_LIMIT,
        "IDEA.v": IDEA_V_TEXT_HARD_LIMIT,
        "RELATION.v": RELATION_V_TEXT_HARD_LIMIT,
        "EXAMPLE.v": EXAMPLE_V_TEXT_HARD_LIMIT,
        "REFERENCE.v": REFERENCE_V_TEXT_HARD_LIMIT,
        "UNCERTAINTY.v": UNCERTAINTY_V_TEXT_HARD_LIMIT,
        "intent": INTENT_TEXT_HARD_LIMIT,
        "aud": AUD_TEXT_HARD_LIMIT,
        "TOPIC.m0": TOPIC_M0_TEXT_HARD_LIMIT,
        "metadata_item": METADATA_ITEM_TEXT_HARD_LIMIT,
    }


def build_policy() -> dict[str, Any]:
    approved = approved_limits()
    live = dict(TEXT_HARD_LIMITS)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "selected_policy": SELECTED_POLICY,
        "universal_ceiling": False,
        "max_value_length_universal": None,
        "character_semantics": "python_len_str_unicode_code_points",
        "truncation": False,
        "compression": False,
        "repair": False,
        "current_policy_version": GRANULARITY_POLICY_VERSION_12_KIND_SPECIFIC,
        "historical_1_1_minimal_version": GRANULARITY_POLICY_VERSION,
        "historical_1_0_version": V10_POLICY_VERSION,
        "historical_1_0_theme": V10_TEXT_HARD_LIMITS["theme"],
        "historical_1_0_example": V10_TEXT_HARD_LIMITS["EXAMPLE.v"],
        "historical_1_1_minimal_limits": dict(V11_MINIMAL_TEXT_HARD_LIMITS),
        "approved_limits": approved,
        "live_text_hard_limits": live,
        "matches_approved": live == {**live, **approved},
        "changed_fields": {
            "theme": {
                "old": V11_MINIMAL_TEXT_HARD_LIMITS["theme"],
                "new": THEME_TEXT_HARD_LIMIT,
            },
            "EXAMPLE.v": {
                "old": V11_MINIMAL_TEXT_HARD_LIMITS["EXAMPLE.v"],
                "new": EXAMPLE_V_TEXT_HARD_LIMIT,
            },
        },
        "unchanged_fields": {
            key: live[key]
            for key in live
            if key not in {"theme", "EXAMPLE.v"}
        },
        "theme_is_not_a_record_kind": True,
        "theme_has_explicit_limit": True,
        "provider_maxlength": False,
        "transport_grammar_constraint": False,
        "canonical_sourcemap_constraint": False,
        "local_semantic_validator_policy": True,
        "granularity_policy": granularity_policy(),
        "signature": {
            "granularity_policy_in_window_signature_inputs": (
                SIGNATURE_INCLUDES_GRANULARITY_POLICY
            ),
            "decision": SIGNATURE_DECISION,
            "reason": (
                "WindowSignatureInputs hashes window input, prompt, transport, "
                "schema, provider, model, thinking — not validator text limits. "
                "A.30 reuses the A.28 WIN003 analysis signature."
            ),
        },
        "historical_reproducibility": {
            "under_a28_policy": "WIN003 FAIL (theme 212>200, EXAMPLE 213>200)",
            "under_a30_policy": "same saved response can PASS",
            "a28_status_unchanged": "FAIL",
        },
    }


__all__ = ["approved_limits", "build_policy"]
