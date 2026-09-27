"""
Validation du contrat Transcript V2.

Aucun transcript_data.json ne doit être publié — et donc déclaré valide — sans
avoir satisfait tous les invariants ci-dessous. La chaîne éditoriale complète
(Source Analyzer → Editorial Planner → Book Generator) dépend de ces garanties :
si le contrat source est faux, tout ce qui en découle est faux.

Validation en Python pur, volontairement : ni jsonschema ni Pydantic.
"""

from __future__ import annotations

import re

from app.transcript_models import (
    SCHEMA_VERSION,
    TranscriptDocument,
    format_audio_id,
    format_src_id,
)

# Identifiant SRC canonique : SRC + 6 chiffres (SRC000001, SRC000102, …).
SRC_ID_PATTERN = re.compile(r"^SRC\d{6}$")


class TranscriptValidationError(RuntimeError):
    """Le document ne satisfait pas le contrat : rien ne doit être publié."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__(
            f"{len(self.errors)} violation(s) du contrat Transcript V2 : "
            + " | ".join(self.errors)
        )


def validate_transcript_document(
    document: TranscriptDocument,
    *,
    allow_source_id_gaps: bool = False,
) -> list[str]:
    """
    Retourne la liste des violations du contrat (vide si le document est valide).

    Invariants vérifiés :
        schema_version présent et attendu
        transcript_id présent
        nom de projet présent
        sources non vides
        source_id uniques, bien formés, ordonnés
        source_order uniques, continus à partir de 1
        filename présent et sans composante de chemin
        duration_seconds >= 0 par source
        SRC uniques, bien formés ; continus à partir de SRC000001
            SAUF si allow_source_id_gaps=True (vue dérivée/clean uniquement)
        chaque SRC référence un AUDIO existant
        source_order d'un SRC cohérent avec sa source
        segments groupés par source dans l'ordre des sources
        start >= 0, end >= start
        chronologie non décroissante au sein d'une même source
        text est une chaîne non vide
        stats cohérentes avec le contenu
        langues cohérentes (primary ∈ detected, detected == langues des sources)

    `allow_source_id_gaps` est FALSE par défaut : le transcript original continue
    d'exiger des SRC continus SRC000001, SRC000002, … Ce drapeau n'autorise les
    trous (SRC000100, SRC000102) que pour une vue filtrée/dérivée, jamais en
    affaiblissant silencieusement la validation de l'original.
    """
    errors: list[str] = []

    _validate_header(document, errors)
    _validate_sources(document, errors)
    _validate_segments(document, errors, allow_source_id_gaps=allow_source_id_gaps)
    _validate_stats(document, errors)
    _validate_languages(document, errors)

    return errors


def ensure_valid_transcript_document(
    document: TranscriptDocument,
    *,
    allow_source_id_gaps: bool = False,
) -> None:
    """Lève TranscriptValidationError si le document viole le contrat."""
    errors = validate_transcript_document(
        document, allow_source_id_gaps=allow_source_id_gaps
    )

    if errors:
        raise TranscriptValidationError(errors)


# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------

def _validate_header(document: TranscriptDocument, errors: list[str]) -> None:
    if not document.schema_version:
        errors.append("schema_version absent")
    elif document.schema_version != SCHEMA_VERSION:
        errors.append(
            f"schema_version inattendu : {document.schema_version!r} "
            f"(attendu {SCHEMA_VERSION!r})"
        )

    if not document.transcript_id:
        errors.append("transcript_id absent")

    if not document.project_name:
        errors.append("nom de projet absent")


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def _validate_sources(document: TranscriptDocument, errors: list[str]) -> None:
    sources = document.sources

    if not sources:
        errors.append("aucune source audio")
        return

    seen_ids: set[str] = set()
    seen_orders: set[int] = set()

    for position, source in enumerate(sources, start=1):
        if source.source_id in seen_ids:
            errors.append(f"source_id dupliqué : {source.source_id}")
        seen_ids.add(source.source_id)

        if source.order in seen_orders:
            errors.append(f"source_order dupliqué : {source.order}")
        seen_orders.add(source.order)

        if source.order != position:
            errors.append(
                f"source_order non continu : {source.source_id} a l'ordre "
                f"{source.order}, position {position} attendue"
            )

        expected_id = format_audio_id(source.order)
        if source.source_id != expected_id:
            errors.append(
                f"source_id incohérent avec son ordre : {source.source_id} "
                f"(attendu {expected_id})"
            )

        if not source.filename:
            errors.append(f"{source.source_id} : filename absent")
        elif "/" in source.filename or "\\" in source.filename:
            errors.append(
                f"{source.source_id} : filename doit rester portable "
                f"(chemin interdit) : {source.filename!r}"
            )

        if source.duration_seconds < 0:
            errors.append(
                f"{source.source_id} : duration_seconds négative "
                f"({source.duration_seconds})"
            )

        if not source.detected_language:
            errors.append(f"{source.source_id} : detected_language absente")


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------

def _validate_segments(
    document: TranscriptDocument,
    errors: list[str],
    *,
    allow_source_id_gaps: bool = False,
) -> None:
    known_sources = {source.source_id: source for source in document.sources}
    seen_ids: set[str] = set()
    last_start_by_source: dict[str, float] = {}
    source_sequence: list[str] = []
    previous_src_number: int | None = None

    for position, segment in enumerate(document.segments, start=1):
        if allow_source_id_gaps:
            if not SRC_ID_PATTERN.fullmatch(segment.id):
                errors.append(
                    f"identifiant SRC mal formé en position {position} : {segment.id}"
                )
            else:
                number = int(segment.id[3:])
                if previous_src_number is not None and number <= previous_src_number:
                    errors.append(
                        f"identifiant SRC hors ordre croissant en position {position} : "
                        f"{segment.id}"
                    )
                previous_src_number = number
        else:
            expected_id = format_src_id(position)
            if segment.id != expected_id:
                errors.append(
                    f"identifiant SRC non continu en position {position} : "
                    f"{segment.id} (attendu {expected_id})"
                )

        if segment.id in seen_ids:
            errors.append(f"identifiant SRC dupliqué : {segment.id}")
        seen_ids.add(segment.id)

        source = known_sources.get(segment.source_id)

        if source is None:
            errors.append(
                f"{segment.id} référence une source inconnue : {segment.source_id}"
            )
        elif segment.source_order != source.order:
            errors.append(
                f"{segment.id} : source_order {segment.source_order} incohérent "
                f"avec {source.source_id} (ordre {source.order})"
            )

        if not isinstance(segment.text, str):
            errors.append(f"{segment.id} : text n'est pas une chaîne")
        elif not segment.text.strip():
            errors.append(f"{segment.id} : text vide")

        if segment.start < 0:
            errors.append(f"{segment.id} : start négatif ({segment.start})")

        if segment.end < segment.start:
            errors.append(
                f"{segment.id} : end {segment.end} antérieur à start {segment.start}"
            )

        if not source_sequence or source_sequence[-1] != segment.source_id:
            if segment.source_id in source_sequence:
                errors.append(
                    f"{segment.id} : les segments de {segment.source_id} ne sont "
                    "pas contigus"
                )
            source_sequence.append(segment.source_id)

        previous_start = last_start_by_source.get(segment.source_id)
        if previous_start is not None and segment.start < previous_start:
            errors.append(
                f"{segment.id} : chronologie décroissante dans "
                f"{segment.source_id} ({segment.start} après {previous_start})"
            )

        last_start_by_source[segment.source_id] = segment.start

    expected_sequence = [
        source.source_id
        for source in document.sources
        if source.source_id in set(source_sequence)
    ]
    if source_sequence != expected_sequence:
        errors.append(
            "les segments ne suivent pas l'ordre canonique des sources : "
            f"{source_sequence} au lieu de {expected_sequence}"
        )


# ---------------------------------------------------------------------------
# Statistiques
# ---------------------------------------------------------------------------

def _validate_stats(document: TranscriptDocument, errors: list[str]) -> None:
    stats = document.stats

    if stats is None:
        errors.append("stats absentes")
        return

    if stats.source_count != len(document.sources):
        errors.append(
            f"stats.source_count {stats.source_count} ≠ "
            f"{len(document.sources)} sources"
        )

    if stats.segment_count != len(document.segments):
        errors.append(
            f"stats.segment_count {stats.segment_count} ≠ "
            f"{len(document.segments)} segments"
        )

    expected_duration = round(
        sum(source.duration_seconds for source in document.sources), 3
    )
    if round(stats.duration_seconds, 3) != expected_duration:
        errors.append(
            f"stats.duration_seconds {stats.duration_seconds} ≠ "
            f"{expected_duration} (somme des durées des sources)"
        )

    # Robustesse : un segment au type invalide est déjà signalé par
    # _validate_segments ; le validateur ne doit pas lui-même lever.
    expected_words = sum(
        len(segment.text.split())
        for segment in document.segments
        if isinstance(segment.text, str)
    )
    if stats.word_count != expected_words:
        errors.append(
            f"stats.word_count {stats.word_count} ≠ {expected_words} mots"
        )


# ---------------------------------------------------------------------------
# Langues
# ---------------------------------------------------------------------------

def _validate_languages(document: TranscriptDocument, errors: list[str]) -> None:
    detected = document.detected_languages

    if not document.primary_language:
        errors.append("language.primary absente")

    if not detected:
        errors.append("language.detected vide")
        return

    if list(detected) != sorted(detected):
        errors.append(f"language.detected non triée : {detected}")

    if len(set(detected)) != len(detected):
        errors.append(f"language.detected contient des doublons : {detected}")

    if document.primary_language and document.primary_language not in detected:
        errors.append(
            f"language.primary {document.primary_language!r} absente de "
            f"language.detected {detected}"
        )

    if document.sources:
        source_languages = sorted(
            {source.detected_language for source in document.sources}
        )
        if list(detected) != source_languages:
            errors.append(
                f"language.detected {detected} incohérente avec les langues des "
                f"sources {source_languages}"
            )
