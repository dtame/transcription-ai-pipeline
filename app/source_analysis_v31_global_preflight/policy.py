"""Politique de consolidation globale figée offline. Pas d'exécution."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import IDEA_KINDS
from app.source_analysis_v31_global_preflight.constants import (
    ALLOWED_DROP_REASONS,
    ALLOWED_IDEA_OPERATIONS,
    DISPOSITION_KINDS_PREFERRED,
    DISPOSITION_KINDS_REQUIRED,
    FORBIDDEN_DROP_REASONS,
    IDEA_DISPOSITION_COVERAGE_REQUIRED,
    IDEA_KIND_POLICY,
    IDEA_TEXT_REWRITE,
    IMPORTANCE_POLICY,
    MODE,
    PHASE,
    PROPOSED_RELATION_POLICY,
    RELATION_POLICY_OPTION,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_schema_boundary.analysis import downstream_consumers


def build_relation_policy(inventory: Mapping[str, Any] | None = None) -> dict[str, Any]:
    totals = (inventory or {}).get("totals") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "RELATION_QUALITY_TECHNICAL_DEBT": RELATION_QUALITY_TECHNICAL_DEBT,
        "local_relation_count": totals.get("RELATION"),
        "observed_quality": (
            "Accepted local-lite windows showed overwhelmingly/all "
            "plausible-loose relations and no demonstrated incorrect "
            "relation in accepted windows."
        ),
        "options_evaluated": {
            "A": "trust local relations as consolidation input",
            "B": "ignore local relations and reconstruct globally",
            "C": "treat local relations as non-authoritative hints",
            "D": "retain only stronger relations",
            "E": "hybrid",
        },
        "selected_option": RELATION_POLICY_OPTION,
        "selected_policy": PROPOSED_RELATION_POLICY,
        "principle": (
            "A weak local relation must not become global truth merely "
            "because it was structurally valid. Global relations must be "
            "source-grounded."
        ),
        "traceability": (
            "Every global relation must trace to supporting local ideas "
            "and/or SRC evidence. No unsupported semantic edges."
        ),
        "operationalization": {
            "pass_local_relations_to_provider": True,
            "authoritative": False,
            "must_re_ground_against_src": True,
            "copy_plausible_loose_as_global_truth": False,
            "future_review_audits_every_global_relation": True,
        },
    }


def build_consolidation_contract(
    *,
    inventory: Mapping[str, Any] | None = None,
    duplicates: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    consumers = downstream_consumers()
    requires_kind = any(
        bool((row or {}).get("consumes_idea_kind")) for row in consumers.values()
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "activated_production": False,
        "consolidator_role": "semantic consolidator / analyst",
        "forbidden_roles": [
            "book author",
            "editorial planner",
            "fact checker",
            "external researcher",
        ],
        "window_invariant": "WINDOW != CHAPTER != SECTION != EDITORIAL UNIT",
        "idea_operations": list(ALLOWED_IDEA_OPERATIONS),
        "idea_merge_rule": {
            "keyword_overlap_is_not_equivalence": True,
            "must_preserve_union_of_src": True,
            "must_not_broaden_proposition_beyond_sources": True,
            "must_not_lose_qualifiers": True,
        },
        "idea_text_rewrite": IDEA_TEXT_REWRITE,
        "idea_text_rewrite_constraint": "source-grounded semantic equivalence only",
        "no_source_loss": {
            "every_local_idea_must_have_disposition": True,
            "silent_disappearance_forbidden": True,
            "required_coverage_percent": IDEA_DISPOSITION_COVERAGE_REQUIRED,
            "dispositions": list(ALLOWED_IDEA_OPERATIONS),
        },
        "drop_policy": {
            "allowed_reasons": list(ALLOWED_DROP_REASONS),
            "forbidden_reasons": list(FORBIDDEN_DROP_REASONS),
            "generic_not_important_forbidden": True,
        },
        "importance_policy": IMPORTANCE_POLICY,
        "idea_kind_policy": IDEA_KIND_POLICY,
        "idea_kinds_vocabulary_unused_locally": list(IDEA_KINDS),
        "downstream": consumers,
        "downstream_requires_idea_kind": requires_kind,
        "idea_kind_decision_reason": (
            "Editorial Planner, Book Generator, and Book Validator are not "
            "implemented and do not consume Idea.kind. Canonical SourceMap "
            "already accepts empty kind. Do not invent a classification "
            "requirement."
        ),
        "author_intent": "global only; infer from full source representation; allow uncertainty",
        "target_audience": "global only; allow uncertainty",
        "author_voice_profile": "global; describe observable source voice; do not rewrite it",
        "repetitions": "global responsibility; cite all relevant SRC; not generated in A.34",
        "references": {
            "same_reference_repeated": "merge mentions, union SRC",
            "partial_reference": "keep as partial; completeness flag",
            "different_mentions_same_work": "link or merge if clearly the same cited object",
            "uncertain_reference": "preserve as REFERENCE or UNCERTAINTY; no external fact-check",
        },
        "uncertainties": "preserve meaningful uncertainties; never convert into fact",
        "examples": "remain examples; may associate with global ideas; never promote to unsupported claims",
        "topics": {
            "local_topics_are_window_local": True,
            "may_merge_equivalent": True,
            "may_rename_for_global_coherence": True,
            "may_create_broader_global_topic_from_several_local": True,
            "must_be_supported_by_constituent_records_and_src": True,
            "no_editorial_chapter_creation": True,
            "do_not_promote_local_topic_ids": True,
            "inventory": (duplicates or {}).get("topics"),
        },
        "disposition_maps": {
            "required": list(DISPOSITION_KINDS_REQUIRED),
            "preferred": list(DISPOSITION_KINDS_PREFERRED),
            "idea_coverage_percent": IDEA_DISPOSITION_COVERAGE_REQUIRED,
        },
        "fidelity_forbids": [
            "new arguments",
            "new examples",
            "new facts",
            "new references",
            "new opinions",
            "external knowledge",
            "editorial chapter structure",
        ],
        "global_theme": "summarize the source's actual central subject(s); not a marketing/book title",
        "canonical_ids": "deterministic postprocessing assigns TOP/IDEA/EX/REF/UNC/REP; provider handles are local",
        "ordering": "earliest supporting SRC position is primary deterministic order",
        "publication": {
            "atomic": True,
            "no_partial_publication": True,
            "failed_consolidation_must_not_overwrite_source_map": True,
        },
        "relation_policy": PROPOSED_RELATION_POLICY,
        "RELATION_QUALITY_TECHNICAL_DEBT": RELATION_QUALITY_TECHNICAL_DEBT,
        "inventory_totals": (inventory or {}).get("totals"),
    }


__all__ = ["build_consolidation_contract", "build_relation_policy"]
