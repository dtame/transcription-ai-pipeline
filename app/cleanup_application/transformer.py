"""
Transformation du transcript original vers la vue clean.

clean_segments = [src for src in original_segments if src.id not in removal_set]

Aucun tri sémantique, aucun déplacement, aucun renumérotage, aucune
réécriture du texte survivant. Les objets TranscriptSegment survivants
sont ceux de l'original (même identité d'attributs).
"""

from __future__ import annotations

from app.cleanup_application.models import ApplicationPlan
from app.transcript_models import TranscriptDocument, TranscriptStats
from app.transcript_writer import render_transcript_text


def transform_document(
    original: TranscriptDocument,
    plan: ApplicationPlan,
) -> TranscriptDocument:
    clean_segments = [
        segment for segment in original.segments if segment.id not in plan.removal_set
    ]
    word_count = sum(len(segment.text.split()) for segment in clean_segments)
    stats = TranscriptStats(
        source_count=len(original.sources),
        segment_count=len(clean_segments),
        duration_seconds=original.stats.duration_seconds,
        word_count=word_count,
    )
    return TranscriptDocument(
        project_name=original.project_name,
        sources=list(original.sources),
        segments=clean_segments,
        stats=stats,
        primary_language=original.primary_language,
        detected_languages=list(original.detected_languages),
        transcript_id=original.transcript_id,
        schema_version=original.schema_version,
    )


def render_clean_text(document: TranscriptDocument) -> str:
    """Réutilise le renderer Phase 1 — les trous d'IDs n'affectent pas le TXT."""
    return render_transcript_text(document)
