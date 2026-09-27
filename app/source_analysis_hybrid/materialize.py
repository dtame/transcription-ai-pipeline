"""
Matérialisation déterministe du contenu d'une fenêtre.

Le futur WindowAnalyzer obtient ici les segments OWNED et CONTEXT-ONLY.
Aucun envoi provider.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.source_analysis.errors import SourceAnalysisWindowPlanError
from app.source_analysis.transcript_input import SourceSegment, TranscriptInput
from app.source_analysis_hybrid.constants import (
    OWNERSHIP_CONTEXT_ONLY,
    OWNERSHIP_OWNED,
)
from app.source_analysis_hybrid.contracts import WindowInput


@dataclass(frozen=True)
class MaterializedSource:
    src_id: str
    segment: SourceSegment
    ownership: str

    def to_dict(self) -> dict[str, str]:
        return {
            "src_id": self.src_id,
            "ownership": self.ownership,
            "source_id": self.segment.source_id,
            "text": self.segment.text,
        }


@dataclass(frozen=True)
class WindowContent:
    window_id: str
    owned: tuple[MaterializedSource, ...]
    context: tuple[MaterializedSource, ...]

    @property
    def owned_segments(self) -> tuple[SourceSegment, ...]:
        return tuple(item.segment for item in self.owned)

    @property
    def context_segments(self) -> tuple[SourceSegment, ...]:
        return tuple(item.segment for item in self.context)

    def to_dict(self) -> dict:
        return {
            "window_id": self.window_id,
            "owned": [item.to_dict() for item in self.owned],
            "context": [item.to_dict() for item in self.context],
        }


def _lookup(transcript: TranscriptInput) -> dict[str, SourceSegment]:
    index: dict[str, SourceSegment] = {}
    for segment in transcript.segments:
        if segment.src_id in index:
            raise SourceAnalysisWindowPlanError(
                f"SRC dupliqué dans TranscriptInput : {segment.src_id}."
            )
        index[segment.src_id] = segment
    return index


def _resolve(
    refs: tuple[str, ...],
    lookup: dict[str, SourceSegment],
    *,
    ownership: str,
    present_order: tuple[str, ...],
) -> tuple[MaterializedSource, ...]:
    resolved: list[MaterializedSource] = []
    positions = {src: index for index, src in enumerate(present_order)}
    previous = -1
    for src_id in refs:
        segment = lookup.get(src_id)
        if segment is None:
            raise SourceAnalysisWindowPlanError(
                f"SRC {src_id} absent du TranscriptInput (membership réelle)."
            )
        position = positions[src_id]
        if position <= previous:
            raise SourceAnalysisWindowPlanError(
                f"ordre source non préservé pour {src_id}."
            )
        previous = position
        resolved.append(
            MaterializedSource(src_id=src_id, segment=segment, ownership=ownership)
        )
    return tuple(resolved)


def materialize_window_content(
    transcript: TranscriptInput, window: WindowInput
) -> WindowContent:
    """
    Segments correspondant à owned_src_refs et context_src_refs.

    L'ordre est celui de TranscriptInput, pas un tri lexical des IDs.
    first/last ne sont jamais expansés en plage numérique.
    """
    lookup = _lookup(transcript)
    present = transcript.src_ids()
    owned = _resolve(
        window.owned_src_refs,
        lookup,
        ownership=OWNERSHIP_OWNED,
        present_order=present,
    )
    context = _resolve(
        window.context_src_refs,
        lookup,
        ownership=OWNERSHIP_CONTEXT_ONLY,
        present_order=present,
    )
    owned_set = {item.src_id for item in owned}
    for item in context:
        if item.src_id in owned_set:
            raise SourceAnalysisWindowPlanError(
                f"SRC {item.src_id} à la fois owned et context dans {window.window_id}."
            )
    return WindowContent(window_id=window.window_id, owned=owned, context=context)
