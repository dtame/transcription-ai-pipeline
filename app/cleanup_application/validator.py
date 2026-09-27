"""
Validation de l'application POLICY_B_PLUS_V1.

Deux niveaux, tous deux AVANT publication :

1. validate_removal_set  — préflight du jeu de suppression. Une seule
   violation → STOP, aucun artefact clean.
2. validate_clean_transcript — vue dérivée (trous d'IDs autorisés) +
   comparaison stricte à l'original.

Le validateur Phase 1 original n'est PAS affaibli : les appels sans
`allow_source_id_gaps` conservent l'invariant SRC continus.
"""

from __future__ import annotations

from app.cleanup_application.constants import (
    CLASSIFICATION_NOT_TRANSLATION,
    CLASSIFICATION_TRANSLATION_AFTER,
    CLASSIFICATION_TRANSLATION_BEFORE,
    CLASSIFICATION_UNCERTAIN,
    DECISION_AUTO_REMOVE,
    DECISION_HUMAN_REVIEW,
    DECISION_KEEP,
    LANGUAGE_FR,
    ORIGIN_NO_ENGLISH_CONTEXT,
    ORIGIN_PHASE_3A1_RESOLVED,
    POLICY_B_PLUS_MAX_WORDS,
    POLICY_B_PLUS_MIN_CONFIDENCE,
    RISK_EXTRA_CONTENT_SIGNAL,
    RISK_HIGH_RISK_EXISTING,
    RISK_MULTI_SRC,
    TRANSLATION_CLASSIFICATIONS,
)
from app.cleanup_application.errors import CleanTranscriptError, PreflightError
from app.cleanup_application.models import ApplicationPlan, PlannedBlock
from app.transcript_models import TranscriptDocument, TranscriptSegment
from app.transcript_validator import (
    SRC_ID_PATTERN,
    validate_transcript_document,
)


def validate_original_still_rejects_gaps(document: TranscriptDocument) -> list[str]:
    """Le contrat original (sans drapeau) continue d'exiger des SRC continus."""
    return validate_transcript_document(document, allow_source_id_gaps=False)


def validate_removal_set(
    plan: ApplicationPlan,
    original: TranscriptDocument,
    language_by_src: dict[str, str],
) -> None:
    """Préflight intégral. Lève PreflightError si UNE validation échoue."""
    errors: list[str] = []
    occurrence = _occurrence_count(original.segments)
    by_id = {segment.id: segment for segment in original.segments}
    auto_blocks = plan.blocks_with(DECISION_AUTO_REMOVE)
    auto_src_to_block: dict[str, PlannedBlock] = {}

    snapshot_refs = [snap.source_ref for snap in plan.removal_snapshots]
    if len(snapshot_refs) != len(set(snapshot_refs)):
        dupes = sorted({ref for ref in snapshot_refs if snapshot_refs.count(ref) > 1})
        errors.append(f"removed snapshots : SRC dupliqué(s) {dupes}")

    if set(snapshot_refs) != set(plan.removal_set):
        errors.append(
            "removal_set ≠ snapshots : "
            f"set={sorted(plan.removal_set)} snapshots={sorted(snapshot_refs)}"
        )

    for block in auto_blocks:
        refs = block.decision.candidate_removed_source_refs
        if len(refs) != 1:
            errors.append(
                f"{block.block_id} AUTO_REMOVE sans exactement 1 SRC : {list(refs)}"
            )
            continue
        src = refs[0]
        if src in auto_src_to_block:
            errors.append(
                f"{src} appartient à deux blocs AUTO_REMOVE : "
                f"{auto_src_to_block[src].block_id} et {block.block_id}"
            )
        auto_src_to_block[src] = block
        errors.extend(_validate_auto_block(block, by_id, occurrence, language_by_src))

    if set(auto_src_to_block) != set(plan.removal_set):
        errors.append(
            "removal_set ≠ SRC des blocs AUTO_REMOVE : "
            f"set={sorted(plan.removal_set)} auto={sorted(auto_src_to_block)}"
        )

    protected = _protected_source_refs(plan)
    leaked = sorted(plan.removal_set & protected)
    if leaked:
        errors.append(
            "removal_set contient des SRC protégés (KEEP/HUMAN_REVIEW/bridge/"
            f"EN/UNKNOWN/MIXED) : {leaked}"
        )

    if errors:
        raise PreflightError(
            "Préflight removal_set invalide, STOP, aucun transcript clean : "
            + " | ".join(errors)
        )


