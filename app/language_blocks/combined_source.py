"""
Lecture en LECTURE SEULE et fusion de transcript_data.json + language_cleanup.json.

Ce module ne réécrit jamais aucun des deux fichiers sources (§4, §38 du cahier
des charges Phase 3A.1.1). Il réutilise volontairement les lecteurs et
validateurs déjà publiés plutôt que de les dupliquer :

    app.transcript_validator.ensure_valid_transcript_document   (contrat V2)
    app.language_cleanup.transcript_source.load_audit_transcript /
        load_transcript_document                                 (lecture)
    app.language_cleanup.writer.read_manifest_payload             (lecture)
    app.language_cleanup.validator.ensure_valid_manifest_payload  (contrat 3A.1)

Le SHA-256 des deux fichiers est calculé sur le contenu texte tel que lu sur le
disque (`app.file_utils.content_hash`), jamais sur une reconstruction : ce sont
ces valeurs qui doivent rester identiques avant et après l'analyse.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.file_utils import content_hash
from app.language_blocks.errors import SourceIntegrityError
from app.language_cleanup.transcript_source import (
    AuditTranscript,
    load_audit_transcript,
    load_transcript_document,
    transcript_data_file,
)
from app.language_cleanup.validator import ensure_valid_manifest_payload
from app.language_cleanup.writer import manifest_path as cleanup_manifest_path
from app.language_cleanup.writer import read_manifest_payload
from app.language_cleanup.errors import ManifestValidationError
from app.transcript_validator import (
    TranscriptValidationError,
    ensure_valid_transcript_document,
)


@dataclass(frozen=True)
class CombinedSegment:
    """Un SRC, avec sa position canonique, sa classification et sa décision 3A.1."""

    position: int
    src_id: str
    audio_id: str
    start: float
    end: float
    text: str
    language: str
    decision: str
    matched_english_source_refs: tuple[str, ...]
    match_direction: str | None
    translation_confidence: float

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(frozen=True)
class AudioSourceInfo:
    audio_id: str
    order: int
    duration_seconds: float


@dataclass(frozen=True)
class CombinedSource:
    """Vue fusionnée, prête pour l'analyse structurelle des blocs FR."""

    project_name: str
    transcript_id: str
    transcript_sha256: str
    language_cleanup_sha256: str
    segments: tuple[CombinedSegment, ...]
    sources: tuple[AudioSourceInfo, ...]

    def src_index(self) -> dict[str, int]:
        return {segment.src_id: segment.position for segment in self.segments}

    def source_by_id(self, audio_id: str) -> AudioSourceInfo | None:
        for source in self.sources:
            if source.audio_id == audio_id:
                return source
        return None


def load_combined_source(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    transcripts_dir: Path | None = None,
    language_cleanup_path: Path | None = None,
) -> CombinedSource:
    """
    Charge, valide et fusionne transcript_data.json et language_cleanup.json.

    Lève SourceIntegrityError (ou laisse propager TranscriptValidationError /
    ManifestValidationError) si l'un des deux fichiers ne satisfait pas son
    propre contrat, ou si les deux fichiers ne concordent pas assez pour être
    analysés ensemble en toute sécurité.
    """
    transcript_path = (
        Path(transcripts_dir) / "transcript_data.json"
        if transcripts_dir is not None
        else transcript_data_file(project_name, sortie_dir=sortie_dir)
    )

    audit_transcript = load_audit_transcript(transcript_path, project_name=project_name)

    # §4 : revalider également avec le validateur V2 complet (pas seulement le
    # sous-ensemble de contrôles que load_audit_transcript effectue).
    document = load_transcript_document(transcript_path)
    try:
        ensure_valid_transcript_document(document)
    except TranscriptValidationError as exc:
        raise SourceIntegrityError(
            f"transcript_data.json ne satisfait pas le contrat Transcript V2 : {exc}"
        ) from exc

    manifest_file = (
        Path(language_cleanup_path)
        if language_cleanup_path is not None
        else cleanup_manifest_path(project_name, sortie_dir=sortie_dir)
    )

    if not manifest_file.exists():
        raise SourceIntegrityError(
            f"language_cleanup.json introuvable : {manifest_file}. La Phase "
            "3A.1.1 exige le manifeste déjà publié par la Phase 3A.1."
        )

    manifest_payload = read_manifest_payload(manifest_file)

    if manifest_payload is None:
        raise SourceIntegrityError(
            f"language_cleanup.json illisible ou vide : {manifest_file}."
        )

    try:
        ensure_valid_manifest_payload(manifest_payload, audit_transcript)
    except ManifestValidationError as exc:
        raise SourceIntegrityError(
            f"language_cleanup.json ne satisfait pas son propre contrat : {exc}"
        ) from exc

    cleanup_raw = manifest_file.read_text(encoding="utf-8")
    cleanup_sha256 = content_hash(cleanup_raw)

    manifest_segments = manifest_payload.get("segments") or []

    if len(manifest_segments) != len(audit_transcript.segments):
        raise SourceIntegrityError(
            "language_cleanup.json et transcript_data.json n'ont pas le même "
            f"nombre de segments ({len(manifest_segments)} != "
            f"{len(audit_transcript.segments)})"
        )

    combined_segments: list[CombinedSegment] = []

    for position, (original, entry) in enumerate(
        zip(audit_transcript.segments, manifest_segments)
    ):
        source_ref = str(entry.get("source_ref") or "")

        if source_ref != original.src_id:
            raise SourceIntegrityError(
                f"ordre incohérent entre les deux fichiers en position "
                f"{position} : transcript={original.src_id!r} vs "
                f"language_cleanup={source_ref!r}"
            )

        matched_refs = entry.get("matched_english_source_refs") or []

        combined_segments.append(
            CombinedSegment(
                position=position,
                src_id=original.src_id,
                audio_id=original.source_id,
                start=original.start,
                end=original.end,
                text=original.text,
                language=str(entry.get("language") or ""),
                decision=str(entry.get("decision") or ""),
                matched_english_source_refs=tuple(str(r) for r in matched_refs),
                match_direction=entry.get("match_direction"),
                translation_confidence=float(entry.get("translation_confidence") or 0.0),
            )
        )

    sources = tuple(
        AudioSourceInfo(
            audio_id=source.source_id,
            order=source.order,
            duration_seconds=source.duration_seconds,
        )
        for source in sorted(document.sources, key=lambda s: s.order)
    )

    return CombinedSource(
        project_name=audit_transcript.project_name,
        transcript_id=audit_transcript.transcript_id,
        transcript_sha256=audit_transcript.content_sha256,
        language_cleanup_sha256=cleanup_sha256,
        segments=tuple(combined_segments),
        sources=sources,
    )
