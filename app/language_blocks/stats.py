"""
Statistiques obligatoires de la Phase 3A.1.1 (§22-28 du cahier des charges).

Ce module ne prend AUCUNE décision : il compte, mesure des distributions, et
délègue l'estimation de charge IA à estimation.py. Toutes les fonctions sont
pures (aucune écriture disque).
"""

from __future__ import annotations

import statistics

from app.language_blocks.combined_source import CombinedSegment, CombinedSource
from app.language_blocks.constants import FR_GAP_SPLIT_THRESHOLD_SECONDS
from app.language_blocks.estimation import compute_ai_estimation
from app.language_blocks.models import (
    CANDIDATE_DIRECTIONS,
    PHASE_3A1_STATUSES,
    SEMANTIC_REVIEW_STATUSES,
    STRUCTURES,
    BlocksManifestStats,
    GapAudit,
    LanguageBlock,
)

LANGUAGE_FR = "FR"

DECISION_REMOVE = "REMOVE_TRANSLATION"
DECISION_REVIEW = "REVIEW"
DECISION_KEEP = "KEEP"

SEGMENT_SIZE_BUCKETS = ("1", "2", "3", "4-5", "6-10", ">10")
WORD_SIZE_BUCKETS = ("1-5", "6-15", "16-30", "31-60", ">60")


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, int(len(sorted_values) * p))
    return sorted_values[index]


def _segment_size_bucket(segment_count: int) -> str:
    if segment_count == 1:
        return "1"
    if segment_count == 2:
        return "2"
    if segment_count == 3:
        return "3"
    if 4 <= segment_count <= 5:
        return "4-5"
    if 6 <= segment_count <= 10:
        return "6-10"
    return ">10"


def _word_size_bucket(word_count: int) -> str:
    if 1 <= word_count <= 5:
        return "1-5"
    if 6 <= word_count <= 15:
        return "6-15"
    if 16 <= word_count <= 30:
        return "16-30"
    if 31 <= word_count <= 60:
        return "31-60"
    return ">60"


def compute_gap_audit(segments: tuple[CombinedSegment, ...]) -> GapAudit:
    """
    §8 : distribution RÉELLE des gaps FR->FR strictement adjacents (même
    AUDIO, aucun SRC entre les deux), calculée sur les données du projet en
    cours d'analyse — indépendamment du seuil fixe appliqué par runs.py.
    """
    gaps: list[float] = []

    for previous, current in zip(segments, segments[1:]):
        if (
            previous.language == LANGUAGE_FR
            and current.language == LANGUAGE_FR
            and previous.audio_id == current.audio_id
        ):
            gaps.append(round(current.start - previous.end, 3))

    if not gaps:
        return GapAudit(
            pair_count=0,
            threshold_retained=FR_GAP_SPLIT_THRESHOLD_SECONDS,
        )

    ordered = sorted(gaps)

    return GapAudit(
        pair_count=len(ordered),
        median_gap=round(statistics.median(ordered), 3),
        p90_gap=round(_percentile(ordered, 0.90), 3),
        p95_gap=round(_percentile(ordered, 0.95), 3),
        p99_gap=round(_percentile(ordered, 0.99), 3),
        max_gap=ordered[-1],
        threshold_retained=FR_GAP_SPLIT_THRESHOLD_SECONDS,
    )


def _quartile_index(position_seconds: float, total_duration: float) -> int:
    """Quartile 0-based (0..3) de `position_seconds` dans une durée totale."""
    if total_duration <= 0:
        return 0
    ratio = max(0.0, min(1.0, position_seconds / total_duration))
    return min(3, int(ratio * 4))


def compute_by_audio(
    combined: CombinedSource, blocks: tuple[LanguageBlock, ...]
) -> tuple[dict, ...]:
    """§23 : distribution des SRC/blocs/mots/décisions FR, par AUDIO."""
    entries = []

    for source in combined.sources:
        fr_segments = [
            segment
            for segment in combined.segments
            if segment.language == LANGUAGE_FR and segment.audio_id == source.audio_id
        ]
        audio_blocks = [block for block in blocks if block.audio_id == source.audio_id]

        entries.append(
            {
                "audio_id": source.audio_id,
                "fr_segments": len(fr_segments),
                "fr_blocks": len(audio_blocks),
                "fr_words": sum(segment.word_count for segment in fr_segments),
                "remove_refs_count": sum(
                    1 for segment in fr_segments if segment.decision == DECISION_REMOVE
                ),
                "review_refs_count": sum(
                    1 for segment in fr_segments if segment.decision == DECISION_REVIEW
                ),
                "keep_refs_count": sum(
                    1 for segment in fr_segments if segment.decision == DECISION_KEEP
                ),
                "blocks_needing_semantic_review": sum(
                    1
                    for block in audio_blocks
                    if block.semantic_review_status == "NEEDED"
                ),
            }
        )

    return tuple(entries)


