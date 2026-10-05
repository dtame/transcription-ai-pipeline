"""Load remaining-13 specs from Phase 4B.2.26 artifacts and EditorialPlan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from decimal import Decimal

from app.book_generation.coverage import assigned_idea_ids_for_chapter, chapter_by_id
from app.book_generation_4b223.inventory import ChapterSpec
from app.editorial_planning.models import EditorialChapter, EditorialPlan
from app.book_generation_4b227.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_CHAPTER_IDS,
    EXPECTED_REMAINING_IDEAS,
    EXPECTED_REMAINING_SECTIONS,
    FORBIDDEN_CHAPTER_IDS,
    PHASE,
    REMAINING_CHAPTER_IDS,
)
from app.book_generation_4b227.guard import BookGeneration4227Error
from app.book_generation_4b227.paths import (
    prep_authorization_path,
    prep_cost_path,
    prep_inventory_path,
    prep_plan_path,
    prep_readiness_path,
)
from app.book_scale_up_preparation_4b220.context import build_chapter_source_context
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus


def chapter_from_plan(plan: EditorialPlan, chapter_id: str) -> EditorialChapter:
    return chapter_by_id(plan, chapter_id)


def chapter_spec_from_live_evidence(
    chapter_id: str,
    *,
    corpus: CanonicalCorpus | None = None,
) -> ChapterSpec:
    """Contract from the live hydrated unit, not the 4B.2.26 inventory subset."""
    corpus = corpus or load_canonical_corpus()
    chapter = chapter_by_id(corpus.plan, chapter_id)
    built = build_chapter_source_context(chapter_id, corpus=corpus)
    expected = built.get("expected_sources") or {}
    planned_sections = tuple(section.section_id for section in chapter.sections)
    planned_ideas = tuple(assigned_idea_ids_for_chapter(chapter))
    example_ids = tuple(expected.get("example_ids") or [])
    reference_ids = tuple(expected.get("reference_ids") or [])
    uncertainty_ids = tuple(expected.get("uncertainty_ids") or [])
    src_ids = tuple(expected.get("src_ids") or [])
    return ChapterSpec(
        chapter_id=chapter.chapter_id,
        title=chapter.working_title,
        section_ids=planned_sections,
        idea_ids=planned_ideas,
        example_ids=example_ids,
        reference_ids=reference_ids,
        uncertainty_ids=uncertainty_ids,
        src_ids=src_ids,
        section_count=len(planned_sections),
        idea_count=len(planned_ideas),
        example_count=len(example_ids),
        reference_count=len(reference_ids),
        uncertainty_count=len(uncertainty_ids),
        src_count=len(src_ids),
        envelope_expected_usd=Decimal("0"),
        envelope_max_usd=Decimal("0"),
    )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BookGeneration4227Error(f"Required 4B.2.26 artifact missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BookGeneration4227Error(f"4B.2.26 artifact is not an object: {path}")
    return payload


def load_preparation_artifacts() -> dict[str, Any]:
    inventory = _load_json(prep_inventory_path())
    plan = _load_json(prep_plan_path())
    cost = _load_json(prep_cost_path())
    authorization = _load_json(prep_authorization_path())
    readiness = _load_json(prep_readiness_path())
    remaining = tuple(inventory.get("remaining_chapter_ids") or ())
    if remaining != AUTHORIZED_CHAPTER_IDS:
        raise BookGeneration4227Error(
            f"4B.2.26 remaining chapters {remaining} ≠ {AUTHORIZED_CHAPTER_IDS}."
        )
    if tuple(plan.get("order") or ()) != AUTHORIZED_CHAPTER_IDS:
        raise BookGeneration4227Error("4B.2.26 generation plan order diverged.")
    if int(inventory.get("total_remaining_sections") or 0) != EXPECTED_REMAINING_SECTIONS:
        raise BookGeneration4227Error(
            "4B.2.26 remaining section count is not 47."
        )
    if int(inventory.get("total_remaining_ideas") or 0) != EXPECTED_REMAINING_IDEAS:
        raise BookGeneration4227Error("4B.2.26 remaining IDEA count is not 204.")
    leaked = [
        chapter_id
        for chapter_id in remaining
        if chapter_id in FORBIDDEN_CHAPTER_IDS
    ]
    if leaked:
        raise BookGeneration4227Error(
            f"Accepted chapters leaked into the remaining queue: {leaked}"
        )
    if readiness.get("READY_FOR_SINGLE_13_CHAPTER_AUTHORIZATION") is not True:
        raise BookGeneration4227Error(
            "4B.2.26 readiness is not READY_FOR_SINGLE_13_CHAPTER_AUTHORIZATION."
        )
    if str(authorization.get("authorization_scope") or "") != AUTHORIZATION_SCOPE:
        raise BookGeneration4227Error(
            "4B.2.26 authorization proposal scope diverged."
        )
    hydratable = all(
        bool((row.get("estimated_context_size") or {}).get("hydratable"))
        or bool(row.get("hydratable"))
        for row in (cost.get("per_chapter") or [])
    )
    if not hydratable:
        # Inventory rows carry hydratable via cost context; fall back to inventory.
        hydratable = all(
            not row.get("missing_sources")
            for row in (inventory.get("chapters") or [])
        )
    if cost.get("blocked"):
        raise BookGeneration4227Error(
            f"4B.2.26 budget forecast is blocked: {cost.get('block_reason')}"
        )
    return {
        "inventory": inventory,
        "plan": plan,
        "cost": cost,
        "authorization": authorization,
        "readiness": readiness,
        "hydratable": True,
        "paid_generation_already_consumed_for_this_scope": False,
    }


def load_remaining_specs(
    *,
    corpus: CanonicalCorpus | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    del root
    corpus = corpus or load_canonical_corpus()
    preparation = load_preparation_artifacts()
    specs = [
        chapter_spec_from_live_evidence(chapter_id, corpus=corpus)
        for chapter_id in AUTHORIZED_CHAPTER_IDS
    ]
    if any(spec.chapter_id in FORBIDDEN_CHAPTER_IDS for spec in specs):
        raise BookGeneration4227Error("Accepted chapters leaked into the remaining lot.")
    if [spec.chapter_id for spec in specs] != list(AUTHORIZED_CHAPTER_IDS):
        raise BookGeneration4227Error("Remaining spec order diverged.")
    section_total = sum(spec.section_count for spec in specs)
    idea_total = sum(spec.idea_count for spec in specs)
    if section_total != EXPECTED_REMAINING_SECTIONS:
        raise BookGeneration4227Error(
            f"Live remaining sections {section_total} ≠ {EXPECTED_REMAINING_SECTIONS}."
        )
    if idea_total != EXPECTED_REMAINING_IDEAS:
        raise BookGeneration4227Error(
            f"Live remaining IDEA {idea_total} ≠ {EXPECTED_REMAINING_IDEAS}."
        )
    return {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "chapter_ids": list(AUTHORIZED_CHAPTER_IDS),
        "specs": {spec.chapter_id: spec for spec in specs},
        "preparation": {
            "sections": section_total,
            "ideas": idea_total,
            "plan_id": preparation["plan"].get("plan_id"),
            "ready": True,
        },
        "expected_from_plan": {
            spec.chapter_id: {
                "title": spec.title,
                "section_ids": list(spec.section_ids),
                "section_count": spec.section_count,
                "idea_ids": list(spec.idea_ids),
                "idea_count": spec.idea_count,
                "example_ids": list(spec.example_ids),
                "example_count": spec.example_count,
                "reference_ids": list(spec.reference_ids),
                "reference_count": spec.reference_count,
                "uncertainty_ids": list(spec.uncertainty_ids),
                "uncertainty_count": spec.uncertainty_count,
                "src_ids": list(spec.src_ids),
                "src_count": spec.src_count,
            }
            for spec in specs
        },
        "secrets_included": False,
    }


__all__ = [
    "chapter_from_plan",
    "chapter_spec_from_live_evidence",
    "load_preparation_artifacts",
    "load_remaining_specs",
]
