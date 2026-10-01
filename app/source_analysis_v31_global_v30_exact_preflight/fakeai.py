"""FakeAI pleine échelle sur l'inventaire local réel. 0 réseau."""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from app.source_analysis_v31_global_reuse_output.fakeai import interpret_transport_v30
from app.source_analysis_v31_global_reuse_output.fixture import all_distinct_reuse_transport
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    DROP_REASONS_V20,
    DROP_STRESS_COUNT,
    EXPECTED_IDEA,
    MERGE_STRESS_SYNTHESIZED,
    SYNTHESIZED_IDEA_MAX_CHARS,
    TEXT_LIMITS,
)


def production_inventory(
    normalized: Mapping[str, Any],
    transcript: Any,
) -> dict[str, Any]:
    records: dict[str, dict[str, Any]] = {}
    for item in normalized.get("all_records") or []:
        input_id = str(item.get("input_id") or "")
        if not input_id:
            continue
        records[input_id] = {
            "id": input_id,
            "kind": item.get("kind"),
            "value": item.get("value"),
            "source_refs": list(item.get("source_refs") or []),
            "metadata": list(item.get("metadata") or []),
            "links": list(item.get("link_input_ids") or []),
            "s": list(item.get("source_refs") or []),
            "v": item.get("value"),
            "m": list(item.get("metadata") or []),
            "l": list(item.get("link_input_ids") or []),
            "window_id": item.get("window_id"),
        }
    idea_ids = [str(item) for item in (normalized.get("idea_input_ids") or [])]
    kind_by_input = {key: str(row.get("kind")) for key, row in records.items()}
    src_by_input = {
        key: list(row.get("source_refs") or []) for key, row in records.items()
    }
    counts: dict[str, int] = {}
    for row in records.values():
        kind = str(row.get("kind") or "")
        counts[kind] = int(counts.get(kind) or 0) + 1
    return {
        "records": records,
        "idea_input_ids": idea_ids,
        "allowed_input_ids": set(records),
        "kind_by_input": kind_by_input,
        "src_by_input": src_by_input,
        "transcript": transcript,
        "counts": counts,
    }


def expected_mix_transport(inventory: Mapping[str, Any]) -> dict[str, Any]:
    payload = all_distinct_reuse_transport(inventory)
    idea_ids = list(inventory["idea_input_ids"])
    if len(idea_ids) < 2:
        return payload
    merged = {
        "h": "I1",
        "v": "Equivalent local propositions are merged into one source-supported idea.",
        "m": [idea_ids[0], idea_ids[1]],
        "p": "supporting",
    }
    remaining = [merged] + payload["i"][2:]
    ideas = []
    for index, row in enumerate(remaining, start=1):
        item = dict(row)
        item["h"] = f"I{index}"
        ideas.append(item)
    payload["i"] = ideas
    payload["drop"] = []
    return payload


