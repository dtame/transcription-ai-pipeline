"""Fixture synthétique 1.1 + FakeAI déterministe. Aucun appel provider."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from app.ai.structured import validate_payload
from app.source_analysis_v31_global_canary_forensics.constants import (
    NEXT_TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    build_global_consolidation_schema_v11,
)
from app.source_analysis_v31_global_canary_forensics.validator_v11 import (
    validate_global_transport_v11,
)
from app.source_analysis_v31_global_grammar_canary.decoder import decode_global_transport
from app.source_analysis_v31_global_grammar_canary.fixture import (
    SYNTHETIC_TEXTS,
    build_synthetic_fixture,
    synthetic_compact_input,
)
from app.source_analysis_v31_global_grammar_canary.handles import inspect_global_handles
from app.source_analysis_v31_global_grammar_canary.reconstruct import (
    reconstruct_source_map,
    replay_reconstruction,
    source_map_public_view,
)
from app.source_analysis_v31_global_grammar_canary.validate import (
    audit_relations_policy_c,
    audit_traceability,
)

A35_DROP_PROSE = (
    "Non-substantive fragment ('and then uh') with no propositional content."
)


def next_expected_dispositions() -> dict[str, str]:
    return {
        "SYN001:I1": "KEEP",
        "SYN001:I2": "MERGE_EQUIVALENT",
        "SYN001:I3": "DROP",
        "SYN002:I1": "MERGE_EQUIVALENT",
        "SYN002:I2": "KEEP",
    }


def next_fixture_payload() -> dict[str, Any]:
    compact = synthetic_compact_input()
    return {
        "transport_version": NEXT_TRANSPORT_VERSION,
        "transcript_id": "TR_CANARY_GARDEN",
        "pastoral": False,
        "real_windows": False,
        "compact": compact,
        "texts": list(SYNTHETIC_TEXTS),
        "expected_dispositions": next_expected_dispositions(),
        "drop_case": {
            "id": "SYN001:I3",
            "content": "and then uh",
            "op": "DROP",
            "reason_code": "non_substantive_fragment",
        },
        "merge_case": {
            "ids": ["SYN001:I2", "SYN002:I1"],
            "op": "MERGE_EQUIVALENT",
        },
        "distinct_keep": ["SYN001:I1", "SYN002:I2"],
        "link_related_required": False,
        "repetition_required": False,
        "relation_evidence": {
            "type": "illustrates",
            "example": "SYN001:E1",
            "idea": "SYN001:I1",
        },
        "uncertainty": "SYN002:U1",
        "example": "SYN001:E1",
        "reference": "SYN001:F1",
        "global_fields": ["theme", "author intent", "target audience", "voice"],
        "classifications": {
            "SYN001:I1": "REQUIRED_BY_CONTRACT",
            "SYN001:I2": "REQUIRED_BY_CONTRACT",
            "SYN001:I3": "REQUIRED_BY_CONTRACT",
            "SYN002:I1": "REQUIRED_BY_CONTRACT",
            "SYN002:I2": "REQUIRED_BY_CONTRACT",
            "REPETITION": "OPTIONAL",
            "LINK_RELATED": "NOT_A_VALID_OPTION",
        },
        "ambiguous_expectations": False,
    }


def expected_valid_transport_v11() -> dict[str, Any]:
    return {
        "gm": {
            "th": "Community garden watering, compost, and companion planting",
            "in": "Teach volunteers simple habits that protect plants and soil.",
            "ic": "high",
            "au": "Community garden volunteers",
            "ac": "medium",
            "vo": "Practical workshop speech with concrete garden examples.",
        },
        "n": [
            {
                "h": "T1",
                "k": "TOPIC",
                "v": "Dawn watering",
                "s": ["SRC998001"],
                "m": [],
            },
            {
                "h": "T2",
                "k": "TOPIC",
                "v": "Soil care",
                "s": ["SRC998005", "SRC998003"],
                "m": [],
            },
            {
                "h": "I1",
                "k": "IDEA",
                "v": "Water garden beds at dawn so leaves dry before noon.",
                "s": ["SRC998001"],
                "m": ["central"],
            },
            {
                "h": "I2",
                "k": "IDEA",
                "v": "Kitchen-scrap compost feeds garden soil without bottled fertilizer.",
                "s": ["SRC998003", "SRC998006"],
                "m": ["supporting"],
            },
            {
                "h": "I3",
                "k": "IDEA",
                "v": "Pairing tomatoes with basil reduces pest pressure on the fruit.",
                "s": ["SRC998007"],
                "m": ["supporting"],
            },
            {
                "h": "E1",
                "k": "EXAMPLE",
                "v": "A volunteer waters the tomato row twice each week at sunrise.",
                "s": ["SRC998002"],
                "m": ["example"],
            },
            {
                "h": "E2",
                "k": "EXAMPLE",
                "v": "Last season the basil row next to tomatoes had fewer chewed leaves.",
                "s": ["SRC998008"],
                "m": ["anecdote"],
            },
            {
                "h": "F1",
                "k": "REFERENCE",
                "v": "Greenlane Garden Almanac, page 12",
                "s": ["SRC998009"],
                "m": ["book", "partial"],
            },
            {
                "h": "U1",
                "k": "UNCERTAINTY",
                "v": "It is unclear whether the first frost usually arrives in October.",
                "s": ["SRC998010"],
                "m": ["ambiguous_meaning", "medium"],
            },
        ],
        "r": [
            {
                "t": "illustrates",
                "a": "E1",
                "b": "I1",
                "s": ["SRC998002"],
            },
            {
                "t": "illustrates",
                "a": "E2",
                "b": "I3",
                "s": ["SRC998008"],
            },
            {
                "t": "supports",
                "a": "I1",
                "b": "T1",
                "s": ["SRC998001"],
            },
            {
                "t": "supports",
                "a": "I3",
                "b": "I2",
                "s": ["SRC998007"],
            },
        ],
        "d": [
            {"i": "SYN001:I1", "o": "KEEP", "g": "I1", "w": "none"},
            {"i": "SYN001:I2", "o": "MERGE_EQUIVALENT", "g": "I2", "w": "none"},
            {
                "i": "SYN001:I3",
                "o": "DROP",
                "g": "",
                "w": "non_substantive_fragment",
            },
            {"i": "SYN002:I1", "o": "MERGE_EQUIVALENT", "g": "I2", "w": "none"},
            {"i": "SYN002:I2", "o": "KEEP", "g": "I3", "w": "none"},
            {"i": "SYN001:T1", "o": "KEEP", "g": "T1", "w": "none"},
            {"i": "SYN002:T1", "o": "KEEP", "g": "T2", "w": "none"},
            {"i": "SYN001:E1", "o": "KEEP", "g": "E1", "w": "none"},
            {"i": "SYN002:E1", "o": "KEEP", "g": "E2", "w": "none"},
            {"i": "SYN001:F1", "o": "KEEP", "g": "F1", "w": "none"},
            {"i": "SYN002:U1", "o": "KEEP", "g": "U1", "w": "none"},
            {"i": "SYN001:L1", "o": "OTHER", "g": "", "w": "none"},
            {"i": "SYN002:L1", "o": "OTHER", "g": "", "w": "none"},
        ],
    }


def _mutate(mutator) -> dict[str, Any]:
    payload = copy.deepcopy(expected_valid_transport_v11())
    mutator(payload)
    return payload


def fakeai_invalid_drop_prose() -> dict[str, Any]:
    def edit(payload: dict[str, Any]) -> None:
        for row in payload["d"]:
            if row["i"] == "SYN001:I3":
                row["w"] = A35_DROP_PROSE

    return _mutate(edit)


def fakeai_silent_drop() -> dict[str, Any]:
    def edit(payload: dict[str, Any]) -> None:
        payload["d"] = [row for row in payload["d"] if row["i"] != "SYN001:I1"]

    return _mutate(edit)


def fakeai_invalid_merge() -> dict[str, Any]:
    def edit(payload: dict[str, Any]) -> None:
        for node in payload["n"]:
            if node["h"] == "I2":
                node["s"] = ["SRC998003"]

    return _mutate(edit)


def fakeai_unknown_input() -> dict[str, Any]:
    def edit(payload: dict[str, Any]) -> None:
        payload["d"].append(
            {"i": "SYN999:I9", "o": "KEEP", "g": "I1", "w": "none"}
        )

    return _mutate(edit)


def fakeai_unknown_handle() -> dict[str, Any]:
    def edit(payload: dict[str, Any]) -> None:
        payload["r"][0]["a"] = "I99"

    return _mutate(edit)


def fakeai_traceability_failure() -> dict[str, Any]:
    def edit(payload: dict[str, Any]) -> None:
        payload["n"][2]["s"] = ["SRC000001"]

    return _mutate(edit)


def fakeai_invalid_drop_token() -> dict[str, Any]:
    def edit(payload: dict[str, Any]) -> None:
        for row in payload["d"]:
            if row["i"] == "SYN001:I3":
                row["w"] = "filler"

    return _mutate(edit)


def fakeai_non_drop_reason_not_none() -> dict[str, Any]:
    def edit(payload: dict[str, Any]) -> None:
        for row in payload["d"]:
            if row["i"] == "SYN001:I1":
                row["w"] = "non_substantive_fragment"

    return _mutate(edit)


def fakeai_link_related_rejected() -> dict[str, Any]:
    def edit(payload: dict[str, Any]) -> None:
        for row in payload["d"]:
            if row["i"] == "SYN002:I2":
                row["o"] = "LINK_RELATED"

    return _mutate(edit)


def fakeai_catalog() -> dict[str, dict[str, Any]]:
    return {
        "VALID": expected_valid_transport_v11(),
        "INVALID_DROP_PROSE": fakeai_invalid_drop_prose(),
        "SILENT_DROP": fakeai_silent_drop(),
        "INVALID_MERGE": fakeai_invalid_merge(),
        "UNKNOWN_INPUT": fakeai_unknown_input(),
        "UNKNOWN_HANDLE": fakeai_unknown_handle(),
        "TRACEABILITY_FAILURE": fakeai_traceability_failure(),
        "INVALID_DROP_TOKEN": fakeai_invalid_drop_token(),
        "NON_DROP_REASON_NOT_NONE": fakeai_non_drop_reason_not_none(),
        "LINK_RELATED_REJECTED": fakeai_link_related_rejected(),
    }


def review_semantic_v11(
    transport: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(transport, Mapping):
        return {"status": "FAIL", "notes": ["transport missing"]}
    nodes = [item for item in (transport.get("n") or []) if isinstance(item, dict)]
    ideas = [item for item in nodes if item.get("k") == "IDEA"]
    uncertainties = [item for item in nodes if item.get("k") == "UNCERTAINTY"]
    examples = [item for item in nodes if item.get("k") == "EXAMPLE"]
    dispositions = [item for item in (transport.get("d") or []) if isinstance(item, dict)]
    by_id = {str(row.get("i") or ""): row for row in dispositions}
    notes: list[str] = []
    watering = by_id.get("SYN001:I1") or {}
    compost_a = by_id.get("SYN001:I2") or {}
    compost_b = by_id.get("SYN002:I1") or {}
    companion = by_id.get("SYN002:I2") or {}
    drop = by_id.get("SYN001:I3") or {}
    if watering.get("o") != "KEEP":
        notes.append("watering idea must KEEP")
    if compost_a.get("o") != "MERGE_EQUIVALENT" or compost_b.get("o") != "MERGE_EQUIVALENT":
        notes.append("compost pair must MERGE_EQUIVALENT")
    if compost_a.get("g") and compost_a.get("g") != compost_b.get("g"):
        notes.append("compost merge handles diverge")
    if companion.get("o") != "KEEP":
        notes.append("companion planting must KEEP as its own idea")
    if drop.get("o") != "DROP" or drop.get("w") != "non_substantive_fragment":
        notes.append("DROP token must be non_substantive_fragment")
    idea_texts = " ".join(str(item.get("v") or "").lower() for item in ideas)
    if "frost" in idea_texts:
        notes.append("uncertainty promoted to IDEA")
    if "chewed leaves" in idea_texts or "twice each week" in idea_texts:
        notes.append("example promoted to IDEA")
    if not uncertainties:
        notes.append("no uncertainty node")
    if not examples:
        notes.append("no example node")
    if len(ideas) < 3:
        notes.append("distinct ideas missing")
    ok = not notes
    return {
        "status": "PASS" if ok else "FAIL",
        "notes": notes,
        "idea_count": len(ideas),
        "repetition_required": False,
        "link_related_required": False,
        "not_production_quality_proof": True,
    }


def interpret_transport_v11(
    parsed: dict[str, Any] | None,
    *,
    raw_text: str | None = None,
    signature: str = "a36-v11",
) -> dict[str, Any]:
    fixture = build_synthetic_fixture()
    decoded = decode_global_transport(parsed, raw_text=raw_text)
    schema = build_global_consolidation_schema_v11()
    working = decoded.get("transport") if isinstance(decoded.get("transport"), dict) else parsed
    if isinstance(working, dict):
        try:
            validate_payload(working, schema)
            decoded["structured_parse"] = "PASS"
        except Exception as exc:  # noqa: BLE001 — forensic, no repair
            decoded["structured_parse"] = "FAIL"
            decoded.setdefault("errors", []).append(str(exc))
    transport = decoded.get("transport")
    handles = inspect_global_handles(transport)
    local_src: dict[str, list[str]] = {}
    for window in fixture.compact.get("windows") or []:
        for item in window.get("records") or []:
            local_src[str(item.get("id") or "")] = list(item.get("s") or [])
    validator = (
        validate_global_transport_v11(
            transport,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            allowed_source_refs=set(fixture.allowed_source_refs),
            local_src_by_input=local_src,
        )
        if isinstance(transport, dict)
        else {
            "ok": False,
            "errors": ["transport missing"],
            "idea_disposition_coverage": 0.0,
            "silent_drop_count": 1,
        }
    )
    traceability = audit_traceability(transport, fixture)
    relations = audit_relations_policy_c(transport, fixture)
    reconstruction = None
    replay = None
    if isinstance(transport, dict):
        reconstruction = reconstruct_source_map(
            transport, fixture.transcript, signature=signature
        )
        replay = replay_reconstruction(
            transport, fixture.transcript, signature=signature
        )
    semantic = review_semantic_v11(transport)
    silent = int(validator.get("silent_drop_count") or 0)
    return {
        "structured_parse": decoded.get("structured_parse") or "FAIL",
        "decoder": decoded.get("decoder"),
        "handle_validation": handles.get("handle_validation"),
        "handles": handles,
        "global_validator": "PASS" if validator.get("ok") else "FAIL",
        "validator": validator,
        "idea_disposition_coverage": validator.get("idea_disposition_coverage"),
        "silent_drops": silent,
        "no_drop_validator": "PASS" if silent == 0 else "FAIL",
        "traceability": traceability.get("status"),
        "relation_validator": relations.get("status"),
        "canonical_reconstruction": (
            "PASS" if reconstruction and reconstruction.get("ok") else "FAIL"
        ),
        "canonical_validation": (
            reconstruction.get("validate_source_map") if reconstruction else "FAIL"
        ),
        "deterministic_replay": replay.get("status") if replay else "FAIL",
        "semantic_review": semantic,
        "reconstruction": (
            source_map_public_view(reconstruction) if reconstruction else None
        ),
        "errors": list(decoded.get("errors") or []) + list(validator.get("errors") or []),
        "transport": transport,
        "repaired": False,
        "transport_version": NEXT_TRANSPORT_VERSION,
    }


def pipeline_pass(interpreted: Mapping[str, Any]) -> bool:
    return all(
        [
            interpreted.get("structured_parse") == "PASS",
            interpreted.get("decoder") == "PASS",
            interpreted.get("handle_validation") == "PASS",
            interpreted.get("global_validator") == "PASS",
            interpreted.get("no_drop_validator") == "PASS",
            interpreted.get("traceability") == "PASS",
            interpreted.get("canonical_reconstruction") == "PASS",
            interpreted.get("canonical_validation") == "PASS",
            (interpreted.get("semantic_review") or {}).get("status") == "PASS",
            float(interpreted.get("idea_disposition_coverage") or 0) >= 100.0,
            int(interpreted.get("silent_drops") or 0) == 0,
        ]
    )


__all__ = [
    "A35_DROP_PROSE",
    "expected_valid_transport_v11",
    "fakeai_catalog",
    "fakeai_invalid_drop_prose",
    "fakeai_invalid_drop_token",
    "fakeai_invalid_merge",
    "fakeai_link_related_rejected",
    "fakeai_non_drop_reason_not_none",
    "fakeai_silent_drop",
    "fakeai_traceability_failure",
    "fakeai_unknown_handle",
    "fakeai_unknown_input",
    "interpret_transport_v11",
    "next_expected_dispositions",
    "next_fixture_payload",
    "pipeline_pass",
    "review_semantic_v11",
]
