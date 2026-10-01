"""Fixtures synthétiques pleine échelle — aucun contenu pastoral. 0 provider."""

from __future__ import annotations

from typing import Any

from app.source_analysis.window_fixtures import make_transcript
from app.source_analysis_v31_global_output_architecture.constants import (
    EXPECTED_EXAMPLE,
    EXPECTED_IDEA,
    EXPECTED_REFERENCE,
    EXPECTED_RELATION,
    EXPECTED_TOPIC,
    EXPECTED_UNCERTAINTY,
    TEXT_LIMITS,
)
from app.source_analysis_v31_global_output_architecture.estimator import (
    estimate_output,
    worst_case_transport,
)
from app.source_analysis_v31_global_output_architecture.membership import (
    derived_src_union,
    validate_global_transport_v20,
)
from app.source_analysis_v31_global_output_architecture.reconstruct import (
    reconstruct_source_map,
)

SYNTHETIC_TRANSCRIPT_ID = "TR_CANARY_GARDEN_A39"
SYNTHETIC_WINDOWS = tuple(f"SYN{index:03d}" for index in range(1, 8))


def _src(index: int) -> str:
    return f"SRC99{index:04d}"


def _record(
    input_id: str,
    kind: str,
    value: str,
    source_refs: list[str],
    *,
    metadata: list[str] | None = None,
    links: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": input_id,
        "kind": kind,
        "value": value,
        "source_refs": list(source_refs),
        "metadata": list(metadata or []),
        "links": list(links or []),
        "s": list(source_refs),
        "v": value,
        "m": list(metadata or []),
        "l": list(links or []),
    }


def build_full_scale_inventory() -> dict[str, Any]:
    records: dict[str, dict[str, Any]] = {}
    idea_ids: list[str] = []
    src_ids: list[str] = []
    src_index = 1

    def next_src() -> str:
        nonlocal src_index
        ref = _src(src_index)
        src_index += 1
        src_ids.append(ref)
        return ref

    for index in range(1, EXPECTED_TOPIC + 1):
        window = SYNTHETIC_WINDOWS[(index - 1) % 7]
        input_id = f"{window}:T{index}"
        ref = next_src()
        records[input_id] = _record(
            input_id,
            "TOPIC",
            f"Garden topic {index}: soil, water, or shared tools.",
            [ref],
        )
    for index in range(1, EXPECTED_IDEA + 1):
        window = SYNTHETIC_WINDOWS[(index - 1) % 7]
        input_id = f"{window}:I{index}"
        idea_ids.append(input_id)
        topic_id = f"{SYNTHETIC_WINDOWS[(index - 1) % 7]}:T{((index - 1) % EXPECTED_TOPIC) + 1}"
        ref = next_src()
        records[input_id] = _record(
            input_id,
            "IDEA",
            f"Volunteers should water bed {index} at dawn so leaves dry before noon.",
            [ref],
            metadata=["supporting"],
            links=[topic_id],
        )
    for index in range(1, EXPECTED_EXAMPLE + 1):
        window = SYNTHETIC_WINDOWS[(index - 1) % 7]
        input_id = f"{window}:E{index}"
        ref = next_src()
        records[input_id] = _record(
            input_id,
            "EXAMPLE",
            f"Last Tuesday a volunteer watered row {index} twice after sunrise.",
            [ref],
            metadata=["example"],
            links=[f"{window}:I{index}"],
        )
    for index in range(1, EXPECTED_REFERENCE + 1):
        window = SYNTHETIC_WINDOWS[(index - 1) % 7]
        input_id = f"{window}:F{index}"
        ref = next_src()
        records[input_id] = _record(
            input_id,
            "REFERENCE",
            f"Greenlane Garden Almanac, page {index}.",
            [ref],
            metadata=["book", "partial"],
        )
    for index in range(1, EXPECTED_UNCERTAINTY + 1):
        window = SYNTHETIC_WINDOWS[(index - 1) % 7]
        input_id = f"{window}:U{index}"
        ref = next_src()
        records[input_id] = _record(
            input_id,
            "UNCERTAINTY",
            f"It is unclear whether frost usually reaches bed {index} in October.",
            [ref],
            metadata=["ambiguous_meaning", "medium"],
        )
    for index in range(1, EXPECTED_RELATION + 1):
        window = SYNTHETIC_WINDOWS[(index - 1) % 7]
        input_id = f"{window}:L{index}"
        records[input_id] = _record(
            input_id,
            "RELATION",
            "supports",
            [],
            links=[f"{window}:I{index}", f"{window}:T{((index - 1) % EXPECTED_TOPIC) + 1}"],
        )
    kind_by_input = {key: str(row.get("kind")) for key, row in records.items()}
    src_by_input = {
        key: list(row.get("source_refs") or []) for key, row in records.items()
    }
    transcript = make_transcript(
        tuple(f"Synthetic garden segment {index}." for index in range(1, len(src_ids) + 1)),
        src_ids=tuple(src_ids),
        transcript_id=SYNTHETIC_TRANSCRIPT_ID,
    )
    return {
        "records": records,
        "idea_input_ids": idea_ids,
        "allowed_input_ids": set(records),
        "kind_by_input": kind_by_input,
        "src_by_input": src_by_input,
        "src_ids": src_ids,
        "transcript": transcript,
        "windows": list(SYNTHETIC_WINDOWS),
        "counts": {
            "TOPIC": EXPECTED_TOPIC,
            "IDEA": EXPECTED_IDEA,
            "EXAMPLE": EXPECTED_EXAMPLE,
            "REFERENCE": EXPECTED_REFERENCE,
            "UNCERTAINTY": EXPECTED_UNCERTAINTY,
            "RELATION": EXPECTED_RELATION,
        },
    }


