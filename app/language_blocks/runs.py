"""
Regroupement des SRC en « runs » de même langue classifiée, par AUDIO.

Un Run est l'unité de travail de la Phase 3A.1.1 : un run FR est un candidat de
bloc avant application des règles de pont (bridging.py) ; un run EN/UNKNOWN/
MIXED est ce que context.py explore pour trouver un contexte anglais local.

Deux différences volontaires avec app.language_cleanup.blocks.build_blocks :

1. un run ne traverse JAMAIS deux AUDIO différents (§7 du cahier des charges
   Phase 3A.1.1 — règle absente de Phase 3A.1, qui n'en avait pas besoin
   puisqu'elle ne raisonne qu'en fenêtre locale de blocs, jamais en frontière
   explicite) ;

2. un run FR est en outre coupé partout où le gap temporel entre deux SRC FR
   consécutifs dépasse FR_GAP_SPLIT_THRESHOLD_SECONDS (§8) : une pause franche
   à l'intérieur d'un même label de langue peut signaler une nouvelle
   intervention.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.language_blocks.combined_source import CombinedSegment
from app.language_blocks.constants import FR_GAP_SPLIT_THRESHOLD_SECONDS

LANGUAGE_FR = "FR"
LANGUAGE_EN = "EN"


@dataclass(frozen=True)
class Run:
    """Run maximal de SRC consécutifs, même langue classifiée, même AUDIO."""

    run_index: int
    language: str
    audio_id: str
    segments: tuple[CombinedSegment, ...]

    @property
    def source_refs(self) -> tuple[str, ...]:
        return tuple(segment.src_id for segment in self.segments)

    @property
    def start_seconds(self) -> float:
        return self.segments[0].start

    @property
    def end_seconds(self) -> float:
        return self.segments[-1].end

    @property
    def first_position(self) -> int:
        return self.segments[0].position

    @property
    def last_position(self) -> int:
        return self.segments[-1].position

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def word_count(self) -> int:
        return sum(segment.word_count for segment in self.segments)

    @property
    def text(self) -> str:
        return " ".join(segment.text for segment in self.segments)


def build_runs(
    segments: tuple[CombinedSegment, ...],
    *,
    fr_gap_split_threshold_seconds: float = FR_GAP_SPLIT_THRESHOLD_SECONDS,
) -> tuple[Run, ...]:
    """
    Construit les runs, dans l'ordre canonique du transcript (`segments`
    n'est jamais réordonné).
    """
    raw_groups: list[list[CombinedSegment]] = []
    current: list[CombinedSegment] = []

    for segment in segments:
        if (
            current
            and current[-1].language == segment.language
            and current[-1].audio_id == segment.audio_id
        ):
            current.append(segment)
            continue

        if current:
            raw_groups.append(current)

        current = [segment]

    if current:
        raw_groups.append(current)

    # Deuxième passe : un run FR est encore coupé sur un gap temporel trop
    # important entre deux SRC FR consécutifs du même run (§8).
    final_groups: list[list[CombinedSegment]] = []

    for group in raw_groups:
        if group[0].language != LANGUAGE_FR or len(group) == 1:
            final_groups.append(group)
            continue

        sub_group: list[CombinedSegment] = [group[0]]

        for previous, current_segment in zip(group, group[1:]):
            gap = current_segment.start - previous.end
            if gap > fr_gap_split_threshold_seconds:
                final_groups.append(sub_group)
                sub_group = [current_segment]
            else:
                sub_group.append(current_segment)

        final_groups.append(sub_group)

    return tuple(
        Run(run_index=index, language=group[0].language, audio_id=group[0].audio_id, segments=tuple(group))
        for index, group in enumerate(final_groups)
    )
