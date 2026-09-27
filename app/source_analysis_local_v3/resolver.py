"""
Résolveur déterministe des handles symboliques v3.

transport → registre → unicité/types → résolution → index internes.
Python ne décide aucune relation sémantique. Aucune réparation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from app.source_analysis.errors import WindowTransportValidationError
from app.source_analysis_local_v3.handles import handle_kind, parse_link_handle
from app.source_analysis_local_v3.links import ALLOWED_TARGET_HANDLE_KINDS, LINK_CARDINALITY


@dataclass
class HandleRegistry:
    topic: dict[str, int] = field(default_factory=dict)
    idea: dict[str, int] = field(default_factory=dict)

    def get(self, handle: str) -> int | None:
        kind = handle_kind(handle)
        if kind == "TOPIC":
            return self.topic.get(handle)
        if kind == "IDEA":
            return self.idea.get(handle)
        return None

    def defined(self, handle: str) -> bool:
        return self.get(handle) is not None

    def to_dict(self) -> dict[str, dict[str, int]]:
        return {"TOPIC": dict(self.topic), "IDEA": dict(self.idea)}


def build_handle_registry(
    records: Sequence[Mapping[str, Any]],
    errors: list[str],
) -> HandleRegistry:
    registry = HandleRegistry()
    for position, record in enumerate(records):
        kind = str(record.get("k") or "")
        handle = record.get("h")
        if kind == "TOPIC" and isinstance(handle, str) and handle:
            if handle in registry.topic:
                errors.append(
                    f"records[{position}] : handle owner dupliqué « {handle} »"
                )
                continue
            registry.topic[handle] = position
        elif kind == "IDEA" and isinstance(handle, str) and handle:
            if handle in registry.idea:
                errors.append(
                    f"records[{position}] : handle owner dupliqué « {handle} »"
                )
                continue
            registry.idea[handle] = position
    return registry


def resolve_symbolic_links(
    records: Sequence[Mapping[str, Any]],
    registry: HandleRegistry,
    errors: list[str],
) -> list[dict[str, Any]]:
    """
    Résout l[] symbolique → index de record internes (Python only).

    Ne devine jamais la cible. Ne convertit jamais T3 en I3.
    Les références avant déclaration sont autorisées.
    """
    resolved: list[dict[str, Any]] = []
    for position, record in enumerate(records):
        kind = str(record.get("k") or "")
        context = f"records[{position}]"
        raw_links = record.get("l") or []
        handles: list[str] = []
        if not isinstance(raw_links, Sequence) or isinstance(raw_links, (str, bytes)):
            errors.append(f"{context}.l : une liste de handles est attendue")
            raw_links = []
        seen: set[str] = set()
        for index, raw in enumerate(raw_links):
            handle, err = parse_link_handle(raw)
            if err:
                errors.append(f"{context}.l[{index}] : {err}")
                continue
            assert handle is not None
            if handle in seen:
                errors.append(f"{context} : handle cible dupliqué {handle}")
            seen.add(handle)
            target_kind = handle_kind(handle)
            allowed = ALLOWED_TARGET_HANDLE_KINDS.get(kind)
            if allowed is not None and target_kind not in allowed:
                errors.append(
                    f"{context} : {kind} ne peut cibler que "
                    f"{sorted(allowed) or 'aucun'} handle, pas {target_kind} ({handle})"
                )
                continue
            target_index = registry.get(handle)
            if target_index is None:
                errors.append(
                    f"{context} : handle inconnu « {handle} » "
                    "(aucune réparation, aucune cible approchée)"
                )
                continue
            handles.append(handle)
        card = LINK_CARDINALITY.get(kind)
        if card is not None:
            if card["empty"] == "required" and handles:
                errors.append(f"{context} : {kind} exige l=[]")
            if card["empty"] == "forbidden" and not handles:
                errors.append(f"{context} : {kind} exige des handles")
            maximum = card["max"]
            if maximum is not None and maximum > 0 and len(handles) > maximum:
                errors.append(
                    f"{context} : {kind} accepte au plus {maximum} handle(s)"
                )
        if kind == "RELATION" and len(handles) == 2:
            if handles[0] == handles[1]:
                errors.append(f"{context} : RELATION auto-cible interdite {handles}")
        indexes: list[int] = []
        for handle in handles:
            target = registry.get(handle)
            if target is not None:
                indexes.append(target)
        resolved.append(
            {
                "k": kind,
                "v": str(record.get("v") or ""),
                "s": list(record.get("s") or []),
                "h": record.get("h") if isinstance(record.get("h"), str) else "",
                "l": indexes,
                "l_handles": handles,
                "m": list(record.get("m") or []),
            }
        )
    return resolved


def resolve_v3_handles(transport: Mapping[str, Any]) -> dict[str, Any]:
    records = transport.get("records")
    if not isinstance(records, list):
        raise WindowTransportValidationError("records absent")
    errors: list[str] = []
    registry = build_handle_registry(records, errors)
    resolved = resolve_symbolic_links(records, registry, errors)
    if errors:
        raise WindowTransportValidationError(" | ".join(errors))
    return {
        "theme": str(transport.get("theme") or "").strip(),
        "intent": str(transport.get("intent") or "").strip(),
        "ic": str(transport.get("ic") or "").strip(),
        "aud": str(transport.get("aud") or "").strip(),
        "ac": str(transport.get("ac") or "").strip(),
        "records": resolved,
        "handle_registry": registry.to_dict(),
    }


def reconstruction_records(resolved: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Forme interne pour assign_intermediate_records — integer l, sans fuite de h."""
    out: list[dict[str, Any]] = []
    for item in resolved.get("records") or []:
        out.append(
            {
                "k": item["k"],
                "v": item["v"],
                "s": list(item.get("s") or []),
                "l": [int(link) for link in (item.get("l") or [])],
                "m": list(item.get("m") or []),
            }
        )
    return out


__all__ = [
    "HandleRegistry",
    "build_handle_registry",
    "reconstruction_records",
    "resolve_symbolic_links",
    "resolve_v3_handles",
]
