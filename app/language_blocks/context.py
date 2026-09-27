"""
Recherche du contexte anglais local avant/après un bloc FR (§11-14).

Principe (repris de app.language_cleanup.translation_matcher, appliqué ici à
des RUNS plutôt qu'à des SRC individuels) : on regarde le run immédiatement
adjacent au bloc FR. S'il est anglais, c'est le contexte. S'il ne l'est pas
(UNKNOWN/MIXED déjà jugé non « pontable » par bridging.py, sinon il aurait
déjà été absorbé dans le bloc), on tolère de sauter au plus
CONTEXT_WINDOW_MAX_BLOCK_SKIP run(s) supplémentaire(s) dans la même direction.
Au-delà, ou en cas de frontière AUDIO, ou en cas d'un autre bloc FR, la
recherche s'arrête : pas de contexte anglais local exploitable dans cette
direction.

Le run anglais trouvé peut être plus grand que les plafonds documentés dans
app.language_blocks.constants (MAX_CONTEXT_*) : dans ce cas, seule la portion
la PLUS PROCHE du bloc FR est conservée (la fin du run pour `english_before`,
le début du run pour `english_after`) — c'est la portion la plus pertinente
pour une future comparaison de traduction, et `truncated=True` le signale.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.language_blocks.bridging import BlockSpan
from app.language_blocks.combined_source import CombinedSegment
from app.language_blocks.constants import (
    CONTEXT_WINDOW_MAX_BLOCK_SKIP,
    MAX_CONTEXT_SECONDS,
    MAX_CONTEXT_SEGMENTS,
    MAX_CONTEXT_WORDS,
)
from app.language_blocks.models import EnglishContext
from app.language_blocks.runs import Run

LANGUAGE_EN = "EN"
LANGUAGE_FR = "FR"

REASON_FOUND_EN = "EN"
REASON_AUDIO_EDGE = "NONE_AUDIO_EDGE"
REASON_BLOCKED_BY_FR = "NONE_BLOCKED_BY_FR"
REASON_BLOCKED_BY_NON_EN = "NONE_BLOCKED_BY_NON_EN"


@dataclass(frozen=True)
class ContextSearchResult:
    """Résultat de la recherche, y compris la RAISON quand il n'y a rien (§15)."""

    context: EnglishContext | None
    reason: str


def _select_local_segments(
    segments: tuple[CombinedSegment, ...], *, from_end: bool
) -> tuple[tuple[CombinedSegment, ...], bool]:
    """
    Réduit `segments` (un run entier) à sa portion locale, la plus proche du
    bloc FR, sous les plafonds MAX_CONTEXT_*. Retourne toujours au moins un
    SRC (jamais de contexte vide alors qu'un run anglais existe).
    """
    ordered = list(reversed(segments)) if from_end else list(segments)

    selected: list[CombinedSegment] = []
    total_words = 0

    for segment in ordered:
        candidate = selected + [segment]
        candidate_words = total_words + segment.word_count
        candidate_duration = (
            max(item.end for item in candidate) - min(item.start for item in candidate)
        )

        if (
            len(candidate) > MAX_CONTEXT_SEGMENTS
            or candidate_words > MAX_CONTEXT_WORDS
            or candidate_duration > MAX_CONTEXT_SECONDS
        ):
            break

        selected = candidate
        total_words = candidate_words

    if not selected:
        selected = [ordered[0]]

    if from_end:
        selected = list(reversed(selected))

    truncated = len(selected) < len(segments)

    return tuple(selected), truncated


def _build_context(
    selected: tuple[CombinedSegment, ...],
    *,
    truncated: bool,
    block_boundary_position: int,
    block_boundary_seconds: float,
    direction: str,
) -> EnglishContext:
    if direction == "before":
        nearest = selected[-1]
        distance_segments = block_boundary_position - nearest.position - 1
        distance_seconds = round(max(0.0, block_boundary_seconds - nearest.end), 3)
    else:
        nearest = selected[0]
        distance_segments = nearest.position - block_boundary_position - 1
        distance_seconds = round(max(0.0, nearest.start - block_boundary_seconds), 3)

    return EnglishContext(
        source_refs=tuple(segment.src_id for segment in selected),
        start_seconds=selected[0].start,
        end_seconds=selected[-1].end,
        text=" ".join(segment.text for segment in selected),
        word_count=sum(segment.word_count for segment in selected),
        segment_count=len(selected),
        distance_segments=max(0, distance_segments),
        distance_seconds=distance_seconds,
        truncated=truncated,
    )


def find_english_context(
    runs: tuple[Run, ...], span: BlockSpan, *, direction: str
) -> ContextSearchResult:
    """
    `direction` vaut "before" ou "after".
    """
    if direction == "before":
        boundary_run_index = span.run_indices[0]
        step = -1
        block_boundary_position = span.segments[0].position
        block_boundary_seconds = span.segments[0].start
    else:
        boundary_run_index = span.run_indices[-1]
        step = 1
        block_boundary_position = span.segments[-1].position
        block_boundary_seconds = span.segments[-1].end

    idx = boundary_run_index + step
    skipped = 0

    while 0 <= idx < len(runs):
        candidate = runs[idx]

        if candidate.audio_id != span.audio_id:
            return ContextSearchResult(context=None, reason=REASON_AUDIO_EDGE)

        if candidate.language == LANGUAGE_EN:
            selected, truncated = _select_local_segments(
                candidate.segments, from_end=(direction == "before")
            )
            context = _build_context(
                selected,
                truncated=truncated,
                block_boundary_position=block_boundary_position,
                block_boundary_seconds=block_boundary_seconds,
                direction=direction,
            )
            return ContextSearchResult(context=context, reason=REASON_FOUND_EN)

        if candidate.language == LANGUAGE_FR:
            return ContextSearchResult(context=None, reason=REASON_BLOCKED_BY_FR)

        # UNKNOWN / MIXED, non absorbé comme pont (sinon il appartiendrait déjà
        # au bloc et n'apparaîtrait pas ici) : on tolère un saut limité.
        skipped += 1
        if skipped > CONTEXT_WINDOW_MAX_BLOCK_SKIP:
            return ContextSearchResult(context=None, reason=REASON_BLOCKED_BY_NON_EN)

        idx += step

    return ContextSearchResult(context=None, reason=REASON_AUDIO_EDGE)
