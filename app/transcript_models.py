"""
Modèles du contrat Transcript V2.

Deux familles de modèles, volontairement distinctes :

1. CAPTURE — ce que Whisper a réellement produit
   CapturedSegment / CapturedPart / AudioCapture

   Capturée au plus près de la sortie du modèle, avant toute mise en forme
   textuelle. Les timestamps d'un CapturedSegment sont LOCAUX au segment
   technique qui l'a produit ; CapturedPart.start_seconds donne son décalage
   dans le fichier audio source.

   C'est un artefact intermédiaire, jamais publié comme contrat.

2. CONTRAT — la représentation canonique publiée
   TranscriptSegment / TranscriptSource / TranscriptStats / TranscriptDocument

   Sérialisée dans transcripts/transcript_data.json. Les timestamps sont
   RELATIFS AU FICHIER AUDIO SOURCE, jamais à une timeline projet artificielle.

Aucune notion éditoriale (chapitre, thème, idée, résumé, importance) n'a sa
place ici : ce contrat décrit la SOURCE, pas le livre.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Version du contrat publié dans transcript_data.json.
SCHEMA_VERSION = "1.0"

# Version du format des artefacts de capture intermédiaires.
CAPTURE_VERSION = "1.0"

# Un projet représente actuellement une œuvre / transcription principale.
DEFAULT_TRANSCRIPT_ID = "TR001"

# Politique de précision : les timestamps sont conservés en nombres, arrondis à
# la milliseconde. Objectif : ne jamais perdre la précision de Whisper (12.37
# reste 12.37) tout en rendant la sérialisation stable et diffable.
TIMESTAMP_DECIMALS = 3

# Langue inconnue (aucune donnée exploitable) — code ISO 639-2 « undetermined ».
UNDETERMINED_LANGUAGE = "und"

CAPTURE_MODE_DIRECT = "direct"
CAPTURE_MODE_SEGMENTED = "segmented"


def round_seconds(value: float) -> float:
    """Arrondit un timestamp selon la politique de précision documentée."""
    return round(float(value), TIMESTAMP_DECIMALS)


def format_src_id(index: int) -> str:
    """
    Identifiant global d'un segment source : SRC000001, SRC000002, …

    Six chiffres : suffisant pour les très longs projets, sans limite utile.
    L'index est 1-based et continu dans l'ordre canonique du transcript.
    """
    return f"SRC{index:06d}"


def format_audio_id(order: int) -> str:
    """Identifiant d'un fichier audio source : AUDIO001, AUDIO002, …"""
    return f"AUDIO{order:03d}"


