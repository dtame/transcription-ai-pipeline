"""Mesures structurelles offline de transports synthétiques. Pas de transcript."""

from __future__ import annotations

import json
from typing import Any

from app.ai.estimation import CHARS_PER_TOKEN, estimate_tokens
from app.source_analysis.window_granularity import (
    HARD_CEILINGS,
    MAX_OUTPUT_TOKENS_FROZEN,
    SAFETY_MARGIN_RATIO,
    SOFT_TARGETS,
    TEXT_HARD_LIMITS,
    TOTAL_HARD_CEILING,
)

_IDEA = (
    "Faith changes how a trial is crossed when the path itself becomes the lesson."
)
_TOPIC = "Faith during trials and adversity"
_TOPIC_SUM = "How trust is revealed when hardship does not lift."
_EXAMPLE = "A man still prayed each morning before the work of the day began."
_REFERENCE = "Paul says somewhere that weakness becomes the place of strength."
_UNCERTAINTY = "The cited Pauline wording is not located in the spoken source."
_REPETITION = "The crossing claim is restated and then developed without a new claim."
_VOICE = "didactic oral teaching with direct address"


def _src(index: int) -> str:
    return f"SRC{index:06d}"


def _record(kind: str, value: str, refs: list[str], links=None, metadata=None) -> dict:
    return {
        "k": kind,
        "v": value,
        "s": list(refs),
        "l": list(links or []),
        "m": list(metadata or []),
    }


def _fill_value(template: str, limit: int) -> str:
    text = template
    while len(text) + 1 + len(template) <= limit:
        text = f"{text} {template}"
    return text[:limit]


def _refs(count: int, start: int = 1) -> list[str]:
    return [_src(start + index) for index in range(count)]


def build_scenario_transport(
    *,
    counts: dict[str, int],
    idea_refs: int,
    topic_refs: int,
    other_refs: int,
    max_text: bool,
) -> dict[str, Any]:
    records: list[dict] = []
    idea_start = 0
    for index in range(counts.get("TOPIC", 0)):
        records.append(
            _record(
                "TOPIC",
                _fill_value(_TOPIC, TEXT_HARD_LIMITS["TOPIC.v"]) if max_text else _TOPIC,
                _refs(topic_refs, 1 + index * topic_refs),
                [],
                [
                    _fill_value(_TOPIC_SUM, TEXT_HARD_LIMITS["TOPIC.m0"])
                    if max_text
                    else _TOPIC_SUM
                ],
            )
        )
    idea_start = len(records)
    for index in range(counts.get("IDEA", 0)):
        records.append(
            _record(
                "IDEA",
                _fill_value(_IDEA, TEXT_HARD_LIMITS["IDEA.v"]) if max_text else _IDEA,
                _refs(idea_refs, 100 + index * idea_refs),
                [0] if counts.get("TOPIC", 0) else [],
                ["claim", "central" if index == 0 else "supporting"],
            )
        )
    for index in range(counts.get("RELATION", 0)):
        left = idea_start + (index % max(counts.get("IDEA", 1), 1))
        right = idea_start + ((index + 1) % max(counts.get("IDEA", 1), 1))
        records.append(_record("RELATION", "supports", [], [right, left], []))
    for index in range(counts.get("EXAMPLE", 0)):
        records.append(
            _record(
                "EXAMPLE",
                _fill_value(_EXAMPLE, TEXT_HARD_LIMITS["EXAMPLE.v"])
                if max_text
                else _EXAMPLE,
                _refs(other_refs, 400 + index * other_refs),
                [idea_start] if counts.get("IDEA", 0) else [],
                ["anecdote"],
            )
        )
    for index in range(counts.get("REFERENCE", 0)):
        records.append(
            _record(
                "REFERENCE",
                _fill_value(_REFERENCE, TEXT_HARD_LIMITS["REFERENCE.v"])
                if max_text
                else _REFERENCE,
                _refs(other_refs, 500 + index * other_refs),
                [],
                ["biblical", "vague", ""],
            )
        )
    for index in range(counts.get("UNCERTAINTY", 0)):
        records.append(
            _record(
                "UNCERTAINTY",
                _fill_value(_UNCERTAINTY, TEXT_HARD_LIMITS["UNCERTAINTY.v"])
                if max_text
                else _UNCERTAINTY,
                _refs(other_refs, 600 + index * other_refs),
                [],
                ["incomplete_reference", "medium"],
            )
        )
    for index in range(counts.get("REPETITION", 0)):
        records.append(
            _record(
                "REPETITION",
                _fill_value(_REPETITION, TEXT_HARD_LIMITS["REPETITION.v"])
                if max_text
                else _REPETITION,
                _refs(other_refs, 700 + index * other_refs),
                [idea_start, idea_start + 1 if counts.get("IDEA", 0) > 1 else idea_start],
                ["development"],
            )
        )
    for index in range(counts.get("VOICE", 0)):
        records.append(_record("VOICE", _VOICE, [], [], ["tone"]))
    for index in range(counts.get("INTENT_KIND", 0)):
        records.append(_record("INTENT_KIND", "enseigner", [], [], []))
    for index in range(counts.get("AUDIENCE_KIND", 0)):
        records.append(_record("AUDIENCE_KIND", "croyants", [], [], []))
    return {
        "theme": _fill_value(_TOPIC, TEXT_HARD_LIMITS["theme"]) if max_text else _TOPIC,
        "intent": _fill_value(_IDEA, TEXT_HARD_LIMITS["intent"]) if max_text else _IDEA,
        "ic": "high",
        "aud": _fill_value(_TOPIC_SUM, TEXT_HARD_LIMITS["aud"]) if max_text else _TOPIC_SUM,
        "ac": "medium",
        "records": records,
    }


