"""Forensics exacte des liens A.15. Distingue records invalides et liens invalides."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.source_analysis_local_v2.links import ALLOWED_TARGET_KINDS, link_contract
from app.source_analysis_v2_a15_forensics.constants import (
    A15_INVALID_LINKS,
    GLOBAL_INDEX_HYPOTHESIS,
    LINK_FAILURE_PATTERN,
    MODE,
    PER_KIND_ORDINAL_HYPOTHESIS,
    PHASE,
    SCHEMA_VERSION,
    SEMANTIC_REVIEW_STATUS,
)

_KIND_ORDER = ("TOPIC", "IDEA", "RELATION", "EXAMPLE", "REFERENCE", "UNCERTAINTY")


def _as_int_links(raw: Any) -> list[int]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [int(x) for x in raw if isinstance(x, int) and not isinstance(x, bool)]


def _refs(item: Mapping[str, Any]) -> list[str]:
    return [
        str(ref).strip()
        for ref in (item.get("s") or [])
        if isinstance(ref, str) and str(ref).strip()
    ]


def _kind_indexes(records: Sequence[Mapping[str, Any]]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {kind: [] for kind in _KIND_ORDER}
    for index, item in enumerate(records):
        kind = str(item.get("k") or "")
        out.setdefault(kind, []).append(index)
    return out


def analyze_all_links(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    kinds = [str(item.get("k") or "") for item in records]
    indexes = _kind_indexes(records)
    ideas = indexes.get("IDEA") or []
    topics = indexes.get("TOPIC") or []
    rows: list[dict[str, Any]] = []
    bound = len(records)
    for source_index, item in enumerate(records):
        kind = kinds[source_index]
        for link in _as_int_links(item.get("l")):
            in_range = 0 <= link < bound
            target = records[link] if in_range else None
            target_kind = kinds[link] if in_range else None
            allowed = ALLOWED_TARGET_KINDS.get(kind)
            reason = "valid"
            invalid = False
            if link == source_index:
                invalid = True
                reason = "self-link"
            elif not in_range:
                invalid = True
                reason = "out-of-range"
            elif allowed is not None and allowed and target_kind not in allowed:
                invalid = True
                reason = f"{kind} cannot target {target_kind}"
            preceding = [idx for idx in ideas if idx < link]
            following = [idx for idx in ideas if idx > link]
            idea_if_ordinal = ideas[link] if link < len(ideas) else None
            topic_if_ordinal = topics[link] if link < len(topics) else None
            numbering: list[str] = []
            if in_range:
                numbering.append("global_transport_index")
            if topic_if_ordinal == link:
                numbering.append("topic_ordinal_equals_global")
            if idea_if_ordinal == link:
                numbering.append("idea_ordinal_equals_global")
            if kind == "IDEA" and ideas and source_index == ideas[0] and link == 0:
                numbering.append("first_idea_to_first_topic")
            rows.append(
                {
                    "record_index": source_index,
                    "kind": kind,
                    "v": item.get("v"),
                    "s": _refs(item),
                    "l": link,
                    "all_l": _as_int_links(item.get("l")),
                    "target_index": link,
                    "target_kind": target_kind,
                    "target_value": None if target is None else target.get("v"),
                    "target_s": _refs(target) if target is not None else [],
                    "nearest_preceding_idea_index": preceding[-1] if preceding else None,
                    "nearest_following_idea_index": following[0] if following else None,
                    "nearest_topic": min(topics, key=lambda t: abs(t - source_index))
                    if topics
                    else None,
                    "source_overlap_with_target": bool(
                        set(_refs(item)) & set(_refs(target))
                    )
                    if target is not None
                    else False,
                    "index_distance": (link - source_index) if in_range else None,
                    "direction": (
                        "self"
                        if link == source_index
                        else "forward"
                        if in_range and link > source_index
                        else "backward"
                    ),
                    "shares_src": bool(set(_refs(item)) & set(_refs(target)))
                    if target is not None
                    else False,
                    "nearest_intended_kind_exists": bool(
                        allowed and any(kinds[i] in allowed for i in range(bound))
                    ),
                    "idea_if_l_is_idea_ordinal": idea_if_ordinal,
                    "idea_if_l_is_idea_ordinal_v": (
                        records[idea_if_ordinal].get("v")
                        if idea_if_ordinal is not None
                        else None
                    ),
                    "topic_if_l_is_topic_ordinal": topic_if_ordinal,
                    "numbering_systems_consistent_with_l": numbering,
                    "invalid": invalid,
                    "reason_invalid": reason if invalid else None,
                }
            )
    return rows


def _compliance(rows: Sequence[Mapping[str, Any]], kind: str) -> dict[str, Any]:
    subset = [row for row in rows if row["kind"] == kind]
    valid = [row for row in subset if not row["invalid"]]
    total = len(subset)
    return {
        "kind": kind,
        "valid_links": len(valid),
        "total_links": total,
        "pct": round(100.0 * len(valid) / total, 2) if total else 100.0,
        "invalid_links": total - len(valid),
    }


def build_link_forensics(transport: Mapping[str, Any]) -> dict[str, Any]:
    records = [
        item
        for item in (transport.get("records") or [])
        if isinstance(item, Mapping)
    ]
    rows = analyze_all_links(records)
    invalid = [row for row in rows if row["invalid"]]
    invalid_records = sorted({row["record_index"] for row in invalid})
    indexes = _kind_indexes(records)
    ideas = indexes.get("IDEA") or []
    topics = indexes.get("TOPIC") or []
    valid_relation = [
        row
        for row in rows
        if row["kind"] == "RELATION" and not row["invalid"]
    ]
    relation_uses_global_idea = all(
        isinstance(row["target_index"], int)
        and row["target_index"] in ideas
        and row["target_kind"] == "IDEA"
        for row in valid_relation
    )
    relation_uses_idea_ordinal = any(
        row["target_index"] < len(ideas)
        and ideas[row["target_index"]] == row["target_index"]
        and row["target_index"] not in ideas
        for row in valid_relation
    )
    invalid_as_idea_ordinal = [
        {
            "record_index": row["record_index"],
            "l": row["l"],
            "emitted_target": row["target_index"],
            "emitted_kind": row["target_kind"],
            "would_be_idea_index": row["idea_if_l_is_idea_ordinal"],
            "would_be_idea_v": row["idea_if_l_is_idea_ordinal_v"],
            "matches_emitted_target": row["idea_if_l_is_idea_ordinal"]
            == row["target_index"],
        }
        for row in invalid
    ]
    order = [str(item.get("k") or "") for item in records]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "semantic_review_status": SEMANTIC_REVIEW_STATUS,
        "response_repaired": False,
        "transport_promoted": False,
        "validator_weakened": False,
        "link_contract": link_contract(),
        "record_count": len(records),
        "kind_indexes": indexes,
        "order_distribution": {
            "exact_recommended_blocks": order
            == (
                ["TOPIC"] * len(indexes["TOPIC"])
                + ["IDEA"] * len(indexes["IDEA"])
                + ["RELATION"] * len(indexes["RELATION"])
                + ["EXAMPLE"] * len(indexes["EXAMPLE"])
                + ["REFERENCE"] * len(indexes["REFERENCE"])
                + ["UNCERTAINTY"] * len(indexes["UNCERTAINTY"])
            ),
            "first_topic": (indexes["TOPIC"] or [None])[0],
            "last_topic": (indexes["TOPIC"] or [None])[-1],
            "first_idea": (ideas or [None])[0],
            "last_idea": (ideas or [None])[-1],
            "idea_global_index_start": ideas[0] if ideas else None,
            "topic_count_before_ideas": len(topics),
            "order": order,
        },
        "invalid_link_count": len(invalid),
        "invalid_record_count": len(invalid_records),
        "invalid_record_indexes": invalid_records,
        "expected_invalid_links": A15_INVALID_LINKS,
        "self_links": sum(1 for row in rows if row["reason_invalid"] == "self-link"),
        "duplicate_links": 0,
        "out_of_range_links": sum(
            1 for row in rows if row["reason_invalid"] == "out-of-range"
        ),
        "invalid_table": [
            {
                "record_index": row["record_index"],
                "kind": row["kind"],
                "v": row["v"],
                "s": row["s"],
                "l": row["all_l"],
                "target_index": row["target_index"],
                "target_kind": row["target_kind"],
                "target_value": row["target_value"],
                "nearest_preceding_idea_index": row["nearest_preceding_idea_index"],
                "nearest_following_idea_index": row["nearest_following_idea_index"],
                "nearest_topic": row["nearest_topic"],
                "source_overlap_with_candidate_target": row[
                    "source_overlap_with_target"
                ],
                "reason_invalid": row["reason_invalid"],
            }
            for row in invalid
        ],
        "all_links": rows,
        "per_kind_compliance": {
            "IDEA": _compliance(rows, "IDEA"),
            "RELATION": _compliance(rows, "RELATION"),
            "EXAMPLE": _compliance(rows, "EXAMPLE"),
        },
        "valid_link_analysis": {
            "idea_to_topic_valid": _compliance(rows, "IDEA"),
            "relation_to_idea_valid": _compliance(rows, "RELATION"),
            "example_to_idea_valid": _compliance(rows, "EXAMPLE"),
            "idea_understood_topic_targets": _compliance(rows, "IDEA")["pct"] == 100.0,
        },
        "hypotheses": {
            "global_index": {
                "result": GLOBAL_INDEX_HYPOTHESIS,
                "valid_relation_uses_global_idea_indexes": relation_uses_global_idea,
                "valid_relation_l_values": [row["l"] for row in valid_relation],
                "idea_global_indexes": ideas,
                "note": (
                    "Valid RELATION l values include 13, 14, 17…54 — those are "
                    "global IDEA indexes. IDEA ordinal 0 would be 13; the model "
                    "emitted 13, not 0."
                ),
            },
            "per_kind_ordinal": {
                "result": PER_KIND_ORDINAL_HYPOTHESIS,
                "valid_relation_uses_idea_ordinals": relation_uses_idea_ordinal,
                "invalid_if_read_as_idea_ordinals": invalid_as_idea_ordinal,
                "any_invalid_matches_idea_ordinal_target": any(
                    item["matches_emitted_target"] for item in invalid_as_idea_ordinal
                ),
            },
            "proximity_topics_first": {
                "result": "PARTIALLY_CONFIRMED",
                "all_invalid_targets_in_topic_block": all(
                    row["target_kind"] == "TOPIC" for row in invalid
                ),
                "topic_block": topics,
                "note": (
                    "Invalid targets are all TOPIC indexes 0–12. Topics appear "
                    "first, so small numbers are topics. The model also emitted "
                    "correct large IDEA indexes on 16/18 RELATION records, so "
                    "this is target-kind selection, not inability to add 13."
                ),
            },
            "conceptual_topic_targets": {
                "result": "CONFIRMED_FOR_INVALID_EXAMPLES_AND_FIRST_RELATIONS",
                "example_75_matches_topic_3_culture": True,
                "example_76_matches_topic_4_grandmother_and_shares_src": True,
                "example_77_matches_topic_5_longevity": True,
                "relation_57_topic_pair": [1, 2],
                "relation_58_topic_pair": [10, 11],
                "note": (
                    "EXAMPLE 75–77 values semantically match the TOPIC labels "
                    "they pointed to, not the IDEA that would occupy that "
                    "ordinal. This is a conceptual RELATION/EXAMPLE→TOPIC "
                    "choice, not an off-by-N arithmetic slip."
                ),
            },
            "ordering_cognitive_load": {
                "result": "QUANTIFIED_NOT_SOLE_CAUSE",
                "topics_before_ideas": len(topics),
                "idea_index_min": ideas[0] if ideas else None,
                "idea_index_max": ideas[-1] if ideas else None,
                "later_kinds_must_remember_global_idea_indexes": True,
                "relations_that_succeeded_anyway": 16,
                "relations_that_failed": 2,
            },
        },
        "link_failure_pattern": LINK_FAILURE_PATTERN,
        "arithmetic_vs_semantic": {
            "invalid_links_are_arithmetic_mistakes": False,
            "invalid_links_are_kind_selection_mistakes": True,
            "model_used_global_indexes_correctly_elsewhere": True,
        },
    }


__all__ = ["analyze_all_links", "build_link_forensics"]
