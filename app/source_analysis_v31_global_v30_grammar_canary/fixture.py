"""Fixture synthétique atelier jardin communautaire — aucun contenu pastoral. 0 provider."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from app.file_utils import content_hash
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_fixtures import make_transcript
from app.source_analysis_v31_global_v30_grammar_canary.constants import (
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    SCHEMA_VERSION,
    SYNTHETIC_SRC_IDS,
    SYNTHETIC_WINDOW_IDS,
    SYNTHESIZED_IDEA_MAX_CHARS,
)
from app.source_analysis_v31_global_v30_grammar_canary.guard import (
    assert_synthetic_identity,
    reject_real_project_input,
)

SYNTHETIC_TEXTS = (
    "Water the shared beds at dawn so leaves dry before noon.",
    "A volunteer waters the tomato row twice each week at sunrise.",
    "Kitchen scraps composted on site feed garden soil without synthetic fertilizer.",
    "um yeah",
    "On-site kitchen-scrap compost feeds the soil without bottled fertilizer.",
    "Planting basil beside tomatoes reduces pest pressure on the fruit.",
    "Shared tools must be cleaned and returned to the shed after each session.",
    "Last season the basil row next to tomatoes had fewer chewed leaves.",
    "The workshop booklet cites the Greenlane Garden Almanac, page 12.",
    "Rain barrels store roof runoff for dry-week irrigation.",
    "It is unclear whether the first frost usually arrives in October.",
    "Gardeners still debate the usual first-frost week.",
)

MERGE_PROPOSITION = (
    "On-site kitchen-scrap compost feeds garden soil without bottled or synthetic fertilizer."
)
assert len(MERGE_PROPOSITION) <= SYNTHESIZED_IDEA_MAX_CHARS


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
                "id": "SYN:W011",
                "theme": "Dawn watering for a shared garden workshop",
                "intent": "Show a simple watering habit that protects leaves.",
                "ic": "high",
                "aud": "Community garden volunteers",
                "ac": "medium",
                "owned": ["SRC998201", "SRC998202", "SRC998203", "SRC998204", "SRC998209"],
                "records": [
                    _record("SYN:T011", "TOPIC", "Dawn watering", ["SRC998201"]),
                    _record(
                        "SYN:I011",
                        "IDEA",
                        "Water the shared beds at dawn so leaves dry before noon.",
                        ["SRC998201"],
                        metadata=["central"],
                        links=["SYN:T011"],
                    ),
                    _record(
                        "SYN:I012",
                        "IDEA",
                        "Kitchen scraps composted on site feed garden soil without synthetic fertilizer.",
                        ["SRC998203"],
                        metadata=["supporting"],
                    ),
                    _record(
                        "SYN:I016",
                        "IDEA",
                        "um yeah",
                        ["SRC998204"],
                        metadata=["minor"],
                    ),
                    _record(
                        "SYN:E011",
                        "EXAMPLE",
                        "A volunteer waters the tomato row twice each week at sunrise.",
                        ["SRC998202"],
                        metadata=["example"],
                        links=["SYN:I011"],
                    ),
                    _record(
                        "SYN:F011",
                        "REFERENCE",
                        "Greenlane Garden Almanac, page 12",
                        ["SRC998209"],
                        metadata=["book", "partial"],
                    ),
                    _record(
                        "SYN:L011",
                        "RELATION",
                        "supports",
                        [],
                        links=["SYN:I011", "SYN:T011"],
                    ),
                ],
            },
            {
                "id": "SYN:W012",
                "theme": "Soil care, companion planting, and shared tools",
                "intent": "Describe soil feeding, a tomato-basil pairing, and tool care.",
                "ic": "medium",
                "aud": "Weekend garden volunteers",
                "ac": "medium",
                "owned": [
                    "SRC998205",
                    "SRC998206",
                    "SRC998207",
                    "SRC998208",
                    "SRC998210",
                    "SRC998211",
                    "SRC998212",
                ],
                "records": [
                    _record(
                        "SYN:T012",
                        "TOPIC",
                        "Soil care and companion planting",
                        ["SRC998205"],
                    ),
                    _record(
                        "SYN:I013",
                        "IDEA",
                        "On-site kitchen-scrap compost feeds the soil without bottled fertilizer.",
                        ["SRC998206"],
                        metadata=["supporting"],
                        links=["SYN:T012"],
                    ),
                    _record(
                        "SYN:I014",
                        "IDEA",
                        "Planting basil beside tomatoes reduces pest pressure on the fruit.",
                        ["SRC998207"],
                        metadata=["supporting"],
                    ),
                    _record(
                        "SYN:I015",
                        "IDEA",
                        "Shared tools must be cleaned and returned to the shed after each session.",
                        ["SRC998208"],
                        metadata=["supporting"],
                    ),
                    _record(
                        "SYN:I017",
                        "IDEA",
                        "Rain barrels store roof runoff for dry-week irrigation.",
                        ["SRC998211"],
                        metadata=["supporting"],
                    ),
                    _record(
                        "SYN:E012",
                        "EXAMPLE",
                        "Last season the basil row next to tomatoes had fewer chewed leaves.",
                        ["SRC998210"],
                        metadata=["anecdote"],
                        links=["SYN:I014"],
                    ),
                    _record(
                        "SYN:U011",
                        "UNCERTAINTY",
                        "It is unclear whether the first frost usually arrives in October.",
                        ["SRC998212"],
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
        "SYN:I011": "KEEP",
        "SYN:I012": "MERGE_EQUIVALENT",
        "SYN:I013": "MERGE_EQUIVALENT",
        "SYN:I014": "KEEP",
        "SYN:I015": "KEEP",
        "SYN:I016": "DROP",
        "SYN:I017": "KEEP",
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
class SyntheticConsolidationFixtureV30:
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
                "local_relation_hints": 1,
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


def build_synthetic_fixture() -> SyntheticConsolidationFixtureV30:
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
    return SyntheticConsolidationFixtureV30(
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


def expected_valid_transport_v30() -> dict[str, Any]:
    """Réponse FakeAI / diagnostic. Pas une réparation d'une sortie provider."""
    return {
        "gm": {
            "th": "Community garden workshop on watering, compost, companion planting, and tools",
            "in": "Teach volunteers simple habits that protect plants, soil, and tools.",
            "ic": "high",
            "au": "Community garden volunteers",
            "ac": "medium",
            "vo": "Practical workshop speech with concrete garden examples.",
        },
        "t": [
            {"h": "T1", "v": "Dawn watering", "m": ["SYN:T011"]},
            {
                "h": "T2",
                "v": "Soil care and companion planting",
                "m": ["SYN:T012"],
            },
        ],
        "i": [
            {
                "h": "I1",
                "m": ["SYN:I011"],
                "p": "central",
            },
            {
                "h": "I2",
                "v": MERGE_PROPOSITION,
                "m": ["SYN:I012", "SYN:I013"],
                "p": "supporting",
            },
            {
                "h": "I3",
                "m": ["SYN:I014"],
                "p": "supporting",
            },
            {
                "h": "I4",
                "m": ["SYN:I015"],
                "p": "supporting",
            },
            {
                "h": "I5",
                "m": ["SYN:I017"],
                "p": "supporting",
            },
        ],
        "x": [
            {"h": "E1", "l": ["SYN:E011"], "g": ["I1"]},
            {"h": "E2", "l": ["SYN:E012"], "g": ["I3"]},
        ],
        "f": [{"h": "F1", "l": ["SYN:F011"]}],
        "u": [{"h": "U1", "l": ["SYN:U011"]}],
        "drop": [{"i": "SYN:I016", "w": "non_substantive_fragment"}],
    }


