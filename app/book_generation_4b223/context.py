"""Hydrate one BATCH-01 chapter from canonical SourceMap, EditorialPlan, and SRC."""

from __future__ import annotations

from typing import Any

from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.evidence import evidence_metrics
from app.book_generation_4b223.constants import FORBIDDEN_CHAPTER_IDS, PHASE
from app.book_generation_4b223.guard import BookGeneration4223Error, assert_chapter_allowed
from app.book_generation_4b223.inventory import ChapterSpec
from app.book_scale_up_preparation_4b220.context import build_chapter_source_context
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus
from app.editorial_planning.models import EditorialChapter, EditorialPlan


def load_corpus() -> CanonicalCorpus:
    return load_canonical_corpus()


def build_chapter_context(
    spec: ChapterSpec,
    *,
    corpus: CanonicalCorpus | None = None,
) -> dict[str, Any]:
    assert_chapter_allowed(spec.chapter_id)
    corpus = corpus or load_corpus()
    chapter = next(
        item for item in corpus.plan.chapters if item.chapter_id == spec.chapter_id
    )
    if chapter.working_title != spec.title:
        raise BookGeneration4223Error(
            f"{spec.chapter_id} title is {chapter.working_title!r}, expected {spec.title!r}."
        )
    built = build_chapter_source_context(spec.chapter_id, corpus=corpus)
    evidence = built.get("evidence") or {}
    _assert_isolation(built, evidence, corpus.plan, chapter, spec)
    return built


def _assert_isolation(
    manifest: dict[str, Any],
    evidence: dict[str, Any],
    plan: EditorialPlan,
    chapter: EditorialChapter,
    spec: ChapterSpec,
) -> None:
    chapter_id = manifest.get("chapter_id") or (evidence.get("chapter") or {}).get("id")
    if chapter_id != spec.chapter_id:
        raise BookGeneration4223Error(f"Evidence chapter is {chapter_id!r}.")
    if chapter_id in FORBIDDEN_CHAPTER_IDS:
        raise BookGeneration4223Error(f"{chapter_id} leaked into a BATCH-01 unit.")
    expected = manifest.get("expected_sources") or {}
    section_ids = tuple(expected.get("section_ids") or [])
    planned = tuple(section.section_id for section in chapter.sections)
    if section_ids != planned or section_ids != spec.section_ids:
        raise BookGeneration4223Error(
            f"{spec.chapter_id} section isolation failed: {section_ids} ≠ {spec.section_ids}"
        )
    idea_ids = tuple(expected.get("idea_ids") or [])
    planned_ideas = tuple(assigned_idea_ids_for_chapter(chapter))
    if set(idea_ids) != set(planned_ideas) or set(idea_ids) != set(spec.idea_ids):
        raise BookGeneration4223Error(
            f"{spec.chapter_id} idea isolation failed: {idea_ids} ≠ {spec.idea_ids}"
        )
    if len(idea_ids) != spec.idea_count:
        raise BookGeneration4223Error(
            f"{spec.chapter_id} expected {spec.idea_count} ideas, got {len(idea_ids)}"
        )
    examples = tuple(expected.get("example_ids") or [])
    references = tuple(expected.get("reference_ids") or [])
    uncertainties = tuple(expected.get("uncertainty_ids") or [])
    if set(examples) != set(spec.example_ids):
        raise BookGeneration4223Error(
            f"{spec.chapter_id} example isolation failed: {examples} ≠ {spec.example_ids}"
        )
    if set(references) != set(spec.reference_ids):
        raise BookGeneration4223Error(
            f"{spec.chapter_id} reference isolation failed: {references} ≠ {spec.reference_ids}"
        )
    if set(uncertainties) != set(spec.uncertainty_ids):
        raise BookGeneration4223Error(
            f"{spec.chapter_id} UNC isolation failed: {uncertainties} ≠ {spec.uncertainty_ids}"
        )
    src_ids = tuple(expected.get("src_ids") or [])
    if spec.src_count and len(src_ids) != spec.src_count:
        raise BookGeneration4223Error(
            f"{spec.chapter_id} expected {spec.src_count} SRC, got {len(src_ids)}."
        )
    hydrated = (manifest.get("resolved_sources") or {}).get("hydrated_count")
    if hydrated != len(src_ids):
        raise BookGeneration4223Error(
            f"{spec.chapter_id} hydrated SRC {hydrated} ≠ expected {len(src_ids)}."
        )
    if manifest.get("missing_sources"):
        raise BookGeneration4223Error(
            "Mandatory SRC excerpts missing: "
            + ",".join(list(manifest.get("missing_sources") or [])[:12])
        )
    if manifest.get("whole_transcript_injected"):
        raise BookGeneration4223Error("Whole transcript was injected. STOP.")
    if manifest.get("raw_transcript_used_as_silent_fallback"):
        raise BookGeneration4223Error("Raw transcript used as silent fallback. STOP.")
    if manifest.get("sources_dropped_to_reduce_cost"):
        raise BookGeneration4223Error("Sources were dropped to reduce cost. STOP.")
    if not evidence.get("src_text"):
        raise BookGeneration4223Error(f"No hydrated SRC excerpts for {spec.chapter_id}.")
    other_ids = [
        item.chapter_id for item in plan.chapters if item.chapter_id != spec.chapter_id
    ]
    leaked = [item for item in other_ids if item == chapter_id]
    if leaked:
        raise BookGeneration4223Error(f"Other chapters leaked into evidence: {leaked}")


def source_context_manifest(built: dict[str, Any], spec: ChapterSpec) -> dict[str, Any]:
    evidence = built.get("evidence") or {}
    payload = {key: value for key, value in built.items() if key != "evidence"}
    metrics = evidence_metrics(evidence) if evidence else built.get("context_size") or {}
    payload["phase"] = PHASE
    payload["expected_title"] = spec.title
    payload["expected_section_count"] = spec.section_count
    payload["expected_idea_count"] = spec.idea_count
    payload["expected_example_count"] = spec.example_count
    payload["expected_reference_count"] = spec.reference_count
    payload["expected_uncertainty_count"] = spec.uncertainty_count
    payload["expected_hydrated_src_count"] = spec.src_count
    payload["context_hash"] = (metrics or {}).get("sha256") or (
        (payload.get("context_size") or {}).get("sha256")
    )
    payload["other_chapters_excluded"] = True
    payload["ch012_excluded"] = True
    payload["ch018_excluded"] = True
    payload["external_sources_added"] = False
    payload["internet_lookup"] = False
    payload["bible_completed_from_memory"] = False
    payload["context_truncated"] = bool(payload.get("potentially_truncated"))
    payload["secrets_included"] = False
    return payload


__all__ = [
    "build_chapter_context",
    "load_corpus",
    "source_context_manifest",
]
