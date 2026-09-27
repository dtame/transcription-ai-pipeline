"""
Population globale des blocs FR (§7, §15-17) — 333 blocs pour le projet réel
pastoral_retreat_v2_validation, mais ce module reste générique (aucun compte
n'est figé en dur ici, seule la cohérence INTERNE est vérifiée — même
principe que app.semantic_canary.runner.load_and_validate_sources).

Une seule fusion, jamais deux populations mélangées silencieusement (§6) :
chaque `BlockRecord` porte son `semantic_origin` explicite
(SEMANTIC_BATCH / PHASE_3A1_RESOLVED / NO_ENGLISH_CONTEXT).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.cleanup_policy.constants import (
    ORIGIN_BY_REVIEW_STATUS,
    ORIGIN_NO_ENGLISH_CONTEXT,
    ORIGIN_PHASE_3A1_RESOLVED,
    ORIGIN_SEMANTIC_BATCH,
    STATUS_ALREADY_RESOLVED,
    STATUS_NEEDED,
    STATUS_NO_ENGLISH_CONTEXT,
)
from app.cleanup_policy.errors import PopulationError


@dataclass(frozen=True)
class BlockRecord:
    """
    Une ligne de population fusionnée : métadonnées structurelles
    (language_blocks.json) + classification sémantique le cas échéant
    (semantic_translation_classification.json) — jamais recalculée (§20).
    """

    block_id: str
    audio_id: str
    start_seconds: float
    end_seconds: float
    fr_source_refs: tuple[str, ...]
    bridge_source_refs: tuple[str, ...]
    word_count: int
    segment_count: int
    fr_segment_count: int
    structure: str
    phase_3a1_status: str
    text: str
    semantic_origin: str

    # Champs sémantiques — présents uniquement pour ORIGIN_SEMANTIC_BATCH.
    classification: str | None = None
    matched_direction: str | None = None
    confidence: float | None = None
    confidence_range: str | None = None
    reason: str | None = None
    requires_human_review_flag: bool = False
    is_high_risk_existing: bool = False

    english_before_text: str | None = None
    english_after_text: str | None = None

    def matched_english_text(self) -> str | None:
        """Texte EN correspondant à `matched_direction` — None si NONE/absent."""
        if self.matched_direction == "BEFORE":
            return self.english_before_text
        if self.matched_direction == "AFTER":
            return self.english_after_text
        return None


def _english_text(block: dict, key: str) -> str | None:
    context = block.get(key)
    if not isinstance(context, dict):
        return None
    text = context.get("text")
    return str(text) if text is not None else None


def build_population(
    blocks: list[dict],
    classification_payload: dict,
) -> list[BlockRecord]:
    """
    Fusionne language_blocks.json + semantic_translation_classification.json
    en une liste déterministe de `BlockRecord`, triée par block_id (§22).

    Lève PopulationError, AVANT tout calcul de politique, si :
        - un block_id apparaît plus d'une fois ;
        - un semantic_review_status n'est pas dans le vocabulaire fermu ;
        - un bloc NEEDED n'a pas de résultat sémantique correspondant ;
        - un résultat sémantique ne correspond à aucun bloc NEEDED.
    """
    ids = [str(block["block_id"]) for block in blocks]
    duplicates = sorted({block_id for block_id in ids if ids.count(block_id) > 1})
    if duplicates:
        raise PopulationError(f"block_id dupliqué(s) dans language_blocks.json : {duplicates}.")

    results_by_id = {
        str(result["block_id"]): result for result in classification_payload.get("results") or []
    }
    high_risk_ids = {
        str(entry["block_id"])
        for entry in classification_payload.get("high_risk_for_deletion_review") or []
    }

    block_ids_set = set(ids)
    orphan_results = sorted(set(results_by_id) - block_ids_set)
    if orphan_results:
        raise PopulationError(
            "semantic_translation_classification.json référence des block_id "
            f"absents de language_blocks.json : {orphan_results}."
        )

    records: list[BlockRecord] = []

    for block in sorted(blocks, key=lambda b: str(b["block_id"])):
        block_id = str(block["block_id"])
        status = block.get("semantic_review_status")

        if status not in ORIGIN_BY_REVIEW_STATUS:
            raise PopulationError(
                f"{block_id} : semantic_review_status inconnu « {status} »."
            )

        origin = ORIGIN_BY_REVIEW_STATUS[status]

        classification = matched_direction = reason = None
        confidence = confidence_range = None
        requires_human_review_flag = False
        is_high_risk_existing = False

        if origin == ORIGIN_SEMANTIC_BATCH:
            result = results_by_id.get(block_id)
            if result is None:
                raise PopulationError(
                    f"{block_id} : NEEDED sans résultat sémantique correspondant "
                    "dans semantic_translation_classification.json."
                )
            classification = result.get("classification")
            matched_direction = result.get("matched_direction")
            confidence = (
                float(result["confidence"]) if result.get("confidence") is not None else None
            )
            confidence_range = result.get("confidence_range")
            reason = result.get("reason")
            requires_human_review_flag = bool(result.get("requires_human_review", False))
            is_high_risk_existing = block_id in high_risk_ids

        records.append(
            BlockRecord(
                block_id=block_id,
                audio_id=str(block.get("audio_id") or ""),
                start_seconds=float(block.get("start_seconds", 0.0)),
                end_seconds=float(block.get("end_seconds", 0.0)),
                fr_source_refs=tuple(block.get("fr_source_refs") or []),
                bridge_source_refs=tuple(block.get("bridge_source_refs") or []),
                word_count=int(block.get("word_count", 0)),
                segment_count=int(block.get("segment_count", 0)),
                fr_segment_count=int(block.get("fr_segment_count", 0)),
                structure=str(block.get("structure") or ""),
                phase_3a1_status=str(block.get("phase_3a1_status") or ""),
                text=str(block.get("text") or ""),
                semantic_origin=origin,
                classification=classification,
                matched_direction=matched_direction,
                confidence=confidence,
                confidence_range=confidence_range,
                reason=reason,
                requires_human_review_flag=requires_human_review_flag,
                is_high_risk_existing=is_high_risk_existing,
                english_before_text=_english_text(block, "english_before"),
                english_after_text=_english_text(block, "english_after"),
            )
        )

    return records


@dataclass(frozen=True)
class PopulationCounts:
    total: int = 0
    semantic_batch: int = 0
    phase_3a1_resolved: int = 0
    no_english_context: int = 0


def count_population(records: list[BlockRecord]) -> PopulationCounts:
    counts = {origin: 0 for origin in (
        ORIGIN_SEMANTIC_BATCH, ORIGIN_PHASE_3A1_RESOLVED, ORIGIN_NO_ENGLISH_CONTEXT
    )}
    for record in records:
        counts[record.semantic_origin] += 1

    return PopulationCounts(
        total=len(records),
        semantic_batch=counts[ORIGIN_SEMANTIC_BATCH],
        phase_3a1_resolved=counts[ORIGIN_PHASE_3A1_RESOLVED],
        no_english_context=counts[ORIGIN_NO_ENGLISH_CONTEXT],
    )


def validate_population(
    records: list[BlockRecord],
    *,
    expected_total: int | None = None,
    expected_semantic_batch: int | None = None,
    expected_phase_3a1_resolved: int | None = None,
    expected_no_english_context: int | None = None,
) -> None:
    """
    Vérifications structurelles (§7, §39) — chaque compte fourni est vérifié
    strictement ; ceux omis (None) ne sont pas contraints, pour rester
    utilisable par un projet de test plus petit que le projet réel.
    """
    errors: list[str] = []

    ids = [record.block_id for record in records]
    if len(ids) != len(set(ids)):
        duplicates = sorted({block_id for block_id in ids if ids.count(block_id) > 1})
        errors.append(f"block_id dupliqué(s) dans la population fusionnée : {duplicates}.")

    counts = count_population(records)

    if expected_total is not None and counts.total != expected_total:
        errors.append(f"population totale = {counts.total}, attendu {expected_total}.")

    if expected_semantic_batch is not None and counts.semantic_batch != expected_semantic_batch:
        errors.append(
            f"SEMANTIC_BATCH = {counts.semantic_batch}, attendu {expected_semantic_batch}."
        )

    if (
        expected_phase_3a1_resolved is not None
        and counts.phase_3a1_resolved != expected_phase_3a1_resolved
    ):
        errors.append(
            f"PHASE_3A1_RESOLVED = {counts.phase_3a1_resolved}, "
            f"attendu {expected_phase_3a1_resolved}."
        )

    if (
        expected_no_english_context is not None
        and counts.no_english_context != expected_no_english_context
    ):
        errors.append(
            f"NO_ENGLISH_CONTEXT = {counts.no_english_context}, "
            f"attendu {expected_no_english_context}."
        )

    for record in records:
        if record.semantic_origin == ORIGIN_SEMANTIC_BATCH and record.classification is None:
            errors.append(f"{record.block_id} : SEMANTIC_BATCH sans classification.")
        if record.semantic_origin != ORIGIN_SEMANTIC_BATCH and record.classification is not None:
            errors.append(
                f"{record.block_id} : origine {record.semantic_origin} ne devrait pas "
                "porter de classification sémantique."
            )

    if errors:
        raise PopulationError(
            "Population invalide, STOP AVANT SIMULATION (§7, §39) : " + " | ".join(errors)
        )
