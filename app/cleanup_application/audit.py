"""
Assemblage déterministe de cleanup_application.json.

Aucun horodatage, aucun UUID, aucun ordre aléatoire. Deux exécutions
avec les mêmes sources produisent le même JSON.
"""

from __future__ import annotations

from app.cleanup_application.constants import (
    CLASSIFICATION_NOT_TRANSLATION,
    CLASSIFICATION_TRANSLATION_AFTER,
    CLASSIFICATION_UNCERTAIN,
    CONFIDENCE_BUCKET_090_094,
    CONFIDENCE_BUCKET_GE_095,
    CONFIDENCE_BUCKET_LT_090,
    CONTROL_SAMPLE_SIZE,
    DECISION_AUTO_REMOVE,
    DECISION_HUMAN_REVIEW,
    DECISION_KEEP,
    DERIVATION_TYPE,
    ORIGIN_NO_ENGLISH_CONTEXT,
    ORIGIN_PHASE_3A1_RESOLVED,
    ORIGINAL_INDEX_BASIS,
    ORIGINAL_INDEX_CONVENTION,
    POLICY_B,
    POLICY_B_PLUS,
    POLICY_B_PLUS_RULES,
    PROVENANCE_LOCATION,
    RISK_EXTRA_CONTENT_SIGNAL,
    RISK_FORMER_ALL_KEEP,
    RISK_HIGH_RISK_EXISTING,
    RISK_MULTI_SRC,
    SCHEMA_VERSION_APPLICATION,
    TOP_SUPPRESSIONS_SIZE,
    TRANSCRIPT_ID_CONVENTION,
    TRANSLATION_CLASSIFICATIONS,
    WORD_BUCKETS,
)
from app.cleanup_application.integrity import IntegritySnapshot
from app.cleanup_application.models import ApplicationPlan, PlannedBlock, RemovalSnapshot
from app.transcript_models import TranscriptDocument


def _word_bucket(word_count: int) -> str:
    if word_count <= 5:
        return "1-5"
    if word_count <= 10:
        return "6-10"
    if word_count <= 20:
        return "11-20"
    if word_count <= 30:
        return "21-30"
    return ">30"


def _confidence_bucket(confidence: float | None) -> str:
    if confidence is None or confidence < 0.90:
        return CONFIDENCE_BUCKET_LT_090
    if confidence < 0.95:
        return CONFIDENCE_BUCKET_090_094
    return CONFIDENCE_BUCKET_GE_095


