"""Métriques records / liens / SRC. Déterministe. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v2.constants import LOCAL_KINDS
from app.source_analysis_local_v2.links import ALLOWED_TARGET_KINDS


def _records(transport: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(transport, Mapping):
        return []
    records = transport.get("records") or []
    return [item for item in records if isinstance(item, Mapping)]


def record_metrics(transport: Mapping[str, Any] | None) -> dict[str, Any]:
    records = _records(transport)
    counts = {kind: 0 for kind in LOCAL_KINDS}
    for item in records:
        kind = str(item.get("k") or "")
        if kind in counts:
            counts[kind] += 1
    return {
        "total_records": len(records),
        "TOPIC": counts["TOPIC"],
        "IDEA": counts["IDEA"],
        "RELATION": counts["RELATION"],
        "EXAMPLE": counts["EXAMPLE"],
        "REFERENCE": counts["REFERENCE"],
        "UNCERTAINTY": counts["UNCERTAINTY"],
    }


def link_metrics(transport: Mapping[str, Any] | None) -> dict[str, Any]:
    records = _records(transport)
    bound = len(records)
    idea_topic = 0
    relation_idea = 0
    example_idea = 0
    self_links = 0
    duplicate_links = 0
    invalid_targets = 0
    out_of_range = 0
    for index, item in enumerate(records):
        kind = str(item.get("k") or "")
        raw = item.get("l") or []
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            continue
        links = [
            int(link)
            for link in raw
            if isinstance(link, int) and not isinstance(link, bool)
        ]
        seen: set[int] = set()
        for link in links:
            if link == index:
                self_links += 1
            if link in seen:
                duplicate_links += 1
            seen.add(link)
            if link < 0 or link >= bound:
                out_of_range += 1
                continue
            target_kind = str(records[link].get("k") or "")
            allowed = ALLOWED_TARGET_KINDS.get(kind)
            if allowed is not None and allowed and target_kind not in allowed:
                invalid_targets += 1
            if kind == "IDEA" and target_kind == "TOPIC":
                idea_topic += 1
            if kind == "RELATION" and target_kind == "IDEA":
                relation_idea += 1
            if kind == "EXAMPLE" and target_kind == "IDEA":
                example_idea += 1
    return {
        "idea_to_topic_links": idea_topic,
        "relation_idea_to_idea_links": relation_idea,
        "example_to_idea_links": example_idea,
        "self_links": self_links,
        "duplicate_links": duplicate_links,
        "invalid_targets": invalid_targets,
        "out_of_range_links": out_of_range,
        "links_valid": self_links == 0
        and duplicate_links == 0
        and invalid_targets == 0
        and out_of_range == 0,
    }


def src_metrics(
    transport: Mapping[str, Any] | None,
    window: WindowInput,
) -> dict[str, Any]:
    records = _records(transport)
    owned = set(window.owned_src_refs)
    referenced: set[str] = set()
    multi = 0
    lengths: list[int] = []
    for item in records:
        refs = [
            str(ref).strip()
            for ref in (item.get("s") or [])
            if isinstance(ref, str) and str(ref).strip()
        ]
        referenced.update(refs)
        lengths.append(len(refs))
        if len(refs) > 1:
            multi += 1
    coverage = len(referenced & owned)
    owned_count = len(owned)
    return {
        "owned_src_count": owned_count,
        "distinct_srcs_referenced": len(referenced),
        "coverage_count": coverage,
        "semantic_src_coverage_pct": round(100.0 * coverage / owned_count, 2)
        if owned_count
        else 0.0,
        "records_with_multi_src": multi,
        "mean_src_refs_per_record": round(sum(lengths) / len(lengths), 3)
        if lengths
        else 0.0,
        "max_src_refs_per_record": max(lengths) if lengths else 0,
        "ownership_coverage": "complete",
        "semantic_reference_coverage_is_not_ownership": True,
    }


def output_size_metrics(
    *,
    raw_text: str | None,
    transport: Mapping[str, Any] | None,
    output_tokens: int | None,
    max_output: int,
) -> dict[str, Any]:
    raw = raw_text or ""
    structured = ""
    if isinstance(transport, Mapping):
        import json

        structured = json.dumps(dict(transport), ensure_ascii=False)
    return {
        "raw_response_chars": len(raw),
        "raw_response_bytes": len(raw.encode("utf-8")),
        "structured_json_chars": len(structured),
        "structured_json_bytes": len(structured.encode("utf-8")),
        "actual_output_tokens": output_tokens,
        "max_output_tokens": max_output,
        "output_ratio": round(output_tokens / max_output, 4)
        if output_tokens is not None and max_output
        else None,
    }


__all__ = ["link_metrics", "output_size_metrics", "record_metrics", "src_metrics"]
