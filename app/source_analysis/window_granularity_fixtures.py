"""Fixtures FakeAI pour la politique de granularité 3B.7.7A.2."""

from __future__ import annotations

from app.source_analysis.window_fixtures import make_transcript, window_for
from app.source_analysis.window_granularity import (
    HARD_CEILINGS,
    OVERFLOW_TOKEN,
    OVERFLOW_UNCERTAINTY_KIND,
    OVERFLOW_UNCERTAINTY_SEVERITY,
    TOTAL_HARD_CEILING,
)


def _record(kind, value, source_refs=None, links=None, metadata=None):
    return {
        "k": kind,
        "v": value,
        "s": list(source_refs or []),
        "l": list(links or []),
        "m": list(metadata or []),
    }


def grouping_transcript():
    return make_transcript(
        (
            "Faith changes how a trial is crossed.",
            "Faith still changes the crossing of hardship.",
            "The same faith keeps shaping the crossing.",
            "A distinct instruction: keep walking through the valley.",
            "A man still prayed each morning before the work began.",
        )
    )


def bounded_success_transport(*, owned: tuple[str, ...]) -> dict:
    a, b = owned[0], owned[1] if len(owned) > 1 else owned[0]
    return {
        "theme": "Faith during trials",
        "intent": "Teach what faith does in hardship.",
        "ic": "high",
        "aud": "Believers facing trials.",
        "ac": "medium",
        "records": [
            _record("INTENT_KIND", "enseigner"),
            _record("AUDIENCE_KIND", "croyants"),
            _record("TOPIC", "Faith in trial", [a, b], [], ["What faith changes."]),
            _record(
                "IDEA",
                "Faith changes how a trial is crossed.",
                [a, b],
                [2],
                ["claim", "central"],
            ),
            _record(
                "IDEA",
                "Keep walking through the valley.",
                [owned[3] if len(owned) > 3 else a],
                [2],
                ["instruction", "supporting"],
            ),
            _record("RELATION", "supports", [], [4, 3], []),
            _record(
                "EXAMPLE",
                "A man who still prayed each morning.",
                [owned[4] if len(owned) > 4 else a],
                [3],
                ["anecdote"],
            ),
            _record(
                "REFERENCE",
                "Paul says somewhere",
                [a],
                [],
                ["biblical", "vague", ""],
            ),
            _record(
                "UNCERTAINTY",
                "The Pauline reference is not located.",
                [a],
                [],
                ["incomplete_reference", "medium"],
            ),
            _record(
                "REPETITION",
                "Faith-crossing claim restated and developed.",
                [a, b],
                [3, 4],
                ["development"],
            ),
            _record("VOICE", "didactic", [], [], ["tone"]),
            _record("VOICE", "oral accessible", [], [], ["register"]),
        ],
    }


def multi_src_idea_transport(*, owned: tuple[str, ...]) -> dict:
    refs = list(owned[:3]) if len(owned) >= 3 else list(owned)
    return {
        "theme": "Faith during trials",
        "intent": "Teach what faith does in hardship.",
        "ic": "high",
        "aud": "Believers facing trials.",
        "ac": "medium",
        "records": [
            _record("TOPIC", "Faith in trial", refs, [], ["Shared theme."]),
            _record(
                "IDEA",
                "Faith changes how a trial is crossed.",
                refs,
                [0],
                ["claim", "central"],
            ),
        ],
    }


def two_similar_ideas_transport(*, owned: tuple[str, ...]) -> dict:
    a, b = owned[0], owned[1] if len(owned) > 1 else owned[0]
    return {
        "theme": "Faith during trials",
        "intent": "Teach what faith does in hardship.",
        "ic": "high",
        "aud": "Believers facing trials.",
        "ac": "medium",
        "records": [
            _record("TOPIC", "Faith in trial", [a], [], ["Theme."]),
            _record(
                "IDEA",
                "Faith changes how a trial is crossed.",
                [a],
                [0],
                ["claim", "central"],
            ),
            _record(
                "IDEA",
                "Faith still changes the crossing of hardship.",
                [b],
                [0],
                ["claim", "supporting"],
            ),
        ],
    }


def repetition_grouped_transport(*, owned: tuple[str, ...]) -> dict:
    a, b = owned[0], owned[1] if len(owned) > 1 else owned[0]
    return {
        "theme": "Faith during trials",
        "intent": "Teach persistence.",
        "ic": "high",
        "aud": "Believers facing trials.",
        "ac": "medium",
        "records": [
            _record("TOPIC", "Persistence", [a, b], [], ["Keep walking."]),
            _record(
                "IDEA",
                "Keep walking through the valley.",
                [a],
                [0],
                ["instruction", "central"],
            ),
            _record(
                "IDEA",
                "The walk itself is the teaching of persistence.",
                [b],
                [0],
                ["explanation", "supporting"],
            ),
            _record(
                "REPETITION",
                "Walking instruction restated and developed.",
                [a, b],
                [1, 2],
                ["development"],
            ),
        ],
    }


