"""Fixtures FakeAI V3 — transcript synthétique, pas le corpus pastoral."""

from __future__ import annotations

from typing import Any

from app.source_analysis.consolidation_models import ConsolidationInput
from app.source_analysis_local_v2.constants import HARD_CEILINGS
from app.source_analysis_local_v2.fixtures import (
    default_recovery,
    global_v2_transport,
    keep_all_v2_transport,
    seven_window_plan,
)
from app.source_analysis_local_v3.handles import recommended_handle


def _record(kind, value, source_refs=None, handle="", links=None, metadata=None):
    return {
        "k": kind,
        "v": value,
        "s": list(source_refs or []),
        "h": handle,
        "l": list(links or []),
        "m": list(metadata or []),
    }


def _lite_idea_metadata(metadata: list[str] | None) -> list[str]:
    if not metadata:
        return []
    if len(metadata) == 1:
        return list(metadata)
    return [metadata[1]]


def to_v31_local_lite_transport(payload: dict) -> dict:
    """Dérive un payload local-lite en abandonnant le sous-type IDEA. Déterministe."""
    out = dict(payload)
    records = []
    for item in payload.get("records") or []:
        record = dict(item)
        if record.get("k") == "IDEA":
            record["m"] = _lite_idea_metadata(list(record.get("m") or []))
        records.append(record)
    out["records"] = records
    return out


def v31_success_transport(*, owned_src: str = "SRC000001") -> dict:
    return to_v31_local_lite_transport(v3_success_transport(owned_src=owned_src))


def v31_prompt_example_transport(*, owned_src: str = "SRC999001") -> dict:
    return to_v31_local_lite_transport(v3_prompt_example_transport(owned_src=owned_src))


def v31_i44_proposition_illustration(*, owned_src: str = "SRC000001") -> dict:
    return {
        "theme": "A teaching is illustrated, not replaced, by a story",
        "intent": "Separate proposition from illustration.",
        "ic": "high",
        "aud": "Listeners who confuse story with teaching.",
        "ac": "medium",
        "records": [
            _record("TOPIC", "Teaching and illustration", [owned_src], "T1", [], ["Keep them distinct."]),
            _record(
                "IDEA",
                "Leadership must serve the common good, not private gain.",
                [owned_src],
                "I1",
                ["T1"],
                ["central"],
            ),
            _record(
                "EXAMPLE",
                "A national leader blamed the economy while wearing a borrowed shirt.",
                [owned_src],
                "",
                ["I1"],
                ["anecdote"],
            ),
        ],
    }


def v31_a22_pattern_transports(*, owned_src: str = "SRC000001") -> list[dict]:
    """Équivalents structurels des motifs A.22 : proposition + illustration."""
    patterns = [
        (
            "Colonial tutors trained appearance, not character.",
            "A student was told to change his shirt before class.",
        ),
        (
            "A minister's formula does not replace a lived testimony.",
            "The speaker recounted how a pastor used a memorized phrase.",
        ),
        (
            "The body is not interchangeable spare parts.",
            "A pig heart and liver were mentioned as surgical images.",
        ),
        (
            "A nation's leader is not the same as its economy.",
            "The illustration named a head of state and market hardship.",
        ),
    ]
    out = []
    for index, (proposition, illustration) in enumerate(patterns, start=1):
        out.append(
            {
                "theme": f"Pattern {index} keeps teaching distinct from story",
                "intent": "Extract proposition and illustration separately.",
                "ic": "high",
                "aud": "Analysts of mixed passages.",
                "ac": "medium",
                "records": [
                    _record(
                        "TOPIC",
                        f"Pattern {index}",
                        [owned_src],
                        "T1",
                        [],
                        ["Proposition plus illustration."],
                    ),
                    _record(
                        "IDEA",
                        proposition,
                        [owned_src],
                        "I1",
                        ["T1"],
                        ["central"],
                    ),
                    _record(
                        "EXAMPLE",
                        illustration,
                        [owned_src],
                        "",
                        ["I1"],
                        ["anecdote"],
                    ),
                ],
            }
        )
    return out


def v31_example_empty_link_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = v31_success_transport(owned_src=owned_src)
    example = next(item for item in payload["records"] if item["k"] == "EXAMPLE")
    example["l"] = []
    return payload


