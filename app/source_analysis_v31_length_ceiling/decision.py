"""Décision architecturale unique A.29. N'implémente pas le changement."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_length_ceiling.constants import (
    A18_PROOF_STILL_APPLIES,
    FAILURE_CLASS,
    MODE,
    PHASE,
    PROMPT_CHANGE_REQUIRED,
    PROPOSED_EXAMPLE_LIMIT,
    PROPOSED_IDEA_LIMIT,
    PROPOSED_THEME_LIMIT,
    SCHEMA_IDENTITY_CHANGES,
    SCHEMA_VERSION,
    SELECTED_POLICY,
    TRANSPORT_VERSION_CHANGE_REQUIRED,
    WIN003_FUTURE_ACTION,
    WIN005_007_SAFE_AFTER_FIX,
)


def build_decision(
    *,
    options: Mapping[str, Any],
    counterfactual: Mapping[str, Any],
    classification: Mapping[str, Any],
    semantic: Mapping[str, Any] | None,
    distribution: Mapping[str, Any],
) -> dict[str, Any]:
    quality = None
    if isinstance(semantic, Mapping):
        quality = semantic.get("semantic_quality")
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "selected_policy": SELECTED_POLICY,
        "exactly_one": True,
        "not_selected": [
            "KEEP_200_HARD",
            "RAISE_UNIVERSAL_LIMIT",
            "SEPARATE_TRANSPORT_AND_SEMANTIC_LIMITS",
            "OTHER_EXPLICITLY_JUSTIFIED",
        ],
        "minimum_change": True,
        "production_mutated": False,
        "proposed_limits": {
            "theme": PROPOSED_THEME_LIMIT,
            "EXAMPLE.v": PROPOSED_EXAMPLE_LIMIT,
            "IDEA.v": PROPOSED_IDEA_LIMIT,
            "TOPIC.v": 80,
            "RELATION.v": 40,
            "REFERENCE.v": 220,
            "UNCERTAINTY.v": 280,
            "intent": 280,
            "aud": 280,
            "TOPIC.m0": 200,
            "metadata_item": 64,
        },
        "why_225_not_250_or_300": (
            "225 is the smallest evaluated candidate that clears theme 212 "
            "and EXAMPLE 213. 250/300 add slack without additional evidence."
        ),
        "why_not_theme_280": (
            "intent/aud are already 280, so theme could match them, but "
            "minimum-change prefers 225 until more windows exceed 225."
        ),
        "prompt_change_required": PROMPT_CHANGE_REQUIRED,
        "prompt_note": (
            "window-analysis-1.4.0 never stated theme/EXAMPLE 200. It can "
            "remain immutable. A future 1.4.1 listing all kind-specific "
            "limits would be hygiene, not a blocker."
        ),
        "transport_version_change_required": TRANSPORT_VERSION_CHANGE_REQUIRED,
        "transport_note": (
            "semantic-transport-v3.1-local-lite has no maxLength. Length "
            "policy lives in window-granularity-1.1-minimal. A future "
            "granularity 1.2 can raise theme/EXAMPLE without a new transport."
        ),
        "schema_identity_changes": SCHEMA_IDENTITY_CHANGES,
        "a18_grammar_proof_still_applies": A18_PROOF_STILL_APPLIES,
        "win003_future_action": WIN003_FUTURE_ACTION,
        "win003_not_ready": True,
        "a28_status_unchanged": "FAIL",
        "win005_007_safe_to_resume_after_fix": WIN005_007_SAFE_AFTER_FIX,
        "win005_007_authorized_now": False,
        "failure_class": FAILURE_CLASS,
        "option_c_selected": options["options"]["C"]["verdict"] == "SELECT",
        "counterfactual_225": counterfactual.get("counterfactual_225"),
        "offending_quality": {
            "theme": classification["theme"]["grounding"],
            "idea": classification["idea"]["grounding"],
            "example": classification["example"]["grounding"],
        },
        "counterfactual_semantic_quality": quality,
        "ready_distribution_maxima": {
            field: (distribution.get("ready_only") or {}).get(field, {}).get("maximum")
            for field in (
                "theme",
                "TOPIC.v",
                "IDEA.v",
                "RELATION.v",
                "EXAMPLE.v",
                "REFERENCE.v",
                "UNCERTAINTY.v",
            )
        },
        "next_action": "HUMAN REVIEW",
    }


__all__ = ["build_decision"]
