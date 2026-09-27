"""
Fusion des runs FR à travers de petits ponts (§5-7 du cahier des charges).

Un bloc FR final peut absorber un run UNKNOWN/MIXED entre deux runs FR
consécutifs — jamais un run EN — si ce run pont satisfait TOUTES les
conditions documentées dans app.language_blocks.constants :

    BRIDGE_MAX_RUN_SEGMENTS       longueur du run pont
    BRIDGE_MAX_WORDS_PER_SEGMENT  nombre de mots de CHAQUE SRC du pont
    BRIDGE_MAX_DURATION_SECONDS   durée de CHAQUE SRC du pont
    BRIDGE_MAX_TOTAL_GAP_SECONDS  silence total à travers le pont

Un pont ne change JAMAIS la classification originale du SRC absorbé (§6) :
il reste UNKNOWN ou MIXED dans language_cleanup.json, seulement listé à part
dans `bridge_source_refs` du bloc qui l'absorbe. Un run FR n'est jamais
fusionné avec un autre run FR : s'ils sont adjacents dans la liste des runs,
c'est que la coupure sur gap temporel (§8, runs.py) a déjà tranché qu'il
s'agit de deux interventions distinctes — les fusionner ici annulerait cette
décision.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.language_blocks.combined_source import CombinedSegment
from app.language_blocks.constants import (
    BRIDGE_MAX_DURATION_SECONDS,
    BRIDGE_MAX_RUN_SEGMENTS,
    BRIDGE_MAX_TOTAL_GAP_SECONDS,
    BRIDGE_MAX_WORDS_PER_SEGMENT,
)
from app.language_blocks.runs import Run

LANGUAGE_FR = "FR"
LANGUAGE_EN = "EN"
BRIDGEABLE_LANGUAGES = ("UNKNOWN", "MIXED")


@dataclass(frozen=True)
class BlockSpan:
    """Un bloc FR final : un ou plusieurs runs FR reliés par des ponts admis."""

    run_indices: tuple[int, ...]
    fr_run_indices: tuple[int, ...]
    bridge_run_indices: tuple[int, ...]
    audio_id: str
    segments: tuple[CombinedSegment, ...]

    @property
    def fr_source_refs(self) -> tuple[str, ...]:
        return tuple(
            segment.src_id for segment in self.segments if segment.language == LANGUAGE_FR
        )

    @property
    def bridge_source_refs(self) -> tuple[str, ...]:
        return tuple(
            segment.src_id for segment in self.segments if segment.language != LANGUAGE_FR
        )


def _run_is_bridgeable(run: Run) -> bool:
    if run.language not in BRIDGEABLE_LANGUAGES:
        return False

    if run.segment_count > BRIDGE_MAX_RUN_SEGMENTS:
        return False

    for segment in run.segments:
        if segment.word_count > BRIDGE_MAX_WORDS_PER_SEGMENT:
            return False
        if segment.duration_seconds > BRIDGE_MAX_DURATION_SECONDS:
            return False

    return True


def build_block_spans(runs: tuple[Run, ...]) -> tuple[BlockSpan, ...]:
    """
    Construit les blocs FR finaux, dans l'ordre d'apparition des runs FR.

    Chaque run FR entame au plus un bloc (jamais absorbé rétroactivement dans
    un bloc précédent) : l'extension ne se fait que vers l'avant.
    """
    spans: list[BlockSpan] = []
    index = 0
    n = len(runs)

    while index < n:
        run = runs[index]

        if run.language != LANGUAGE_FR:
            index += 1
            continue

        span_run_indices = [index]
        fr_run_indices = [index]
        bridge_run_indices: list[int] = []
        last_fr_run = run
        cursor = index

        while True:
            bridge_position = cursor + 1

            if bridge_position >= n:
                break

            bridge_candidate = runs[bridge_position]

            if bridge_candidate.audio_id != run.audio_id:
                break

            if not _run_is_bridgeable(bridge_candidate):
                break

            fr_position = bridge_position + 1

            if fr_position >= n:
                break

            next_fr_candidate = runs[fr_position]

            if (
                next_fr_candidate.language != LANGUAGE_FR
                or next_fr_candidate.audio_id != run.audio_id
            ):
                break

            total_gap = next_fr_candidate.start_seconds - last_fr_run.end_seconds

            if total_gap > BRIDGE_MAX_TOTAL_GAP_SECONDS:
                break

            # Le pont et le run FR suivant sont admis : on étend le bloc.
            span_run_indices.append(bridge_position)
            span_run_indices.append(fr_position)
            bridge_run_indices.append(bridge_position)
            fr_run_indices.append(fr_position)
            last_fr_run = next_fr_candidate
            cursor = fr_position

        segments = tuple(
            segment
            for run_idx in span_run_indices
            for segment in runs[run_idx].segments
        )

        spans.append(
            BlockSpan(
                run_indices=tuple(span_run_indices),
                fr_run_indices=tuple(fr_run_indices),
                bridge_run_indices=tuple(bridge_run_indices),
                audio_id=run.audio_id,
                segments=segments,
            )
        )

        index = cursor + 1

    return tuple(spans)