def _evenly_spaced(items: list, size: int) -> list:
    if not items:
        return []
    if len(items) <= size:
        return list(items)
    last = len(items) - 1
    return [items[i * last // (size - 1)] for i in range(size)]


def _policy_b_auto_ids(simulation: dict) -> dict[str, dict]:
    auto: dict[str, dict] = {}
    for entry in simulation.get("blocks") or []:
        sim = (entry.get("simulations") or {}).get(POLICY_B) or {}
        if sim.get("decision") == DECISION_AUTO_REMOVE:
            auto[str(entry["block_id"])] = entry
    return auto


def _safe_consensus_ids(simulation: dict) -> list[str]:
    stats = simulation.get("statistics") or {}
    candidate = stats.get("safe_consensus_candidate") or {}
    return list(candidate.get("block_ids") or [])


def _policy_b_totals(simulation: dict) -> dict:
    totals = ((simulation.get("statistics") or {}).get("global_totals") or {}).get(POLICY_B) or {}
    return {
        "auto_remove_blocks": int(totals.get("auto_remove_blocks") or 0),
        "removed_src": int(totals.get("auto_remove_fr_src_count") or 0),
        "removed_words": int(totals.get("auto_remove_words") or 0),
        "removed_duration_seconds": totals.get("auto_remove_duration_seconds"),
        "human_review_blocks": int(totals.get("human_review_blocks") or 0),
        "keep_blocks": int(totals.get("keep_blocks") or 0),
    }


def _human_review_entry(block: PlannedBlock) -> dict:
    record = block.record
    return {
        "block_id": record.block_id,
        "origin": record.semantic_origin,
        "classification": record.classification,
        "confidence": record.confidence,
        "word_count": record.word_count,
        "fr_source_refs": list(record.fr_source_refs),
        "bridge_source_refs": list(record.bridge_source_refs),
        "risk_flags": list(block.risk_flags),
        "decision_reasons": list(block.decision.reasons),
        "fr_text": record.text,
        "english_before_text": record.english_before_text,
        "english_after_text": block.english_after_text if block.english_after_text is not None else record.english_after_text,
        "english_before_source_refs": list(block.english_before_source_refs),
        "english_after_source_refs": list(block.english_after_source_refs),
    }


def _keep_entry(block: PlannedBlock) -> dict:
    record = block.record
    entry = {
        "block_id": record.block_id,
        "origin": record.semantic_origin,
        "classification": record.classification,
        "status": record.semantic_origin if record.classification is None else record.classification,
        "fr_source_refs": list(record.fr_source_refs),
        "decision_reasons": list(block.decision.reasons),
    }
    if record.classification in (CLASSIFICATION_NOT_TRANSLATION, CLASSIFICATION_UNCERTAIN):
        entry["semantic_reason"] = record.reason
    return entry


def _audio_distribution(plan: ApplicationPlan) -> dict:
    audio_ids = sorted({block.record.audio_id for block in plan.blocks})
    result: dict[str, dict] = {}
    snapshots_by_audio: dict[str, list[RemovalSnapshot]] = {audio_id: [] for audio_id in audio_ids}
    for snap in plan.removal_snapshots:
        snapshots_by_audio.setdefault(snap.audio_id, []).append(snap)

    for audio_id in audio_ids:
        subset = [block for block in plan.blocks if block.record.audio_id == audio_id]
        auto = [b for b in subset if b.decision.decision == DECISION_AUTO_REMOVE]
        human = [b for b in subset if b.decision.decision == DECISION_HUMAN_REVIEW]
        keep = [b for b in subset if b.decision.decision == DECISION_KEEP]
        snaps = snapshots_by_audio.get(audio_id) or []
        result[audio_id] = {
            "auto_remove_blocks": len(auto),
            "human_review_blocks": len(human),
            "keep_blocks": len(keep),
            "removed_src": len(snaps),
            "removed_words": sum(s.word_count for s in snaps),
            "removed_duration_seconds": round(sum(s.duration_seconds for s in snaps), 6),
        }
    return result


def _confidence_distribution(snapshots: tuple[RemovalSnapshot, ...]) -> dict:
    buckets = {
        CONFIDENCE_BUCKET_LT_090: 0,
        CONFIDENCE_BUCKET_090_094: 0,
        CONFIDENCE_BUCKET_GE_095: 0,
    }
    for snap in snapshots:
        buckets[_confidence_bucket(snap.confidence)] += 1
    return buckets


def _word_distribution(snapshots: tuple[RemovalSnapshot, ...]) -> dict:
    buckets = {bucket: 0 for bucket in WORD_BUCKETS}
    for snap in snapshots:
        buckets[_word_bucket(snap.word_count)] += 1
    return buckets


def _top_suppressions(plan: ApplicationPlan) -> list[dict]:
    ranked = sorted(
        plan.removal_snapshots,
        key=lambda s: (-s.word_count, s.block_id, s.source_ref),
    )[:TOP_SUPPRESSIONS_SIZE]
    return [
        {
            "block_id": snap.block_id,
            "source_ref": snap.source_ref,
            "audio_id": snap.audio_id,
            "start": snap.start,
            "end": snap.end,
            "word_count": snap.word_count,
            "confidence": snap.confidence,
            "fr_text": snap.text,
            "english_before_text": snap.matched_english_before_text,
            "semantic_reason": snap.semantic_reason,
        }
        for snap in ranked
    ]


def _control_sample(plan: ApplicationPlan) -> list[dict]:
    ordered = sorted(plan.removal_snapshots, key=lambda s: (s.original_index, s.source_ref))
    sample = _evenly_spaced(ordered, CONTROL_SAMPLE_SIZE)
    return [
        {
            "block_id": snap.block_id,
            "source_ref": snap.source_ref,
            "original_index": snap.original_index,
            "fr_removed": snap.text,
            "english_before_kept": snap.matched_english_before_text,
            "confidence": snap.confidence,
            "word_count": snap.word_count,
        }
        for snap in sample
    ]


def _src_gaps(original: TranscriptDocument, clean: TranscriptDocument) -> list[dict]:
    """Quelques trous d'IDs créés (preuves de non-renumérotage)."""
    original_ids = [segment.id for segment in original.segments]
    clean_ids = [segment.id for segment in clean.segments]
    examples: list[dict] = []
    clean_set = set(clean_ids)
    for position, src_id in enumerate(original_ids):
        if src_id in clean_set:
            continue
        previous_kept = next(
            (original_ids[i] for i in range(position - 1, -1, -1) if original_ids[i] in clean_set),
            None,
        )
        next_kept = next(
            (original_ids[i] for i in range(position + 1, len(original_ids)) if original_ids[i] in clean_set),
            None,
        )
        examples.append(
            {
                "removed": src_id,
                "surviving_before": previous_kept,
                "surviving_after": next_kept,
            }
        )
        if len(examples) >= 8:
            break
    return examples


def _classification_counts(plan: ApplicationPlan, classification: str | None, origin: str | None) -> dict:
    matching = [
        block
        for block in plan.blocks
        if (classification is None or block.record.classification == classification)
        and (origin is None or block.record.semantic_origin == origin)
    ]
    retained = all(
        set(block.record.fr_source_refs).isdisjoint(plan.removal_set) for block in matching
    )
    return {
        "observed_count": len(matching),
        "all_retained": retained,
        "block_ids": [block.block_id for block in matching],
    }


def build_audit(
    *,
    plan: ApplicationPlan,
    original: TranscriptDocument,
    clean: TranscriptDocument,
    integrity_before: IntegritySnapshot,
    simulation: dict,
    clean_transcript_data_sha256: str,
    clean_transcript_txt_sha256: str,
    validation: dict,
) -> dict:
    auto = plan.blocks_with(DECISION_AUTO_REMOVE)
    human = plan.blocks_with(DECISION_HUMAN_REVIEW)
    keep = plan.blocks_with(DECISION_KEEP)
    snapshots = plan.removal_snapshots

    policy_b = _policy_b_totals(simulation)
    policy_b_auto = _policy_b_auto_ids(simulation)
    bplus_auto_ids = {block.block_id for block in auto}
    excluded = []
    for block_id, entry in sorted(policy_b_auto.items()):
        if block_id in bplus_auto_ids:
            continue
        planned = next((b for b in plan.blocks if b.block_id == block_id), None)
        source = entry.get("source") or {}
        semantic = entry.get("semantic") or {}
        excluded.append(
            {
                "block_id": block_id,
                "exclusion_reasons": list(planned.decision.reasons) if planned else ["ABSENT_FROM_B_PLUS_PLAN"],
                "source_refs": list(source.get("fr_source_refs") or []),
                "word_count": source.get("word_count"),
                "confidence": semantic.get("confidence"),
                "risk_flags": list(entry.get("risk_flags") or []),
                "classification": semantic.get("classification"),
            }
        )

    safe_ids = _safe_consensus_ids(simulation)
    decision_by_id = {block.block_id: block.decision.decision for block in plan.blocks}
    reasons_by_id = {block.block_id: list(block.decision.reasons) for block in plan.blocks}
    safe_distribution = {
        DECISION_AUTO_REMOVE: [bid for bid in safe_ids if decision_by_id.get(bid) == DECISION_AUTO_REMOVE],
        DECISION_HUMAN_REVIEW: [bid for bid in safe_ids if decision_by_id.get(bid) == DECISION_HUMAN_REVIEW],
        DECISION_KEEP: [bid for bid in safe_ids if decision_by_id.get(bid) == DECISION_KEEP],
    }
    safe_non_auto = [
        {
            "block_id": bid,
            "decision": decision_by_id.get(bid),
            "decision_reasons": reasons_by_id.get(bid, []),
        }
        for bid in safe_ids
        if decision_by_id.get(bid) != DECISION_AUTO_REMOVE
    ]

    former = [
        {
            "block_id": snap.block_id,
            "source_ref": snap.source_ref,
            "word_count": snap.word_count,
            "confidence": snap.confidence,
            "fr_text": snap.text,
            "english_before_text": snap.matched_english_before_text,
        }
        for snap in snapshots
        if RISK_FORMER_ALL_KEEP in snap.risk_flags
    ]

    multi_src_translation = [
        block
        for block in plan.blocks
        if block.record.classification in TRANSLATION_CLASSIFICATIONS
        and (RISK_MULTI_SRC in block.risk_flags or len(block.record.fr_source_refs) > 1)
    ]
    high_risk = [block for block in plan.blocks if RISK_HIGH_RISK_EXISTING in block.risk_flags]
    extra_content = [block for block in plan.blocks if RISK_EXTRA_CONTENT_SIGNAL in block.risk_flags]
    with_bridges = [block for block in plan.blocks if block.record.bridge_source_refs]

    def _all_retained(blocks: list[PlannedBlock]) -> bool:
        return all(set(b.record.fr_source_refs).isdisjoint(plan.removal_set) for b in blocks) and all(
            set(b.record.bridge_source_refs).isdisjoint(plan.removal_set) for b in blocks
        )

    removed_duration = round(sum(snap.duration_seconds for snap in snapshots), 6)

    return {
        "schema_version": SCHEMA_VERSION_APPLICATION,
        "project": plan.project_name,
        "policy": dict(POLICY_B_PLUS_RULES),
        "derivation": {
            "type": DERIVATION_TYPE,
            "source_transcript_id": original.transcript_id,
            "policy": POLICY_B_PLUS,
            "removed_source_count": len(snapshots),
            "cleanup_application_ref": "audit/cleanup_application.json",
            "provenance_location": PROVENANCE_LOCATION,
            "transcript_id_convention": TRANSCRIPT_ID_CONVENTION,
            "note": POLICY_B_PLUS_RULES["clean_view_note"],
        },
        "original_index": {
            "convention": ORIGINAL_INDEX_CONVENTION,
            "basis": ORIGINAL_INDEX_BASIS,
        },
        "source_hashes": integrity_before.to_dict(),
        "clean_hashes": {
            "clean_transcript_data_sha256": clean_transcript_data_sha256,
            "clean_transcript_txt_sha256": clean_transcript_txt_sha256,
        },
        "stats": {
            "total_fr_blocks": len(plan.blocks),
            "auto_remove_blocks": len(auto),
            "human_review_blocks": len(human),
            "keep_blocks": len(keep),
            "removed_source_count": len(snapshots),
            "removed_word_count": sum(snap.word_count for snap in snapshots),
            "removed_duration_seconds": removed_duration,
            "original_segment_count": original.stats.segment_count,
            "clean_segment_count": clean.stats.segment_count,
            "original_word_count": original.stats.word_count,
            "clean_word_count": clean.stats.word_count,
            "original_duration_seconds": original.stats.duration_seconds,
            "clean_duration_seconds": clean.stats.duration_seconds,
        },
        "policy_b_comparison": {
            "policy_b": policy_b,
            "policy_b_plus": {
                "auto_remove_blocks": len(auto),
                "removed_src": len(snapshots),
                "removed_words": sum(snap.word_count for snap in snapshots),
                "removed_duration_seconds": removed_duration,
            },
            "excluded_block_count": len(excluded),
            "excluded_src_count": sum(len(item["source_refs"]) for item in excluded),
            "excluded_word_count": sum(int(item["word_count"] or 0) for item in excluded),
            "excluded_blocks": excluded,
        },
        "safe_consensus": {
            "historical_count": len(safe_ids),
            "auto_remove_ids": safe_distribution[DECISION_AUTO_REMOVE],
            "human_review_ids": safe_distribution[DECISION_HUMAN_REVIEW],
            "keep_ids": safe_distribution[DECISION_KEEP],
            "auto_remove_count": len(safe_distribution[DECISION_AUTO_REMOVE]),
            "human_review_count": len(safe_distribution[DECISION_HUMAN_REVIEW]),
            "keep_count": len(safe_distribution[DECISION_KEEP]),
            "non_auto_explanations": safe_non_auto,
        },
        "former_all_keep_auto_remove": former,
        "translation_after": _classification_counts(
            plan, CLASSIFICATION_TRANSLATION_AFTER, None
        ),
        "multi_src_translation": {
            "observed_count": len(multi_src_translation),
            "all_retained": _all_retained(multi_src_translation),
            "block_ids": [b.block_id for b in multi_src_translation],
        },
        "high_risk": {
            "observed_count": len(high_risk),
            "all_retained": _all_retained(high_risk),
            "block_ids": [b.block_id for b in high_risk],
        },
        "bridges": {
            "observed_count": len(with_bridges),
            "all_retained": _all_retained(with_bridges),
            "block_ids": [b.block_id for b in with_bridges],
        },
        "extra_content": {
            "observed_count": len(extra_content),
            "all_retained": _all_retained(extra_content),
            "block_ids": [b.block_id for b in extra_content],
        },
        "legacy_resolved": _classification_counts(plan, None, ORIGIN_PHASE_3A1_RESOLVED),
        "not_translation": _classification_counts(plan, CLASSIFICATION_NOT_TRANSLATION, None),
        "uncertain": _classification_counts(plan, CLASSIFICATION_UNCERTAIN, None),
        "no_english_context": _classification_counts(plan, None, ORIGIN_NO_ENGLISH_CONTEXT),
        "by_audio": _audio_distribution(plan),
        "by_confidence_auto_remove": _confidence_distribution(snapshots),
        "by_word_count_auto_remove": _word_distribution(snapshots),
        "top_suppressions": _top_suppressions(plan),
        "control_sample": _control_sample(plan),
        "src_id_stability": {
            "renumbering": False,
            "gaps_are_intentional": True,
            "gap_examples": _src_gaps(original, clean),
        },
        "removed": [snap.to_dict() for snap in snapshots],
        "human_review": [_human_review_entry(block) for block in human],
        "kept": [_keep_entry(block) for block in keep],
        "network": {
            "anthropic_calls": 0,
            "openai_calls": 0,
            "whisper_calls": 0,
            "ollama_calls": 0,
            "lm_studio_calls": 0,
            "other_network_calls": 0,
        },
        "validation": validation,
    }