def _validate_auto_block(
    block: PlannedBlock,
    by_id: dict[str, TranscriptSegment],
    occurrence: dict[str, int],
    language_by_src: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    record = block.record
    src = block.decision.candidate_removed_source_refs[0]
    label = f"{block.block_id}/{src}"

    if record.classification != CLASSIFICATION_TRANSLATION_BEFORE:
        errors.append(f"{label} : classification={record.classification} ≠ TRANSLATION_BEFORE")
    if record.confidence is None or record.confidence < POLICY_B_PLUS_MIN_CONFIDENCE:
        errors.append(f"{label} : confidence={record.confidence} < {POLICY_B_PLUS_MIN_CONFIDENCE}")
    if record.word_count > POLICY_B_PLUS_MAX_WORDS:
        errors.append(f"{label} : word_count={record.word_count} > {POLICY_B_PLUS_MAX_WORDS}")
    if record.bridge_source_refs:
        errors.append(f"{label} : bridge_source_refs non vide {list(record.bridge_source_refs)}")
    if RISK_HIGH_RISK_EXISTING in block.risk_flags:
        errors.append(f"{label} : HIGH_RISK_EXISTING")
    if RISK_MULTI_SRC in block.risk_flags or len(record.fr_source_refs) != 1:
        errors.append(f"{label} : MULTI_SRC / fr_source_refs={list(record.fr_source_refs)}")
    if RISK_EXTRA_CONTENT_SIGNAL in block.risk_flags:
        errors.append(f"{label} : EXTRA_CONTENT_SIGNAL")
    if occurrence.get(src, 0) != 1:
        errors.append(f"{label} : occurrence originale={occurrence.get(src, 0)} (attendu 1)")
    segment = by_id.get(src)
    if segment is None:
        errors.append(f"{label} : SRC absent du transcript original")
        return errors
    if segment.text != record.text:
        errors.append(f"{label} : texte SRC ≠ texte FR reconstructible")
    if segment.source_id != record.audio_id:
        errors.append(
            f"{label} : audio_id SRC={segment.source_id} ≠ bloc={record.audio_id}"
        )
    if language_by_src.get(src) != LANGUAGE_FR:
        errors.append(f"{label} : language={language_by_src.get(src)!r} ≠ FR")
    if len(segment.text.split()) > POLICY_B_PLUS_MAX_WORDS:
        errors.append(f"{label} : mots SRC={len(segment.text.split())} > {POLICY_B_PLUS_MAX_WORDS}")
    return errors


def _protected_source_refs(plan: ApplicationPlan) -> set[str]:
    protected: set[str] = set()
    for block in plan.blocks:
        if block.decision.decision != DECISION_AUTO_REMOVE:
            protected.update(block.record.fr_source_refs)
        protected.update(block.record.bridge_source_refs)
        protected.update(block.english_before_source_refs)
        protected.update(block.english_after_source_refs)
    return protected


def _occurrence_count(segments: list[TranscriptSegment]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for segment in segments:
        counts[segment.id] = counts.get(segment.id, 0) + 1
    return counts


def validate_clean_transcript(
    original: TranscriptDocument,
    clean: TranscriptDocument,
    plan: ApplicationPlan,
    language_by_src: dict[str, str],
) -> None:
    """Valide la vue dérivée. Lève CleanTranscriptError si une invariante casse."""
    errors = validate_transcript_document(clean, allow_source_id_gaps=True)

    if clean.schema_version != original.schema_version:
        errors.append(
            f"schema_version clean={clean.schema_version!r} ≠ original={original.schema_version!r}"
        )
    if clean.transcript_id != original.transcript_id:
        errors.append(
            f"transcript_id clean={clean.transcript_id!r} ≠ original={original.transcript_id!r}"
        )
    if clean.project_name != original.project_name:
        errors.append("nom de projet clean ≠ original")
    if clean.primary_language != original.primary_language:
        errors.append(
            f"primary_language clean={clean.primary_language!r} ≠ "
            f"original={original.primary_language!r}"
        )
    if list(clean.detected_languages) != list(original.detected_languages):
        errors.append("detected_languages clean ≠ original")

    if [s.to_dict() for s in clean.sources] != [s.to_dict() for s in original.sources]:
        errors.append("métadonnées audio clean ≠ original (IDs, durées, filenames)")

    if clean.stats.duration_seconds != original.stats.duration_seconds:
        errors.append(
            f"duration_seconds clean={clean.stats.duration_seconds} ≠ "
            f"original={original.stats.duration_seconds} (durée audio source à préserver)"
        )
    if clean.stats.source_count != len(original.sources):
        errors.append("stats.source_count ≠ nombre de sources originales")
    if clean.stats.segment_count != len(clean.segments):
        errors.append("stats.segment_count ≠ len(segments clean)")
    expected_words = sum(len(s.text.split()) for s in clean.segments)
    if clean.stats.word_count != expected_words:
        errors.append(f"stats.word_count {clean.stats.word_count} ≠ {expected_words}")

    original_ids = [segment.id for segment in original.segments]
    clean_ids = [segment.id for segment in clean.segments]
    original_set = set(original_ids)
    clean_set = set(clean_ids)
    removed = set(plan.removal_set)

    if clean_set & removed:
        errors.append(f"SRC retirés encore présents dans le clean : {sorted(clean_set & removed)}")
    unexpected_absent = (original_set - clean_set) - removed
    if unexpected_absent:
        errors.append(f"SRC absents du clean sans être dans removal_set : {sorted(unexpected_absent)}")
    extra = clean_set - original_set
    if extra:
        errors.append(f"SRC supplémentaires dans le clean : {sorted(extra)}")
    if clean_set != original_set - removed:
        errors.append("ensemble clean ≠ original − removal_set")

    original_by_id = {segment.id: segment for segment in original.segments}
    last_original_pos = -1
    for segment in clean.segments:
        if not SRC_ID_PATTERN.fullmatch(segment.id):
            errors.append(f"SRC mal formé dans le clean : {segment.id}")
        original_segment = original_by_id.get(segment.id)
        if original_segment is None:
            continue
        pos = original_ids.index(segment.id)
        if pos <= last_original_pos:
            errors.append(f"{segment.id} : ordre relatif non conservé")
        last_original_pos = pos
        if segment.id != original_segment.id:
            errors.append(f"renumérotage détecté : {original_segment.id} → {segment.id}")
        if segment.text != original_segment.text:
            errors.append(f"{segment.id} : texte survivant modifié")
        if segment.start != original_segment.start or segment.end != original_segment.end:
            errors.append(f"{segment.id} : timestamps survivants modifiés")
        if segment.source_id != original_segment.source_id:
            errors.append(f"{segment.id} : audio ownership modifié")
        if segment.source_order != original_segment.source_order:
            errors.append(f"{segment.id} : source_order modifié")

    errors.extend(_retention_errors(plan, clean_set, original_by_id, language_by_src))

    if errors:
        raise CleanTranscriptError(
            "Transcript clean invalide : " + " | ".join(errors[:40])
        )


def _retention_errors(
    plan: ApplicationPlan,
    clean_set: set[str],
    original_by_id: dict[str, TranscriptSegment],
    language_by_src: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    for block in plan.blocks:
        decision = block.decision.decision
        refs = set(block.record.fr_source_refs)
        bridges = set(block.record.bridge_source_refs)
        if decision in (DECISION_HUMAN_REVIEW, DECISION_KEEP):
            missing = sorted((refs | bridges) - clean_set)
            if missing:
                errors.append(
                    f"{block.block_id} {decision} : SRC manquants dans le clean : {missing}"
                )
        if block.record.classification == CLASSIFICATION_TRANSLATION_AFTER:
            missing = sorted(refs - clean_set)
            if missing:
                errors.append(f"{block.block_id} TRANSLATION_AFTER retiré : {missing}")
        if (
            block.record.classification in TRANSLATION_CLASSIFICATIONS
            and (RISK_MULTI_SRC in block.risk_flags or len(block.record.fr_source_refs) > 1)
        ):
            missing = sorted(refs - clean_set)
            if missing:
                errors.append(f"{block.block_id} MULTI_SRC retiré : {missing}")
        if RISK_HIGH_RISK_EXISTING in block.risk_flags:
            missing = sorted(refs - clean_set)
            if missing:
                errors.append(f"{block.block_id} HIGH_RISK retiré : {missing}")
        if block.record.bridge_source_refs:
            missing = sorted(bridges - clean_set)
            if missing:
                errors.append(f"{block.block_id} bridge retiré : {missing}")
        if RISK_EXTRA_CONTENT_SIGNAL in block.risk_flags:
            missing = sorted(refs - clean_set)
            if missing:
                errors.append(f"{block.block_id} EXTRA_CONTENT retiré : {missing}")
        if block.record.classification in (
            CLASSIFICATION_NOT_TRANSLATION,
            CLASSIFICATION_UNCERTAIN,
        ) or block.record.semantic_origin in (
            ORIGIN_NO_ENGLISH_CONTEXT,
            ORIGIN_PHASE_3A1_RESOLVED,
        ):
            missing = sorted(refs - clean_set)
            if missing:
                errors.append(f"{block.block_id} {block.record.semantic_origin}/{block.record.classification} retiré : {missing}")

    for src in plan.removal_set:
        language = language_by_src.get(src)
        if language and language != LANGUAGE_FR:
            errors.append(f"{src} retiré mais language={language} (FR attendu)")
        segment = original_by_id.get(src)
        if segment is None:
            continue
        # Les SRC anglais du transcript ne doivent jamais être dans removal_set.
        if language_by_src.get(src) != LANGUAGE_FR:
            errors.append(f"retrait d'un SRC non-FR : {src} ({language_by_src.get(src)})")

    return errors
