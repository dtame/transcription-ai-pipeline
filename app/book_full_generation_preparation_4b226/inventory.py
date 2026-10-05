"""Inventory the 13 remaining EditorialPlan chapters. Coverage is not assumed."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.book_full_generation_preparation_4b226.constants import (
    ACCEPTED_CHAPTER_COUNT,
    ACCEPTED_CHAPTER_IDS,
    PHASE,
    REMAINING_CHAPTER_COUNT,
    REMAINING_CHAPTER_IDS,
    TOTAL_CHAPTER_COUNT,
)
from app.book_full_generation_preparation_4b226.guard import (
    BookFullGenerationPreparation4226Error,
)
from app.book_generation.coverage import assigned_idea_ids_for_chapter, chapter_by_id
from app.book_generation_4b223.inventory import ChapterSpec
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus
from app.book_scale_up_preparation_4b220.inventory import inventory_row


def remaining_chapter_rows(
    corpus: CanonicalCorpus | None = None,
) -> list[dict[str, Any]]:
    corpus = corpus or load_canonical_corpus()
    rows = []
    for index, chapter in enumerate(corpus.plan.chapters, start=1):
        if chapter.chapter_id not in REMAINING_CHAPTER_IDS:
            continue
        row = inventory_row(
            chapter,
            book_order=index,
            source_map=corpus.source_map,
            transcript=corpus.transcript,
        )
        row["generation_status"] = "PENDING_HUMAN_AUTHORIZATION"
        row["validation_status"] = "NOT_STARTED"
        row["editorial_status"] = "NOT_STARTED"
        row["must_not_be_generated_in_this_phase"] = True
        rows.append(row)
    return rows


def remaining_chapters_inventory(
    corpus: CanonicalCorpus | None = None,
    *,
    costs_by_chapter: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    corpus = corpus or load_canonical_corpus()
    plan_ids = [chapter.chapter_id for chapter in corpus.plan.chapters]
    if len(plan_ids) != TOTAL_CHAPTER_COUNT:
        raise BookFullGenerationPreparation4226Error(
            f"EditorialPlan has {len(plan_ids)} chapters, expected {TOTAL_CHAPTER_COUNT}."
        )
    if sorted(set(plan_ids)) != sorted(plan_ids):
        raise BookFullGenerationPreparation4226Error(
            "EditorialPlan contains duplicate chapter IDs."
        )
    missing_accepted = [item for item in ACCEPTED_CHAPTER_IDS if item not in plan_ids]
    if missing_accepted:
        raise BookFullGenerationPreparation4226Error(
            f"Accepted chapters missing from EditorialPlan: {missing_accepted}"
        )
    missing_remaining = [item for item in REMAINING_CHAPTER_IDS if item not in plan_ids]
    if missing_remaining:
        raise BookFullGenerationPreparation4226Error(
            f"Remaining chapters missing from EditorialPlan: {missing_remaining}"
        )
    rows = remaining_chapter_rows(corpus)
    if costs_by_chapter:
        for row in rows:
            cost = costs_by_chapter.get(row["chapter_id"]) or {}
            row["historical_observed_cost_usd"] = cost.get("historical_observed_cost_usd")
            row["central_estimate_usd"] = cost.get("central_estimate_usd")
            row["preflight_max_cost_usd"] = cost.get("preflight_max_cost_usd")
            row["pricing_status"] = cost.get("pricing_status")
    ids = [row["chapter_id"] for row in rows]
    if ids != list(REMAINING_CHAPTER_IDS):
        raise BookFullGenerationPreparation4226Error(
            f"Remaining order {ids} ≠ {list(REMAINING_CHAPTER_IDS)}."
        )
    leaked = [item for item in ids if item in ACCEPTED_CHAPTER_IDS]
    if leaked:
        raise BookFullGenerationPreparation4226Error(
            f"Accepted chapters leaked into the remaining queue: {leaked}"
        )
    if len(rows) != REMAINING_CHAPTER_COUNT:
        raise BookFullGenerationPreparation4226Error(
            f"Remaining inventory has {len(rows)} chapters, expected "
            f"{REMAINING_CHAPTER_COUNT}."
        )
    return {
        "phase": PHASE,
        "total_chapters_in_plan": len(plan_ids),
        "accepted_chapter_ids": list(ACCEPTED_CHAPTER_IDS),
        "accepted_chapter_count": ACCEPTED_CHAPTER_COUNT,
        "remaining_chapter_ids": list(REMAINING_CHAPTER_IDS),
        "remaining_chapter_count": len(rows),
        "expected_remaining_chapter_count": REMAINING_CHAPTER_COUNT,
        "order_deterministic": True,
        "accepted_excluded": True,
        "total_remaining_sections": sum(row["section_count"] for row in rows),
        "total_remaining_ideas": sum(row["idea_count"] for row in rows),
        "total_remaining_examples": sum(row["example_count"] for row in rows),
        "total_remaining_references": sum(row["reference_count"] for row in rows),
        "total_remaining_uncertainties": sum(row["uncertainty_count"] for row in rows),
        "total_remaining_src": sum(row["src_count"] for row in rows),
        "chapters": rows,
        "coverage_not_inferred_from_plan": True,
        "generation_forbidden_in_this_phase": True,
        "secrets_included": False,
    }


def chapter_spec_from_plan(
    chapter_id: str,
    *,
    corpus: CanonicalCorpus | None = None,
) -> ChapterSpec:
    corpus = corpus or load_canonical_corpus()
    chapter = chapter_by_id(corpus.plan, chapter_id)
    book_order = next(
        index
        for index, item in enumerate(corpus.plan.chapters, start=1)
        if item.chapter_id == chapter_id
    )
    row = inventory_row(
        chapter,
        book_order=book_order,
        source_map=corpus.source_map,
        transcript=corpus.transcript,
    )
    planned_sections = tuple(section.section_id for section in chapter.sections)
    planned_ideas = tuple(assigned_idea_ids_for_chapter(chapter))
    return ChapterSpec(
        chapter_id=chapter.chapter_id,
        title=chapter.working_title,
        section_ids=planned_sections,
        idea_ids=planned_ideas,
        example_ids=tuple(row.get("example_ids") or []),
        reference_ids=tuple(row.get("reference_ids") or []),
        uncertainty_ids=tuple(row.get("uncertainty_ids") or []),
        src_ids=tuple(row.get("src_ids") or []),
        section_count=len(planned_sections),
        idea_count=len(planned_ideas),
        example_count=int(row.get("example_count") or 0),
        reference_count=int(row.get("reference_count") or 0),
        uncertainty_count=int(row.get("uncertainty_count") or 0),
        src_count=int(row.get("src_count") or 0),
        envelope_expected_usd=Decimal("0"),
        envelope_max_usd=Decimal("0"),
    )


__all__ = [
    "chapter_spec_from_plan",
    "remaining_chapter_rows",
    "remaining_chapters_inventory",
]
