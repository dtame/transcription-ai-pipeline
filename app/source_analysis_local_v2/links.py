"""
Contrat local de liens semantic-transport-v2.

Hérité de semantic-transport-v1 / canonical_vocabulary / hybrid_reconstructor.
Ne mute pas v1. Le schéma provider ne peut pas exprimer ces règles de graphe :
validité schéma ≠ validité sémantique.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

INDEX_BASE = 0
SELF_LINKS = "FORBIDDEN"
FORWARD_LINKS = "ALLOWED"
BACKWARD_LINKS = "ALLOWED"
CYCLES_ACROSS_DISTINCT_RECORDS = "ALLOWED"
DUPLICATE_INDEXES_IN_ONE_L = "FORBIDDEN"
PROVIDER_CONTROLS_CANONICAL_IDS = False
RECORD_INDEXES_ARE_INTERMEDIATE_ONLY = True
RECOMMENDED_KIND_ORDER = (
    "TOPIC",
    "IDEA",
    "RELATION",
    "EXAMPLE",
    "REFERENCE",
    "UNCERTAINTY",
)
KIND_ORDER_REQUIRED = False

# source_kind -> allowed target kinds. Empty frozenset = l must be empty.
ALLOWED_TARGET_KINDS: dict[str, frozenset[str]] = {
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
    "l": (
        "0-based TARGET transport record indexes in THIS transport. "
        "Never the current record index. Never a canonical ID. "
        "Provider does not control canonical IDs."
    ),
    "m": "kind-specific metadata tokens / free text slots",
}


def link_contract() -> dict[str, Any]:
    return {
        "transport": "semantic-transport-v2",
        "index_base": INDEX_BASE,
        "l_meaning": FIELD_MEANINGS["l"],
        "fields": dict(FIELD_MEANINGS),
        "self_links": SELF_LINKS,
        "forward_links": FORWARD_LINKS,
        "backward_links": BACKWARD_LINKS,
        "cycles_across_distinct_records": CYCLES_ACROSS_DISTINCT_RECORDS,
        "duplicate_indexes": DUPLICATE_INDEXES_IN_ONE_L,
        "provider_controls_canonical_ids": PROVIDER_CONTROLS_CANONICAL_IDS,
        "record_indexes_intermediate_only": RECORD_INDEXES_ARE_INTERMEDIATE_ONLY,
        "kind_order_required": KIND_ORDER_REQUIRED,
        "recommended_kind_order": list(RECOMMENDED_KIND_ORDER),
        "allowed_target_kinds": {
            kind: sorted(targets) for kind, targets in ALLOWED_TARGET_KINDS.items()
        },
        "cardinality": LINK_CARDINALITY,
        "canonical_mapping": dict(CANONICAL_MAPPING),
        "idea_l_retained": True,
        "idea_l_reason": (
            "IDEA.l is topic membership (topic_refs). RELATION is IDEA→IDEA. "
            "Different canonical purposes; IDEA.l is not redundant."
        ),
        "example_l_retained": True,
        "example_l_reason": (
            "EXAMPLE.l associates the illustration with local IDEA records "
            "(supports_idea_refs)."
        ),
        "reference_l_empty": True,
        "uncertainty_l_empty": True,
        "topic_l_empty": True,
        "relation_arity": 2,
        "relation_type_field": "v",
        "v1_inherited": True,
        "v1_unchanged": True,
        "schema_cannot_express_graph_rules": True,
    }


def validate_v2_link_semantics(
    records: Sequence[Mapping[str, Any]],
    errors: list[str],
) -> None:
    """
    Règles V2 supplémentaires. Ne remplace pas _validate_links v1.

    Auto-lien explicite + doublons. Hors-plage / kind cible restent v1.
    """
    bound = len(records)
    for position, record in enumerate(records):
        kind = str(record.get("k") or "")
        context = f"records[{position}]"
        raw_links = record.get("l") or []
        if not isinstance(raw_links, Sequence) or isinstance(raw_links, (str, bytes)):
            continue
        links = [int(link) for link in raw_links if isinstance(link, int) and not isinstance(link, bool)]
        seen: set[int] = set()
        for link in links:
            if link == position:
                errors.append(
                    f"{context} : auto-lien interdit "
                    f"(l pointe vers le record courant index {link})"
                )
            if link in seen:
                errors.append(f"{context} : lien dupliqué {link}")
            seen.add(link)
        card = LINK_CARDINALITY.get(kind)
        if card is not None:
            maximum = card["max"]
            if maximum == 0 and links:
                # déjà couvert par v1 _NO_LINKS ; message V2 explicite si absent
                pass
            if card["empty"] == "forbidden" and not links:
                errors.append(f"{context} : {kind} exige des liens")
            if maximum is not None and maximum > 0 and len(links) > maximum:
                errors.append(
                    f"{context} : {kind} accepte au plus {maximum} lien(s)"
                )
        allowed = ALLOWED_TARGET_KINDS.get(kind)
        if allowed is not None and not allowed and links:
            pass
        if 0 <= position < bound:
            for link in links:
                if link < 0 or link >= bound:
                    continue
                target_kind = str(records[link].get("k") or "")
                if allowed is not None and allowed and target_kind not in allowed:
                    # v1 émet déjà le message kind ; pas de doublon ici
                    pass


__all__ = [
    "ALLOWED_TARGET_KINDS",
    "CANONICAL_MAPPING",
    "FIELD_MEANINGS",
    "INDEX_BASE",
    "LINK_CARDINALITY",
    "SELF_LINKS",
    "link_contract",
    "validate_v2_link_semantics",
]
