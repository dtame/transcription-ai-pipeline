"""
Fixtures de la Phase 3A.2B (application POLICY_B+).

    make_context / decide_for     tests unitaires purs (aucun disque)
    make_document                 petit TranscriptDocument synthétique
    prepare_fixture_project       vrai petit projet sur disque + simulation 3A.2A
"""

from __future__ import annotations

from pathlib import Path

from app.cleanup_application.policy import PolicyContext, decide_policy_b_plus
from app.cleanup_policy.risk import compute_risk_flags
from app.language_cleanup.models import LANGUAGE_FR
from app.tests.cleanup_policy_fixtures import PROJECT, make_record
from app.transcript_models import (
    TranscriptDocument,
    TranscriptSegment,
    TranscriptSource,
    TranscriptStats,
)

__all__ = [
    "PROJECT",
    "make_record",
    "make_context",
    "decide_for",
    "make_document",
    "prepare_fixture_project",
]


def make_context(
    record,
    *,
    src_text: str | None = None,
    language: str = LANGUAGE_FR,
    missing_src: bool = False,
    duplicate_src: bool = False,
    audio_id: str | None = None,
) -> PolicyContext:
    segments: dict[str, TranscriptSegment] = {}
    counts: dict[str, int] = {}
    languages: dict[str, str] = {}
    text = record.text if src_text is None else src_text
    owner = audio_id if audio_id is not None else record.audio_id

    if not missing_src:
        for ref in record.fr_source_refs:
            segments[ref] = TranscriptSegment(
                ref,
                owner,
                1,
                record.start_seconds,
                record.end_seconds,
                text if len(record.fr_source_refs) == 1 else f"part {ref}",
            )
            counts[ref] = 2 if duplicate_src else 1
            languages[ref] = language

    for ref in record.bridge_source_refs:
        segments[ref] = TranscriptSegment(ref, owner, 1, 0.0, 0.4, "bridge token")
        counts[ref] = 1
        languages[ref] = "UNKNOWN"

    return PolicyContext(
        segments_by_id=segments,
        occurrence_count=counts,
        language_by_src=languages,
    )


def decide_for(record, **kwargs):
    context = make_context(record, **kwargs)
    return decide_policy_b_plus(record, compute_risk_flags(record), context)


def make_document(
    *,
    project_name: str = "demo",
    segments: list[TranscriptSegment] | None = None,
    sources: list[TranscriptSource] | None = None,
    primary_language: str = "en",
    detected_languages: list[str] | None = None,
    transcript_id: str = "TR001",
) -> TranscriptDocument:
    sources = sources if sources is not None else [
        TranscriptSource("AUDIO001", 1, "a.mp3", 300.0, "en"),
        TranscriptSource("AUDIO002", 2, "b.mp3", 600.0, "en"),
    ]
    segments = segments if segments is not None else [
        TranscriptSegment("SRC000001", "AUDIO001", 1, 0.0, 5.0, "english one"),
        TranscriptSegment("SRC000002", "AUDIO001", 1, 5.0, 8.0, "bonjour le monde"),
        TranscriptSegment("SRC000003", "AUDIO002", 2, 0.0, 4.0, "english two"),
    ]
    stats = TranscriptStats(
        source_count=len(sources),
        segment_count=len(segments),
        duration_seconds=round(sum(s.duration_seconds for s in sources), 3),
        word_count=sum(len(s.text.split()) for s in segments),
    )
    return TranscriptDocument(
        project_name=project_name,
        sources=sources,
        segments=segments,
        stats=stats,
        primary_language=primary_language,
        detected_languages=list(detected_languages or ["en"]),
        transcript_id=transcript_id,
    )


def write_fixture_transcript_txt(sortie_dir: Path) -> Path:
    from app.language_cleanup.transcript_source import load_transcript_document
    from app.source_analysis.transcript_input import transcript_data_file
    from app.source_analysis.writer import transcripts_dir
    from app.transcript_writer import render_transcript_text, transcript_text_path

    tdir = transcripts_dir(PROJECT, sortie_dir=sortie_dir)
    document = load_transcript_document(transcript_data_file(tdir))
    path = transcript_text_path(tdir)
    path.write_text(render_transcript_text(document), encoding="utf-8")
    return path


def prepare_fixture_project(sortie_dir: Path, *, overrides: dict[str, dict] | None = None):
    """
    Projet fixture complet prêt pour POLICY_B+ : artefacts 3A.1/3A.2A +
    transcript.txt + cleanup_policy_simulation.json.
    """
    from app.cleanup_policy.runner import run_cleanup_policy_simulation
    from app.language_blocks.writer import manifest_path as blocks_manifest_path
    from app.language_blocks.writer import read_manifest_payload
    from app.tests.cleanup_policy_fixtures import (
        build_full_fixture_project,
        write_classification_artifact_for_fixture,
    )

    result = build_full_fixture_project(sortie_dir, overrides=overrides)
    write_fixture_transcript_txt(sortie_dir)

    if overrides:
        payload = read_manifest_payload(blocks_manifest_path(PROJECT, sortie_dir=sortie_dir))
        write_classification_artifact_for_fixture(
            sortie_dir, blocks=list(payload["blocks"]), overrides=overrides
        )

    run_cleanup_policy_simulation(PROJECT, sortie_dir=sortie_dir)
    return result