def v31_two_distinct_ideas_same_importance(*, owned_src: str = "SRC000001") -> dict:
    return {
        "theme": "Two teachings remain two teachings",
        "intent": "Prevent silent merge when subtype is absent.",
        "ic": "high",
        "aud": "Anyone who would collapse distinct ideas.",
        "ac": "medium",
        "records": [
            _record("TOPIC", "Distinct teachings", [owned_src], "T1", [], ["Keep them apart."]),
            _record(
                "IDEA",
                "Faith changes how a trial is crossed.",
                [owned_src],
                "I1",
                ["T1"],
                ["central"],
            ),
            _record(
                "IDEA",
                "Prayer stays when the valley is dark.",
                [owned_src],
                "I2",
                ["T1"],
                ["central"],
            ),
        ],
    }


def v3_success_transport(*, owned_src: str = "SRC000001") -> dict:
    return {
        "theme": "Faith changes how trials are crossed",
        "intent": "Teach what faith does in hardship.",
        "ic": "high",
        "aud": "Believers facing trials.",
        "ac": "medium",
        "records": [
            _record("TOPIC", "Faith in trial", [owned_src], "T1", [], ["What faith changes."]),
            _record(
                "IDEA",
                "Faith changes the crossing.",
                [owned_src],
                "I1",
                ["T1"],
                ["claim", "central"],
            ),
            _record(
                "IDEA",
                "Prayer stays when the valley is dark.",
                [owned_src],
                "I2",
                ["T1"],
                ["instruction", "supporting"],
            ),
            _record("RELATION", "supports", [], "", ["I2", "I1"], []),
            _record(
                "EXAMPLE",
                "A man still prayed each morning.",
                [owned_src],
                "",
                ["I1"],
                ["anecdote"],
            ),
            _record(
                "REFERENCE",
                "Paul speaks of weakness as strength.",
                [owned_src],
                "",
                [],
                ["biblical", "vague", ""],
            ),
            _record(
                "UNCERTAINTY",
                "The exact Pauline wording is not located.",
                [owned_src],
                "",
                [],
                ["incomplete_reference", "medium"],
            ),
        ],
    }


def v3_prompt_example_transport(*, owned_src: str = "SRC999001") -> dict:
    second = "SRC999002"
    return {
        "theme": "Planning prevents avoidable mistakes",
        "intent": "Teach careful checking.",
        "ic": "high",
        "aud": "Anyone who plans work.",
        "ac": "medium",
        "records": [
            _record("TOPIC", "Planning", [owned_src], "T1", [], ["Careful plans."]),
            _record("TOPIC", "Checking", [second], "T2", [], ["Verify twice."]),
            _record(
                "IDEA",
                "Planning reduces mistakes.",
                [owned_src],
                "I1",
                ["T1"],
                ["claim", "central"],
            ),
            _record(
                "IDEA",
                "A second check catches gaps.",
                [second],
                "I2",
                ["T2"],
                ["claim", "supporting"],
            ),
            _record(
                "IDEA",
                "Checking serves planning.",
                [second],
                "I3",
                ["T1", "T2"],
                ["claim", "supporting"],
            ),
            _record("RELATION", "supports", [], "", ["I3", "I1"], []),
            _record(
                "EXAMPLE",
                "Check the plan twice.",
                [second],
                "",
                ["I2"],
                ["anecdote"],
            ),
        ],
    }


def v3_forward_handle_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = v3_success_transport(owned_src=owned_src)
    payload["records"] = [
        _record(
            "IDEA",
            "Faith changes the crossing.",
            [owned_src],
            "I1",
            ["T1"],
            ["claim", "central"],
        ),
        _record("TOPIC", "Faith in trial", [owned_src], "T1", [], ["What faith changes."]),
        _record(
            "EXAMPLE",
            "A man still prayed each morning.",
            [owned_src],
            "",
            ["I1"],
            ["anecdote"],
        ),
        _record(
            "IDEA",
            "Prayer stays when the valley is dark.",
            [owned_src],
            "I2",
            ["T1"],
            ["instruction", "supporting"],
        ),
        _record("RELATION", "supports", [], "", ["I2", "I1"], []),
        payload["records"][5],
        payload["records"][6],
    ]
    return payload


def v3_nonsequential_handle_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = v3_success_transport(owned_src=owned_src)
    payload["records"][0]["h"] = "T1"
    payload["records"][1]["h"] = "I3"
    payload["records"][1]["l"] = ["T1"]
    payload["records"][2]["h"] = "I7"
    payload["records"][2]["l"] = ["T1"]
    payload["records"][3]["l"] = ["I7", "I3"]
    payload["records"][4]["l"] = ["I3"]
    return payload


