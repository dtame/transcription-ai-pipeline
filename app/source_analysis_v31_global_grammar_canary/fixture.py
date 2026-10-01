"""Fixture synthétique jardin communautaire — aucun contenu pastoral."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.file_utils import content_hash
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_fixtures import make_transcript
from app.source_analysis_v31_global_grammar_canary.constants import (
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    SCHEMA_VERSION,
    SYNTHETIC_SRC_IDS,
    SYNTHETIC_WINDOW_IDS,
)
from app.source_analysis_v31_global_grammar_canary.guard import (
    assert_synthetic_identity,
    reject_real_project_input,
)

SYNTHETIC_TEXTS = (
    "Water the beds at dawn so leaves dry before noon.",
    "A volunteer waters the tomato row twice each week at sunrise.",
    "Compost from kitchen scraps feeds the soil without synthetic fertilizer.",
    "and then uh",
    "Healthy soil holds moisture and supports shallow roots.",
    "Kitchen-scrap compost feeds garden soil without bottled fertilizer.",
    "Pairing tomatoes with basil reduces pest pressure on the fruit.",
    "Last season the basil row next to tomatoes had fewer chewed leaves.",
    "The workshop booklet cites the Greenlane Garden Almanac, page 12.",
    "It is unclear whether the first frost usually arrives in October.",
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
    }


def synthetic_compact_input() -> dict[str, Any]:
    return {
        "contract": "normalized-consolidation-input-1.0",
        "is_source_map": False,
        "windows": [
            {
                "id": "SYN001",
                "theme": "Dawn watering for a shared garden",
                "intent": "Show a simple watering habit that protects leaves.",
                "ic": "high",
                "aud": "Community garden volunteers",
                "ac": "medium",
                "owned": ["SRC998001", "SRC998002", "SRC998003", "SRC998004"],
                "records": [
                    _record(
                        "SYN001:T1",
                        "TOPIC",
                        "Dawn watering",
                        ["SRC998001"],
                    ),
                    _record(
                        "SYN001:I1",
                        "IDEA",
                        "Water garden beds at dawn so leaves dry before noon.",
                        ["SRC998001"],
                        metadata=["central"],
                        links=["SYN001:T1"],
                    ),
                    _record(
                        "SYN001:I2",
                        "IDEA",
                        "Compost from kitchen scraps feeds soil without synthetic fertilizer.",
                        ["SRC998003"],
                        metadata=["supporting"],
                    ),
                    _record(
                        "SYN001:I3",
                        "IDEA",
                        "and then uh",
                        ["SRC998004"],
                        metadata=["minor"],
                    ),
                    _record(
                        "SYN001:E1",
                        "EXAMPLE",
                        "A volunteer waters the tomato row twice each week at sunrise.",
                        ["SRC998002"],
                        metadata=["example"],
                        links=["SYN001:I1"],
                    ),
                    _record(
                        "SYN001:F1",
                        "REFERENCE",
                        "Greenlane Garden Almanac, page 12",
                        ["SRC998009"],
                        metadata=["book", "partial"],
                    ),
                    _record(
                        "SYN001:L1",
                        "RELATION",
                        "supports",
                        [],
                        links=["SYN001:I1", "SYN001:T1"],
                    ),
                ],
            },
            {
                "id": "SYN002",
                "theme": "Soil care and companion planting",
                "intent": "Describe soil feeding and a tomato-basil pairing.",
                "ic": "medium",
                "aud": "Weekend garden volunteers",
                "ac": "medium",
                "owned": ["SRC998005", "SRC998006", "SRC998007", "SRC998008", "SRC998010"],
                "records": [
                    _record(
                        "SYN002:T1",
                        "TOPIC",
                        "Soil care",
                        ["SRC998005"],
                    ),
                    _record(
                        "SYN002:I1",
                        "IDEA",
                        "Kitchen-scrap compost feeds garden soil without bottled fertilizer.",
                        ["SRC998006"],
                        metadata=["supporting"],
                        links=["SYN002:T1"],
                    ),
                    _record(
                        "SYN002:I2",
                        "IDEA",
                        "Pairing tomatoes with basil reduces pest pressure on the fruit.",
                        ["SRC998007"],
                        metadata=["supporting"],
                    ),
                    _record(
                        "SYN002:E1",
                        "EXAMPLE",
                        "Last season the basil row next to tomatoes had fewer chewed leaves.",
                        ["SRC998008"],
                        metadata=["anecdote"],
                        links=["SYN002:I2"],
                    ),
                    _record(
                        "SYN002:U1",
                        "UNCERTAINTY",
                        "It is unclear whether the first frost usually arrives in October.",
                        ["SRC998010"],
                        metadata=["ambiguous_meaning", "medium"],
                    ),
                    _record(
                        "SYN002:L1",
                        "RELATION",
                        "supports",
                        [],
                        links=["SYN002:I2", "SYN002:I1"],
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


def expected_dispositions() -> dict[str, str]:
    return {
        "SYN001:I1": "KEEP",
        "SYN001:I2": "MERGE_EQUIVALENT",
        "SYN001:I3": "DROP",
        "SYN002:I1": "MERGE_EQUIVALENT",
        "SYN002:I2": "LINK_RELATED",
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
class SyntheticConsolidationFixture:
    transcript: TranscriptInput
    compact: dict[str, Any]
    fixture_hash: str
    idea_input_ids: tuple[str, ...]
    allowed_input_ids: frozenset[str]
    allowed_source_refs: frozenset[str]
    expected_dispositions: dict[str, str]

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
                "local_ideas": 5,
                "local_examples": 2,
                "local_references": 1,
                "local_uncertainties": 1,
                "local_relation_hints": 2,
                "global_topics_min": 2,
                "global_ideas_min": 3,
                "keep": True,
                "merge_equivalent": True,
                "link_related": True,
                "drop": True,
                "repetition": True,
            },
        }


def build_synthetic_fixture() -> SyntheticConsolidationFixture:
    payload = fixture_payload()
    assert_synthetic_identity(
        window_id=CANARY_WINDOW_ID,
        transcript_id=CANARY_TRANSCRIPT_ID,
        src_ids=SYNTHETIC_SRC_IDS,
        local_window_ids=SYNTHETIC_WINDOW_IDS,
    )
    reject_real_project_input(payload)
    transcript = make_transcript(
        SYNTHETIC_TEXTS,
        src_ids=SYNTHETIC_SRC_IDS,
        transcript_id=CANARY_TRANSCRIPT_ID,
        language="en",
        content_sha256=fixture_hash(),
    )
    return SyntheticConsolidationFixture(
        transcript=transcript,
        compact=synthetic_compact_input(),
        fixture_hash=fixture_hash(),
        idea_input_ids=tuple(idea_input_ids()),
        allowed_input_ids=frozenset(allowed_input_ids()),
        allowed_source_refs=frozenset(allowed_source_refs()),
        expected_dispositions=expected_dispositions(),
    )


def expected_valid_transport() -> dict[str, Any]:
    """Réponse FakeAI / diagnostic. Pas une réparation d'une sortie provider."""
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
            {
                "h": "P1",
                "k": "REPETITION",
                "v": "Soil feeding without bottled fertilizer is restated across two local notes.",
                "s": ["SRC998003", "SRC998006"],
                "m": ["recap", "I2", "I3"],
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
                "a": "I2",
                "b": "T2",
                "s": ["SRC998003"],
            },
            {
                "t": "develops",
                "a": "I3",
                "b": "I2",
                "s": ["SRC998007"],
            },
        ],
        "d": [
            {"i": "SYN001:I1", "o": "KEEP", "g": "I1", "w": "same watering proposition"},
            {
                "i": "SYN001:I2",
                "o": "MERGE_EQUIVALENT",
                "g": "I2",
                "w": "same compost proposition as SYN002:I1",
            },
            {
                "i": "SYN001:I3",
                "o": "DROP",
                "g": "",
                "w": "transport_artifact",
            },
            {
                "i": "SYN002:I1",
                "o": "MERGE_EQUIVALENT",
                "g": "I2",
                "w": "same compost proposition as SYN001:I2",
            },
            {
                "i": "SYN002:I2",
                "o": "LINK_RELATED",
                "g": "I3",
                "w": "related to compost idea I2 but distinct",
            },
            {"i": "SYN001:T1", "o": "KEEP", "g": "T1", "w": ""},
            {"i": "SYN002:T1", "o": "KEEP", "g": "T2", "w": ""},
            {"i": "SYN001:E1", "o": "KEEP", "g": "E1", "w": ""},
            {"i": "SYN002:E1", "o": "KEEP", "g": "E2", "w": ""},
            {"i": "SYN001:F1", "o": "KEEP", "g": "F1", "w": ""},
            {"i": "SYN002:U1", "o": "KEEP", "g": "U1", "w": ""},
            {
                "i": "SYN001:L1",
                "o": "OTHER",
                "g": "",
                "w": "local hint; global relation is source-grounded separately",
            },
            {
                "i": "SYN002:L1",
                "o": "OTHER",
                "g": "",
                "w": "local hint; not copied as global truth",
            },
        ],
    }


__all__ = [
    "SYNTHETIC_TEXTS",
    "SyntheticConsolidationFixture",
    "all_records",
    "allowed_input_ids",
    "allowed_source_refs",
    "build_synthetic_fixture",
    "expected_dispositions",
    "expected_valid_transport",
    "fixture_hash",
    "fixture_payload",
    "idea_input_ids",
    "synthetic_compact_input",
]