def _gm() -> dict[str, str]:
    return {
        "th": "A community garden handbook about watering, soil, and shared tools.",
        "in": "Teach volunteers a few durable habits that protect plants.",
        "ic": "high",
        "au": "Community garden volunteers",
        "ac": "medium",
        "vo": "Practical spoken instruction with short concrete examples.",
    }


def all_distinct_transport(inventory: dict[str, Any]) -> dict[str, Any]:
    ideas = []
    for index, input_id in enumerate(inventory["idea_input_ids"], start=1):
        row = inventory["records"][input_id]
        text = str(row.get("value") or "")[: TEXT_LIMITS["idea"]]
        ideas.append({"h": f"I{index}", "v": text, "m": [input_id], "p": "supporting"})
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
        "gm": _gm(),
        "t": topics,
        "i": ideas,
        "x": examples,
        "f": references,
        "u": uncertainties,
        "drop": [],
    }


def mass_merge_transport(inventory: dict[str, Any]) -> dict[str, Any]:
    idea_ids = list(inventory["idea_input_ids"])
    groups: list[list[str]] = []
    for index in range(0, len(idea_ids), 4):
        groups.append(idea_ids[index : index + 4])
    ideas = []
    for index, members in enumerate(groups, start=1):
        ideas.append(
            {
                "h": f"I{index}",
                "v": f"Shared garden watering habit group {index}.",
                "m": members,
                "p": "supporting",
            }
        )
    topic_ids = [
        key for key, row in inventory["records"].items() if row.get("kind") == "TOPIC"
    ]
    topic_groups: list[list[str]] = []
    for index in range(0, len(topic_ids), 3):
        topic_groups.append(topic_ids[index : index + 3])
    topics = [
        {
            "h": f"T{index}",
            "v": f"Merged garden theme {index}.",
            "m": members,
        }
        for index, members in enumerate(topic_groups, start=1)
    ]
    base = all_distinct_transport(inventory)
    base["t"] = topics
    base["i"] = ideas
    base["x"] = [
        {"h": row["h"], "l": row["l"], "g": ["I1"]} for row in base["x"]
    ]
    return base


def drop_transport(inventory: dict[str, Any]) -> dict[str, Any]:
    payload = all_distinct_transport(inventory)
    dropped = payload["i"][-2:]
    payload["i"] = payload["i"][:-2]
    payload["drop"] = [
        {"i": dropped[0]["m"][0], "w": "transport_artifact"},
        {"i": dropped[1]["m"][0], "w": "non_substantive_fragment"},
    ]
    return payload


def unknown_member_transport(inventory: dict[str, Any]) -> dict[str, Any]:
    payload = all_distinct_transport(inventory)
    payload["i"][0]["m"] = ["SYN999:I1"]
    return payload


def duplicate_member_transport(inventory: dict[str, Any]) -> dict[str, Any]:
    payload = all_distinct_transport(inventory)
    shared = payload["i"][0]["m"][0]
    payload["i"][1]["m"] = [shared]
    return payload