# ---------------------------------------------------------------------------
# 1 — Capture (proche de la sortie Whisper)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CapturedSegment:
    """Un segment Whisper brut, timestamps locaux au segment technique."""

    start: float
    end: float
    text: str

    def to_dict(self) -> dict:
        return {
            "start": round_seconds(self.start),
            "end": round_seconds(self.end),
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CapturedSegment:
        return cls(
            start=float(data["start"]),
            end=float(data["end"]),
            text=str(data["text"]),
        )


@dataclass
class CapturedPart:
    """
    Un segment TECHNIQUE d'un fichier audio (part_001, part_002, …).

    Un fichier audio court produit une seule partie (« direct »), de décalage 0.
    Un fichier audio long en produit autant que de découpes ffmpeg.

    Les parties techniques sont invisibles dans le contrat publié : elles ne
    deviennent jamais des sources éditoriales.
    """

    id: str
    start_seconds: float
    end_seconds: float
    effective_start_local: float
    detected_language: str
    segments: list[CapturedSegment] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "start_seconds": round_seconds(self.start_seconds),
            "end_seconds": round_seconds(self.end_seconds),
            "effective_start_local": round_seconds(self.effective_start_local),
            "detected_language": self.detected_language,
            "segments": [segment.to_dict() for segment in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict) -> CapturedPart:
        return cls(
            id=str(data["id"]),
            start_seconds=float(data["start_seconds"]),
            end_seconds=float(data["end_seconds"]),
            effective_start_local=float(data["effective_start_local"]),
            detected_language=str(data["detected_language"]),
            segments=[
                CapturedSegment.from_dict(item)
                for item in data.get("segments", [])
            ],
        )


@dataclass
class AudioCapture:
    """
    Tout ce qui a été transcrit pour UN fichier audio source.

    `filename` est le nom du fichier d'origine, sans chemin : le contrat publié
    doit rester portable.
    """

    filename: str
    duration_seconds: float
    mode: str
    parts: list[CapturedPart] = field(default_factory=list)
    capture_version: str = CAPTURE_VERSION

    def to_dict(self) -> dict:
        return {
            "capture_version": self.capture_version,
            "filename": self.filename,
            "duration_seconds": round_seconds(self.duration_seconds),
            "mode": self.mode,
            "parts": [part.to_dict() for part in self.parts],
        }

    @classmethod
    def from_dict(cls, data: dict) -> AudioCapture:
        return cls(
            filename=str(data["filename"]),
            duration_seconds=float(data["duration_seconds"]),
            mode=str(data["mode"]),
            parts=[CapturedPart.from_dict(item) for item in data.get("parts", [])],
            capture_version=str(data.get("capture_version", CAPTURE_VERSION)),
        )


# ---------------------------------------------------------------------------
# 2 — Contrat publié
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TranscriptSegment:
    """
    Un segment source transcrit — l'unité de traçabilité du pipeline éditorial.

    SRC ne représente ni un paragraphe final, ni une idée, ni un chunk
    technique, ni un chapitre.

    start / end sont relatifs au fichier audio identifié par source_id.
    """

    id: str
    source_id: str
    source_order: int
    start: float
    end: float
    text: str

    @property
    def duration_seconds(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "source_order": self.source_order,
            "start": self.start,
            "end": self.end,
            "text": self.text,
        }


@dataclass(frozen=True)
class TranscriptSource:
    """Un fichier audio source du projet."""

    source_id: str
    order: int
    filename: str
    duration_seconds: float
    detected_language: str

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "order": self.order,
            "filename": self.filename,
            "duration_seconds": self.duration_seconds,
            "detected_language": self.detected_language,
        }


@dataclass(frozen=True)
class TranscriptStats:
    """Comptages dérivés, vérifiés par le validateur avant publication."""

    source_count: int
    segment_count: int
    duration_seconds: float
    word_count: int

    def to_dict(self) -> dict:
        return {
            "source_count": self.source_count,
            "segment_count": self.segment_count,
            "duration_seconds": self.duration_seconds,
            "word_count": self.word_count,
        }


@dataclass
class TranscriptDocument:
    """
    Représentation structurée canonique d'un projet transcrit.

    C'est la source unique de transcript_data.json ET de transcript.txt : le
    texte humain est un rendu de ce modèle, jamais l'inverse.
    """

    project_name: str
    sources: list[TranscriptSource]
    segments: list[TranscriptSegment]
    stats: TranscriptStats
    primary_language: str
    detected_languages: list[str]
    transcript_id: str = DEFAULT_TRANSCRIPT_ID
    schema_version: str = SCHEMA_VERSION

    def source_by_id(self, source_id: str) -> TranscriptSource | None:
        for source in self.sources:
            if source.source_id == source_id:
                return source
        return None

    def segments_for(self, source_id: str) -> list[TranscriptSegment]:
        return [
            segment for segment in self.segments
            if segment.source_id == source_id
        ]

    def to_dict(self) -> dict:
        """
        Sérialisation déterministe du contrat.

        Aucun champ non déterministe (date de génération, UUID aléatoire) :
        à données Whisper identiques, le JSON produit est identique.
        """
        return {
            "schema_version": self.schema_version,
            "transcript_id": self.transcript_id,
            "project": {
                "name": self.project_name,
            },
            "language": {
                "primary": self.primary_language,
                "detected": list(self.detected_languages),
            },
            "sources": [source.to_dict() for source in self.sources],
            "segments": [segment.to_dict() for segment in self.segments],
            "stats": self.stats.to_dict(),
        }
