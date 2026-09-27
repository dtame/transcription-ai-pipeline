"""
Accès en LECTURE SEULE au Transcript V2 pour l'audit linguistique.

Ce module ne dépend PAS de app/source_analysis (indépendance exigée par §6 du
cahier des charges Phase 3A.1), même si sa forme s'inspire délibérément de
app/source_analysis/transcript_input.py : même prudence de lecture, même
refus de reconstruire quoi que ce soit depuis merged/, chunks/, processed/,
reviewed/, final/ ou publication/.

Ce module n'écrit jamais dans transcript_data.json ni transcript.txt. Le SHA-256
qu'il calcule est celui du FICHIER lu sur le disque, jamais d'une
reconstruction — c'est ce SHA qui doit être identique avant et après l'audit
(§5 du cahier des charges).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.file_utils import content_hash
from app.language_cleanup.errors import AuditTranscriptError
from app.paths import SORTIE_DIR
from app.transcript_models import SCHEMA_VERSION as TRANSCRIPT_SCHEMA_VERSION

TRANSCRIPTS_DIR_NAME = "transcripts"
TRANSCRIPT_JSON_NAME = "transcript_data.json"
AUDIT_DIR_NAME = "audit"


@dataclass(frozen=True)
class AuditSourceSegment:
    """Un SRC du transcript, tel que publié. Jamais modifié ici."""

    src_id: str
    source_id: str
    start: float
    end: float
    text: str

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(frozen=True)
class AuditTranscript:
    """
    Vue en lecture seule du transcript V2, prête pour l'audit linguistique.

    `content_sha256` est le hash du FICHIER tel qu'il a été lu : c'est cette
    valeur qui doit rester identique avant et après l'audit (§5), et c'est elle
    qui entre dans le manifeste publié.
    """

    project_name: str
    transcript_id: str
    schema_version: str
    primary_language: str
    detected_languages: tuple[str, ...]
    segments: tuple[AuditSourceSegment, ...]
    path: Path
    content_sha256: str
    source_count: int
    stats_word_count: int
    stats_duration_seconds: float

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def word_count(self) -> int:
        return sum(segment.word_count for segment in self.segments)

    def src_index(self) -> dict[str, int]:
        """Position canonique (0-based) de chaque SRC, dans l'ordre du fichier."""
        return {segment.src_id: position for position, segment in enumerate(self.segments)}

    def src_ids(self) -> tuple[str, ...]:
        return tuple(segment.src_id for segment in self.segments)