def compute_temporal_quartiles(
    combined: CombinedSource, blocks: tuple[LanguageBlock, ...]
) -> tuple[dict, ...]:
    """
    §24 : chaque AUDIO divisé en quartiles temporels (0-25 / 25-50 / 50-75 /
    75-100 % de sa durée déclarée). Un bloc est rattaché au quartile de son
    SEGMENT DE DÉPART (`start_seconds`) : un bloc qui chevauche une frontière
    de quartile n'est jamais compté deux fois.
    """
    duration_by_audio = {source.audio_id: source.duration_seconds for source in combined.sources}

    entries: list[dict] = []

    for source in combined.sources:
        total_duration = duration_by_audio.get(source.audio_id, 0.0)

        fr_segments = [
            segment
            for segment in combined.segments
            if segment.language == LANGUAGE_FR and segment.audio_id == source.audio_id
        ]
        audio_blocks = [block for block in blocks if block.audio_id == source.audio_id]

        buckets = [
            {"fr_segments": 0, "fr_blocks": 0, "fr_words": 0} for _ in range(4)
        ]

        for segment in fr_segments:
            q = _quartile_index(segment.start, total_duration)
            buckets[q]["fr_segments"] += 1
            buckets[q]["fr_words"] += segment.word_count

        for block in audio_blocks:
            q = _quartile_index(block.start_seconds, total_duration)
            buckets[q]["fr_blocks"] += 1

        for quartile_number in range(4):
            entries.append(
                {
                    "audio_id": source.audio_id,
                    "quartile": quartile_number + 1,
                    "fr_segments": buckets[quartile_number]["fr_segments"],
                    "fr_blocks": buckets[quartile_number]["fr_blocks"],
                    "fr_words": buckets[quartile_number]["fr_words"],
                }
            )

    return tuple(entries)


def compute_size_histograms(
    blocks: tuple[LanguageBlock, ...]
) -> tuple[dict, dict]:
    """§25 : histogrammes de taille des blocs, en SRC et en mots."""
    segments_histogram = {bucket: 0 for bucket in SEGMENT_SIZE_BUCKETS}
    words_histogram = {bucket: 0 for bucket in WORD_SIZE_BUCKETS}

    for block in blocks:
        segments_histogram[_segment_size_bucket(block.segment_count)] += 1
        words_histogram[_word_size_bucket(block.word_count)] += 1

    return segments_histogram, words_histogram


def compute_context_availability(blocks: tuple[LanguageBlock, ...]) -> dict:
    """§26 : disponibilité et taille du contexte anglais local."""
    with_before = [block for block in blocks if block.english_before is not None]
    with_after = [block for block in blocks if block.english_after is not None]
    with_both = [
        block
        for block in blocks
        if block.english_before is not None and block.english_after is not None
    ]
    with_none = [
        block
        for block in blocks
        if block.english_before is None and block.english_after is None
    ]

    def _word_stats(items: list[LanguageBlock], accessor) -> dict:
        values = sorted(accessor(block).word_count for block in items)
        if not values:
            return {"mean": 0.0, "median": 0, "p95": 0}
        return {
            "mean": round(statistics.mean(values), 2),
            "median": statistics.median(values),
            "p95": _percentile(values, 0.95),
        }

    return {
        "blocks_with_EN_before": len(with_before),
        "blocks_with_EN_after": len(with_after),
        "blocks_with_both": len(with_both),
        "blocks_with_no_EN_context": len(with_none),
        "english_before_word_count_stats": _word_stats(
            with_before, lambda block: block.english_before
        ),
        "english_after_word_count_stats": _word_stats(
            with_after, lambda block: block.english_after
        ),
    }


def _distribution(values: list[str], vocabulary: tuple[str, ...]) -> dict:
    counts = {label: 0 for label in vocabulary}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def compute_stats(
    combined: CombinedSource,
    blocks: tuple[LanguageBlock, ...],
    *,
    analysis_duration_seconds: float,
) -> BlocksManifestStats:
    fr_segments = [
        segment for segment in combined.segments if segment.language == LANGUAGE_FR
    ]

    fr_segment_counts = [block.fr_segment_count for block in blocks]

    segments_histogram, words_histogram = compute_size_histograms(blocks)

    return BlocksManifestStats(
        total_FR_segments=len(fr_segments),
        total_FR_blocks=len(blocks),
        single_segment_blocks=sum(1 for block in blocks if block.segment_count == 1),
        multi_segment_blocks=sum(1 for block in blocks if block.segment_count > 1),
        max_FR_segments_in_block=max(fr_segment_counts) if fr_segment_counts else 0,
        median_FR_segments_per_block=(
            statistics.median(fr_segment_counts) if fr_segment_counts else 0.0
        ),
        mean_FR_segments_per_block=(
            round(statistics.mean(fr_segment_counts), 3) if fr_segment_counts else 0.0
        ),
        total_FR_words=sum(segment.word_count for segment in fr_segments),
        structure_distribution=_distribution(
            [block.structure for block in blocks], STRUCTURES
        ),
        candidate_direction_distribution=_distribution(
            [block.candidate_direction for block in blocks], CANDIDATE_DIRECTIONS
        ),
        phase_3a1_status_distribution=_distribution(
            [block.phase_3a1_status for block in blocks], PHASE_3A1_STATUSES
        ),
        semantic_review_distribution=_distribution(
            [block.semantic_review_status for block in blocks], SEMANTIC_REVIEW_STATUSES
        ),
        by_audio=compute_by_audio(combined, blocks),
        temporal_quartiles=compute_temporal_quartiles(combined, blocks),
        block_size_segments_histogram=segments_histogram,
        block_size_words_histogram=words_histogram,
        context_availability=compute_context_availability(blocks),
        gap_audit=compute_gap_audit(combined.segments),
        ai_estimation=compute_ai_estimation(blocks),
        analysis_duration_seconds=analysis_duration_seconds,
    )
