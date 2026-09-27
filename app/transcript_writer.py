"""
Publication des artefacts Transcript V2.

    TranscriptDocument
          ↓
    ┌─────┴─────┐
    ↓           ↓
transcript   transcript_data
   .txt          .json

transcript.txt          représentation humaine unifiée (lecture, diagnostic)
transcript_data.json    source structurée canonique du pipeline éditorial

Les deux fichiers proviennent du MÊME modèle structuré : le JSON ne dépend
jamais de la capacité à reparser le texte.

Garanties de publication :

- validation complète du contrat AVANT toute écriture ;
- écritures atomiques (« .partial » puis replace) : aucun artefact tronqué ;
- JSON publié en dernier : le contrat canonique n'apparaît qu'une fois le
  rendu humain écrit ;
- en cas d'échec, un transcript_data.json antérieur est explicitement invalidé
  et ne peut donc pas être pris pour le résultat courant.
"""

from __future__ import annotations

from pathlib import Path

from app.audio_utils import format_timestamp
from app.file_utils import write_json_atomic, write_text_atomic
from app.logger import log_event
from app.transcript_models import TranscriptDocument
from app.transcript_validator import ensure_valid_transcript_document

TRANSCRIPT_TXT_NAME = "transcript.txt"
TRANSCRIPT_JSON_NAME = "transcript_data.json"
INVALIDATED_JSON_NAME = "transcript_data.invalid.json"

SEPARATOR = "=" * 80


# ---------------------------------------------------------------------------
# Rendu humain
# ---------------------------------------------------------------------------

def render_transcript_text(
    document: TranscriptDocument,
    include_src_ids: bool = False,
) -> str:
    """
    Rendu lisible du transcript, une section par fichier audio source.

        ================================================================================
        SOURCE 1 — 01-introduction.mp3
        ================================================================================

        [00:00 -> 00:11] Ceci est un test...

    Les timestamps humains restent au format V1 ([MM:SS] / [HH:MM:SS]) et sont
    relatifs au fichier audio de la section.

    `include_src_ids=True` préfixe chaque ligne de son identifiant SRC : option
    de diagnostic, désactivée par défaut pour ne pas alourdir la lecture. Les
    identifiants restent disponibles dans transcript_data.json.
    """
    blocks: list[str] = []

    for source in document.sources:
        lines = [
            SEPARATOR,
            f"SOURCE {source.order} — {source.filename}",
            SEPARATOR,
            "",
        ]

        for segment in document.segments_for(source.source_id):
            timestamps = (
                f"[{format_timestamp(segment.start)} -> "
                f"{format_timestamp(segment.end)}]"
            )
            prefix = f"{segment.id} " if include_src_ids else ""
            lines.append(f"{prefix}{timestamps} {segment.text}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks).strip() + "\n" if blocks else ""


# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------

def transcript_text_path(transcripts_dir: Path) -> Path:
    return Path(transcripts_dir) / TRANSCRIPT_TXT_NAME


def transcript_data_path(transcripts_dir: Path) -> Path:
    return Path(transcripts_dir) / TRANSCRIPT_JSON_NAME


def invalidate_published_transcript(transcripts_dir: Path) -> Path | None:
    """
    Retire le statut de contrat courant à un transcript_data.json antérieur.

    Le fichier n'est pas détruit : il est renommé en transcript_data.invalid.json
    pour inspection. Après un échec de construction ou de validation, aucun
    fichier nommé transcript_data.json ne prétend donc décrire l'état courant.
    """
    published = transcript_data_path(transcripts_dir)

    if not published.exists():
        return None

    invalidated = Path(transcripts_dir) / INVALIDATED_JSON_NAME
    published.replace(invalidated)

    log_event({
        "event": "transcript_v2_artifact_invalidated",
        "path": str(invalidated),
    })

    return invalidated


def publish_transcript_artifacts(
    document: TranscriptDocument,
    transcripts_dir: Path,
    include_src_ids: bool = False,
) -> dict[str, Path]:
    """
    Valide puis publie transcript.txt et transcript_data.json.

    Lève TranscriptValidationError si le contrat n'est pas respecté : dans ce cas
    aucun fichier n'est écrit et un artefact antérieur est invalidé.

    Retourne les chemins publiés : {"text": ..., "data": ...}.
    """
    transcripts_dir = Path(transcripts_dir)

    try:
        ensure_valid_transcript_document(document)
    except Exception as exc:
        log_event({
            "event": "transcript_v2_validation_failed",
            "project": document.project_name,
            "error": str(exc),
        })
        invalidate_published_transcript(transcripts_dir)
        raise

    text_path = transcript_text_path(transcripts_dir)
    data_path = transcript_data_path(transcripts_dir)

    # Le rendu humain d'abord : le contrat canonique n'est publié qu'ensuite,
    # donc un JSON présent implique toujours un transcript.txt correspondant.
    write_text_atomic(text_path, render_transcript_text(document, include_src_ids))
    write_json_atomic(data_path, document.to_dict())

    return {"text": text_path, "data": data_path}