def transcripts_dir(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    return root / project_name / TRANSCRIPTS_DIR_NAME


def transcript_data_file(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return transcripts_dir(project_name, sortie_dir=sortie_dir) / TRANSCRIPT_JSON_NAME


def audit_dir(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    """Répertoire des artefacts de l'audit linguistique Phase 3A.1."""
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    return root / project_name / AUDIT_DIR_NAME


def compute_file_sha256(path: Path) -> str:
    """SHA-256 du fichier tel qu'il existe actuellement sur le disque."""
    raw = Path(path).read_text(encoding="utf-8")
    return content_hash(raw)


def load_audit_transcript(path: Path, *, project_name: str | None = None) -> AuditTranscript:
    """
    Lit et contrôle transcript_data.json, puis en retourne une vue d'audit.

    Les contrôles sont limités à ce dont l'audit a besoin pour être correct
    (présence, version, identité, segments, langue) : le contrat complet est
    déjà garanti par app/transcript_validator.py, revalidé séparément par
    l'appelant (voir auditor.py) plutôt que dupliqué ici.
    """
    path = Path(path)

    if not path.exists():
        raise AuditTranscriptError(
            f"Transcript V2 introuvable : {path}. L'audit linguistique exige le "
            "contrat publié par la Phase 1 et ne reconstruit rien depuis les "
            "artefacts V1."
        )

    raw = path.read_text(encoding="utf-8")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AuditTranscriptError(
            f"Transcript V2 illisible ({path}) : JSON invalide ligne {exc.lineno}."
        ) from exc

    if not isinstance(payload, dict):
        raise AuditTranscriptError(
            f"Transcript V2 invalide ({path}) : un objet JSON est attendu."
        )

    schema_version = str(payload.get("schema_version", ""))

    if schema_version != TRANSCRIPT_SCHEMA_VERSION:
        raise AuditTranscriptError(
            f"Version de contrat Transcript inattendue : « {schema_version} » "
            f"au lieu de « {TRANSCRIPT_SCHEMA_VERSION} ». L'audit refuse "
            "d'analyser un contrat qu'il ne connaît pas."
        )

    transcript_id = str(payload.get("transcript_id") or "").strip()

    if not transcript_id:
        raise AuditTranscriptError(
            f"Transcript V2 invalide ({path}) : transcript_id absent."
        )

    language = payload.get("language") or {}

    if not isinstance(language, dict):
        raise AuditTranscriptError(
            f"Transcript V2 invalide ({path}) : bloc « language » malformé."
        )

    primary_language = str(language.get("primary") or "").strip()

    if not primary_language:
        raise AuditTranscriptError(
            f"Transcript V2 invalide ({path}) : language.primary absent."
        )

    detected = language.get("detected") or []

    if not isinstance(detected, list):
        raise AuditTranscriptError(
            f"Transcript V2 invalide ({path}) : language.detected malformé."
        )

    sources = payload.get("sources") or []

    if not isinstance(sources, list):
        raise AuditTranscriptError(
            f"Transcript V2 invalide ({path}) : bloc « sources » malformé."
        )

    segments = _read_segments(payload, path)

    resolved_project = project_name or str((payload.get("project") or {}).get("name") or "")

    if not resolved_project:
        raise AuditTranscriptError(
            f"Transcript V2 invalide ({path}) : nom de projet absent."
        )

    stats = payload.get("stats") or {}

    return AuditTranscript(
        project_name=resolved_project,
        transcript_id=transcript_id,
        schema_version=schema_version,
        primary_language=primary_language,
        detected_languages=tuple(str(code) for code in detected),
        segments=segments,
        path=path,
        content_sha256=content_hash(raw),
        source_count=len(sources),
        stats_word_count=int(stats.get("word_count", 0) or 0),
        stats_duration_seconds=float(stats.get("duration_seconds", 0.0) or 0.0),
    )


def _read_segments(payload: dict, path: Path) -> tuple[AuditSourceSegment, ...]:
    raw_segments = payload.get("segments")

    if not isinstance(raw_segments, list) or not raw_segments:
        raise AuditTranscriptError(
            f"Transcript V2 invalide ({path}) : aucun segment source."
        )

    segments: list[AuditSourceSegment] = []
    seen: set[str] = set()

    for position, entry in enumerate(raw_segments, start=1):
        if not isinstance(entry, dict):
            raise AuditTranscriptError(
                f"Transcript V2 invalide ({path}) : segment n°{position} malformé."
            )

        src_id = str(entry.get("id") or "").strip()

        if not src_id:
            raise AuditTranscriptError(
                f"Transcript V2 invalide ({path}) : segment n°{position} sans "
                "identifiant."
            )

        if src_id in seen:
            raise AuditTranscriptError(
                f"Transcript V2 invalide ({path}) : identifiant de segment "
                f"dupliqué « {src_id} »."
            )

        seen.add(src_id)

        segments.append(
            AuditSourceSegment(
                src_id=src_id,
                source_id=str(entry.get("source_id") or ""),
                start=float(entry.get("start", 0.0)),
                end=float(entry.get("end", 0.0)),
                text=str(entry.get("text") or ""),
            )
        )

    return tuple(segments)


def load_transcript_document(path: Path):
    """
    Relit transcript_data.json comme app.transcript_models.TranscriptDocument,
    pour le passer aux validateurs V2 existants (§4 du cahier des charges :
    « valider également le transcript avec les validateurs V2 existants »).

    Import local pour ne pas alourdir le chemin d'audit courant : cette
    fonction ne sert qu'au contrôle d'intégrité amont, appelé une fois.
    """
    from app.transcript_models import (
        TranscriptDocument,
        TranscriptSegment,
        TranscriptSource,
        TranscriptStats,
    )

    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    sources = [
        TranscriptSource(
            source_id=str(item.get("source_id") or ""),
            order=int(item.get("order") or 0),
            filename=str(item.get("filename") or ""),
            duration_seconds=float(item.get("duration_seconds") or 0.0),
            detected_language=str(item.get("detected_language") or ""),
        )
        for item in payload.get("sources") or []
    ]

    segments = [
        TranscriptSegment(
            id=str(item.get("id") or ""),
            source_id=str(item.get("source_id") or ""),
            source_order=int(item.get("source_order") or 0),
            start=float(item.get("start") or 0.0),
            end=float(item.get("end") or 0.0),
            text=str(item.get("text") or ""),
        )
        for item in payload.get("segments") or []
    ]

    stats_raw = payload.get("stats") or {}
    stats = TranscriptStats(
        source_count=int(stats_raw.get("source_count") or 0),
        segment_count=int(stats_raw.get("segment_count") or 0),
        duration_seconds=float(stats_raw.get("duration_seconds") or 0.0),
        word_count=int(stats_raw.get("word_count") or 0),
    )

    language = payload.get("language") or {}

    return TranscriptDocument(
        project_name=str((payload.get("project") or {}).get("name") or ""),
        sources=sources,
        segments=segments,
        stats=stats,
        primary_language=str(language.get("primary") or ""),
        detected_languages=list(language.get("detected") or []),
        transcript_id=str(payload.get("transcript_id") or ""),
        schema_version=str(payload.get("schema_version") or ""),
    )
