"""
Accès à la source de vérité métier de la Phase 3.

Mode SOURCE (défaut) : sortie/<projet>/transcripts/transcript_data.json
avec le contrat Phase 1 (SRC continus).

Mode DERIVED (explicite) : une vue dérivée (ex. transcripts/clean/) n'est
chargée qu'avec une provenance vérifiée (cleanup_application.json). Les
trous de SRC n'y sont jamais un défaut global.

Ce module ne reconstruit rien depuis merged/, chunks/, processed/,
reviewed/, final/ ni publication/ : ces répertoires sont des artefacts V1.

`document_final.md` n'est pas lu, même s'il existe.

Ce qui sort d'ici est une vue en LECTURE SEULE : segments dans leur ordre
canonique, index de SRC PRÉSENTS pour la validation des références, langue
principale pour la langue de sortie de l'analyse.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.file_utils import content_hash
from app.source_analysis.errors import (
    SourceTranscriptError,
    SourceTranscriptProvenanceError,
)
from app.transcript_models import SCHEMA_VERSION as TRANSCRIPT_SCHEMA_VERSION
from app.transcript_models import format_src_id
from app.transcript_validator import SRC_ID_PATTERN
from app.transcript_writer import TRANSCRIPT_JSON_NAME

# Répertoire canonique d'une vue dérivée : transcripts/clean/transcript_data.json.
# La résolution de l'original est explicite (frère du parent `clean/`), jamais
# une recherche sur le disque ni un test du type « /clean/ dans le chemin ».
CLEAN_DIR_NAME = "clean"


class TranscriptInputMode(str, Enum):
    """
    Contrat de chargement du transcript pour le Source Analyzer.

    SOURCE   — transcript original Phase 1 : SRC continus obligatoires.
               C'est le DEFAULT. Les trous sont INVALIDES.
    DERIVED  — vue dérivée validée (ex. clean POLICY_B+) : trous autorisés
               uniquement si une provenance (cleanup_application.json) le
               démontre. Jamais le défaut. Jamais un simple allow_gaps.
    """

    SOURCE = "SOURCE"
    DERIVED = "DERIVED"

# Sous le seuil, il n'y a pas de discours à analyser : quelques mots isolés,
# un raclement de gorge, un fichier presque silencieux. Le seuil ne prétend pas
# mesurer la richesse d'un contenu — il distingue « rien » de « quelque chose ».
# Au-dessus, une analyse sans aucune idée est un échec (voir le garde-fou de
# complétude dans validator.py) ; en dessous, l'analyse est refusée d'emblée.
SUBSTANTIAL_WORD_THRESHOLD = 30


@dataclass(frozen=True)
class SourceSegment:
    """Un SRC du transcript, tel qu'il est publié. Jamais modifié ici."""

    src_id: str
    source_id: str
    start: float
    end: float
    text: str
    source_order: int = 0

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass(frozen=True)
class TranscriptInput:
    """
    Vue en lecture seule du transcript V2, prête pour l'analyse.

    `content_sha256` est le hash du FICHIER tel qu'il a été lu : c'est lui qui
    entre dans la signature de cache, pas une reconstruction du contenu qui
    pourrait diverger du fichier réellement présent sur le disque.
    """

    project_name: str
    transcript_id: str
    primary_language: str
    detected_languages: tuple[str, ...]
    segments: tuple[SourceSegment, ...]
    path: Path
    content_sha256: str
    schema_version: str
    duration_seconds: float = 0.0
    mode: TranscriptInputMode = TranscriptInputMode.SOURCE
    provenance_path: Path | None = None
    original_transcript_path: Path | None = None

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def word_count(self) -> int:
        return sum(segment.word_count for segment in self.segments)

    @property
    def is_substantial(self) -> bool:
        """
        True si la source contient assez de discours pour qu'une analyse ait un
        sens. Voir SUBSTANTIAL_WORD_THRESHOLD pour la justification du seuil.
        """
        return self.word_count >= SUBSTANTIAL_WORD_THRESHOLD

    def src_index(self) -> dict[str, int]:
        """
        Position canonique (0-based) de chaque SRC PRÉSENT.

        L'index suit l'ordre du fichier, pas une plage numérique SRC000001…
        SRC000N. Un transcript DERIVED avec SRC000100, SRC000102 a donc
        l'index {SRC000100: 0, SRC000102: 1} — SRC000101 n'existe pas.
        """
        return {segment.src_id: position for position, segment in enumerate(self.segments)}

    def src_ids(self) -> tuple[str, ...]:
        return tuple(segment.src_id for segment in self.segments)

    def src_set(self) -> frozenset[str]:
        """Ensemble des SRC réellement présents — pas une plage continue."""
        return frozenset(self.src_ids())


