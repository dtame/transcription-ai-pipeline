"""Batch generation plan. This phase prepares lots. It does not execute them."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_batch_preparation_4b222.constants import (
    ACCEPTED_CHAPTERS,
    BATCH_CHAPTERS,
    BATCH_IDS,
    FAITHFUL_PROMPT_1_1,
    FIRST_BATCH_ID,
    MODEL,
    PHASE,
    PROVIDER,
    REMAINING_CHAPTER_COUNT,
)
from app.book_batch_preparation_4b222.guard import BookBatchPreparation4222Error


def _batch_row(
    batch_id: str,
    *,
    remaining_ids: list[str],
    costs: Mapping[str, Any],
) -> dict[str, Any]:
    chapter_ids = list(BATCH_CHAPTERS[batch_id])
    missing = [item for item in chapter_ids if item not in remaining_ids]
    extra_accepted = [item for item in chapter_ids if item in ACCEPTED_CHAPTERS]
    if missing or extra_accepted:
        raise BookBatchPreparation4222Error(
            f"{batch_id} chapter list is invalid: missing={missing} accepted={extra_accepted}"
        )
    cost_row = next(
        (row for row in costs.get("batches") or [] if row.get("batch_id") == batch_id),
        {},
    )
    return {
        "batch_id": batch_id,
        "chapter_ids": chapter_ids,
        "deterministic_order": chapter_ids,
        "editorial_book_order": True,
        "chapter_count": len(chapter_ids),
        "one_provider_call_per_chapter": True,
        "multi_chapter_provider_call": False,
        "expected_cost_usd": cost_row.get("expected_cost_usd"),
        "calculable_maximum_usd": cost_row.get("calculable_maximum_usd"),
        "proposed_cap_usd": cost_row.get("proposed_cap_usd"),
        "authorized_cap_usd": 0.0,
        "progress_state": "PREPARED_NOT_AUTHORIZED",
        "authorized": False,
        "executable_in_this_phase": False,
        "independent_artifacts": True,
        "resume_without_rerunning_completed": True,
        "stop_conditions": [
            "invalid_json",
            "missing_sections",
            "untraced_required_ideas",
            "invented_src",
            "truncated_response",
            "cost_unknown",
            "cap_exceeded",
            "uncertain_call_state",
            "missing_authorization",
            "unauthorized_prompt_or_model_change",
        ],
        "max_calls": len(chapter_ids),
        "max_calls_per_chapter": 1,
        "retries": 0,
        "fallbacks": 0,
    }


def batch_generation_plan(
    *,
    inventory: Mapping[str, Any],
    cost: Mapping[str, Any],
) -> dict[str, Any]:
    remaining_ids = [row["chapter_id"] for row in inventory.get("chapters") or []]
    planned = [chapter for batch_id in BATCH_IDS for chapter in BATCH_CHAPTERS[batch_id]]
    if remaining_ids != planned:
        raise BookBatchPreparation4222Error(
            "Batch chapter list must equal the remaining 17 chapters in editorial order."
        )
    if len(set(planned)) != REMAINING_CHAPTER_COUNT:
        raise BookBatchPreparation4222Error("Batch plan has duplicates or missing chapters.")
    batches = [
        _batch_row(batch_id, remaining_ids=remaining_ids, costs=cost)
        for batch_id in BATCH_IDS
    ]
    return {
        "phase": PHASE,
        "this_phase_executes": False,
        "assembly_order": "editorial_book_order",
        "execution_order": "editorial_book_order",
        "execution_order_deviation_justified": False,
        "batch_size_rationale": (
            "Editorial order is retained. Observed 4+4+4+5 sizes keep each lot "
            "interruptible. BATCH-02 carries CH006, the largest remaining chapter "
            "(38 IDEA / 8 sections), so its proposed cap is higher than the others. "
            "Reordering CH006 later would break editorial execution without a "
            "hard financial block: its calculable maximum remains individually "
            "boundable."
        ),
        "indicative_sizes_checked_against_real_costs": True,
        "batches": batches,
        "first_batch_id": FIRST_BATCH_ID,
        "provider": PROVIDER,
        "model": MODEL,
        "prompt_version": FAITHFUL_PROMPT_1_1,
        "one_chapter_per_provider_call": True,
        "publication": "not_granted",
        "secrets_included": False,
    }


__all__ = ["batch_generation_plan"]
