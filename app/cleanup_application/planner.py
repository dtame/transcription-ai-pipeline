"""
Plan d'application POLICY_B_PLUS_V1 : décisions par bloc + removal_set.

Aucune écriture, aucun réseau. Le removal_set est construit ICI, validé
ensuite par validator.validate_removal_set AVANT toute génération clean.
"""

from __future__ import annotations

from app.cleanup_application.constants import DECISION_AUTO_REMOVE
from app.cleanup_application.loader import (
    occurrence_count,
    original_index_by_src,
    segments_by_id,
)
from app.cleanup_application.models import (
    ApplicationPlan,
    PlannedBlock,
    RemovalSnapshot,
)
from app.cleanup_application.policy import PolicyContext, decide_policy_b_plus
from app.cleanup_policy.population import BlockRecord, build_population, validate_population
from app.cleanup_policy.risk import compute_risk_flags
from app.transcript_models import TranscriptDocument, TranscriptSegment


def _english_refs(extras: dict, key: str) -> tuple[str, ...]:
    return tuple(extras.get(key) or ())


def plan_application(
    *,
    project_name: str,
    records: list[BlockRecord],
    document: TranscriptDocument,
    language_by_src: dict[str, str],
    block_extras: dict[str, dict],
) -> ApplicationPlan:
    """Construit le plan déterministe, trié par block_id."""
    records = sorted(records, key=lambda r: r.block_id)
    context = PolicyContext(
        segments_by_id=segments_by_id(document.segments),
        occurrence_count=occurrence_count(document.segments),
        language_by_src=language_by_src,
    )
    index_by_src = original_index_by_src(document.segments)

    planned: list[PlannedBlock] = []
    snapshots: list[RemovalSnapshot] = []
    removal_ids: list[str] = []

    for record in records:
        risk_flags = compute_risk_flags(record)
        decision = decide_policy_b_plus(record, risk_flags, context)
        extras = block_extras.get(record.block_id) or {}
        planned.append(
            PlannedBlock(
                record=record,
                risk_flags=risk_flags,
                decision=decision,
                english_before_source_refs=_english_refs(extras, "english_before_source_refs"),
                english_after_source_refs=_english_refs(extras, "english_after_source_refs"),
                english_after_text=extras.get("english_after_text"),
            )
        )

        if decision.decision == DECISION_AUTO_REMOVE:
            src = decision.candidate_removed_source_refs[0]
            segment: TranscriptSegment = context.segments_by_id[src]
            snapshots.append(
                RemovalSnapshot(
                    source_ref=src,
                    audio_id=segment.source_id,
                    source_order=segment.source_order,
                    start=segment.start,
                    end=segment.end,
                    text=segment.text,
                    word_count=len(segment.text.split()),
                    original_index=index_by_src[src],
                    block_id=record.block_id,
                    classification=record.classification,
                    matched_direction=record.matched_direction,
                    confidence=record.confidence,
                    semantic_reason=record.reason,
                    risk_flags=risk_flags,
                    matched_english_before_source_refs=_english_refs(
                        extras, "english_before_source_refs"
                    ),
                    matched_english_before_text=record.english_before_text,
                    policy_decision=decision.decision,
                    decision_reasons=decision.reasons,
                )
            )
            removal_ids.append(src)

    snapshots.sort(key=lambda s: (s.original_index, s.source_ref))

    return ApplicationPlan(
        project_name=project_name,
        blocks=tuple(planned),
        removal_snapshots=tuple(snapshots),
        removal_set=frozenset(removal_ids),
    )


def build_records(blocks: list[dict], classification_payload: dict) -> list[BlockRecord]:
    records = build_population(blocks, classification_payload)
    validate_population(records)
    return records