def equivalent_v20_style_transport() -> dict[str, Any]:
    """Même fixture avec v sur chaque IDEA — comparaison compactness offline."""
    payload = copy.deepcopy(expected_valid_transport_v30())
    local = {item["id"]: item["v"] for item in all_records() if item["k"] == "IDEA"}
    ideas = []
    for idea in payload["i"]:
        row = dict(idea)
        members = list(row.get("m") or [])
        if len(members) == 1:
            row["v"] = local[members[0]]
        ideas.append(row)
    payload["i"] = ideas
    return payload


def with_forbidden_single_member_rewrite() -> dict[str, Any]:
    payload = expected_valid_transport_v30()
    payload["i"][0]["v"] = "Water the shared beds at dawn so leaves dry before noon."
    return payload


def with_missing_synthesis() -> dict[str, Any]:
    payload = expected_valid_transport_v30()
    payload["i"][1].pop("v", None)
    return payload


def with_oversized_merge_v() -> dict[str, Any]:
    payload = expected_valid_transport_v30()
    payload["i"][1]["v"] = "x" * (SYNTHESIZED_IDEA_MAX_CHARS + 1)
    return payload


__all__ = [
    "MERGE_PROPOSITION",
    "SYNTHETIC_TEXTS",
    "SyntheticConsolidationFixtureV30",
    "all_records",
    "allowed_input_ids",
    "allowed_source_refs",
    "build_synthetic_fixture",
    "equivalent_v20_style_transport",
    "expected_dispositions",
    "expected_valid_transport_v30",
    "fixture_hash",
    "fixture_payload",
    "idea_input_ids",
    "kind_by_input",
    "src_by_input",
    "synthetic_compact_input",
    "with_forbidden_single_member_rewrite",
    "with_missing_synthesis",
    "with_oversized_merge_v",
]
