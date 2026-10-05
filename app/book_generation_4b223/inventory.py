"""Load and verify BATCH-01 chapter specs from the 4B.2.22 plan and EditorialPlan."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.book_generation.coverage import assigned_idea_ids_for_chapter, chapter_by_id
from app.book_generation_4b223.constants import (
    AUTHORIZED_CHAPTER_IDS,
    BATCH_ID,
    FORBIDDEN_CHAPTER_IDS,
    PHASE,
    PREPARATION_CALCULABLE_MAXIMUM_USD,
)
from app.book_generation_4b223.guard import BookGeneration4223Error, assert_chapter_allowed
from app.book_generation_4b223.paths import (
    batch_envelope_path,
    batch_plan_path,
    remaining_inventory_path,
    repo_root,
)
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus
from app.editorial_planning.models import EditorialChapter, EditorialPlan


@dataclass(frozen=True)
class ChapterSpec:
    chapter_id: str
    title: str
    section_ids: tuple[str, ...]
    idea_ids: tuple[str, ...]
    example_ids: tuple[str, ...]
    reference_ids: tuple[str, ...]
    uncertainty_ids: tuple[str, ...]
    src_ids: tuple[str, ...]
    section_count: int
    idea_count: int
    example_count: int
    reference_count: int
    uncertainty_count: int
    src_count: int
    envelope_expected_usd: Decimal
    envelope_max_usd: Decimal


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BookGeneration4223Error(f"Required preparation artifact missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BookGeneration4223Error(f"Preparation artifact is not an object: {path}")
    return payload


def load_preparation(*, root: Path | None = None) -> dict[str, Any]:
    # 4B.2.22 preparation artifacts are immutable and always read from the repo.
    del root
    base = repo_root()
    plan = _load_json(batch_plan_path(root=base))
    envelope = _load_json(batch_envelope_path(root=base))
    inventory = _load_json(remaining_inventory_path(root=base))
    batches = list(plan.get("batches") or [])
    batch01 = next((row for row in batches if row.get("batch_id") == BATCH_ID), None)
    if batch01 is None:
        raise BookGeneration4223Error("BATCH-01 is missing from the generation plan.")
    chapter_ids = tuple(batch01.get("chapter_ids") or ())
    order = tuple(batch01.get("deterministic_order") or ())
    if chapter_ids != AUTHORIZED_CHAPTER_IDS or order != AUTHORIZED_CHAPTER_IDS:
        raise BookGeneration4223Error(
            f"BATCH-01 chapters {chapter_ids} / {order} ≠ {AUTHORIZED_CHAPTER_IDS}."
        )
    if int(batch01.get("max_calls") or 0) != 4:
        raise BookGeneration4223Error("BATCH-01 max_calls is not 4.")
    if int(batch01.get("max_calls_per_chapter") or 0) != 1:
        raise BookGeneration4223Error("BATCH-01 max_calls_per_chapter is not 1.")
    if int(batch01.get("retries", 0)) != 0 or int(batch01.get("fallbacks", 0)) != 0:
        raise BookGeneration4223Error("BATCH-01 retries/fallbacks must be 0.")
    envelope_batch = next(
        (row for row in envelope.get("batches") or [] if row.get("batch_id") == BATCH_ID),
        None,
    )
    if envelope_batch is None:
        raise BookGeneration4223Error("BATCH-01 is missing from the cost envelope.")
    calculable = Decimal(str(envelope_batch.get("calculable_maximum_usd")))
    if calculable != PREPARATION_CALCULABLE_MAXIMUM_USD:
        raise BookGeneration4223Error(
            f"BATCH-01 calculable maximum {calculable} ≠ "
            f"{PREPARATION_CALCULABLE_MAXIMUM_USD}."
        )
    return {
        "phase": PHASE,
        "plan": plan,
        "envelope": envelope,
        "inventory": inventory,
        "batch01": batch01,
        "envelope_batch": envelope_batch,
    }


def _inventory_row(inventory: dict[str, Any], chapter_id: str) -> dict[str, Any]:
    for row in inventory.get("chapters") or []:
        if row.get("chapter_id") == chapter_id:
            return row
    raise BookGeneration4223Error(f"{chapter_id} missing from remaining-17 inventory.")


def _envelope_row(envelope: dict[str, Any], chapter_id: str) -> dict[str, Any]:
    for row in envelope.get("per_chapter") or []:
        if row.get("chapter_id") == chapter_id:
            return row
    raise BookGeneration4223Error(f"{chapter_id} missing from the cost envelope.")


def _live_chapter(plan: EditorialPlan, chapter_id: str) -> EditorialChapter:
    assert_chapter_allowed(chapter_id)
    return chapter_by_id(plan, chapter_id)


def chapter_spec(
    chapter_id: str,
    *,
    corpus: CanonicalCorpus | None = None,
    preparation: dict[str, Any] | None = None,
    root: Path | None = None,
) -> ChapterSpec:
    corpus = corpus or load_canonical_corpus()
    preparation = preparation or load_preparation(root=root)
    chapter = _live_chapter(corpus.plan, chapter_id)
    inventory = _inventory_row(preparation["inventory"], chapter_id)
    envelope = _envelope_row(preparation["envelope"], chapter_id)
    planned_sections = tuple(section.section_id for section in chapter.sections)
    planned_ideas = tuple(assigned_idea_ids_for_chapter(chapter))
    inv_sections = tuple(inventory.get("section_ids") or [])
    inv_ideas = tuple(inventory.get("idea_ids") or [])
    if planned_sections != inv_sections:
        raise BookGeneration4223Error(
            f"{chapter_id} sections diverge: plan={planned_sections} "
            f"inventory={inv_sections}."
        )
    if set(planned_ideas) != set(inv_ideas) or len(planned_ideas) != len(inv_ideas):
        raise BookGeneration4223Error(
            f"{chapter_id} IDEA set diverges from inventory."
        )
    if chapter.working_title != inventory.get("working_title"):
        raise BookGeneration4223Error(
            f"{chapter_id} title {chapter.working_title!r} ≠ "
            f"{inventory.get('working_title')!r}."
        )
    if chapter.working_title != envelope.get("working_title"):
        raise BookGeneration4223Error(
            f"{chapter_id} envelope title {envelope.get('working_title')!r} diverges."
        )
    if int(inventory.get("idea_count") or 0) != len(planned_ideas):
        raise BookGeneration4223Error(f"{chapter_id} idea_count does not match the plan.")
    if int(inventory.get("section_count") or 0) != len(planned_sections):
        raise BookGeneration4223Error(
            f"{chapter_id} section_count does not match the plan."
        )
    if int(envelope.get("idea_count") or 0) != len(planned_ideas):
        raise BookGeneration4223Error(f"{chapter_id} envelope idea_count diverges.")
    if int(envelope.get("section_count") or 0) != len(planned_sections):
        raise BookGeneration4223Error(f"{chapter_id} envelope section_count diverges.")
    return ChapterSpec(
        chapter_id=chapter_id,
        title=chapter.working_title,
        section_ids=planned_sections,
        idea_ids=planned_ideas,
        example_ids=tuple(inventory.get("example_ids") or []),
        reference_ids=tuple(inventory.get("reference_ids") or []),
        uncertainty_ids=tuple(inventory.get("uncertainty_ids") or []),
        src_ids=tuple(inventory.get("src_ids") or []),
        section_count=len(planned_sections),
        idea_count=len(planned_ideas),
        example_count=int(inventory.get("example_count") or 0),
        reference_count=int(inventory.get("reference_count") or 0),
        uncertainty_count=int(inventory.get("uncertainty_count") or 0),
        src_count=int(inventory.get("src_count") or 0),
        envelope_expected_usd=Decimal(str(envelope.get("expected_cost_usd"))),
        envelope_max_usd=Decimal(str(envelope.get("calculable_maximum_usd"))),
    )


def load_batch01_specs(
    *,
    corpus: CanonicalCorpus | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    corpus = corpus or load_canonical_corpus()
    preparation = load_preparation(root=root)
    specs = [
        chapter_spec(chapter_id, corpus=corpus, preparation=preparation, root=root)
        for chapter_id in AUTHORIZED_CHAPTER_IDS
    ]
    if any(spec.chapter_id in FORBIDDEN_CHAPTER_IDS for spec in specs):
        raise BookGeneration4223Error("Accepted chapters leaked into BATCH-01.")
    if [spec.chapter_id for spec in specs] != list(AUTHORIZED_CHAPTER_IDS):
        raise BookGeneration4223Error("BATCH-01 spec order is not CH001-CH004.")
    return {
        "phase": PHASE,
        "batch_id": BATCH_ID,
        "chapter_ids": list(AUTHORIZED_CHAPTER_IDS),
        "specs": {spec.chapter_id: spec for spec in specs},
        "preparation": {
            "plan_max_calls": preparation["batch01"].get("max_calls"),
            "calculable_maximum_usd": str(
                preparation["envelope_batch"].get("calculable_maximum_usd")
            ),
            "expected_cost_usd": preparation["envelope_batch"].get("expected_cost_usd"),
        },
        "secrets_included": False,
    }


def chapter_from_plan(plan: EditorialPlan, chapter_id: str) -> EditorialChapter:
    return _live_chapter(plan, chapter_id)


__all__ = [
    "ChapterSpec",
    "chapter_from_plan",
    "chapter_spec",
    "load_batch01_specs",
    "load_preparation",
]
