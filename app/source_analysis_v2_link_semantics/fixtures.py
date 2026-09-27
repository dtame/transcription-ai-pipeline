"""Fixtures synthétiques A.14 — même scénario minuscule qu'A.13, liens corrigés."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.source_analysis_v2_grammar_canary.constants import SYNTHETIC_SRC_IDS


def _base(*, idea_links, example_links, extra_records=None) -> dict[str, Any]:
    records = [
        {
            "k": "TOPIC",
            "v": "Careful planning",
            "s": [SYNTHETIC_SRC_IDS[0]],
            "l": [],
            "m": ["Planning reduces avoidable mistakes"],
        },
        {
            "k": "IDEA",
            "v": "Careful planning reduces avoidable mistakes",
            "s": [SYNTHETIC_SRC_IDS[0]],
            "l": list(idea_links),
            "m": ["claim", "central"],
        },
        {
            "k": "EXAMPLE",
            "v": "Checking the plan twice as an example of careful planning",
            "s": [SYNTHETIC_SRC_IDS[1]],
            "l": list(example_links),
            "m": ["example"],
        },
    ]
    if extra_records:
        records.extend(extra_records)
    return {
        "theme": "synthetic canary: planning and mistake reduction",
        "intent": "synthetic test note only",
        "ic": "high",
        "aud": "synthetic test consumer",
        "ac": "medium",
        "records": records,
    }


def corrected_a13_transport() -> dict[str, Any]:
    """Même scénario A.13 ; IDEA → TOPIC 0 ; EXAMPLE → IDEA 1."""
    return _base(idea_links=[0], example_links=[1])


def self_link_transport() -> dict[str, Any]:
    """Reproduction A.13 : IDEA.l=[1], EXAMPLE.l=[2]."""
    return _base(idea_links=[1], example_links=[2])


def out_of_range_transport() -> dict[str, Any]:
    return _base(idea_links=[99], example_links=[1])


def wrong_kind_target_transport() -> dict[str, Any]:
    """EXAMPLE pointe vers TOPIC."""
    return _base(idea_links=[0], example_links=[0])


def duplicate_link_transport() -> dict[str, Any]:
    return _base(idea_links=[0, 0], example_links=[1])


def valid_multi_link_transport() -> dict[str, Any]:
    payload = _base(idea_links=[0], example_links=[1])
    payload["records"].append(
        {
            "k": "TOPIC",
            "v": "Checking twice",
            "s": [SYNTHETIC_SRC_IDS[1]],
            "l": [],
            "m": ["Verification habit."],
        }
    )
    payload["records"][1]["l"] = [0, 3]
    return payload


def forward_link_transport() -> dict[str, Any]:
    """IDEA avant TOPIC — lien avant autorisé par le contrat choisi."""
    payload = _base(idea_links=[2], example_links=[0])
    payload["records"] = [
        payload["records"][1],
        payload["records"][2],
        payload["records"][0],
    ]
    payload["records"][0]["l"] = [2]
    payload["records"][1]["l"] = [0]
    payload["records"][2]["l"] = []
    return payload


def empty_link_by_kind_transports() -> dict[str, dict[str, Any]]:
    idea_empty = _base(idea_links=[], example_links=[1])
    example_empty = _base(idea_links=[0], example_links=[])
    topic_linked = _base(idea_links=[0], example_links=[1])
    topic_linked["records"][0]["l"] = [1]
    reference = _base(idea_links=[0], example_links=[1])
    reference["records"].append(
        {
            "k": "REFERENCE",
            "v": "A planning handbook",
            "s": [SYNTHETIC_SRC_IDS[0]],
            "l": [1],
            "m": ["book", "vague", ""],
        }
    )
    uncertainty = _base(idea_links=[0], example_links=[1])
    uncertainty["records"].append(
        {
            "k": "UNCERTAINTY",
            "v": "Exact wording not located",
            "s": [SYNTHETIC_SRC_IDS[0]],
            "l": [1],
            "m": ["incomplete_reference", "medium"],
        }
    )
    relation_ok = _base(idea_links=[0], example_links=[1])
    relation_ok["records"].insert(
        2,
        {
            "k": "IDEA",
            "v": "Checking twice prevents avoidable mistakes",
            "s": [SYNTHETIC_SRC_IDS[1]],
            "l": [0],
            "m": ["claim", "supporting"],
        },
    )
    relation_ok["records"][3]["l"] = [1]
    relation_ok["records"].append(
        {
            "k": "RELATION",
            "v": "supports",
            "s": [],
            "l": [2, 1],
            "m": [],
        }
    )
    relation_empty = deepcopy(relation_ok)
    relation_empty["records"][-1]["l"] = []
    return {
        "idea_empty_allowed": idea_empty,
        "example_empty_allowed": example_empty,
        "topic_must_be_empty": topic_linked,
        "reference_must_be_empty": reference,
        "uncertainty_must_be_empty": uncertainty,
        "relation_required": relation_empty,
        "relation_valid": relation_ok,
    }


__all__ = [
    "corrected_a13_transport",
    "duplicate_link_transport",
    "empty_link_by_kind_transports",
    "forward_link_transport",
    "out_of_range_transport",
    "self_link_transport",
    "valid_multi_link_transport",
    "wrong_kind_target_transport",
]
