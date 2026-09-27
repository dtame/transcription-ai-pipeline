"""
Contrat local de liens semantic-transport-v3.

Handles kind-local. Pas d'index numériques globaux.
Ne mute pas v1 / v2.
"""

from __future__ import annotations

from typing import Any

from app.source_analysis_local_v3.constants import SEMANTIC_TRANSPORT_VERSION_V3

HANDLE_INDEX_BASE = 1
SELF_LINKS = "FORBIDDEN"
FORWARD_LINKS = "ALLOWED"
BACKWARD_LINKS = "ALLOWED"
CYCLES_ACROSS_DISTINCT_IDEAS = "ALLOWED"
DUPLICATE_HANDLES_IN_ONE_L = "FORBIDDEN"
GAP_FREE_NUMBERING = "RECOMMENDED_NOT_REQUIRED"
PROVIDER_CONTROLS_CANONICAL_IDS = False
HANDLES_ARE_INTERMEDIATE_ONLY = True
KIND_ORDER_REQUIRED = False
RECOMMENDED_KIND_ORDER = (
    "TOPIC",
    "IDEA",
    "RELATION",
    "EXAMPLE",
    "REFERENCE",
    "UNCERTAINTY",
)

OWNER_HANDLE_KINDS = {
    "TOPIC": "T",
    "IDEA": "I",
}
NON_OWNER_KINDS = frozenset(
    {"RELATION", "EXAMPLE", "REFERENCE", "UNCERTAINTY"}
)

ALLOWED_TARGET_HANDLE_KINDS: dict[str, frozenset[str]] = {
    "TOPIC": frozenset(),
    "IDEA": frozenset({"TOPIC"}),
    "RELATION": frozenset({"IDEA"}),
    "EXAMPLE": frozenset({"IDEA"}),
    "REFERENCE": frozenset(),
    "UNCERTAINTY": frozenset(),
}

LINK_CARDINALITY = {
    "TOPIC": {"min": 0, "max": 0, "empty": "required"},
    "IDEA": {"min": 0, "max": None, "empty": "allowed"},
    "RELATION": {"min": 2, "max": 2, "empty": "forbidden"},
    "EXAMPLE": {"min": 0, "max": None, "empty": "allowed"},
    "REFERENCE": {"min": 0, "max": 0, "empty": "required"},
    "UNCERTAINTY": {"min": 0, "max": 0, "empty": "required"},
}

CANONICAL_MAPPING = {
    "TOPIC.l": None,
    "IDEA.l": "topic_refs",
    "RELATION.l": "idea relations [from, to]; type in v",
    "EXAMPLE.l": "supports_idea_refs",
    "REFERENCE.l": None,
    "UNCERTAINTY.l": None,
}

FIELD_MEANINGS = {
    "k": "record kind (local semantic kind token)",
    "v": "primary semantic value (label / summary / type / raw / description)",
    "s": "sparse SRC refs owned by this window; not links",
    "h": (
        "kind-local owner handle for THIS record. "
        "TOPIC owns Tn. IDEA owns In. Other kinds emit empty h. "
        "Temporary, provider-produced, non-canonical. Not a SRC/TOP/IDEA/DB id."
    ),
    "l": (
        "symbolic target handles in THIS transport. "
        "IDEA → Tn. RELATION → exactly two distinct In. EXAMPLE → In. "
        "Never a global numeric record index. Never a canonical ID."
    ),
    "m": "kind-specific metadata tokens / free text slots",
}


def link_contract() -> dict[str, Any]:
    return {
        "transport": SEMANTIC_TRANSPORT_VERSION_V3,
        "index_base": HANDLE_INDEX_BASE,
        "handle_form": "kind-local symbolic labels",
        "not_numeric_global_indexes": True,
        "not_i37_alias_of_37": True,
        "h_meaning": FIELD_MEANINGS["h"],
        "l_meaning": FIELD_MEANINGS["l"],
        "m_not_used_for_handles": True,
        "m_reason": (
            "m retains kind-specific metadata (summary / kind / importance). "
            "Ownership is a new wire concept and is represented by h."
        ),
        "fields": dict(FIELD_MEANINGS),
        "self_links": SELF_LINKS,
        "forward_links": FORWARD_LINKS,
        "backward_links": BACKWARD_LINKS,
        "cycles_across_distinct_ideas": CYCLES_ACROSS_DISTINCT_IDEAS,
        "duplicate_handles": DUPLICATE_HANDLES_IN_ONE_L,
        "gap_free_numbering": GAP_FREE_NUMBERING,
        "gap_free_reason": (
            "Uniqueness and correct type matter more than sequential gaps. "
            "T1,T3 is valid. Exact sequentiality is recommended, not required."
        ),
        "provider_controls_canonical_ids": PROVIDER_CONTROLS_CANONICAL_IDS,
        "handles_intermediate_only": HANDLES_ARE_INTERMEDIATE_ONLY,
        "kind_order_required": KIND_ORDER_REQUIRED,
        "recommended_kind_order": list(RECOMMENDED_KIND_ORDER),
        "owner_handle_kinds": dict(OWNER_HANDLE_KINDS),
        "non_owner_kinds": sorted(NON_OWNER_KINDS),
        "allowed_target_handle_kinds": {
            kind: sorted(targets)
            for kind, targets in ALLOWED_TARGET_HANDLE_KINDS.items()
        },
        "cardinality": LINK_CARDINALITY,
        "canonical_mapping": dict(CANONICAL_MAPPING),
        "resolution_after_complete_parse": True,
        "forward_references_allowed": True,
        "no_semantic_guessing": True,
        "no_fuzzy_repair": True,
        "schema_cannot_express_graph_rules": True,
        "v2_unchanged": True,
    }


__all__ = [
    "ALLOWED_TARGET_HANDLE_KINDS",
    "CANONICAL_MAPPING",
    "FIELD_MEANINGS",
    "HANDLE_INDEX_BASE",
    "LINK_CARDINALITY",
    "NON_OWNER_KINDS",
    "OWNER_HANDLE_KINDS",
    "link_contract",
]
