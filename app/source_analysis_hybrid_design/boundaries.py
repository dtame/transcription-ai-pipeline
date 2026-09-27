"""
Audit des signaux de frontière disponibles — aucun découpage sémantique.

Les signaux techniques (AUDIO, pauses, parts) sont inventoriés. Ils ne
deviennent pas une segmentation sémantique Python.
"""

from __future__ import annotations

from typing import Any

from app.source_analysis.transcript_input import TranscriptInput

# Seuil d'inventaire seulement. Pas une règle de coupe.
LONG_PAUSE_SECONDS = 5.0


def audit_boundary_signals(transcript: TranscriptInput) -> dict[str, Any]:
    segments = transcript.segments
    source_ids: list[str] = []
    source_changes: list[dict[str, Any]] = []
    long_pauses: list[dict[str, Any]] = []
    previous_source = ""
    previous_end = 0.0
    same_source_gaps = 0
    cross_source_gaps = 0

    for index, segment in enumerate(segments):
        source = segment.source_id or ""
        if source and source not in source_ids:
            source_ids.append(source)
        if previous_source and source != previous_source:
            source_changes.append(
                {
                    "after_src": segments[index - 1].src_id,
                    "at_src": segment.src_id,
                    "from_source_id": previous_source,
                    "to_source_id": source,
                    "gap_seconds": round(segment.start - previous_end, 3)
                    if segment.start >= previous_end
                    else None,
                }
            )
            cross_source_gaps += 1
        elif previous_source and source == previous_source:
            gap = segment.start - previous_end
            same_source_gaps += 1
            if gap >= LONG_PAUSE_SECONDS:
                long_pauses.append(
                    {
                        "after_src": segments[index - 1].src_id,
                        "at_src": segment.src_id,
                        "gap_seconds": round(gap, 3),
                        "source_id": source,
                    }
                )
        previous_source = source
        previous_end = segment.end

    return {
        "available_signals": [
            "source_id / AUDIO recording identity",
            "segment start/end timestamps",
            "source_order",
            "technical audio part boundaries in project_state (not on SRC)",
        ],
        "not_available_as_reliable_semantic_cuts": [
            "topic labels",
            "idea boundaries",
            "speaker-turn semantics derived from text",
        ],
        "distinct_source_ids": source_ids,
        "distinct_source_id_count": len(source_ids),
        "audio_source_change_count": len(source_changes),
        "audio_source_changes": source_changes,
        "long_pause_threshold_seconds": LONG_PAUSE_SECONDS,
        "long_pause_count": len(long_pauses),
        "long_pauses_first_twenty": long_pauses[:20],
        "same_source_consecutive_pairs": same_source_gaps,
        "cross_source_pairs": cross_source_gaps,
        "policy": (
            "Token-balanced SRC boundaries are the production cut rule. "
            "Audio/source changes and long pauses are technical metadata "
            "only. They must not become chapters, themes, or Python-invented "
            "semantic segments. Optional later snap-to-nearby-audio-boundary "
            "is deferred; v1 does not prefer them."
        ),
        "used_for_v1_cuts": False,
    }
