"""
Validateur de language_cleanup.json — §25 du cahier des charges Phase 3A.1.

Distinct de l'auditeur à dessein (même séparation que
app/transcript_validator.py et app/source_analysis/validator.py) : celui-ci
fabrique un manifeste, celui-là le juge. Un validateur qui répare un manifeste
invalide serait pire qu'un manifeste refusé.

Style repris de app/transcript_validator.py : les violations sont COLLECTÉES
puis retournées ensemble, plutôt que de s'arrêter à la première.
"""

from __future__ import annotations

from typing import Mapping

from app.language_cleanup.errors import ManifestValidationError
from app.language_cleanup.models import DECISIONS, LANGUAGE_LABELS, MATCH_DIRECTIONS
from app.language_cleanup.transcript_source import AuditTranscript

# Distance maximale (en position d'index dans le transcript) tolérée entre un
# SRC français et l'un de ses matched_english_source_refs. Ce n'est PAS une
# reproduction du calcul de fenêtre de translation_matcher.py (qui raisonne en
# nombre de BLOCS, pas de SRC) : c'est un garde-fou de PLAUSIBILITÉ, généreux,
# qui empêche seulement une correspondance manifestement lointaine (bug, ou
# faux positif grossier) de passer la validation. Voir §16 : « matched refs
# sont réellement locaux ».
MAX_LOCAL_DISTANCE_SRC = 400


def validate_manifest_payload(
    payload: Mapping, transcript: AuditTranscript
) -> list[str]:
    """Retourne les violations du manifeste (vide si valide, ne lève jamais)."""
    errors: list[str] = []

    if not isinstance(payload, Mapping):
        return ["manifeste illisible : un objet JSON est attendu"]

    _validate_header(payload, transcript, errors)

    segments = payload.get("segments")

    if not isinstance(segments, list):
        errors.append("« segments » absent ou n'est pas une liste")
        return errors

    src_index = transcript.src_index()
    segments_by_ref = {segment.src_id: segment for segment in transcript.segments}

    seen_refs: set[str] = set()

    for position, entry in enumerate(segments, start=1):
        if not isinstance(entry, Mapping):
            errors.append(f"segment n°{position} : entrée malformée")
            continue

        _validate_segment_entry(
            entry,
            position,
            src_index=src_index,
            segments_by_ref=segments_by_ref,
            seen_refs=seen_refs,
            errors=errors,
        )

    return errors


def ensure_valid_manifest_payload(payload: Mapping, transcript: AuditTranscript) -> None:
    errors = validate_manifest_payload(payload, transcript)

    if errors:
        raise ManifestValidationError(errors)


# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------

def _validate_header(payload: Mapping, transcript: AuditTranscript, errors: list[str]) -> None:
    if not payload.get("schema_version"):
        errors.append("schema_version absent")

    transcript_id = payload.get("transcript_id")
    if transcript_id != transcript.transcript_id:
        errors.append(
            f"transcript_id incohérent : « {transcript_id} » alors que le "
            f"transcript audité est « {transcript.transcript_id} »"
        )

    manifest_sha = payload.get("transcript_sha256")
    if manifest_sha != transcript.content_sha256:
        errors.append(
            "transcript_sha256 incohérent avec le transcript_data.json "
            f"actuel : « {manifest_sha} » déclaré, « {transcript.content_sha256} » "
            "attendu"
        )

    if not isinstance(payload.get("policy"), Mapping):
        errors.append("« policy » absent ou malformé")

    if not isinstance(payload.get("stats"), Mapping):
        errors.append("« stats » absent ou malformé")


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------

def _validate_segment_entry(
    entry: Mapping,
    position: int,
    *,
    src_index: dict[str, int],
    segments_by_ref: dict,
    seen_refs: set[str],
    errors: list[str],
) -> None:
    source_ref = entry.get("source_ref")

    if not isinstance(source_ref, str) or not source_ref:
        errors.append(f"segment n°{position} : source_ref absent")
        return

    label = source_ref

    if source_ref in seen_refs:
        errors.append(f"{label} : source_ref dupliqué dans le manifeste")
    seen_refs.add(source_ref)

    original = segments_by_ref.get(source_ref)

    if original is None:
        errors.append(f"{label} : source_ref inventé, absent du transcript audité")
        return

    # Texte recopié — doit correspondre EXACTEMENT à la source (§25, §18).
    manifest_text = entry.get("text")
    if manifest_text != original.text:
        errors.append(
            f"{label} : texte du manifeste différent du transcript original "
            "(byte-identical attendu)"
        )

    # Timestamps — doivent correspondre exactement à la source.
    if entry.get("start_seconds") != original.start:
        errors.append(
            f"{label} : start_seconds incohérent avec le transcript "
            f"({entry.get('start_seconds')} != {original.start})"
        )

    if entry.get("end_seconds") != original.end:
        errors.append(
            f"{label} : end_seconds incohérent avec le transcript "
            f"({entry.get('end_seconds')} != {original.end})"
        )

    if entry.get("audio_id") != original.source_id:
        errors.append(
            f"{label} : audio_id incohérent avec le transcript "
            f"({entry.get('audio_id')} != {original.source_id})"
        )

    # Vocabulaire fermé.
    language = entry.get("language")
    if language not in LANGUAGE_LABELS:
        errors.append(f"{label} : language invalide « {language} »")

    decision = entry.get("decision")
    if decision not in DECISIONS:
        errors.append(f"{label} : decision invalide « {decision} »")

    direction = entry.get("match_direction")
    if direction is not None and direction not in MATCH_DIRECTIONS:
        errors.append(f"{label} : match_direction invalide « {direction} »")

    matched_refs = entry.get("matched_english_source_refs")
    if not isinstance(matched_refs, list):
        errors.append(f"{label} : matched_english_source_refs absent ou malformé")
        matched_refs = []

    # Règles métier — §16, §17, §23.
    if decision == "REMOVE_TRANSLATION":
        if language != "FR":
            errors.append(
                f"{label} : REMOVE_TRANSLATION attribué à un segment classifié "
                f"« {language} » — réservé aux segments FR"
            )

        if not matched_refs:
            errors.append(
                f"{label} : REMOVE_TRANSLATION sans aucun matched_english_source_ref"
            )

        if direction not in ("BEFORE", "AFTER", "BOTH"):
            errors.append(
                f"{label} : REMOVE_TRANSLATION avec match_direction invalide "
                f"« {direction} »"
            )

    if decision == "REVIEW" and language == "EN":
        errors.append(
            f"{label} : REVIEW attribué à un segment classifié EN — la langue "
            "cible ne devrait jamais nécessiter de révision de traduction"
        )

    if decision == "REMOVE_TRANSLATION" and language == "EN":
        errors.append(f"{label} : REMOVE_TRANSLATION ne doit jamais cibler l'anglais")

    # Chaque matched ref doit exister et rester local.
    fr_position = src_index.get(source_ref)

    for ref in matched_refs:
        if ref not in src_index:
            errors.append(
                f"{label} : matched_english_source_refs contient « {ref} », "
                "absent du transcript"
            )
            continue

        if fr_position is not None:
            distance = abs(src_index[ref] - fr_position)
            if distance > MAX_LOCAL_DISTANCE_SRC:
                errors.append(
                    f"{label} : matched ref « {ref} » trop distant "
                    f"({distance} positions) pour être considéré local"
                )