def missing_member_transport(inventory: dict[str, Any]) -> dict[str, Any]:
    payload = all_distinct_transport(inventory)
    payload["i"] = payload["i"][1:]
    return payload


def interpret_transport_v20(
    transport: dict[str, Any],
    inventory: dict[str, Any],
    *,
    signature: str,
) -> dict[str, Any]:
    validated = validate_global_transport_v20(
        transport,
        idea_input_ids=inventory["idea_input_ids"],
        allowed_input_ids=inventory["allowed_input_ids"],
        local_kind_by_input=inventory["kind_by_input"],
    )
    reconstructed = None
    if validated.get("ok"):
        reconstructed = reconstruct_source_map(
            transport,
            inventory,
            inventory["transcript"],
            signature=signature,
        )
    unions_ok = True
    union_errors: list[str] = []
    if validated.get("ok"):
        local_src = inventory["src_by_input"]
        for idea in transport.get("i") or []:
            members = list(idea.get("m") or [])
            derived = derived_src_union(members, local_src)
            expected: list[str] = []
            seen: set[str] = set()
            for member in members:
                for ref in local_src.get(member) or []:
                    if ref not in seen:
                        seen.add(ref)
                        expected.append(ref)
            if derived != expected:
                unions_ok = False
                union_errors.append(str(idea.get("h")))
    return {
        "validator": validated,
        "reconstruction": reconstructed,
        "pipeline_pass": bool(
            validated.get("ok")
            and reconstructed
            and reconstructed.get("ok")
            and unions_ok
        ),
        "derived_src_ok": unions_ok,
        "derived_src_errors": union_errors,
        "structured_parse": "PASS",
        "canonical_reconstruction": (
            reconstructed.get("validate_source_map") if reconstructed else "FAIL"
        ),
        "canonical_validation": (
            reconstructed.get("ensure_valid_source_map") if reconstructed else "FAIL"
        ),
    }


def fakeai_catalog(inventory: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    inv = inventory or build_full_scale_inventory()
    return {
        "ALL_DISTINCT": all_distinct_transport(inv),
        "MASS_MERGE": mass_merge_transport(inv),
        "DROPS": drop_transport(inv),
        "UNKNOWN_MEMBER": unknown_member_transport(inv),
        "DUPLICATE_MEMBER": duplicate_member_transport(inv),
        "MISSING_MEMBER": missing_member_transport(inv),
        "WORST_CASE": worst_case_transport(),
    }


def stress_report(inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    inv = inventory or build_full_scale_inventory()
    catalog = fakeai_catalog(inv)
    cases: dict[str, Any] = {}
    expected_pass = {"ALL_DISTINCT", "MASS_MERGE", "DROPS"}
    expected_fail = {"UNKNOWN_MEMBER", "DUPLICATE_MEMBER", "MISSING_MEMBER"}
    for name, payload in catalog.items():
        if name == "WORST_CASE":
            estimate = estimate_output(members_per_idea=1, members_per_topic=1)
            cases[name] = {
                "estimator": estimate,
                "fits_safety": estimate.get("fits_safety"),
                "pipeline_pass": None,
            }
            continue
        interpreted = interpret_transport_v20(
            payload, inv, signature=f"fakeai-{name.lower()}"
        )
        cases[name] = {
            "pipeline_pass": interpreted.get("pipeline_pass"),
            "coverage": (interpreted.get("validator") or {}).get(
                "idea_disposition_coverage"
            ),
            "silent_drops": (interpreted.get("validator") or {}).get("silent_drops"),
            "errors": (interpreted.get("validator") or {}).get("errors") or [],
            "canonical_reconstruction": interpreted.get("canonical_reconstruction"),
            "canonical_validation": interpreted.get("canonical_validation"),
            "derived_src_ok": interpreted.get("derived_src_ok"),
        }
    ok = all(cases[name]["pipeline_pass"] is True for name in expected_pass) and all(
        cases[name]["pipeline_pass"] is False for name in expected_fail
    )
    return {"ok": ok, "cases": cases, "inventory_counts": inv["counts"]}


__all__ = [
    "all_distinct_transport",
    "build_full_scale_inventory",
    "drop_transport",
    "duplicate_member_transport",
    "fakeai_catalog",
    "interpret_transport_v20",
    "mass_merge_transport",
    "missing_member_transport",
    "stress_report",
    "unknown_member_transport",
]
