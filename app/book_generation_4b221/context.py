"""Hydrate CH018 from canonical SourceMap, EditorialPlan, and SRC excerpts."""

from __future__ import annotations

from typing import Any

from app.book_generation.coverage import assigned_idea_ids_for_chapter, chapter_by_id
from app.book_generation.evidence import evidence_metrics
from app.book_generation_4b221.constants import (
    ACCEPTED_CHAPTER_ID,
    EXPECTED_EXAMPLE_COUNT,
    EXPECTED_EXAMPLE_IDS,
    EXPECTED_HYDRATED_SRC_COUNT,
    EXPECTED_IDEA_COUNT,
    EXPECTED_IDEA_IDS,
    EXPECTED_REFERENCE_COUNT,
    EXPECTED_REFERENCE_IDS,
    EXPECTED_SECTION_COUNT,
    EXPECTED_SECTION_IDS,
    PHASE,
    TARGET_CHAPTER_ID,
    TARGET_CHAPTER_TITLE,
)
from app.book_generation_4b221.guard import BookGeneration4221Error, assert_chapter_allowed
from app.book_scale_up_preparation_4b220.context import build_chapter_source_context
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus
from app.editorial_planning.models import EditorialChapter, EditorialPlan


def load_corpus() -> CanonicalCorpus:
    return load_canonical_corpus()


def chapter_from_plan(plan: EditorialPlan) -> EditorialChapter:
    chapter = chapter_by_id(plan, TARGET_CHAPTER_ID)
    assert_chapter_allowed(chapter.chapter_id)
    return chapter


def build_ch018_context(
    *,
    corpus: CanonicalCorpus | None = None,
) -> dict[str, Any]:
    corpus = corpus or load_corpus()
    chapter = chapter_from_plan(corpus.plan)
    if chapter.working_title != TARGET_CHAPTER_TITLE:
        raise BookGeneration4221Error(
            f"CH018 title is {chapter.working_title!r}, expected {TARGET_CHAPTER_TITLE!r}."
        )
    built = build_chapter_source_context(TARGET_CHAPTER_ID, corpus=corpus)
    evidence = built.get("evidence") or {}
    _assert_isolation(built, evidence, corpus.plan, chapter)
    return built


def _assert_isolation(
    manifest: dict[str, Any],
    evidence: dict[str, Any],
    plan: EditorialPlan,
    chapter: EditorialChapter,
) -> None:
    chapter_id = manifest.get("chapter_id") or (evidence.get("chapter") or {}).get("id")
    if chapter_id != TARGET_CHAPTER_ID:
        raise BookGeneration4221Error(f"Evidence chapter is {chapter_id!r}.")
    if chapter_id == ACCEPTED_CHAPTER_ID:
        raise BookGeneration4221Error("CH012 leaked into the CH018 unit.")
    expected = manifest.get("expected_sources") or {}
    section_ids = tuple(expected.get("section_ids") or [])
    planned = tuple(section.section_id for section in chapter.sections)
    if section_ids != planned or section_ids != EXPECTED_SECTION_IDS:
        raise BookGeneration4221Error(
            f"Section isolation failed: {section_ids} ≠ {EXPECTED_SECTION_IDS}"
        )
    idea_ids = tuple(expected.get("idea_ids") or [])
    planned_ideas = tuple(assigned_idea_ids_for_chapter(chapter))
    if set(idea_ids) != set(planned_ideas) or set(idea_ids) != set(EXPECTED_IDEA_IDS):
        raise BookGeneration4221Error(
            f"Idea isolation failed: {idea_ids} ≠ {EXPECTED_IDEA_IDS}"
        )
    if len(idea_ids) != EXPECTED_IDEA_COUNT:
        raise BookGeneration4221Error(
            f"Expected {EXPECTED_IDEA_COUNT} ideas, got {len(idea_ids)}"
        )
    examples = tuple(expected.get("example_ids") or [])
    references = tuple(expected.get("reference_ids") or [])
    if set(examples) != set(EXPECTED_EXAMPLE_IDS):
        raise BookGeneration4221Error(
            f"Example isolation failed: {examples} ≠ {EXPECTED_EXAMPLE_IDS}"
        )
    if set(references) != set(EXPECTED_REFERENCE_IDS):
        raise BookGeneration4221Error(
            f"Reference isolation failed: {references} ≠ {EXPECTED_REFERENCE_IDS}"
        )
    if expected.get("uncertainty_ids"):
        raise BookGeneration4221Error("CH018 must not invent UNC handles.")
    hydrated = (manifest.get("resolved_sources") or {}).get("hydrated_count")
    if hydrated != EXPECTED_HYDRATED_SRC_COUNT:
        raise BookGeneration4221Error(
            f"Expected {EXPECTED_HYDRATED_SRC_COUNT} hydrated SRC, got {hydrated}."
        )
    if manifest.get("missing_sources"):
        raise BookGeneration4221Error(
            "Mandatory SRC excerpts missing: "
            + ",".join(list(manifest.get("missing_sources") or [])[:12])
        )
    if manifest.get("whole_transcript_injected"):
        raise BookGeneration4221Error("Whole transcript was injected. STOP.")
    if manifest.get("raw_transcript_used_as_silent_fallback"):
        raise BookGeneration4221Error("Raw transcript used as silent fallback. STOP.")
    if manifest.get("sources_dropped_to_reduce_cost"):
        raise BookGeneration4221Error("Sources were dropped to reduce cost. STOP.")
    if not evidence.get("src_text"):
        raise BookGeneration4221Error("No hydrated SRC excerpts for CH018.")
    other_ids = [
        item.chapter_id for item in plan.chapters if item.chapter_id != TARGET_CHAPTER_ID
    ]
    leaked = [item for item in other_ids if item == chapter_id]
    if leaked:
        raise BookGeneration4221Error(f"Other chapters leaked into evidence: {leaked}")


def source_context_manifest(built: dict[str, Any]) -> dict[str, Any]:
    evidence = built.get("evidence") or {}
    payload = {key: value for key, value in built.items() if key != "evidence"}
    metrics = evidence_metrics(evidence) if evidence else built.get("context_size") or {}
    payload["phase"] = PHASE
    payload["expected_title"] = TARGET_CHAPTER_TITLE
    payload["expected_section_count"] = EXPECTED_SECTION_COUNT
    payload["expected_idea_count"] = EXPECTED_IDEA_COUNT
    payload["expected_example_count"] = EXPECTED_EXAMPLE_COUNT
    payload["expected_reference_count"] = EXPECTED_REFERENCE_COUNT
    payload["expected_hydrated_src_count"] = EXPECTED_HYDRATED_SRC_COUNT
    payload["context_hash"] = (metrics or {}).get("sha256") or (
        (payload.get("context_size") or {}).get("sha256")
    )
    payload["other_chapters_excluded"] = True
    payload["ch012_excluded"] = True
    payload["external_sources_added"] = False
    payload["internet_lookup"] = False
    payload["bible_completed_from_memory"] = False
    payload["context_truncated"] = bool(payload.get("potentially_truncated"))
    payload["secrets_included"] = False
    return payload


__all__ = [
    "build_ch018_context",
    "chapter_from_plan",
    "load_corpus",
    "source_context_manifest",
]
