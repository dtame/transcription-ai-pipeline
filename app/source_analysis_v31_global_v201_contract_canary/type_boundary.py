"""Audit de frontière de types IDEA-only. 0 réparation. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_global_v201_contract_canary.constants import (
    RELATION_HINT_ID,
)

NON_IDEA_KINDS = ("TOPIC", "RELATION", "EXAMPLE", "REFERENCE", "UNCERTAINTY")


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if isinstance(item, str) and item]


def _collect_members(transport: Mapping[str, Any] | None) -> list[str]:
    members: list[str] = []
    if not isinstance(transport, Mapping):
        return members
    for idea in _as_list(transport.get("i")):
        if isinstance(idea, Mapping):
            members.extend(_strings(idea.get("m")))
    return members


def _collect_drops(transport: Mapping[str, Any] | None) -> list[str]:
    dropped: list[str] = []
    if not isinstance(transport, Mapping):
        return dropped
    for row in _as_list(transport.get("drop")):
        if isinstance(row, Mapping):
            local_id = str(row.get("i") or "")
            if local_id:
                dropped.append(local_id)
    return dropped


def type_boundary_audit(
    transport: Mapping[str, Any] | None,
    *,
    kind_by_input: Mapping[str, str],
    relation_hint_id: str = RELATION_HINT_ID,
) -> dict[str, Any]:
    members = _collect_members(transport)
    dropped = _collect_drops(transport)
    non_idea_members = [
        item for item in members if kind_by_input.get(item) not in {None, "IDEA"}
    ]
    non_idea_drops = [
        item for item in dropped if kind_by_input.get(item) not in {None, "IDEA"}
    ]
    relation_in_members = relation_hint_id in members
    relation_in_drop = relation_hint_id in dropped

    def _kind_violations(kind: str) -> list[str]:
        hits = []
        for item in members:
            if kind_by_input.get(item) == kind:
                hits.append(f"member:{item}")
        for item in dropped:
            if kind_by_input.get(item) == kind:
                hits.append(f"drop:{item}")
        return hits

    topic_hits = _kind_violations("TOPIC")
    example_hits = _kind_violations("EXAMPLE")
    reference_hits = _kind_violations("REFERENCE")
    uncertainty_hits = _kind_violations("UNCERTAINTY")
    relation_hits = _kind_violations("RELATION")
    ok = (
        not non_idea_members
        and not non_idea_drops
        and not relation_in_members
        and not relation_in_drop
        and not topic_hits
        and not example_hits
        and not reference_hits
        and not uncertainty_hits
    )
    return {
        "relation_hint_id": relation_hint_id,
        "members": members,
        "drops": dropped,
        "NON_IDEA_IN_MEMBERS": len(non_idea_members),
        "NON_IDEA_IN_DROP": len(non_idea_drops),
        "non_idea_members": non_idea_members,
        "non_idea_drops": non_idea_drops,
        "RELATION_HINT_IN_MEMBERS": "YES" if relation_in_members else "NO",
        "RELATION_HINT_IN_DROP": "YES" if relation_in_drop else "NO",
        "TOPIC_IDEA_DOMAIN_VIOLATIONS": len(topic_hits),
        "EXAMPLE_IDEA_DOMAIN_VIOLATIONS": len(example_hits),
        "REFERENCE_IDEA_DOMAIN_VIOLATIONS": len(reference_hits),
        "UNCERTAINTY_IDEA_DOMAIN_VIOLATIONS": len(uncertainty_hits),
        "RELATION_IDEA_DOMAIN_VIOLATIONS": len(relation_hits),
        "topic_hits": topic_hits,
        "example_hits": example_hits,
        "reference_hits": reference_hits,
        "uncertainty_hits": uncertainty_hits,
        "relation_hits": relation_hits,
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
    }


def classify_a40_root_defect(boundary: Mapping[str, Any]) -> str:
    if (
        boundary.get("RELATION_HINT_IN_DROP") == "YES"
        or int(boundary.get("NON_IDEA_IN_DROP") or 0) > 0
    ):
        return "PERSISTS"
    if boundary.get("RELATION_HINT_IN_MEMBERS") == "YES":
        return "OTHER"
    if boundary.get("ok") is True:
        return "ELIMINATED_BY_PROMPT_2_0_1"
    return "OTHER"


__all__ = [
    "NON_IDEA_KINDS",
    "classify_a40_root_defect",
    "type_boundary_audit",
]
