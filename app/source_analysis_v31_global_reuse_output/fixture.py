"""Fixtures synthétiques jardin + pleine échelle. Aucun contenu pastoral. 0 provider."""

from __future__ import annotations

import copy
from typing import Any

from app.source_analysis_v31_global_output_architecture.fixture import (
    build_full_scale_inventory,
)
from app.source_analysis_v31_global_reuse_output.constants import TEXT_LIMITS
from app.source_analysis_v31_global_v20_grammar_canary.fixture import (
    build_synthetic_fixture,
    expected_valid_transport_v20,
)


def expected_valid_transport_v30() -> dict[str, Any]:
    payload = copy.deepcopy(expected_valid_transport_v20())
    ideas = []
    for idea in payload.get("i") or []:
        row = dict(idea)
        if len(row.get("m") or []) == 1:
            row.pop("v", None)
        ideas.append(row)
    payload["i"] = ideas
    return payload


def with_forbidden_single_member_rewrite() -> dict[str, Any]:
    payload = expected_valid_transport_v30()
    payload["i"][0]["v"] = "Water garden beds at dawn so leaves dry before noon."
    return payload


def with_missing_synthesis() -> dict[str, Any]:
    payload = expected_valid_transport_v30()
    merge = payload["i"][1]
    merge.pop("v", None)
    return payload


def all_distinct_reuse_transport(inventory: dict[str, Any]) -> dict[str, Any]:
    ideas = []
    for index, input_id in enumerate(inventory["idea_input_ids"], start=1):
        ideas.append({"h": f"I{index}", "m": [input_id], "p": "supporting"})
    topics = []
    topic_ids = [
        key for key, row in inventory["records"].items() if row.get("kind") == "TOPIC"
    ]
    for index, input_id in enumerate(topic_ids, start=1):
        row = inventory["records"][input_id]
        topics.append(
            {
                "h": f"T{index}",
                "v": str(row.get("value") or "")[: TEXT_LIMITS["topic"]],
                "m": [input_id],
            }
        )
    examples = []
    example_ids = [
        key for key, row in inventory["records"].items() if row.get("kind") == "EXAMPLE"
    ]
    for index, input_id in enumerate(example_ids, start=1):
        examples.append({"h": f"E{index}", "l": [input_id], "g": [f"I{index}"]})
    references = []
    ref_ids = [
        key for key, row in inventory["records"].items() if row.get("kind") == "REFERENCE"
    ]
    for index, input_id in enumerate(ref_ids, start=1):
        references.append({"h": f"F{index}", "l": [input_id]})
    uncertainties = []
    unc_ids = [
        key for key, row in inventory["records"].items() if row.get("kind") == "UNCERTAINTY"
    ]
    for index, input_id in enumerate(unc_ids, start=1):
        uncertainties.append({"h": f"U{index}", "l": [input_id]})
    return {
        "gm": {
            "th": "A community garden handbook about watering, soil, and shared tools.",
            "in": "Teach volunteers a few durable habits that protect plants.",
            "ic": "high",
            "au": "Community garden volunteers",
            "ac": "medium",
            "vo": "Practical spoken instruction with short concrete examples.",
        },
        "t": topics,
        "i": ideas,
        "x": examples,
        "f": references,
        "u": uncertainties,
        "drop": [],
    }


def mixed_full_scale_transport(inventory: dict[str, Any]) -> dict[str, Any]:
    payload = all_distinct_reuse_transport(inventory)
    idea_ids = list(inventory["idea_input_ids"])
    first = payload["i"][0]
    second = payload["i"][1]
    merged = {
        "h": "I1",
        "v": "Volunteers water garden beds at dawn so leaves dry before noon.",
        "m": [idea_ids[0], idea_ids[1]],
        "p": "supporting",
    }
    dropped = payload["i"][-1]
    remaining = [merged] + payload["i"][2:-1]
    # re-number handles after the merge
    ideas = []
    for index, row in enumerate(remaining, start=1):
        item = dict(row)
        item["h"] = f"I{index}"
        ideas.append(item)
    payload["i"] = ideas
    payload["drop"] = [{"i": dropped["m"][0], "w": "non_substantive_fragment"}]
    payload["x"] = [
        {"h": row["h"], "l": row["l"], "g": ["I1"]} for row in payload["x"]
    ]
    return payload


def future_grammar_canary_fixture() -> dict[str, Any]:
    fixture = build_synthetic_fixture()
    expected = expected_valid_transport_v30()
    return {
        "executed": False,
        "new_grammar_canary_required": True,
        "prompt_version": "global-consolidation-3.0",
        "transport_version": "global-consolidation-transport-3.0",
        "pastoral": False,
        "real_windows": False,
        "must_exercise": {
            "single_member_reuse": True,
            "multi_member_synthesis": True,
            "idea_drop": True,
            "non_idea_relation_hint_omission": True,
            "derived_src": True,
            "canonical_reconstruction": True,
        },
        "idea_input_ids": list(fixture.idea_input_ids),
        "relation_hint_id": "SYN:L001",
        "expected_valid_transport": expected,
        "expected_dispositions": dict(fixture.expected_dispositions),
        "inventory": fixture.inventory(),
        "transcript_id": fixture.transcript.transcript_id,
    }


__all__ = [
    "all_distinct_reuse_transport",
    "build_full_scale_inventory",
    "expected_valid_transport_v30",
    "future_grammar_canary_fixture",
    "mixed_full_scale_transport",
    "with_forbidden_single_member_rewrite",
    "with_missing_synthesis",
]
