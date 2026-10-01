"""Estimateur de sortie réutilisable pour le transport compact 2.0."""

from __future__ import annotations

import json
import math
from typing import Any, Mapping

from app.ai.estimation import estimate_tokens
from app.source_analysis_v31_global_output_architecture.constants import (
    A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN,
    EXPECTED_EXAMPLE,
    EXPECTED_IDEA,
    EXPECTED_REFERENCE,
    EXPECTED_TOPIC,
    EXPECTED_UNCERTAINTY,
    MAX_EXAMPLE_IDEA_REFS,
    MAX_LOCAL_IDS_PER_SATELLITE,
    MAX_MEMBERS_PER_IDEA,
    MAX_MEMBERS_PER_TOPIC,
    MODEL,
    NEXT_MAX_OUTPUT_TOKENS,
    SAFETY_RATIO,
    OUTPUT_BUDGET_TEXT_LIMITS,
)


def _provider_tokens(chars: int) -> int:
    return int(math.ceil(chars / A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN))


def _fill(length: int, glyph: str = "x") -> str:
    return glyph * int(length)


def _member(index: int, kind: str = "I") -> str:
    window = (index % 7) + 1
    return f"SYN{window:03d}:{kind}{index}"


def worst_case_transport(
    *,
    topics: int = EXPECTED_TOPIC,
    ideas: int = EXPECTED_IDEA,
    examples: int = EXPECTED_EXAMPLE,
    references: int = EXPECTED_REFERENCE,
    uncertainties: int = EXPECTED_UNCERTAINTY,
    drops: int = 0,
    members_per_idea: int = 1,
    members_per_topic: int = 1,
    limits: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    bounds = dict(OUTPUT_BUDGET_TEXT_LIMITS if limits is None else limits)
    idea_members = max(1, min(int(members_per_idea), MAX_MEMBERS_PER_IDEA))
    topic_members = max(1, min(int(members_per_topic), MAX_MEMBERS_PER_TOPIC))
    payload = {
        "gm": {
            "th": _fill(bounds["theme"]),
            "in": _fill(bounds["intent"]),
            "ic": "medium",
            "au": _fill(bounds["audience"]),
            "ac": "medium",
            "vo": _fill(bounds["voice"]),
        },
        "t": [
            {
                "h": f"T{index}",
                "v": _fill(bounds["topic"]),
                "m": [_member(index * topic_members + offset, "T") for offset in range(topic_members)],
            }
            for index in range(1, topics + 1)
        ],
        "i": [
            {
                "h": f"I{index}",
                "v": _fill(bounds["idea"]),
                "m": [_member(index * idea_members + offset, "I") for offset in range(idea_members)],
                "p": "supporting",
            }
            for index in range(1, ideas + 1)
        ],
        "x": [
            {
                "h": f"E{index}",
                "l": [_member(index, "E") for _ in range(min(1, MAX_LOCAL_IDS_PER_SATELLITE))],
                "g": [f"I{min(index, max(ideas, 1))}"][:MAX_EXAMPLE_IDEA_REFS],
            }
            for index in range(1, examples + 1)
        ],
        "f": [
            {
                "h": f"F{index}",
                "l": [_member(index, "F")],
            }
            for index in range(1, references + 1)
        ],
        "u": [
            {
                "h": f"U{index}",
                "l": [_member(index, "U")],
            }
            for index in range(1, uncertainties + 1)
        ],
        "drop": [
            {"i": _member(900 + index, "I"), "w": "transport_artifact"}
            for index in range(1, drops + 1)
        ],
    }
    return payload


def estimate_output(
    *,
    topics: int = EXPECTED_TOPIC,
    ideas: int = EXPECTED_IDEA,
    examples: int = EXPECTED_EXAMPLE,
    references: int = EXPECTED_REFERENCE,
    uncertainties: int = EXPECTED_UNCERTAINTY,
    drops: int = 0,
    members_per_idea: int = 1,
    members_per_topic: int = 1,
    idea_text_chars: int | None = None,
    topic_text_chars: int | None = None,
    limits: Mapping[str, int] | None = None,
    max_output: int = NEXT_MAX_OUTPUT_TOKENS,
    safety_ratio: float = SAFETY_RATIO,
) -> dict[str, Any]:
    bounds = dict(OUTPUT_BUDGET_TEXT_LIMITS if limits is None else limits)
    if idea_text_chars is not None:
        bounds["idea"] = int(idea_text_chars)
    if topic_text_chars is not None:
        bounds["topic"] = int(topic_text_chars)
    hard_payload = worst_case_transport(
        topics=topics,
        ideas=ideas,
        examples=examples,
        references=references,
        uncertainties=uncertainties,
        drops=drops,
        members_per_idea=members_per_idea,
        members_per_topic=members_per_topic,
        limits=bounds,
    )
    expected_bounds = dict(bounds)
    expected_bounds["idea"] = min(bounds["idea"], 140)
    expected_bounds["topic"] = min(bounds["topic"], 80)
    expected_bounds["theme"] = min(bounds["theme"], 240)
    expected_payload = worst_case_transport(
        topics=max(1, int(topics * 0.7)),
        ideas=ideas,
        examples=examples,
        references=references,
        uncertainties=uncertainties,
        drops=drops,
        members_per_idea=1,
        members_per_topic=1,
        limits=expected_bounds,
    )
    hard_json = json.dumps(hard_payload, ensure_ascii=False, separators=(",", ":"))
    expected_json = json.dumps(expected_payload, ensure_ascii=False, separators=(",", ":"))
    local_hard = estimate_tokens(hard_json, model=MODEL)
    local_expected = estimate_tokens(expected_json, model=MODEL)
    hard_provider = _provider_tokens(len(hard_json))
    expected_provider = _provider_tokens(len(expected_json))
    safety = int(max_output * safety_ratio)
    return {
        "cardinalities": {
            "topics": topics,
            "ideas": ideas,
            "examples": examples,
            "references": references,
            "uncertainties": uncertainties,
            "drops": drops,
            "members_per_idea": members_per_idea,
            "members_per_topic": members_per_topic,
        },
        "length_bounds": bounds,
        "serialized_chars": {
            "expected": len(expected_json),
            "hard": len(hard_json),
        },
        "local_tokens": {
            "method": local_expected.method,
            "expected": local_expected.tokens,
            "hard": local_hard.tokens,
            "estimated": True,
        },
        "provider_planning_tokens": {
            "chars_per_token": A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN,
            "source": "A.38 observed 75150 chars / 32000 tokens",
            "expected": expected_provider,
            "hard": hard_provider,
        },
        "max_output": max_output,
        "safety_ratio": safety_ratio,
        "safety_target": safety,
        "fits_safety": hard_provider <= safety,
        "fits_max": hard_provider <= max_output,
        "margin_vs_max": max_output - hard_provider,
        "margin_vs_safety": safety - hard_provider,
    }


def pastoral_cardinalities() -> dict[str, int]:
    return {
        "topics": EXPECTED_TOPIC,
        "ideas": EXPECTED_IDEA,
        "examples": EXPECTED_EXAMPLE,
        "references": EXPECTED_REFERENCE,
        "uncertainties": EXPECTED_UNCERTAINTY,
    }


__all__ = [
    "estimate_output",
    "pastoral_cardinalities",
    "worst_case_transport",
]
