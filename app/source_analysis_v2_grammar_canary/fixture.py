"""Fixture synthétique isolée — aucun SRC / WIN / TR pastoral."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.file_utils import content_hash
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_fixtures import make_transcript, window_for
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v2_grammar_canary.constants import (
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


__all__ = [
    "SyntheticCanaryFixture",
    "build_synthetic_fixture",
    "synthetic_fixture_hash",
    "synthetic_fixture_payload",
]
