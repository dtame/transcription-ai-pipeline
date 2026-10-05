"""Inventory the 17 remaining EditorialPlan chapters. Coverage is not assumed."""

from __future__ import annotations

from typing import Any

from app.book_batch_preparation_4b222.constants import (
    ACCEPTED_CHAPTER_COUNT,
    ACCEPTED_CHAPTERS,
    ACCEPTED_CH012_ID,
    ACCEPTED_CH018_ID,
    PHASE,
    REMAINING_CHAPTER_COUNT,
    STATUS_ACCEPTED,
    STATUS_PENDING,
    TOTAL_CHAPTER_COUNT,
)
from app.book_batch_preparation_4b222.guard import BookBatchPreparation4222Error
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus
from app.book_scale_up_preparation_4b220.inventory import inventory_row


def remaining_17_chapters(
    corpus: CanonicalCorpus | None = None,
) -> list[dict[str, Any]]:
    corpus = corpus or load_canonical_corpus()
    rows = []
    for index, chapter in enumerate(corpus.plan.chapters, start=1):
        if chapter.chapter_id in ACCEPTED_CHAPTERS:
            continue
        row = inventory_row(
            chapter,
            book_order=index,
            source_map=corpus.source_map,
            transcript=corpus.transcript,
        )
        row["generation_status"] = STATUS_PENDING
        row["validation_status"] = "NOT_STARTED"
        row["editorial_status"] = "NOT_STARTED"
        rows.append(row)
    return rows


def remaining_17_chapters_inventory(
    corpus: CanonicalCorpus | None = None,
    *,
    costs_by_chapter: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    corpus = corpus or load_canonical_corpus()
    plan_ids = [chapter.chapter_id for chapter in corpus.plan.chapters]
    if len(plan_ids) != TOTAL_CHAPTER_COUNT:
        raise BookBatchPreparation4222Error(
            f"EditorialPlan has {len(plan_ids)} chapters, expected {TOTAL_CHAPTER_COUNT}."
        )
    if sorted(set(plan_ids)) != sorted(plan_ids):
        raise BookBatchPreparation4222Error("EditorialPlan contains duplicate chapter IDs.")
    missing_accepted = [item for item in ACCEPTED_CHAPTERS if item not in plan_ids]
    if missing_accepted:
        raise BookBatchPreparation4222Error(
            f"Accepted chapters missing from EditorialPlan: {missing_accepted}"
        )
    rows = remaining_17_chapters(corpus)
    if costs_by_chapter:
        for row in rows:
            cost = costs_by_chapter.get(row["chapter_id"]) or {}
            row["estimated_cost_usd"] = cost.get("expected_cost_usd")
            row["calculable_maximum_usd"] = cost.get("calculable_maximum_usd")
            row["authorized_budget_usd"] = cost.get("authorized_budget_usd")
    ids = [row["chapter_id"] for row in rows]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    forgotten = [
        chapter_id
        for chapter_id in plan_ids
        if chapter_id not in ACCEPTED_CHAPTERS and chapter_id not in ids
    ]
    if len(rows) != REMAINING_CHAPTER_COUNT:
        raise BookBatchPreparation4222Error(
            f"Remaining inventory has {len(rows)} chapters, expected "
            f"{REMAINING_CHAPTER_COUNT}."
        )
    if ACCEPTED_CH012_ID in ids or ACCEPTED_CH018_ID in ids:
        raise BookBatchPreparation4222Error(
            "Accepted chapters must be excluded from the remaining generation queue."
        )
    if duplicates:
        raise BookBatchPreparation4222Error(f"Duplicate remaining chapter IDs: {duplicates}")
    if forgotten:
        raise BookBatchPreparation4222Error(f"Forgotten remaining chapters: {forgotten}")
    book_order = [row["book_order"] for row in rows]
    if book_order != sorted(book_order):
        raise BookBatchPreparation4222Error("Remaining chapters are not in book order.")
    return {
        "phase": PHASE,
        "total_chapters_in_plan": len(plan_ids),
        "accepted_chapters": [
            {
                "chapter_id": ACCEPTED_CH012_ID,
                "generation_status": STATUS_ACCEPTED,
                "validation_status": "EDITORIAL_ACCEPTED_NOT_SEMANTICALLY_CERTIFIED",
                "content_duplicated": False,
            },
            {
                "chapter_id": ACCEPTED_CH018_ID,
                "generation_status": STATUS_ACCEPTED,
                "validation_status": "EDITORIAL_ACCEPTED_NOT_SEMANTICALLY_CERTIFIED",
                "content_duplicated": False,
            },
        ],
        "accepted_chapter_count": ACCEPTED_CHAPTER_COUNT,
        "remaining_chapter_count": len(rows),
        "expected_remaining_chapter_count": REMAINING_CHAPTER_COUNT,
        "duplicate_ids": duplicates,
        "forgotten_ids": forgotten,
        "book_order_preserved": True,
        "total_remaining_sections": sum(row["section_count"] for row in rows),
        "total_remaining_ideas": sum(row["idea_count"] for row in rows),
        "total_remaining_examples": sum(row["example_count"] for row in rows),
        "total_remaining_references": sum(row["reference_count"] for row in rows),
        "total_remaining_uncertainties": sum(row["uncertainty_count"] for row in rows),
        "total_remaining_src": sum(row["src_count"] for row in rows),
        "chapters": rows,
        "coverage_not_inferred_from_plan": True,
        "secrets_included": False,
    }


__all__ = ["remaining_17_chapters", "remaining_17_chapters_inventory"]
