"""
Validateur de language_blocks.json (§32 du cahier des charges Phase 3A.1.1).

Même style que app/language_cleanup/validator.py : les violations sont
COLLECTÉES puis retournées ensemble, jamais levées à la première rencontrée.
Ce module JUGE un manifeste déjà écrit ; il ne le fabrique ni ne le répare.
"""

from __future__ import annotations

from collections import Counter
from typing import Mapping

from app.language_blocks.combined_source import CombinedSource
from app.language_blocks.errors import BlocksValidationError
from app.language_blocks.models import (
    CANDIDATE_DIRECTIONS,
    PHASE_3A1_STATUSES,
    SEMANTIC_REVIEW_STATUSES,
    STRUCTURES,
)

LANGUAGE_FR = "FR"
LANGUAGE_EN = "EN"

DECISION_REMOVE = "REMOVE_TRANSLATION"
DECISION_REVIEW = "REVIEW"
DECISION_KEEP = "KEEP"


def validate_blocks_payload(payload: Mapping, combined: CombinedSource) -> list[str]:
    """Retourne les violations du manifeste (vide si valide, ne lève jamais)."""
    errors: list[str] = []

    if not isinstance(payload, Mapping):
        return ["manifeste illisible : un objet JSON est attendu"]

    _validate_header(payload, combined, errors)

    blocks = payload.get("blocks")

    if not isinstance(blocks, list):
        errors.append("« blocks » absent ou n'est pas une liste")
        return errors

    src_index = {segment.src_id: segment.position for segment in combined.segments}
    audio_by_ref = {segment.src_id: segment.audio_id for segment in combined.segments}
    text_by_ref = {segment.src_id: segment.text for segment in combined.segments}
    start_by_ref = {segment.src_id: segment.start for segment in combined.segments}
    end_by_ref = {segment.src_id: segment.end for segment in combined.segments}
    language_by_ref = {segment.src_id: segment.language for segment in combined.segments}
    decision_by_ref = {segment.src_id: segment.decision for segment in combined.segments}
    matched_by_ref = {
        segment.src_id: segment.matched_english_source_refs for segment in combined.segments
    }

    all_fr_refs_in_transcript = {
        segment.src_id for segment in combined.segments if segment.language == LANGUAGE_FR
    }

    all_fr_refs_in_blocks: list[str] = []
    last_end_position: int | None = None

    for position, entry in enumerate(blocks, start=1):
        if not isinstance(entry, Mapping):
            errors.append(f"bloc n°{position} : entrée malformée")
            continue

        block_id = entry.get("block_id")
        expected_id = f"FRB{position:04d}"
        if block_id != expected_id:
            errors.append(
                f"bloc n°{position} : block_id « {block_id} » attendu « {expected_id} » "
                "(§9 : IDs FRB continus, dans l'ordre d'apparition)"
            )

        last_end_position = _validate_block_entry(
            entry,
            label=block_id or f"bloc n°{position}",
            src_index=src_index,
            audio_by_ref=audio_by_ref,
            text_by_ref=text_by_ref,
            start_by_ref=start_by_ref,
            end_by_ref=end_by_ref,
            language_by_ref=language_by_ref,
            decision_by_ref=decision_by_ref,
            matched_by_ref=matched_by_ref,
            last_end_position=last_end_position,
            errors=errors,
        )

        fr_refs = entry.get("fr_source_refs")
        if isinstance(fr_refs, list):
            all_fr_refs_in_blocks.extend(str(ref) for ref in fr_refs)

    # §32 : tous les FR du manifeste 3A.1 apparaissent EXACTEMENT une fois.
    counts = Counter(all_fr_refs_in_blocks)

    for ref in sorted(all_fr_refs_in_transcript):
        if counts.get(ref, 0) == 0:
            errors.append(f"{ref} : classifié FR par Phase 3A.1 mais absent de tout bloc")

    for ref, count in counts.items():
        if ref not in all_fr_refs_in_transcript:
            errors.append(f"{ref} : listé dans fr_source_refs mais non classifié FR")
        elif count > 1:
            errors.append(f"{ref} : dupliqué dans fr_source_refs de {count} blocs")

    return errors


