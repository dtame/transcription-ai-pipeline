"""Fixture synthétique isolée — aucun SRC / WIN / TR pastoral."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.file_utils import content_hash
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_fixtures import make_transcript, window_for
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    SYNTHETIC_SRC_IDS,
    SYNTHETIC_TEXTS,
)


@dataclass(frozen=True)
class SyntheticCanaryFixture:
    transcript: TranscriptInput
    window: WindowInput
    fixture_hash: str

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "transcript_id": self.transcript.transcript_id,
            "window_id": self.window.window_id,
            "src_ids": list(self.transcript.src_ids()),
            "owned_src_refs": list(self.window.owned_src_refs),
            "texts": [segment.text for segment in self.transcript.segments],
            "fixture_hash": self.fixture_hash,
            "pastoral": False,
            "required_structure": {
                "topics": 2,
                "ideas": 3,
                "relations": 1,
                "examples": 1,
                "idea_to_topic": True,
                "relation_to_idea": True,
                "example_to_idea": True,
            },
        }


def synthetic_fixture_payload() -> dict[str, Any]:
    return {
        "transcript_id": CANARY_TRANSCRIPT_ID,
        "window_id": CANARY_WINDOW_ID,
        "src_ids": list(SYNTHETIC_SRC_IDS),
        "texts": list(SYNTHETIC_TEXTS),
    }


def synthetic_fixture_hash() -> str:
    return content_hash(
        json.dumps(synthetic_fixture_payload(), ensure_ascii=False, sort_keys=True)
    )


def build_synthetic_fixture() -> SyntheticCanaryFixture:
    transcript = make_transcript(
        SYNTHETIC_TEXTS,
        src_ids=SYNTHETIC_SRC_IDS,
        transcript_id=CANARY_TRANSCRIPT_ID,
        language="en",
        content_sha256=synthetic_fixture_hash(),
    )
    window = window_for(
        transcript,
        owned=SYNTHETIC_SRC_IDS,
        context=(),
        window_id=CANARY_WINDOW_ID,
    )
    return SyntheticCanaryFixture(
        transcript=transcript,
        window=window,
        fixture_hash=synthetic_fixture_hash(),
    )


def expected_valid_transport() -> dict[str, Any]:
    """Transport FakeAI / diagnostic — 2T / 3I / 1R / 1E. Pas une réparation."""
    return {
        "theme": "Planning and review",
        "intent": "Show that planning and review support careful execution.",
        "ic": "high",
        "aud": "People who execute plans.",
        "ac": "medium",
        "records": [
            {
                "k": "TOPIC",
                "v": "Planning",
                "s": ["SRC998001"],
                "h": "T1",
                "l": [],
                "m": ["Careful plans reduce mistakes."],
            },
            {
                "k": "TOPIC",
                "v": "Review",
                "s": ["SRC998002"],
                "h": "T2",
                "l": [],
                "m": ["Review finds missing steps."],
            },
            {
                "k": "IDEA",
                "v": "Planning reduces avoidable mistakes.",
                "s": ["SRC998001"],
                "h": "I1",
                "l": ["T1"],
                "m": ["claim", "central"],
            },
            {
                "k": "IDEA",
                "v": "Reviewing a plan can reveal missing steps.",
                "s": ["SRC998002"],
                "h": "I2",
                "l": ["T2"],
                "m": ["claim", "supporting"],
            },
            {
                "k": "IDEA",
                "v": "Planning and review support careful execution.",
                "s": ["SRC998004"],
                "h": "I3",
                "l": ["T1", "T2"],
                "m": ["claim", "supporting"],
            },
            {
                "k": "RELATION",
                "v": "supports",
                "s": [],
                "h": "",
                "l": ["I2", "I1"],
                "m": [],
            },
            {
                "k": "EXAMPLE",
                "v": "Checking a checklist twice.",
                "s": ["SRC998003"],
                "h": "",
                "l": ["I2"],
                "m": ["anecdote"],
            },
        ],
    }


__all__ = [
    "SyntheticCanaryFixture",
    "build_synthetic_fixture",
    "expected_valid_transport",
    "synthetic_fixture_hash",
    "synthetic_fixture_payload",
]
