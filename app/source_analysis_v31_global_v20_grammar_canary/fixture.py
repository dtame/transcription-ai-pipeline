"""Fixture synthétique jardin communautaire — aucun contenu pastoral. 0 provider."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.file_utils import content_hash
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_fixtures import make_transcript
from app.source_analysis_v31_global_v20_grammar_canary.constants import (
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    SCHEMA_VERSION,
    SYNTHETIC_SRC_IDS,
    SYNTHETIC_WINDOW_IDS,
)
from app.source_analysis_v31_global_v20_grammar_canary.guard import (
    assert_synthetic_identity,
    reject_real_project_input,
)

SYNTHETIC_TEXTS = (
    "Water the beds at dawn so leaves dry before noon.",
    "A volunteer waters the tomato row twice each week at sunrise.",
    "Compost from kitchen scraps feeds the soil without synthetic fertilizer.",
    "and then uh",
    "Kitchen-scrap compost feeds garden soil without bottled fertilizer.",
    "Pairing tomatoes with basil reduces pest pressure on the fruit.",
    "Shared tools should be cleaned and returned to the shed after each session.",
    "Last season the basil row next to tomatoes had fewer chewed leaves.",
    "The workshop booklet cites the Greenlane Garden Almanac, page 12.",
    "Rain barrels collect roof water for dry-week irrigation.",
    "It is unclear whether the first frost usually arrives in October.",
    "Gardeners still debate the usual first-frost week.",
)


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
        "k": kind,
        "v": value,
        "s": list(source_refs),
        "m": list(metadata or []),
        "l": list(links or []),
        "kind": kind,
        "value": value,
        "source_refs": list(source_refs),
        "metadata": list(metadata or []),
        "links": list(links or []),
    }


def synthetic_compact_input() -> dict[str, Any]:
    return {
        "contract": "normalized-consolidation-input-1.0",
        "is_source_map": False,
        "windows": [
            {
                "id": "SYN:W001",
                "theme": "Dawn watering for a shared garden",
                "intent": "Show a simple watering habit that protects leaves.",
                "ic": "high",
                "aud": "Community garden volunteers",
                "ac": "medium",
                "owned": ["SRC998101", "SRC998102", "SRC998103", "SRC998104", "SRC998109"],
                "records": [
                    _record("SYN:T001", "TOPIC", "Dawn watering", ["SRC998101"]),
                    _record(
                        "SYN:I001",
                        "IDEA",
                        "Water garden beds at dawn so leaves dry before noon.",
                        ["SRC998101"],
                        metadata=["central"],
                        links=["SYN:T001"],
                    ),
                    _record(
                        "SYN:I002",
                        "IDEA",
                        "Compost from kitchen scraps feeds the soil without synthetic fertilizer.",
                        ["SRC998103"],
                        metadata=["supporting"],
                    ),
                    _record(
                        "SYN:I006",
                        "IDEA",
                        "and then uh",
                        ["SRC998104"],
                        metadata=["minor"],
                    ),
                    _record(
                        "SYN:E001",
                        "EXAMPLE",
                        "A volunteer waters the tomato row twice each week at sunrise.",
                        ["SRC998102"],
                        metadata=["example"],
                        links=["SYN:I001"],
                    ),
                    _record(
                        "SYN:F001",
                        "REFERENCE",
                        "Greenlane Garden Almanac, page 12",
                        ["SRC998109"],
                        metadata=["book", "partial"],
                    ),
                    _record(
                        "SYN:L001",
                        "RELATION",
                        "supports",
                        [],
                        links=["SYN:I001", "SYN:T001"],
                    ),
                ],
            },
            {
                "id": "SYN:W002",
                "theme": "Soil care, companion planting, and shared tools",
                "intent": "Describe soil feeding, a tomato-basil pairing, and tool care.",
                "ic": "medium",
                "aud": "Weekend garden volunteers",
                "ac": "medium",
                "owned": [
                    "SRC998105",
                    "SRC998106",
                    "SRC998107",
                    "SRC998108",
                    "SRC998110",
                    "SRC998111",
                    "SRC998112",
                ],
                "records": [
                    _record(
                        "SYN:T002",
                        "TOPIC",
                        "Soil care and companion planting",
                        ["SRC998105"],
                    ),
                    _record(
                        "SYN:I003",
                        "IDEA",
                        "Kitchen-scrap compost feeds garden soil without bottled fertilizer.",
                        ["SRC998106"],
                        metadata=["supporting"],
                        links=["SYN:T002"],
                    ),
                    _record(
                        "SYN:I004",
                        "IDEA",
                        "Pairing tomatoes with basil reduces pest pressure on the fruit.",
                        ["SRC998107"],
                        metadata=["supporting"],
                    ),
                    _record(
                        "SYN:I005",
                        "IDEA",
                        "Shared tools should be cleaned and returned to the shed after each session.",
                        ["SRC998108"],
                        metadata=["supporting"],
                    ),
                    _record(
                        "SYN:I007",
                        "IDEA",
                        "Rain barrels collect roof water for dry-week irrigation.",
                        ["SRC998111"],
                        metadata=["supporting"],
                    ),
                    _record(
                        "SYN:E002",
                        "EXAMPLE",
                        "Last season the basil row next to tomatoes had fewer chewed leaves.",
                        ["SRC998110"],
                        metadata=["anecdote"],
                        links=["SYN:I004"],
                    ),
                    _record(
                        "SYN:U001",
                        "UNCERTAINTY",
                        "It is unclear whether the first frost usually arrives in October.",
                        ["SRC998112"],
                        metadata=["ambiguous_meaning", "medium"],
                    ),
                ],
            },
        ],
    }


def all_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for window in synthetic_compact_input()["windows"]:
        for item in window["records"]:
            row = dict(item)
            row["window_id"] = window["id"]
            records.append(row)
    return records


def idea_input_ids() -> list[str]:
    return [item["id"] for item in all_records() if item["k"] == "IDEA"]


def allowed_input_ids() -> set[str]:
    return {item["id"] for item in all_records()}


def allowed_source_refs() -> set[str]:
    return set(SYNTHETIC_SRC_IDS)


def kind_by_input() -> dict[str, str]:
    return {item["id"]: str(item["k"]) for item in all_records()}


def src_by_input() -> dict[str, list[str]]:
    return {item["id"]: list(item["s"]) for item in all_records()}


def expected_dispositions() -> dict[str, str]:
    return {
        "SYN:I001": "KEEP",
        "SYN:I002": "MERGE_EQUIVALENT",
        "SYN:I003": "MERGE_EQUIVALENT",
        "SYN:I004": "KEEP",
        "SYN:I005": "KEEP",
        "SYN:I006": "DROP",
        "SYN:I007": "KEEP",
    }


def fixture_payload() -> dict[str, Any]:
    compact = synthetic_compact_input()
    return {
        "schema_version": SCHEMA_VERSION,
        "transcript_id": CANARY_TRANSCRIPT_ID,
        "window_id": CANARY_WINDOW_ID,
        "local_window_ids": list(SYNTHETIC_WINDOW_IDS),
        "src_ids": list(SYNTHETIC_SRC_IDS),
        "texts": list(SYNTHETIC_TEXTS),
        "compact": compact,
        "idea_input_ids": idea_input_ids(),
        "allowed_input_ids": sorted(allowed_input_ids()),
        "expected_dispositions": expected_dispositions(),
        "pastoral": False,
        "real_windows": False,
    }


def fixture_hash() -> str:
    return content_hash(
        json.dumps(fixture_payload(), ensure_ascii=False, sort_keys=True)
    )


@dataclass(frozen=True)
class SyntheticConsolidationFixtureV20:
    transcript: TranscriptInput
    compact: dict[str, Any]
    fixture_hash: str
    idea_input_ids: tuple[str, ...]
    allowed_input_ids: frozenset[str]
    allowed_source_refs: frozenset[str]
    expected_dispositions: dict[str, str]
    kind_by_input: dict[str, str]
    src_by_input: dict[str, list[str]]
    records: dict[str, dict[str, Any]]

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "transcript_id": self.transcript.transcript_id,
            "window_id": CANARY_WINDOW_ID,
            "local_window_ids": list(SYNTHETIC_WINDOW_IDS),
            "src_ids": list(self.transcript.src_ids()),
            "texts": [segment.text for segment in self.transcript.segments],
            "fixture_hash": self.fixture_hash,
            "idea_input_ids": list(self.idea_input_ids),
            "expected_dispositions": dict(self.expected_dispositions),
            "compact_chars": len(
                json.dumps(self.compact, ensure_ascii=False, separators=(",", ":"))
            ),
            "pastoral": False,
            "required_structure": {
                "local_topics": 2,
                "local_ideas": 7,
                "local_examples": 2,
                "local_references": 1,
                "local_uncertainties": 1,
                "single_member_keep": True,
                "multi_member_merge": True,
                "explicit_drop": True,
                "distinct_surviving_ideas": True,
            },
        }

    def inventory(self) -> dict[str, Any]:
        return {
            "records": dict(self.records),
            "idea_input_ids": list(self.idea_input_ids),
            "allowed_input_ids": set(self.allowed_input_ids),
            "kind_by_input": dict(self.kind_by_input),
            "src_by_input": {key: list(value) for key, value in self.src_by_input.items()},
            "transcript": self.transcript,
        }


def build_synthetic_fixture() -> SyntheticConsolidationFixtureV20:
    payload = fixture_payload()
    assert_synthetic_identity(
        window_id=CANARY_WINDOW_ID,
        transcript_id=CANARY_TRANSCRIPT_ID,
        src_ids=SYNTHETIC_SRC_IDS,
        local_window_ids=SYNTHETIC_WINDOW_IDS,
    )
    reject_real_project_input(payload)
    records = {item["id"]: item for item in all_records()}
    transcript = make_transcript(
        SYNTHETIC_TEXTS,
        src_ids=SYNTHETIC_SRC_IDS,
        transcript_id=CANARY_TRANSCRIPT_ID,
        language="en",
        content_sha256=fixture_hash(),
    )
    return SyntheticConsolidationFixtureV20(
        transcript=transcript,
        compact=synthetic_compact_input(),
        fixture_hash=fixture_hash(),
        idea_input_ids=tuple(idea_input_ids()),
        allowed_input_ids=frozenset(allowed_input_ids()),
        allowed_source_refs=frozenset(allowed_source_refs()),
        expected_dispositions=expected_dispositions(),
        kind_by_input=kind_by_input(),
        src_by_input=src_by_input(),
        records=records,
    )


def expected_valid_transport_v20() -> dict[str, Any]:
    """Réponse FakeAI / diagnostic. Pas une réparation d'une sortie provider."""
    return {
        "gm": {
            "th": "Community garden watering, compost, companion planting, and shared tools",
            "in": "Teach volunteers simple habits that protect plants, soil, and tools.",
            "ic": "high",
            "au": "Community garden volunteers",
            "ac": "medium",
            "vo": "Practical workshop speech with concrete garden examples.",
        },
        "t": [
            {"h": "T1", "v": "Dawn watering", "m": ["SYN:T001"]},
            {
                "h": "T2",
                "v": "Soil care and companion planting",
                "m": ["SYN:T002"],
            },
        ],
        "i": [
            {
                "h": "I1",
                "v": "Water garden beds at dawn so leaves dry before noon.",
                "m": ["SYN:I001"],
                "p": "central",
            },
            {
                "h": "I2",
                "v": "Kitchen-scrap compost feeds garden soil without bottled fertilizer.",
                "m": ["SYN:I002", "SYN:I003"],
                "p": "supporting",
            },
            {
                "h": "I3",
                "v": "Pairing tomatoes with basil reduces pest pressure on the fruit.",
                "m": ["SYN:I004"],
                "p": "supporting",
            },
            {
                "h": "I4",
                "v": "Shared tools should be cleaned and returned to the shed after each session.",
                "m": ["SYN:I005"],
                "p": "supporting",
            },
            {
                "h": "I5",
                "v": "Rain barrels collect roof water for dry-week irrigation.",
                "m": ["SYN:I007"],
                "p": "supporting",
            },
        ],
        "x": [
            {"h": "E1", "l": ["SYN:E001"], "g": ["I1"]},
            {"h": "E2", "l": ["SYN:E002"], "g": ["I3"]},
        ],
        "f": [{"h": "F1", "l": ["SYN:F001"]}],
        "u": [{"h": "U1", "l": ["SYN:U001"]}],
        "drop": [{"i": "SYN:I006", "w": "non_substantive_fragment"}],
    }


__all__ = [
    "SYNTHETIC_TEXTS",
    "SyntheticConsolidationFixtureV20",
    "all_records",
    "allowed_input_ids",
    "allowed_source_refs",
    "build_synthetic_fixture",
    "expected_dispositions",
    "expected_valid_transport_v20",
    "fixture_hash",
    "fixture_payload",
    "idea_input_ids",
    "kind_by_input",
    "src_by_input",
    "synthetic_compact_input",
]
