"""
Inspection handles V3 — diagnostic only. Aucune réparation.

Python valide, enregistre, résout. Python ne devine pas.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.handles import (
    handle_kind,
    is_idea_handle,
    is_topic_handle,
    is_valid_handle,
)
from app.source_analysis_local_v3.links import ALLOWED_TARGET_HANDLE_KINDS, NON_OWNER_KINDS
from app.source_analysis_local_v3.result import v3_transport_to_window_result
from app.source_analysis_local_v3.validator import validate_v3_transport
from app.source_analysis.window_models import WindowProviderMetadata


def _is_int_link(raw: Any) -> bool:
    return isinstance(raw, int) and not isinstance(raw, bool)


def inspect_handle_metrics(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """
    Compte owners / liens / défauts sur le payload brut.

    N'altère rien. N'invente aucune cible. Unknown != réparé.
    """
    topic_owners: list[str] = []
    idea_owners: list[str] = []
    idea_to_topic: list[str] = []
    relation_to_idea: list[str] = []
    example_to_idea: list[str] = []
    unknown_handles: list[str] = []
    wrong_kind: list[str] = []
    duplicate_owners: list[str] = []
    self_relations: list[str] = []
    malformed: list[str] = []
    numeric_links: list[Any] = []
    non_owner_invented: list[str] = []
    kinds: list[str] = []

    records = []
    if isinstance(payload, Mapping):
        raw_records = payload.get("records") or []
        if isinstance(raw_records, list):
            records = [item for item in raw_records if isinstance(item, dict)]

    seen_topic: set[str] = set()
    seen_idea: set[str] = set()
    registry_topic: set[str] = set()
    registry_idea: set[str] = set()

    for item in records:
        kind = str(item.get("k") or "")
        kinds.append(kind)
        handle = item.get("h")
        if kind == "TOPIC":
            if isinstance(handle, str) and is_topic_handle(handle):
                if handle in seen_topic:
                    duplicate_owners.append(handle)
                seen_topic.add(handle)
                topic_owners.append(handle)
                registry_topic.add(handle)
            elif handle not in (None,):
                malformed.append(f"TOPIC.h={handle!r}")
        elif kind == "IDEA":
            if isinstance(handle, str) and is_idea_handle(handle):
                if handle in seen_idea:
                    duplicate_owners.append(handle)
                seen_idea.add(handle)
                idea_owners.append(handle)
                registry_idea.add(handle)
            elif handle not in (None,):
                malformed.append(f"IDEA.h={handle!r}")
        elif kind in NON_OWNER_KINDS:
            if isinstance(handle, str) and handle != "":
                non_owner_invented.append(f"{kind}.h={handle}")

    for item in records:
        kind = str(item.get("k") or "")
        raw_links = item.get("l")
        if raw_links is None:
            raw_links = []
        if not isinstance(raw_links, list):
            malformed.append(f"{kind}.l not a list")
            continue
        parsed: list[str] = []
        for raw in raw_links:
            if _is_int_link(raw):
                numeric_links.append(raw)
                continue
            if not isinstance(raw, str):
                malformed.append(f"{kind}.l={raw!r}")
                continue
            if not is_valid_handle(raw):
                malformed.append(raw)
                continue
            target = handle_kind(raw)
            allowed = ALLOWED_TARGET_HANDLE_KINDS.get(kind)
            if allowed is not None and target not in allowed:
                wrong_kind.append(f"{kind}->{raw}")
                continue
            if target == "TOPIC" and raw not in registry_topic:
                unknown_handles.append(raw)
                continue
            if target == "IDEA" and raw not in registry_idea:
                unknown_handles.append(raw)
                continue
            parsed.append(raw)
            if kind == "IDEA" and target == "TOPIC":
                idea_to_topic.append(raw)
            elif kind == "RELATION" and target == "IDEA":
                relation_to_idea.append(raw)
            elif kind == "EXAMPLE" and target == "IDEA":
                example_to_idea.append(raw)
        if kind == "RELATION" and len(parsed) == 2 and parsed[0] == parsed[1]:
            self_relations.append(parsed[0])

    numeric_regression = bool(numeric_links)
    return {
        "topic_owner_handles": topic_owners,
        "idea_owner_handles": idea_owners,
        "idea_to_topic_links": idea_to_topic,
        "relation_to_idea_links": relation_to_idea,
        "example_to_idea_links": example_to_idea,
        "unknown_handles": unknown_handles,
        "wrong_kind_handles": wrong_kind,
        "duplicate_owners": duplicate_owners,
        "self_relations": self_relations,
        "malformed_handles": malformed,
        "non_owner_invented_handles": non_owner_invented,
        "numeric_links": numeric_links,
        "numeric_link_regression": "YES" if numeric_regression else "NO",
        "kinds": kinds,
        "counts": {
            "topic_owners": len(topic_owners),
            "idea_owners": len(idea_owners),
            "idea_to_topic": len(idea_to_topic),
            "relation_to_idea": len(relation_to_idea),
            "example_to_idea": len(example_to_idea),
            "unknown": len(unknown_handles),
            "wrong_kind": len(wrong_kind),
            "duplicate_owners": len(duplicate_owners),
            "self_relations": len(self_relations),
            "malformed": len(malformed),
        },
        "coverage": {
            "idea_to_topic": bool(idea_to_topic),
            "relation_to_idea": bool(relation_to_idea),
            "example_to_idea": bool(example_to_idea),
        },
        "python_structural_only": True,
        "repaired": False,
    }


def reconstruct_diagnostic(
    transport: Mapping[str, Any],
    window: WindowInput,
    *,
    signature: str,
) -> dict[str, Any]:
    """
    Mapping intermédiaire synthétique seulement.

    Prouve que les handles se résolvent en structures relationnelles
    canoniques locales. Ne publie PAS de SourceMap.
    """
    resolved = validate_v3_transport(transport, window)
    result = v3_transport_to_window_result(
        resolved,
        window,
        signature=signature,
        provider_metadata=WindowProviderMetadata(
            provider="anthropic",
            model="claude-sonnet-5",
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            usage_source="canary_diagnostic",
            finish_reason=None,
        ),
    )
    rows = []
    for record in result.records:
        rows.append(
            {
                "record_id": record.record_id,
                "kind": record.kind,
                "value": record.value,
                "source_refs": list(record.source_refs),
                "link_record_ids": list(record.link_record_ids),
                "owner_handle_not_in_canonical_id": not (
                    record.record_id.startswith("T") and record.record_id[1:].isdigit()
                )
                and not (
                    record.record_id.startswith("I") and record.record_id[1:].isdigit()
                ),
            }
        )
    return {
        "window_id": result.window_id,
        "canonical_ids_are_intermediate": all(
            row["record_id"].startswith(f"{window.window_id}:R") for row in rows
        ),
        "handles_not_used_as_canonical_ids": all(
            row["owner_handle_not_in_canonical_id"] for row in rows
        ),
        "record_count": len(rows),
        "records": rows,
        "source_map_published": False,
        "handle_registry": resolved.get("handle_registry"),
    }


__all__ = ["inspect_handle_metrics", "reconstruct_diagnostic"]
