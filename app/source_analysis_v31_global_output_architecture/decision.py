"""Décisions d'architecture A.39. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_global_output_architecture.constants import (
    DERIVED_SRC_UNION,
    DROP_REASONS_V20,
    EXACT_DUPLICATE_POLICY,
    INVERSE_IDEA_MEMBERSHIP,
    NEXT_MAX_OUTPUT_TOKENS,
    NEXT_PROMPT_VERSION,
    NEXT_TRANSPORT_VERSION,
    OTHER_DISPOSITION,
    PROVIDER_EMITTED_DISPOSITION_LEDGER,
    RELATION_POLICY,
    REPETITION_POLICY,
    SELECTED_ARCHITECTURE,
    SELECTED_OPTION,
    TEXT_LIMITS,
)


def membership_contract() -> dict[str, Any]:
    return {
        "model": "INVERSE_MEMBERSHIP",
        "provider_emits_disposition_ledger": PROVIDER_EMITTED_DISPOSITION_LEDGER,
        "inverse_idea_membership": INVERSE_IDEA_MEMBERSHIP,
        "keep": "global idea with exactly one local member → deterministic KEEP",
        "merge": (
            "global idea with two or more equivalent local members → "
            "deterministic MERGE_EQUIVALENT"
        ),
        "drop": (
            "explicit drop[] of local IDEA id + exact reason "
            f"{list(DROP_REASONS_V20)}"
        ),
        "coverage": (
            "all local IDEA IDs = union(global idea members) ∪ union(drop ids)"
        ),
        "duplicate_membership": "FAIL",
        "unknown_member": "FAIL",
        "missing_member": "SILENT_DROP FAIL",
        "derived_src_union": DERIVED_SRC_UNION,
        "merge_source_union": "union(SRC(local members)) ⊆ SRC(global idea) via derivation",
        "exact_duplicate_policy": EXACT_DUPLICATE_POLICY,
        "other_disposition": OTHER_DISPOSITION,
        "semantic_benefit": (
            "Provider states which local propositions compose each global "
            "proposition instead of emitting a second redundant d[] ledger."
        ),
    }


def relation_decision() -> dict[str, Any]:
    return {
        "policy": RELATION_POLICY,
        "options_considered": [
            "RELATIONS_IN_PRIMARY_GLOBAL_CALL",
            "RELATIONS_SECOND_STAGE",
            "RELATIONS_DEFERRED",
        ],
        "source_map_requires_global_relations": False,
        "evidence": [
            "Canonical Idea.relations defaults to empty and validates if empty.",
            "SourceMap has no mandatory top-level relations collection.",
            "A.38 never reached r[].",
            "RELATION_QUALITY_TECHNICAL_DEBT = YES.",
            "Local 127 relations remain non-authoritative hints.",
        ],
        "why_deferred": (
            "A valid Phase 3 SourceMap can exist without new global relations. "
            "Deferring avoids spending output budget on a known weak contract."
        ),
        "not_cleared": True,
    }


def repetition_decision() -> dict[str, Any]:
    return {
        "policy": REPETITION_POLICY,
        "primary": False,
        "derived": False,
        "later_enrichment": True,
        "optional": True,
        "why": (
            "Local-lite deferred repetition. A.38 emitted 0 REPETITION keys. "
            "Genuine restatement can later be recovered from multi-member "
            "ideas plus distinct SRC positions."
        ),
    }


def selected_architecture(estimate: Mapping[str, Any]) -> dict[str, Any]:
    hard = int((estimate.get("provider_planning_tokens") or {}).get("hard") or 0)
    expected = int((estimate.get("provider_planning_tokens") or {}).get("expected") or 0)
    return {
        "selected": SELECTED_ARCHITECTURE,
        "option": SELECTED_OPTION,
        "provider_emitted_disposition_ledger": PROVIDER_EMITTED_DISPOSITION_LEDGER,
        "inverse_idea_membership": INVERSE_IDEA_MEMBERSHIP,
        "derived_src_union": DERIVED_SRC_UNION,
        "relation_policy": RELATION_POLICY,
        "repetition_policy": REPETITION_POLICY,
        "other_disposition": OTHER_DISPOSITION,
        "exact_duplicate_policy": EXACT_DUPLICATE_POLICY,
        "next_prompt": NEXT_PROMPT_VERSION,
        "next_transport": NEXT_TRANSPORT_VERSION,
        "next_max_output": NEXT_MAX_OUTPUT_TOKENS,
        "why_48000": (
            "All-distinct 286 with semantically adequate text limits cannot "
            "sit safely under 75% of 32000 at A.38 token density. 48000 is "
            "an explicit bound for the compact contract, not a 1.1 retry."
        ),
        "text_limits": dict(TEXT_LIMITS),
        "expected_output_tokens": expected,
        "hard_output_tokens": hard,
        "separable_responsibilities": {
            "A_global_semantic_reconstruction": "PRIMARY_CALL",
            "B_exhaustive_disposition_ledger": "DERIVED_FROM_MEMBERSHIP",
            "C_global_relation_reconstruction": "DEFERRED",
            "D_global_metadata": "PRIMARY_CALL_LOW_VOLUME",
        },
        "one_provider_output_was_doing_too_much": True,
        "canonical_source_map_remains_rich": True,
        "provider_transport_is_not_domain_model": True,
    }


__all__ = [
    "membership_contract",
    "relation_decision",
    "repetition_decision",
    "selected_architecture",
]
