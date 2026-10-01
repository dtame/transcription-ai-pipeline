"""Transport mécanique valide pour FakeAI. 0 réseau. Couvre 286 IDEAs."""

from __future__ import annotations

from typing import Any, Mapping


def mechanical_keep_transport(normalized: Mapping[str, Any]) -> dict[str, Any]:
    """KEEP every local IDEA; copy other kinds; OTHER local RELATION hints."""
    nodes: list[dict[str, Any]] = []
    dispositions: list[dict[str, Any]] = []
    counters = {"TOPIC": 0, "IDEA": 0, "EXAMPLE": 0, "REFERENCE": 0, "UNCERTAINTY": 0}
    prefixes = {
        "TOPIC": "T",
        "IDEA": "I",
        "EXAMPLE": "E",
        "REFERENCE": "F",
        "UNCERTAINTY": "U",
    }
    first_idea_handle = ""
    first_topic_handle = ""
    first_example_handle = ""
    for item in normalized.get("all_records") or []:
        kind = str(item.get("kind") or "")
        input_id = str(item.get("input_id") or "")
        refs = [str(ref) for ref in (item.get("source_refs") or []) if isinstance(ref, str)]
        value = str(item.get("value") or "")
        if kind == "RELATION":
            dispositions.append({"i": input_id, "o": "OTHER", "g": "", "w": "none"})
            continue
        if kind not in prefixes:
            continue
        counters[kind] += 1
        handle = f"{prefixes[kind]}{counters[kind]}"
        meta: list[str] = []
        if kind == "IDEA":
            importance = str(item.get("importance") or "")
            meta = [importance if importance in {"central", "supporting", "minor"} else "supporting"]
            if not first_idea_handle:
                first_idea_handle = handle
        elif kind == "EXAMPLE":
            meta = ["example"]
            if not first_example_handle:
                first_example_handle = handle
        elif kind == "REFERENCE":
            meta = ["other", "partial"]
        elif kind == "UNCERTAINTY":
            meta = ["ambiguous_meaning", "medium"]
        elif kind == "TOPIC" and not first_topic_handle:
            first_topic_handle = handle
        nodes.append({"h": handle, "k": kind, "v": value, "s": refs, "m": meta})
        dispositions.append({"i": input_id, "o": "KEEP", "g": handle, "w": "none"})
    relations: list[dict[str, Any]] = []
    if first_idea_handle and first_topic_handle:
        idea = next(node for node in nodes if node["h"] == first_idea_handle)
        relations.append(
            {
                "t": "supports",
                "a": first_idea_handle,
                "b": first_topic_handle,
                "s": list(idea.get("s") or [])[:2],
            }
        )
    if first_example_handle and first_idea_handle:
        example = next(node for node in nodes if node["h"] == first_example_handle)
        relations.append(
            {
                "t": "illustrates",
                "a": first_example_handle,
                "b": first_idea_handle,
                "s": list(example.get("s") or [])[:2],
            }
        )
    windows = list((normalized.get("windows") or {}).values())
    theme = " ".join(str(row.get("theme") or "") for row in windows[:3]).strip()
    intent = " ".join(str(row.get("intent") or "") for row in windows[:2]).strip()
    audience = " ".join(str(row.get("audience") or "") for row in windows[:2]).strip()
    return {
        "gm": {
            "th": theme or "Source theme from seven-window local extraction",
            "in": intent or "Author intent inferred from supplied local records",
            "ic": "medium",
            "au": audience or "Audience inferred from supplied local records",
            "ac": "medium",
            "vo": "Observable oral teaching voice from the supplied local records",
        },
        "n": nodes,
        "r": relations,
        "d": dispositions,
    }


__all__ = ["mechanical_keep_transport"]