def sparse_relations_transport(*, owned: tuple[str, ...], idea_count: int = 8) -> dict:
    src = owned[0]
    records = [
        _record("TOPIC", "Faith in trial", [src], [], ["Theme."]),
    ]
    for index in range(idea_count):
        records.append(
            _record(
                "IDEA",
                f"Distinct teaching point {index + 1} about walking by faith.",
                [owned[index % len(owned)]],
                [0],
                ["claim", "supporting" if index else "central"],
            )
        )
    records.append(_record("RELATION", "supports", [], [2, 1], []))
    records.append(_record("RELATION", "explains", [], [3, 1], []))
    return {
        "theme": "Faith during trials",
        "intent": "Teach several related points.",
        "ic": "high",
        "aud": "Believers facing trials.",
        "ac": "medium",
        "records": records,
    }


def idea_hard_limit_transport(*, owned: tuple[str, ...]) -> dict:
    src = owned[0]
    records = [_record("TOPIC", "Overflow ideas", [src], [], ["Too many ideas."])]
    for index in range(HARD_CEILINGS["IDEA"] + 1):
        records.append(
            _record(
                "IDEA",
                f"Distinct semantic unit {index + 1:02d} about faith and trial.",
                [src],
                [0],
                ["claim", "minor"],
            )
        )
    return {
        "theme": "Faith during trials",
        "intent": "Over-produce ideas.",
        "ic": "high",
        "aud": "Believers.",
        "ac": "medium",
        "records": records,
    }


def total_limit_transport(*, owned: tuple[str, ...]) -> dict:
    src = owned[0]
    records: list[dict] = []
    mix = (
        ("TOPIC", HARD_CEILINGS["TOPIC"], [src], ["Summary of a topic."]),
        ("IDEA", HARD_CEILINGS["IDEA"], [src], ["claim", "minor"]),
        ("EXAMPLE", HARD_CEILINGS["EXAMPLE"], [src], ["anecdote"]),
        ("REFERENCE", HARD_CEILINGS["REFERENCE"], [src], ["biblical", "vague", ""]),
        ("UNCERTAINTY", HARD_CEILINGS["UNCERTAINTY"], [src], ["ambiguous_meaning", "low"]),
        ("REPETITION", HARD_CEILINGS["REPETITION"], [src], ["verbatim"]),
        ("VOICE", HARD_CEILINGS["VOICE"], [], ["tone"]),
        ("INTENT_KIND", 3, [], []),
    )
    for kind, count, refs, metadata in mix:
        for index in range(count):
            records.append(
                _record(
                    kind,
                    f"{kind} unit {index + 1:02d} stays inside its kind ceiling.",
                    refs,
                    [0] if kind == "REPETITION" else [],
                    list(metadata),
                )
            )
    assert len(records) > TOTAL_HARD_CEILING
    return {
        "theme": "Faith during trials",
        "intent": "Exceed total record ceiling.",
        "ic": "high",
        "aud": "Believers.",
        "ac": "medium",
        "records": records,
    }


def relation_explosion_transport(*, owned: tuple[str, ...]) -> dict:
    src = owned[0]
    idea_count = 10
    records = [_record("TOPIC", "Faith in trial", [src], [], ["Theme."])]
    for index in range(idea_count):
        records.append(
            _record(
                "IDEA",
                f"Idea {index + 1} remains within the idea ceiling.",
                [src],
                [0],
                ["claim", "supporting"],
            )
        )
    # Pairwise among ideas — exceeds RELATION hard ceiling.
    idea_start = 1
    for left in range(idea_start, idea_start + idea_count):
        for right in range(left + 1, idea_start + idea_count):
            records.append(_record("RELATION", "supports", [], [right, left], []))
    return {
        "theme": "Faith during trials",
        "intent": "Enumerate every pair.",
        "ic": "high",
        "aud": "Believers.",
        "ac": "medium",
        "records": records,
    }


def overflow_signal_transport(*, owned: tuple[str, ...]) -> dict:
    src = owned[0]
    payload = bounded_success_transport(owned=owned)
    payload["records"].append(
        _record(
            "UNCERTAINTY",
            OVERFLOW_TOKEN,
            [src],
            [],
            [OVERFLOW_UNCERTAINTY_KIND, OVERFLOW_UNCERTAINTY_SEVERITY],
        )
    )
    return payload


def oversized_idea_text_transport(*, owned: tuple[str, ...]) -> dict:
    src = owned[0]
    long_value = "Faith changes the crossing. " * 20
    return {
        "theme": "Faith during trials",
        "intent": "Teach what faith does in hardship.",
        "ic": "high",
        "aud": "Believers facing trials.",
        "ac": "medium",
        "records": [
            _record("TOPIC", "Faith in trial", [src], [], ["Theme."]),
            _record("IDEA", long_value, [src], [0], ["claim", "central"]),
        ],
    }


def default_window():
    transcript = grouping_transcript()
    return transcript, window_for(transcript)
