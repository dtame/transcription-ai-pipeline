"""Targeted SRC transcript hydration. Clean transcript only. No technical chunks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.book_generation.constants import HYDRATION_POLICY_VERSION
from app.file_utils import content_hash
from app.source_analysis.transcript_input import SourceSegment, TranscriptInput
from app.source_analysis_execution_strategy.windows import load_clean_transcript


@dataclass(frozen=True)
class HydratedSegment:
    src_id: str
    text: str
    source_order: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "src_id": self.src_id,
            "text": self.text,
            "source_order": self.source_order,
        }


@dataclass(frozen=True)
class TranscriptIndex:
    transcript_id: str
    content_sha256: str
    path: str
    primary_language: str
    segments: tuple[SourceSegment, ...]

    def by_src(self) -> dict[str, SourceSegment]:
        return {segment.src_id: segment for segment in self.segments}

    def to_identity(self) -> dict[str, Any]:
        return {
            "transcript_id": self.transcript_id,
            "content_sha256": self.content_sha256,
            "path": self.path,
            "primary_language": self.primary_language,
            "segment_count": len(self.segments),
            "artifact": "transcripts/clean/transcript_data.json",
            "mutated": False,
        }


def load_clean_transcript_index(
    project_name: str, *, sortie_dir: Path | None = None
) -> TranscriptIndex:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    return index_transcript(transcript)


def index_transcript(transcript: TranscriptInput) -> TranscriptIndex:
    path = str(getattr(transcript, "path", "") or "").replace("\\", "/")
    return TranscriptIndex(
        transcript_id=transcript.transcript_id,
        content_sha256=transcript.content_sha256,
        path=path,
        primary_language=transcript.primary_language,
        segments=tuple(transcript.segments),
    )


def hydrate_src_ids(
    src_ids: Iterable[str],
    index: TranscriptIndex | None,
) -> tuple[HydratedSegment, ...]:
    if index is None:
        return ()
    lookup = index.by_src()
    ordered: list[HydratedSegment] = []
    seen: set[str] = set()
    for src_id in _canonical_src_order(src_ids):
        if src_id in seen:
            continue
        seen.add(src_id)
        segment = lookup.get(src_id)
        if segment is None:
            continue
        ordered.append(
            HydratedSegment(
                src_id=segment.src_id,
                text=segment.text,
                source_order=segment.source_order,
            )
        )
    return tuple(ordered)


def _canonical_src_order(src_ids: Iterable[str]) -> tuple[str, ...]:
    unique = []
    seen: set[str] = set()
    for src_id in src_ids:
        if src_id in seen:
            continue
        seen.add(src_id)
        unique.append(src_id)
    return tuple(sorted(unique, key=_src_sort_key))


def _src_sort_key(src_id: str) -> tuple[int, str]:
    digits = "".join(ch for ch in src_id if ch.isdigit())
    return (int(digits) if digits else 0, src_id)


def hydration_policy_dict() -> dict[str, Any]:
    return {
        "version": HYDRATION_POLICY_VERSION,
        "artifact": "post-language-cleanup canonical transcript",
        "not_used": [
            "pre-clean interpreter-duplicated source",
            "V1 technical chunks",
            "whole transcript per chapter",
        ],
        "selection": "IDEA/EX/REF/UNC/section SRC refs → unique SRC IDs",
        "order": "canonical SRC identifier order",
        "overlap": "unique SRC IDs only; Phase 1 ownership not reopened",
        "missing_src": "omit silently from hydration; validator still requires resolution",
    }


def segments_identity(segments: Iterable[HydratedSegment]) -> str:
    payload = [
        {"src_id": item.src_id, "text": item.text} for item in segments
    ]
    return content_hash(
        __import__("json").dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def compact_segment_dicts(segments: Iterable[HydratedSegment]) -> list[dict[str, str]]:
    return [{"id": item.src_id, "t": item.text} for item in segments]
