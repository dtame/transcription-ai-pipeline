"""Read-only canonical corpus loader. No production writes. No provider calls."""

from __future__ import annotations

from dataclasses import dataclass

from app.book_generation.hydrate import TranscriptIndex, load_clean_transcript_index
from app.book_generation.identity import ProductionInputs, load_production_inputs
from app.book_generation.language import resolve_canonical_language
from app.book_scale_up_preparation_4b220.constants import (
    EXPECTED_TRANSCRIPT,
    PROJECT_NAME,
)
from app.book_scale_up_preparation_4b220.guard import BookScaleUpPreparation4220Error
from app.editorial_planning.models import EditorialPlan
from app.source_analysis.models import SourceMap


@dataclass(frozen=True)
class CanonicalCorpus:
    inputs: ProductionInputs
    transcript: TranscriptIndex
    language: str

    @property
    def plan(self) -> EditorialPlan:
        return self.inputs.plan

    @property
    def source_map(self) -> SourceMap:
        return self.inputs.source_map


def load_canonical_corpus() -> CanonicalCorpus:
    inputs = load_production_inputs(PROJECT_NAME)
    index = load_clean_transcript_index(PROJECT_NAME)
    if index.content_sha256 != EXPECTED_TRANSCRIPT:
        raise BookScaleUpPreparation4220Error(
            "Clean transcript SHA-256 mismatch: "
            f"{index.content_sha256} ≠ {EXPECTED_TRANSCRIPT}"
        )
    language = resolve_canonical_language(
        source_map_primary_language=inputs.source_map.primary_language,
        transcript_primary_language=index.primary_language,
    )
    return CanonicalCorpus(inputs=inputs, transcript=index, language=language)


__all__ = ["CanonicalCorpus", "load_canonical_corpus"]
