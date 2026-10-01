"""Plan de revue sémantique post-appel. Aucun appel ici."""

from __future__ import annotations

from typing import Any


def semantic_review_plan() -> dict[str, Any]:
    return {
        "executed": False,
        "provider_called": False,
        "criteria": {
            "no_unsupported_global_proposition": True,
            "merge_members_genuinely_equivalent": True,
            "merge_v_faithful": True,
            "no_substantive_idea_dropped": True,
            "uncertainty_preserved": True,
            "metadata_source_supported": True,
            "no_editorial_chapter_section_structure": True,
        },
        "merge_review": {
            "scope": "every synthesized multi-member global IDEA",
            "expected_set_size": "small",
            "fields": (
                "global_handle",
                "member_local_ids",
                "member_local_texts",
                "provider_v",
                "equivalence_judgment",
                "fidelity_judgment",
                "unsupported_content",
            ),
            "reuse_excluded": True,
            "note": "Only merges generate new IDEA text.",
        },
        "reuse_review": {
            "provider_text_comparison": False,
            "verify": (
                "membership",
                "local_text_identity",
                "source_traceability",
            ),
        },
        "drop_review": {
            "every_drop_explicit": True,
            "silent_drops_forbidden": True,
            "allowed_reasons": ("transport_artifact", "non_substantive_fragment"),
            "substantive_drop_fails_review": True,
        },
        "global_metadata_review": {
            "fields": ("theme", "intent", "audience", "voice"),
            "must_be_source_supported": True,
            "no_marketing_titles": True,
        },
        "topic_review": {
            "separate_from_idea_reuse": True,
            "provider_created_labels": True,
            "must_not_invent_structure": True,
        },
        "relations": "DEFERRED — not scored as IDEA accountability",
        "repetitions": "DEFERRED",
        "publication_requires_accepted_review": True,
    }


__all__ = ["semantic_review_plan"]