def v3_a15_synthetic_equivalent(*, owned_src: str = "SRC000001") -> dict:
    """
    Fixture diagnostique — PAS A.15 réparé.

    TOPICs d'abord, puis IDEAs. RELATION/EXAMPLE ciblent des I handles.
    Ils ne peuvent pas résoudre vers TOPIC parce que les TOPIC sont premiers.
    """
    return {
        "theme": "Spirit, food culture, and longevity",
        "intent": "Teach embodied faith without confusing topics for ideas.",
        "ic": "high",
        "aud": "Retreat listeners.",
        "ac": "medium",
        "records": [
            _record("TOPIC", "Spirit, soul, body preservation", [owned_src], "T1", [], ["Whole person."]),
            _record("TOPIC", "Hearing from God vs outside information", [owned_src], "T2", [], ["Discernment."]),
            _record("TOPIC", "Cultural eating habits", [owned_src], "T3", [], ["Food culture."]),
            _record(
                "IDEA",
                "The whole person is kept by God.",
                [owned_src],
                "I1",
                ["T1"],
                ["claim", "central"],
            ),
            _record(
                "IDEA",
                "Hearing God is not the same as collecting information.",
                [owned_src],
                "I2",
                ["T2"],
                ["claim", "supporting"],
            ),
            _record(
                "IDEA",
                "Food habits shift across generations.",
                [owned_src],
                "I3",
                ["T3"],
                ["observation", "supporting"],
            ),
            _record("RELATION", "explains", [], "", ["I1", "I2"], []),
            _record(
                "EXAMPLE",
                "A daughter treats meat as essential while the speaker sets it aside.",
                [owned_src],
                "",
                ["I3"],
                ["anecdote"],
            ),
        ],
    }


def insert_topic_before(transport: dict, *, owned_src: str = "SRC000001") -> dict:
    extra = _record(
        "TOPIC",
        "Unrelated inserted topic",
        [owned_src],
        "T99",
        [],
        ["Inserted later."],
    )
    out = dict(transport)
    out["records"] = [extra, *list(transport["records"])]
    return out


def insert_unrelated_idea(transport: dict, *, owned_src: str = "SRC000001") -> dict:
    extra = _record(
        "IDEA",
        "An unrelated inserted idea.",
        [owned_src],
        "I99",
        ["T1"] if any(r.get("h") == "T1" for r in transport["records"]) else [],
        ["claim", "supporting"],
    )
    out = dict(transport)
    records = list(transport["records"])
    first_idea = next(i for i, r in enumerate(records) if r["k"] == "IDEA")
    records.insert(first_idea, extra)
    out["records"] = records
    return out


def v3_over_limit_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = v3_success_transport(owned_src=owned_src)
    extras = []
    ceiling = HARD_CEILINGS["IDEA"]
    for index in range(ceiling + 1):
        extras.append(
            _record(
                "IDEA",
                f"Idea overflow {index}.",
                [owned_src],
                recommended_handle("IDEA", index + 10),
                ["T1"],
                ["claim", "supporting"],
            )
        )
    payload["records"] = [payload["records"][0], *extras]
    return payload


def gm_from_v3_input(consolidation_input: ConsolidationInput) -> dict[str, Any]:
    from app.source_analysis_local_v2.fixtures import gm_from_v2_input

    return gm_from_v2_input(consolidation_input)


def keep_all_v3_transport(consolidation_input: ConsolidationInput) -> dict[str, Any]:
    return keep_all_v2_transport(consolidation_input)


def global_v3_transport(consolidation_input: ConsolidationInput) -> dict[str, Any]:
    return global_v2_transport(consolidation_input)


__all__ = [
    "default_recovery",
    "global_v3_transport",
    "insert_topic_before",
    "insert_unrelated_idea",
    "keep_all_v3_transport",
    "seven_window_plan",
    "to_v31_local_lite_transport",
    "v3_a15_synthetic_equivalent",
    "v3_forward_handle_transport",
    "v3_nonsequential_handle_transport",
    "v3_over_limit_transport",
    "v3_prompt_example_transport",
    "v3_success_transport",
    "v31_a22_pattern_transports",
    "v31_example_empty_link_transport",
    "v31_i44_proposition_illustration",
    "v31_prompt_example_transport",
    "v31_success_transport",
    "v31_two_distinct_ideas_same_importance",
]