def merge_stress_transport(inventory: Mapping[str, Any]) -> dict[str, Any]:
    payload = all_distinct_reuse_transport(inventory)
    idea_ids = list(inventory["idea_input_ids"])
    merges = min(MERGE_STRESS_SYNTHESIZED, len(idea_ids) // 2)
    synthesized = []
    consumed = 0
    for index in range(merges):
        left = idea_ids[consumed]
        right = idea_ids[consumed + 1]
        synthesized.append(
            {
                "h": f"I{index + 1}",
                "v": "x" * SYNTHESIZED_IDEA_MAX_CHARS,
                "m": [left, right],
                "p": "supporting",
            }
        )
        consumed += 2
    reused = []
    for offset, input_id in enumerate(idea_ids[consumed:], start=1):
        reused.append(
            {
                "h": f"I{merges + offset}",
                "m": [input_id],
                "p": "supporting",
            }
        )
    payload["i"] = synthesized + reused
    payload["drop"] = []
    return payload


def drop_stress_transport(inventory: Mapping[str, Any]) -> dict[str, Any]:
    payload = all_distinct_reuse_transport(inventory)
    idea_ids = list(inventory["idea_input_ids"])
    drop_n = min(DROP_STRESS_COUNT, len(idea_ids))
    dropped = idea_ids[-drop_n:]
    kept = payload["i"][:-drop_n] if drop_n else payload["i"]
    ideas = []
    for index, row in enumerate(kept, start=1):
        item = dict(row)
        item["h"] = f"I{index}"
        ideas.append(item)
    payload["i"] = ideas
    reasons = list(DROP_REASONS_V20)
    payload["drop"] = [
        {"i": input_id, "w": reasons[index % len(reasons)]}
        for index, input_id in enumerate(dropped)
    ]
    return payload


def _summarize(label: str, interpreted: Mapping[str, Any], inventory: Mapping[str, Any]) -> dict[str, Any]:
    validator = interpreted.get("validator") or {}
    reconstruction = interpreted.get("reconstruction") or {}
    ideas = len(inventory["idea_input_ids"])
    accounted = ideas if validator.get("exact_set_equality") else 0
    ok = interpreted.get("pipeline_pass") is True and accounted == EXPECTED_IDEA
    replay = None
    if reconstruction.get("ok") and reconstruction.get("canonical_json"):
        replay = json.dumps(
            json.loads(reconstruction["canonical_json"]),
            ensure_ascii=False,
            sort_keys=True,
        )
        ok = ok and replay == reconstruction["canonical_json"]
    return {
        "status": "PASS" if ok else "FAIL",
        "ok": ok,
        "ideas": ideas,
        "accounted": accounted,
        "coverage": interpreted.get("coverage"),
        "canonical_reconstruction": interpreted.get("canonical_reconstruction"),
        "canonical_validation": interpreted.get("canonical_validation"),
        "reuse_text_exact": interpreted.get("reuse_text_exact"),
        "derived_src_ok": interpreted.get("derived_src_ok"),
        "deterministic_replay": replay == reconstruction.get("canonical_json")
        if reconstruction.get("canonical_json")
        else False,
        "relations_empty": reconstruction.get("relations_present") is False,
        "label": label,
        "errors": (validator.get("errors") or [])[:12],
    }


def full_scale_production_stress(
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    if len(inventory["idea_input_ids"]) != EXPECTED_IDEA:
        return {
            "ok": False,
            "error": f"inventory ideas {len(inventory['idea_input_ids'])} != {EXPECTED_IDEA}",
        }
    distinct = interpret_transport_v30(
        all_distinct_reuse_transport(inventory),
        inventory,
        signature="a45-all-distinct-reuse",
    )
    expected = interpret_transport_v30(
        expected_mix_transport(inventory),
        inventory,
        signature="a45-expected-mix",
    )
    merges = interpret_transport_v30(
        merge_stress_transport(inventory),
        inventory,
        signature="a45-merge-stress",
    )
    drops = interpret_transport_v30(
        drop_stress_transport(inventory),
        inventory,
        signature="a45-drop-stress",
    )
    rows = {
        "all_distinct_286_reuse": _summarize("all-distinct", distinct, inventory),
        "expected_mix": _summarize("expected-mix", expected, inventory),
        "merge_stress": _summarize("merge-stress", merges, inventory),
        "drop_stress": _summarize("drop-stress", drops, inventory),
    }
    ok = all(row.get("ok") for row in rows.values())
    first = rows["all_distinct_286_reuse"]
    return {
        "ok": ok,
        "idea_accountability": f"{EXPECTED_IDEA} / {EXPECTED_IDEA}" if ok else "FAIL",
        "canonical_reconstruction": first.get("canonical_reconstruction") if ok else "FAIL",
        "canonical_validation": first.get("canonical_validation") if ok else "FAIL",
        "topic_limit": TEXT_LIMITS["topic"],
        "scenarios": rows,
        "used_production_inventory": True,
        "synthetic_garden_substitution": False,
    }


def reconstruct_twice(inventory: Mapping[str, Any]) -> dict[str, Any]:
    payload = all_distinct_reuse_transport(inventory)
    first = interpret_transport_v30(
        copy.deepcopy(payload), inventory, signature="a45-replay-a"
    )
    second = interpret_transport_v30(
        copy.deepcopy(payload), inventory, signature="a45-replay-a"
    )
    left = ((first.get("reconstruction") or {}).get("canonical_json")) or ""
    right = ((second.get("reconstruction") or {}).get("canonical_json")) or ""
    equal = bool(left) and left == right
    return {
        "ok": equal and first.get("pipeline_pass") is True,
        "identical": equal,
        "canonical_reconstruction": first.get("canonical_reconstruction"),
        "canonical_validation": first.get("canonical_validation"),
    }


__all__ = [
    "drop_stress_transport",
    "expected_mix_transport",
    "full_scale_production_stress",
    "merge_stress_transport",
    "production_inventory",
    "reconstruct_twice",
]