def transcript_data_file(transcripts_dir: Path) -> Path:
    """Chemin du contrat Transcript V2 dans un répertoire transcripts/."""
    return Path(transcripts_dir) / TRANSCRIPT_JSON_NAME


def coerce_transcript_mode(mode: TranscriptInputMode | str) -> TranscriptInputMode:
    """Normalise le mode de chargement. Toute valeur inconnue est un échec."""
    if isinstance(mode, TranscriptInputMode):
        return mode

    text = str(mode).strip().upper()

    try:
        return TranscriptInputMode(text)
    except ValueError as exc:
        raise SourceTranscriptError(
            f"mode de transcript inconnu : {mode!r} "
            f"(attendu {TranscriptInputMode.SOURCE.value} ou "
            f"{TranscriptInputMode.DERIVED.value})."
        ) from exc


def resolve_original_transcript_path(derived_path: Path) -> Path:
    """
    Résolution EXPLICITE de l'original à partir d'une vue `clean/`.

    transcripts/clean/transcript_data.json
        → transcripts/transcript_data.json

    Pas de recherche sur le disque, pas de test « /clean/ dans le chemin »
    ailleurs, pas de fallback. Si le parent n'est pas `clean`, échec.
    """
    derived_path = Path(derived_path)
    parent = derived_path.parent

    if parent.name != CLEAN_DIR_NAME:
        raise SourceTranscriptProvenanceError(
            f"Impossible de résoudre le transcript original depuis {derived_path} : "
            f"le parent doit s'appeler « {CLEAN_DIR_NAME} » "
            f"(résolution explicite transcripts/clean/ → transcripts/)."
        )

    return parent.parent / derived_path.name


def load_transcript_input(
    path: Path,
    *,
    project_name: str | None = None,
    mode: TranscriptInputMode | str = TranscriptInputMode.SOURCE,
    provenance_path: Path | None = None,
    original_transcript_path: Path | None = None,
) -> TranscriptInput:
    """
    Lit et contrôle transcript_data.json, puis en retourne une vue d'analyse.

    `mode` vaut SOURCE par défaut : le contrat Phase 1 (SRC continus) reste
    inchangé. DERIVED n'est jamais deviné — il doit être demandé explicitement
    et s'accompagne d'une provenance vérifiée (cleanup_application.json).

    Les contrôles de présence / version / langue restent ceux de la Phase 3.
    La continuité SRC, elle, est désormais appliquée ici selon le mode :
    SOURCE exige SRC000001, SRC000002, … ; DERIVED n'autorise les trous qu'après
    preuve de provenance.
    """
    path = Path(path)
    resolved_mode = coerce_transcript_mode(mode)

    if not path.exists():
        raise SourceTranscriptError(
            f"Transcript V2 introuvable : {path}. La Phase 3 exige le contrat "
            "publié par la Phase 1 et ne reconstruit rien depuis les artefacts V1."
        )

    if resolved_mode is TranscriptInputMode.DERIVED:
        if provenance_path is None:
            raise SourceTranscriptProvenanceError(
                f"Transcript DERIVED ({path}) : provenance_path obligatoire "
                "(cleanup_application.json). Les trous de SRC ne sont acceptés "
                "qu'avec une preuve de provenance, jamais par défaut."
            )
        from app.source_analysis.provenance import validate_derived_provenance

        provenance = validate_derived_provenance(
            derived_path=path,
            provenance_path=Path(provenance_path),
            original_transcript_path=(
                Path(original_transcript_path)
                if original_transcript_path is not None
                else None
            ),
        )
        original_resolved = provenance.original_path
    else:
        original_resolved = None

    raw = path.read_text(encoding="utf-8")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SourceTranscriptError(
            f"Transcript V2 illisible ({path}) : JSON invalide ligne {exc.lineno}."
        ) from exc

    if not isinstance(payload, dict):
        raise SourceTranscriptError(
            f"Transcript V2 invalide ({path}) : un objet JSON est attendu."
        )

    schema_version = str(payload.get("schema_version", ""))

    if schema_version != TRANSCRIPT_SCHEMA_VERSION:
        raise SourceTranscriptError(
            f"Version de contrat Transcript inattendue : « {schema_version} » "
            f"au lieu de « {TRANSCRIPT_SCHEMA_VERSION} ». Le Source Analyzer "
            "refuse d'analyser un contrat qu'il ne connaît pas."
        )

    transcript_id = str(payload.get("transcript_id") or "").strip()

    if not transcript_id:
        raise SourceTranscriptError(
            f"Transcript V2 invalide ({path}) : transcript_id absent."
        )

    language = payload.get("language") or {}

    if not isinstance(language, dict):
        raise SourceTranscriptError(
            f"Transcript V2 invalide ({path}) : bloc « language » malformé."
        )

    primary_language = str(language.get("primary") or "").strip()

    if not primary_language:
        raise SourceTranscriptError(
            f"Transcript V2 invalide ({path}) : language.primary absent. "
            "La langue de sortie de l'analyse en dépend."
        )

    detected = language.get("detected") or []

    if not isinstance(detected, list):
        raise SourceTranscriptError(
            f"Transcript V2 invalide ({path}) : language.detected malformé."
        )

    segments = _read_segments(payload, path, mode=resolved_mode)
    duration_seconds, declared_segments, declared_words = _read_stats(payload, path)

    if declared_segments is not None and declared_segments != len(segments):
        raise SourceTranscriptError(
            f"Transcript V2 invalide ({path}) : stats.segment_count "
            f"{declared_segments} ≠ {len(segments)} segments présents."
        )

    computed_words = sum(segment.word_count for segment in segments)

    if declared_words is not None and declared_words != computed_words:
        raise SourceTranscriptError(
            f"Transcript V2 invalide ({path}) : stats.word_count "
            f"{declared_words} ≠ {computed_words} mots présents."
        )

    resolved_project = project_name or str((payload.get("project") or {}).get("name") or "")

    if not resolved_project:
        raise SourceTranscriptError(
            f"Transcript V2 invalide ({path}) : nom de projet absent."
        )

    return TranscriptInput(
        project_name=resolved_project,
        transcript_id=transcript_id,
        primary_language=primary_language,
        detected_languages=tuple(str(code) for code in detected),
        segments=segments,
        path=path,
        content_sha256=content_hash(raw),
        schema_version=schema_version,
        duration_seconds=duration_seconds,
        mode=resolved_mode,
        provenance_path=Path(provenance_path) if provenance_path is not None else None,
        original_transcript_path=original_resolved,
    )


