"""
Index déterministe des segments SRC de transcript_data.json (§20, §24).

Sert uniquement à mesurer l'impact (durée, mots) des `fr_source_refs`
candidats à la suppression — jamais à modifier ou reconstruire le
transcript. Lecture seule, aucune écriture.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SegmentInfo:
    """Vue minimale d'un SRC, dérivée du contrat Transcript V2."""

    src_id: str
    source_id: str
    start: float
    end: float
    word_count: int

    @property
    def duration_seconds(self) -> float:
        return round(self.end - self.start, 6)


@dataclass(frozen=True)
class TranscriptIndex:
    """Index en mémoire des segments d'un transcript_data.json chargé."""

    segments_by_id: dict[str, SegmentInfo]
    total_segment_count: int
    total_word_count: int
    total_duration_seconds: float

    def duration_for_refs(self, refs: list[str]) -> float:
        """Somme des durées des SRC listés — 0.0 si `refs` est vide."""
        return round(
            sum(self.segments_by_id[ref].duration_seconds for ref in refs), 6
        )

    def word_count_for_refs(self, refs: list[str]) -> int:
        """Somme des `word_count` (texte segmenté) des SRC listés."""
        return sum(self.segments_by_id[ref].word_count for ref in refs)


def build_transcript_index(transcript_data: dict) -> TranscriptIndex:
    """
    Construit l'index depuis le payload complet de transcript_data.json.

    N'invente rien : `word_count` par segment est recompté depuis le texte
    publié (`len(text.split())`), exactement comme
    app.transcript_models.TranscriptStats.word_count l'agrège déjà pour le
    total du document (§24 : original_words = 39055, vérifié depuis
    l'artefact réel, pas depuis un rapport).
    """
    segments_by_id: dict[str, SegmentInfo] = {}

    for segment in transcript_data.get("segments") or []:
        src_id = str(segment["id"])
        text = str(segment.get("text") or "")
        segments_by_id[src_id] = SegmentInfo(
            src_id=src_id,
            source_id=str(segment.get("source_id") or ""),
            start=float(segment.get("start", 0.0)),
            end=float(segment.get("end", 0.0)),
            word_count=len(text.split()),
        )

    stats = transcript_data.get("stats") or {}

    return TranscriptIndex(
        segments_by_id=segments_by_id,
        total_segment_count=int(stats.get("segment_count", len(segments_by_id))),
        total_word_count=int(
            stats.get("word_count", sum(s.word_count for s in segments_by_id.values()))
        ),
        total_duration_seconds=float(stats.get("duration_seconds", 0.0)),
    )