SCENARIO_SPECS: dict[str, dict[str, Any]] = {
    "SMALL": {
        "counts": {
            "TOPIC": 3,
            "IDEA": 8,
            "RELATION": 4,
            "EXAMPLE": 2,
            "REFERENCE": 1,
            "UNCERTAINTY": 2,
            "REPETITION": 1,
            "VOICE": 8,
            "INTENT_KIND": 1,
            "AUDIENCE_KIND": 1,
        },
        "idea_refs": 2,
        "topic_refs": 2,
        "other_refs": 2,
        "max_text": False,
    },
    "MEDIUM": {
        "counts": {
            "TOPIC": 6,
            "IDEA": 24,
            "RELATION": 12,
            "EXAMPLE": 6,
            "REFERENCE": 4,
            "UNCERTAINTY": 4,
            "REPETITION": 3,
            "VOICE": 12,
            "INTENT_KIND": 2,
            "AUDIENCE_KIND": 2,
        },
        "idea_refs": 4,
        "topic_refs": 4,
        "other_refs": 3,
        "max_text": False,
    },
    "LARGE": {
        "counts": dict(SOFT_TARGETS),
        "idea_refs": 8,
        "topic_refs": 6,
        "other_refs": 4,
        "max_text": False,
    },
    "STRESS": {
        "counts": {
            "TOPIC": 12,
            "IDEA": 56,
            "RELATION": 28,
            "EXAMPLE": 14,
            "REFERENCE": 10,
            "UNCERTAINTY": 12,
            "REPETITION": 8,
            "VOICE": 16,
            "INTENT_KIND": 2,
            "AUDIENCE_KIND": 2,
        },
        "idea_refs": 12,
        "topic_refs": 10,
        "other_refs": 6,
        "max_text": False,
    },
    "MAX_POLICY_VALID": {
        "counts": {
            "TOPIC": HARD_CEILINGS["TOPIC"],
            "IDEA": HARD_CEILINGS["IDEA"],
            "RELATION": 32,
            "EXAMPLE": 12,
            "REFERENCE": 8,
            "UNCERTAINTY": 8,
            "REPETITION": 6,
            "VOICE": 12,
            "INTENT_KIND": 2,
            "AUDIENCE_KIND": 2,
        },
        "idea_refs": 16,
        "topic_refs": 12,
        "other_refs": 6,
        "max_text": True,
    },
}


def measure_transport(transport: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(transport, ensure_ascii=False, separators=(",", ":"))
    encoded = text.encode("utf-8")
    estimate = estimate_tokens(text, model="claude-sonnet-5")
    local = estimate.tokens
    return {
        "json_chars": len(text),
        "json_bytes": len(encoded),
        "local_estimated_tokens": local,
        "estimator_method": estimate.method,
        "chars_per_token_constant": CHARS_PER_TOKEN,
        "percent_of_32000": round(100.0 * local / MAX_OUTPUT_TOKENS_FROZEN, 4),
        "record_count": len(transport.get("records") or []),
        "kind_counts": _kind_counts(transport),
        "not_provider_tokenization": True,
    }


def _kind_counts(transport: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in transport.get("records") or []:
        kind = str(item.get("k") or "")
        counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))


def run_size_study() -> dict[str, Any]:
    scenarios: dict[str, Any] = {}
    for name, spec in SCENARIO_SPECS.items():
        transport = build_scenario_transport(
            counts=spec["counts"],
            idea_refs=spec["idea_refs"],
            topic_refs=spec["topic_refs"],
            other_refs=spec["other_refs"],
            max_text=spec["max_text"],
        )
        measured = measure_transport(transport)
        measured["counts"] = dict(spec["counts"])
        measured["idea_source_refs_each"] = spec["idea_refs"]
        measured["topic_source_refs_each"] = spec["topic_refs"]
        measured["other_source_refs_each"] = spec["other_refs"]
        measured["max_text"] = spec["max_text"]
        measured["within_total_hard"] = (
            measured["record_count"] <= TOTAL_HARD_CEILING
        )
        scenarios[name] = measured
    max_valid = scenarios["MAX_POLICY_VALID"]
    local = int(max_valid["local_estimated_tokens"])
    return {
        "scenarios": scenarios,
        "max_policy_valid_local_tokens": local,
        "max_output_frozen": MAX_OUTPUT_TOKENS_FROZEN,
        "safety_margin_ratio": SAFETY_MARGIN_RATIO,
        "safety_margin_tokens": MAX_OUTPUT_TOKENS_FROZEN - local,
        "within_safety_margin": local
        <= int(MAX_OUTPUT_TOKENS_FROZEN * SAFETY_MARGIN_RATIO),
        "percent_of_32000": max_valid["percent_of_32000"],
        "transcript_text_included": False,
        "provider_tokenization_claimed": False,
    }


__all__ = [
    "SCENARIO_SPECS",
    "build_scenario_transport",
    "measure_transport",
    "run_size_study",
]
