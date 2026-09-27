"""Inspection handles V3 WIN001 — diagnostic only. Aucune réparation."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_local_v3.handles import handle_kind, is_valid_handle
from app.source_analysis_v3_symbolic_grammar_canary.handles import inspect_handle_metrics


def _is_int_link(raw: Any) -> bool:
    return isinstance(raw, int) and not isinstance(raw, bool)


def inspect_symbolic_refs(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Ajoute unique T/I et refs avant/après déclaration. N'altère rien."""
    base = inspect_handle_metrics(payload)
    records: list[dict[str, Any]] = []
    if isinstance(payload, Mapping):
        raw = payload.get("records") or []
        if isinstance(raw, list):
            records = [item for item in raw if isinstance(item, dict)]

    owner_pos: dict[str, int] = {}
    for index, item in enumerate(records):
        handle = item.get("h")
        if isinstance(handle, str) and is_valid_handle(handle):
            owner_pos.setdefault(handle, index)

    forward: list[str] = []
    backward: list[str] = []
    for index, item in enumerate(records):
        raw_links = item.get("l")
        if not isinstance(raw_links, list):
            continue
        for raw in raw_links:
            if _is_int_link(raw) or not isinstance(raw, str) or not is_valid_handle(raw):
                continue
            owner = owner_pos.get(raw)
            if owner is None:
                continue
            if owner > index:
                forward.append(raw)
            else:
                backward.append(raw)

    t_handles = list(base.get("topic_owner_handles") or [])
    i_handles = list(base.get("idea_owner_handles") or [])
    extra = {
        "t_handles": len(t_handles),
        "i_handles": len(i_handles),
        "unique_t_handles": len(set(t_handles)),
        "unique_i_handles": len(set(i_handles)),
        "forward_symbolic_refs": len(forward),
        "backward_symbolic_refs": len(backward),
        "forward_ref_samples": forward[:12],
        "backward_ref_samples": backward[:12],
        "numeric_link_regression": base.get("numeric_link_regression", "NO"),
        "python_must_not_guess": True,
        "repaired": False,
    }
    merged = dict(base)
    merged.update(extra)
    counts = dict(base.get("counts") or {})
    counts.update(
        {
            "t_handles": extra["t_handles"],
            "i_handles": extra["i_handles"],
            "unique_t_handles": extra["unique_t_handles"],
            "unique_i_handles": extra["unique_i_handles"],
            "forward_symbolic_refs": extra["forward_symbolic_refs"],
            "backward_symbolic_refs": extra["backward_symbolic_refs"],
        }
    )
    merged["counts"] = counts
    return merged


def handle_gate_status(metrics: Mapping[str, Any] | None) -> dict[str, Any]:
    data = metrics or {}
    counts = data.get("counts") or {}
    unknown = int(counts.get("unknown") or 0)
    wrong_kind = int(counts.get("wrong_kind") or 0)
    duplicate = int(counts.get("duplicate_owners") or 0)
    malformed = int(counts.get("malformed") or 0)
    self_rel = int(counts.get("self_relations") or 0)
    numeric = data.get("numeric_link_regression") == "YES"
    ok = (
        unknown == 0
        and wrong_kind == 0
        and duplicate == 0
        and malformed == 0
        and self_rel == 0
        and not numeric
    )
    return {
        "unknown_handles": unknown,
        "wrong_kind_handles": wrong_kind,
        "duplicate_owners": duplicate,
        "malformed_handles": malformed,
        "self_relations": self_rel,
        "numeric_link_regression": "YES" if numeric else "NO",
        "handle_gate_pass": ok,
    }


def example_target_kinds(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(payload, Mapping):
        return rows
    records = [item for item in (payload.get("records") or []) if isinstance(item, dict)]
    for index, item in enumerate(records):
        if str(item.get("k") or "") != "EXAMPLE":
            continue
        links = [raw for raw in (item.get("l") or []) if isinstance(raw, str)]
        rows.append(
            {
                "index": index,
                "value_excerpt": str(item.get("v") or "")[:180],
                "links": links,
                "target_kinds": [handle_kind(raw) for raw in links],
                "links_to_topic": any(handle_kind(raw) == "TOPIC" for raw in links),
                "links_to_idea": any(handle_kind(raw) == "IDEA" for raw in links),
            }
        )
    return rows


__all__ = [
    "example_target_kinds",
    "handle_gate_status",
    "inspect_handle_metrics",
    "inspect_symbolic_refs",
]