def ensure_valid_blocks_payload(payload: Mapping, combined: CombinedSource) -> None:
    errors = validate_blocks_payload(payload, combined)

    if errors:
        raise BlocksValidationError(errors)


# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------

def _validate_header(payload: Mapping, combined: CombinedSource, errors: list[str]) -> None:
    if not payload.get("schema_version"):
        errors.append("schema_version absent")

    if payload.get("transcript_id") != combined.transcript_id:
        errors.append(
            f"transcript_id incohérent : « {payload.get('transcript_id')} » alors "
            f"que le transcript analysé est « {combined.transcript_id} »"
        )

    if payload.get("transcript_sha256") != combined.transcript_sha256:
        errors.append(
            "transcript_sha256 incohérent avec le transcript_data.json actuel"
        )

    if payload.get("language_cleanup_sha256") != combined.language_cleanup_sha256:
        errors.append(
            "language_cleanup_sha256 incohérent avec le language_cleanup.json actuel"
        )

    if not isinstance(payload.get("configuration"), Mapping):
        errors.append("« configuration » absent ou malformé")

    if not isinstance(payload.get("stats"), Mapping):
        errors.append("« stats » absent ou malformé")


# ---------------------------------------------------------------------------
# Un bloc
# ---------------------------------------------------------------------------

