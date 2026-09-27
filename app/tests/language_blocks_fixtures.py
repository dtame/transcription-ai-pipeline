"""
Fixtures partagées des tests de la Phase 3A.1.1 (analyse structurelle des
blocs FR — app.language_blocks).

Deux familles d'aides :

1. `make_segment` / `build_sequence` / `make_combined` : construisent un
   `CombinedSource` directement en mémoire, SANS passer par un vrai
   transcript_data.json ni un vrai language_cleanup.json. Utile pour tester
   runs.py / bridging.py / context.py / classifier.py / builder.py en
   contrôlant précisément langue, durée, mots et décision Phase 3A.1 de
   chaque SRC — sans dépendre des heuristiques de language_detector.py ni de
   translation_matcher.py (déjà testées par app/tests/test_language_cleanup_*).

2. rien ici ne touche à un projet réel : tout vit en mémoire ou dans
   tmp_path (voir les tests eux-mêmes pour la variante bout-en-bout, qui
   réutilise app.tests.source_analysis_fixtures pour produire un VRAI
   transcript V2 avant d'y faire tourner l'audit Phase 3A.1 puis l'analyse
   Phase 3A.1.1).
"""

from __future__ import annotations

from app.language_blocks.combined_source import (
    AudioSourceInfo,
    CombinedSegment,
    CombinedSource,
)

DEFAULT_TRANSCRIPT_SHA = "a" * 64
DEFAULT_CLEANUP_SHA = "b" * 64


def make_segment(
    position: int,
    *,
    src_id: str | None = None,
    audio_id: str = "AUDIO001",
    start: float = 0.0,
    end: float = 1.0,
    text: str = "word",
    language: str = "EN",
    decision: str = "KEEP",
    matched: tuple[str, ...] = (),
    direction: str | None = None,
    confidence: float = 0.0,
) -> CombinedSegment:
    return CombinedSegment(
        position=position,
        src_id=src_id or f"SRC{position + 1:06d}",
        audio_id=audio_id,
        start=start,
        end=end,
        text=text,
        language=language,
        decision=decision,
        matched_english_source_refs=tuple(matched),
        match_direction=direction,
        translation_confidence=confidence,
    )


def build_sequence(
    specs: list[dict],
    *,
    default_audio_id: str = "AUDIO001",
    default_duration: float = 1.0,
    default_gap: float = 0.1,
    start_at: float = 0.0,
) -> tuple[CombinedSegment, ...]:
    """
    Construit une séquence de CombinedSegment consécutifs (positions 0..n-1).

    Chaque `spec` accepte : language (obligatoire), text, decision, duration,
    gap_before (silence avant CE segment, ignoré pour le premier), audio_id,
    matched, direction, confidence, src_id.
    """
    segments: list[CombinedSegment] = []
    cursor = start_at

    for index, spec in enumerate(specs):
        gap_before = spec.get("gap_before", default_gap) if index > 0 else 0.0
        cursor += gap_before

        duration = spec.get("duration", default_duration)
        audio_id = spec.get("audio_id", default_audio_id)

        segments.append(
            make_segment(
                index,
                src_id=spec.get("src_id"),
                audio_id=audio_id,
                start=cursor,
                end=cursor + duration,
                text=spec.get("text", f"word{index}"),
                language=spec["language"],
                decision=spec.get("decision", "KEEP"),
                matched=tuple(spec.get("matched", ())),
                direction=spec.get("direction"),
                confidence=spec.get("confidence", 0.0),
            )
        )
        cursor += duration

    return tuple(segments)


def make_combined(
    segments: tuple[CombinedSegment, ...],
    *,
    sources: tuple[AudioSourceInfo, ...] | None = None,
    transcript_id: str = "TR001",
    transcript_sha256: str = DEFAULT_TRANSCRIPT_SHA,
    language_cleanup_sha256: str = DEFAULT_CLEANUP_SHA,
    project_name: str = "test_project",
    default_source_duration: float = 1_000_000.0,
) -> CombinedSource:
    """
    `default_source_duration` est volontairement énorme : les tests qui ne
    portent pas explicitement sur les quartiles temporels (§24) n'ont pas à se
    soucier de la position relative de leurs SRC de test dans une durée
    d'AUDIO réaliste.
    """
    if sources is None:
        seen: list[str] = []
        for segment in segments:
            if segment.audio_id not in seen:
                seen.append(segment.audio_id)
        sources = tuple(
            AudioSourceInfo(
                audio_id=audio_id, order=index + 1, duration_seconds=default_source_duration
            )
            for index, audio_id in enumerate(seen)
        )

    return CombinedSource(
        project_name=project_name,
        transcript_id=transcript_id,
        transcript_sha256=transcript_sha256,
        language_cleanup_sha256=language_cleanup_sha256,
        segments=segments,
        sources=sources,
    )