def _read_stats(payload: dict, path: Path) -> tuple[float, int | None, int | None]:
    stats = payload.get("stats")

    if stats is None:
        return 0.0, None, None

    if not isinstance(stats, dict):
        raise SourceTranscriptError(
            f"Transcript V2 invalide ({path}) : bloc « stats » malformé."
        )

    duration = float(stats.get("duration_seconds") or 0.0)
    segment_count = stats.get("segment_count")
    word_count = stats.get("word_count")

    return (
        duration,
        int(segment_count) if segment_count is not None else None,
        int(word_count) if word_count is not None else None,
    )


def _read_segments(
    payload: dict,
    path: Path,
    *,
    mode: TranscriptInputMode,
) -> tuple[SourceSegment, ...]:
    raw_segments = payload.get("segments")

    if not isinstance(raw_segments, list) or not raw_segments:
        raise SourceTranscriptError(
            f"Transcript V2 invalide ({path}) : aucun segment source. "
            "Il n'y a rien à analyser."
        )

    segments: list[SourceSegment] = []
    seen: set[str] = set()
    previous_number: int | None = None

    for position, entry in enumerate(raw_segments, start=1):
        if not isinstance(entry, dict):
            raise SourceTranscriptError(
                f"Transcript V2 invalide ({path}) : segment n°{position} malformé."
            )

        src_id = str(entry.get("id") or "").strip()

        if not src_id:
            raise SourceTranscriptError(
                f"Transcript V2 invalide ({path}) : segment n°{position} sans identifiant."
            )

        if src_id in seen:
            raise SourceTranscriptError(
                f"Transcript V2 invalide ({path}) : identifiant de segment "
                f"dupliqué « {src_id} »."
            )

        seen.add(src_id)

        if mode is TranscriptInputMode.SOURCE:
            expected_id = format_src_id(position)
            if src_id != expected_id:
                raise SourceTranscriptError(
                    f"Transcript V2 invalide ({path}) : identifiant SRC non "
                    f"continu en position {position} : {src_id} "
                    f"(attendu {expected_id}). Un trou n'est accepté qu'en "
                    f"mode {TranscriptInputMode.DERIVED.value} avec provenance."
                )
        else:
            if not SRC_ID_PATTERN.fullmatch(src_id):
                raise SourceTranscriptError(
                    f"Transcript V2 invalide ({path}) : identifiant SRC mal "
                    f"formé en position {position} : {src_id}."
                )
            number = int(src_id[3:])
            if previous_number is not None and number <= previous_number:
                raise SourceTranscriptError(
                    f"Transcript V2 invalide ({path}) : identifiant SRC hors "
                    f"ordre croissant en position {position} : {src_id}."
                )
            previous_number = number

        segments.append(
            SourceSegment(
                src_id=src_id,
                source_id=str(entry.get("source_id") or ""),
                start=float(entry.get("start", 0.0)),
                end=float(entry.get("end", 0.0)),
                text=str(entry.get("text") or ""),
                source_order=int(entry.get("source_order") or 0),
            )
        )

    return tuple(segments)