def _validate_block_entry(
    entry: Mapping,
    *,
    label: str,
    src_index: dict[str, int],
    audio_by_ref: dict[str, str],
    text_by_ref: dict[str, str],
    start_by_ref: dict[str, float],
    end_by_ref: dict[str, float],
    language_by_ref: dict[str, str],
    decision_by_ref: dict[str, str],
    matched_by_ref: dict[str, tuple[str, ...]],
    last_end_position: int | None,
    errors: list[str],
) -> int | None:
    audio_id = entry.get("audio_id")

    all_refs = entry.get("all_source_refs")
    fr_refs = entry.get("fr_source_refs")
    bridge_refs = entry.get("bridge_source_refs")

    if not isinstance(all_refs, list) or not all_refs:
        errors.append(f"{label} : all_source_refs absent ou vide")
        return last_end_position

    if not isinstance(fr_refs, list):
        errors.append(f"{label} : fr_source_refs absent ou malformé")
        fr_refs = []

    if not isinstance(bridge_refs, list):
        errors.append(f"{label} : bridge_source_refs absent ou malformé")
        bridge_refs = []

    # Aucun SRC inventé.
    positions: list[int] = []
    for ref in all_refs:
        if ref not in src_index:
            errors.append(f"{label} : all_source_refs contient « {ref} », absent du transcript")
            continue
        positions.append(src_index[ref])

    if not positions:
        return last_end_position

    # Ordre SRC strictement croissant, à l'intérieur du bloc.
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        errors.append(f"{label} : all_source_refs n'est pas strictement croissant")

    # Ordre SRC strictement croissant, entre blocs successifs.
    if last_end_position is not None and positions and min(positions) <= last_end_position:
        errors.append(f"{label} : chevauche le bloc précédent (ordre SRC global)")

    # Aucun bloc ne traverse AUDIO.
    audios = {audio_by_ref.get(ref) for ref in all_refs if ref in audio_by_ref}
    if len(audios) > 1:
        errors.append(f"{label} : traverse plusieurs AUDIO {sorted(a for a in audios if a)}")
    elif audios and audio_id not in audios:
        errors.append(f"{label} : audio_id « {audio_id} » incohérent avec ses SRC")

    # fr_source_refs / bridge_source_refs : cohérence avec all_source_refs.
    if set(fr_refs) | set(bridge_refs) != set(all_refs):
        errors.append(
            f"{label} : fr_source_refs ∪ bridge_source_refs ≠ all_source_refs"
        )
    if set(fr_refs) & set(bridge_refs):
        errors.append(f"{label} : fr_source_refs et bridge_source_refs se recoupent")

    for ref in fr_refs:
        if language_by_ref.get(ref) != LANGUAGE_FR:
            errors.append(
                f"{label} : fr_source_refs contient « {ref} », classifié "
                f"« {language_by_ref.get(ref)} » (FR attendu)"
            )

    for ref in bridge_refs:
        if ref not in src_index:
            errors.append(f"{label} : bridge_source_refs contient « {ref} », absent du transcript")
            continue
        if language_by_ref.get(ref) == LANGUAGE_EN:
            errors.append(f"{label} : bridge_source_refs contient « {ref} », classifié EN")

    # Texte reconstructible depuis le transcript.
    expected_text = " ".join(
        text_by_ref[ref] for ref in all_refs if ref in text_by_ref
    )
    if entry.get("text") != expected_text:
        errors.append(f"{label} : text ne correspond pas à la concaténation des SRC d'origine")

    # Timestamps cohérents.
    first_ref, last_ref = all_refs[0], all_refs[-1]
    if first_ref in start_by_ref and entry.get("start_seconds") != start_by_ref[first_ref]:
        errors.append(f"{label} : start_seconds incohérent avec {first_ref}")
    if last_ref in end_by_ref and entry.get("end_seconds") != end_by_ref[last_ref]:
        errors.append(f"{label} : end_seconds incohérent avec {last_ref}")

    # Vocabulaire fermé.
    structure = entry.get("structure")
    if structure not in STRUCTURES:
        errors.append(f"{label} : structure invalide « {structure} »")

    direction = entry.get("candidate_direction")
    if direction not in CANDIDATE_DIRECTIONS:
        errors.append(f"{label} : candidate_direction invalide « {direction} »")

    status = entry.get("phase_3a1_status")
    if status not in PHASE_3A1_STATUSES:
        errors.append(f"{label} : phase_3a1_status invalide « {status} »")

    semantic_status = entry.get("semantic_review_status")
    if semantic_status not in SEMANTIC_REVIEW_STATUSES:
        errors.append(f"{label} : semantic_review_status invalide « {semantic_status} »")

    # Contextes anglais.
    for side in ("english_before", "english_after"):
        context = entry.get(side)
        if context is None:
            continue
        if not isinstance(context, Mapping):
            errors.append(f"{label} : {side} malformé")
            continue

        context_refs = context.get("source_refs")
        if not isinstance(context_refs, list) or not context_refs:
            errors.append(f"{label} : {side}.source_refs absent ou vide")
            continue

        for ref in context_refs:
            if ref not in src_index:
                errors.append(f"{label} : {side} contient « {ref} », absent du transcript")
                continue
            if audio_by_ref.get(ref) != audio_id:
                errors.append(f"{label} : {side} contient « {ref} », d'un AUDIO différent")
            if language_by_ref.get(ref) == LANGUAGE_FR:
                errors.append(f"{label} : {side} contient « {ref} », classifié FR")

    # already_resolved / semantic_review_status : cohérence interne.
    already_resolved = entry.get("already_resolved")
    needs_review = entry.get("needs_semantic_review")

    if already_resolved:
        if semantic_status != "ALREADY_RESOLVED":
            errors.append(
                f"{label} : already_resolved=true mais semantic_review_status="
                f"« {semantic_status} »"
            )
        if needs_review:
            errors.append(f"{label} : already_resolved=true mais needs_semantic_review=true")
        if status != "ALL_REMOVE":
            errors.append(f"{label} : already_resolved=true mais phase_3a1_status ≠ ALL_REMOVE")
        for ref in fr_refs:
            if not matched_by_ref.get(ref):
                errors.append(
                    f"{label} : already_resolved=true mais {ref} n'a aucun "
                    "matched_english_source_ref valide"
                )

    if semantic_status == "NO_ENGLISH_CONTEXT":
        if entry.get("english_before") is not None or entry.get("english_after") is not None:
            errors.append(
                f"{label} : semantic_review_status=NO_ENGLISH_CONTEXT mais un "
                "contexte anglais est présent"
            )
        if needs_review:
            errors.append(f"{label} : semantic_review_status=NO_ENGLISH_CONTEXT mais needs_semantic_review=true")

    if semantic_status == "NEEDED" and not needs_review:
        errors.append(f"{label} : semantic_review_status=NEEDED mais needs_semantic_review=false")

    return max(positions)
