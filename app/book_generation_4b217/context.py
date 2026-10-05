"""Hydrate CH012 from canonical SourceMap, EditorialPlan, and SRC excerpts."""

from __future__ import annotations

from typing import Any

from app.book_generation.coverage import assigned_idea_ids_for_chapter, chapter_by_id
from app.book_generation.evidence import (
    build_chapter_evidence,
    classify_handle,
    evidence_metrics,
)
from app.book_generation.hydrate import load_clean_transcript_index
from app.book_generation.identity import load_production_inputs
from app.book_generation.language import resolve_canonical_language
from app.book_generation_4b217.constants import (
    EXPECTED_IDEA_COUNT,
    EXPECTED_SECTION_COUNT,
    EXPECTED_SECTION_IDS,
    EXPECTED_TRANSCRIPT,
    EXPECTED_UNCERTAINTY_ID,
    PHASE,
    PROJECT_NAME,
    TARGET_CHAPTER_ID,
    TARGET_CHAPTER_TITLE,
)
from app.book_generation_4b217.guard import BookGeneration4217Error, assert_chapter_allowed
from app.editorial_planning.models import EditorialChapter, EditorialPlan
from app.source_analysis.models import SourceMap


def load_canonical_corpus():
    inputs = load_production_inputs(PROJECT_NAME)
    index = load_clean_transcript_index(PROJECT_NAME)
    if index.content_sha256 != EXPECTED_TRANSCRIPT:
        raise BookGeneration4217Error(
            "Clean transcript SHA-256 mismatch: "
            f"{index.content_sha256} ≠ {EXPECTED_TRANSCRIPT}"
        )
    language = resolve_canonical_language(
        source_map_primary_language=inputs.source_map.primary_language,
        transcript_primary_language=index.primary_language,
    )
    return inputs, index, language


def chapter_from_plan(plan: EditorialPlan) -> EditorialChapter:
    chapter = chapter_by_id(plan, TARGET_CHAPTER_ID)
    assert_chapter_allowed(chapter.chapter_id)
    return chapter


def build_ch012_evidence(
    plan: EditorialPlan,
    source_map: SourceMap,
    chapter: EditorialChapter,
    *,
    language: str,
    transcript_index,
) -> dict[str, Any]:
    evidence = build_chapter_evidence(
        plan,
        source_map,
        chapter,
        language=language,
        hydrate=True,
        transcript_index=transcript_index,
    )
    _assert_isolation(evidence, plan, chapter)
    return evidence


def _assert_isolation(
    evidence: dict[str, Any],
    plan: EditorialPlan,
    chapter: EditorialChapter,
) -> None:
    chapter_id = (evidence.get("chapter") or {}).get("id")
    if chapter_id != TARGET_CHAPTER_ID:
        raise BookGeneration4217Error(f"Evidence chapter is {chapter_id!r}.")
    section_ids = tuple(row.get("id") for row in evidence.get("sections") or [])
    planned = tuple(section.section_id for section in chapter.sections)
    if section_ids != planned:
        raise BookGeneration4217Error(
            f"Section isolation failed: {section_ids} ≠ {planned}"
        )
    if section_ids != EXPECTED_SECTION_IDS:
        raise BookGeneration4217Error(
            f"Expected sections {EXPECTED_SECTION_IDS}, got {section_ids}"
        )
    idea_ids = tuple(row.get("id") for row in evidence.get("ideas") or [])
    planned_ideas = assigned_idea_ids_for_chapter(chapter)
    if set(idea_ids) != set(planned_ideas):
        raise BookGeneration4217Error(
            f"Idea isolation failed: {idea_ids} ≠ {planned_ideas}"
        )
    if len(idea_ids) != EXPECTED_IDEA_COUNT:
        raise BookGeneration4217Error(
            f"Expected {EXPECTED_IDEA_COUNT} ideas, got {len(idea_ids)}"
        )
    other_ids = [item.chapter_id for item in plan.chapters if item.chapter_id != TARGET_CHAPTER_ID]
    leaked = [item for item in other_ids if item in {chapter_id}]
    if leaked:
        raise BookGeneration4217Error(f"Other chapters leaked into evidence: {leaked}")
    src_text = evidence.get("src_text") or []
    if not src_text:
        raise BookGeneration4217Error("No hydrated SRC excerpts for CH012.")
    missing_src = [
        src_id
        for src_id in evidence.get("src") or []
        if not any(item.get("id") == src_id for item in src_text)
    ]
    if missing_src:
        raise BookGeneration4217Error(
            "Mandatory SRC excerpts missing from hydration: "
            + ",".join(missing_src[:12])
        )


def chapter_context_manifest(
    plan: EditorialPlan,
    source_map: SourceMap,
    chapter: EditorialChapter,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    sections = []
    for section in chapter.sections:
        sections.append(
            {
                "section_id": section.section_id,
                "working_title": section.working_title,
                "purpose": section.purpose,
                "idea_ids": list(section.idea_refs),
                "example_ids": list(section.example_refs),
                "reference_ids": list(section.reference_refs),
                "uncertainty_ids": list(section.uncertainty_refs),
                "source_refs": list(section.source_refs),
            }
        )
    return {
        "phase": PHASE,
        "chapter_id": chapter.chapter_id,
        "working_title": chapter.working_title,
        "expected_title": TARGET_CHAPTER_TITLE,
        "purpose": chapter.purpose,
        "language": evidence.get("canonical_document_language"),
        "section_count": len(sections),
        "expected_section_count": EXPECTED_SECTION_COUNT,
        "idea_count": len(evidence.get("ideas") or []),
        "expected_idea_count": EXPECTED_IDEA_COUNT,
        "idea_ids": [row.get("id") for row in evidence.get("ideas") or []],
        "example_ids": [row.get("id") for row in evidence.get("examples") or []],
        "reference_ids": [row.get("id") for row in evidence.get("references") or []],
        "uncertainty_ids": [row.get("id") for row in evidence.get("uncertainties") or []],
        "unc029_present": EXPECTED_UNCERTAINTY_ID
        in {row.get("id") for row in evidence.get("uncertainties") or []},
        "sections": sections,
        "allowed_handles": list(evidence.get("allowed") or []),
        "blocked_handles": list(evidence.get("blocked") or []),
        "other_chapters_excluded": True,
        "whole_transcript_injected": False,
        "external_sources_added": False,
        "internet_lookup": False,
        "bible_completed_from_memory": False,
        "secrets_included": False,
    }


def hydrated_source_manifest(evidence: dict[str, Any]) -> dict[str, Any]:
    src_text = list(evidence.get("src_text") or [])
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "src_ids": list(evidence.get("src") or []),
        "hydrated_count": len(src_text),
        "hydrated": [
            {
                "id": item.get("id"),
                "chars": len(str(item.get("t") or "")),
                "kind": classify_handle(str(item.get("id") or "")),
            }
            for item in src_text
        ],
        "metrics": evidence_metrics(evidence),
        "whole_transcript_sent": False,
        "full_source_map_sent": False,
        "secrets_included": False,
    }


__all__ = [
    "build_ch012_evidence",
    "chapter_context_manifest",
    "chapter_from_plan",
    "hydrated_source_manifest",
    "load_canonical_corpus",
]
