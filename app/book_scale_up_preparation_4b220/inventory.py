"""Inventory the 18 remaining EditorialPlan chapters. Coverage is not assumed."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.book_generation.budget import estimate_manuscript_output
from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.evidence import collect_unit_src_ids
from app.book_scale_up_preparation_4b220.constants import (
    ACCEPTED_CHAPTER,
    PHASE,
    REMAINING_CHAPTER_COUNT,
    STATUS_ACCEPTED,
    STATUS_PENDING,
)
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus
from app.book_scale_up_preparation_4b220.guard import BookScaleUpPreparation4220Error
from app.editorial_planning.models import EditorialChapter, EditorialPlan
from app.source_analysis.models import SourceMap


def _unique(values) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if item))


def chapter_support_ids(chapter: EditorialChapter) -> dict[str, list[str]]:
    examples: list[str] = []
    references: list[str] = []
    uncertainties: list[str] = list(chapter.uncertainty_refs)
    extra_src: list[str] = list(chapter.source_refs)
    for section in chapter.sections:
        examples.extend(section.example_refs)
        references.extend(section.reference_refs)
        uncertainties.extend(section.uncertainty_refs)
        extra_src.extend(section.source_refs)
    return {
        "example_ids": _unique(examples),
        "reference_ids": _unique(references),
        "uncertainty_ids": _unique(uncertainties),
        "section_source_refs": _unique(extra_src),
    }


def chapter_src_ids(
    source_map: SourceMap, chapter: EditorialChapter, idea_ids: tuple[str, ...]
) -> tuple[str, ...]:
    support = chapter_support_ids(chapter)
    return collect_unit_src_ids(
        source_map,
        idea_ids=idea_ids,
        extra_src=support["section_source_refs"],
        example_ids=support["example_ids"],
        reference_ids=support["reference_ids"],
        uncertainty_ids=support["uncertainty_ids"],
    )


def editorial_complexity(
    *,
    idea_count: int,
    section_count: int,
    src_count: int,
    chapter_id: str,
) -> str:
    if idea_count >= 24 or section_count >= 8 or chapter_id == "CH016":
        return "HIGH"
    if idea_count >= 16 or section_count >= 5 or src_count >= 90:
        return "MEDIUM"
    return "LOW"


def coverage_risks(
    *,
    idea_count: int,
    src_count: int,
    section_count: int,
    audio_count: int,
    example_count: int,
    reference_count: int,
) -> list[str]:
    risks = [
        "planned_presence_is_not_generated_coverage",
        "section_or_idea_appearance_in_plan_is_not_proof_of_restatement",
    ]
    if idea_count >= 20:
        risks.append("high_idea_volume")
    if src_count >= 100:
        risks.append("large_src_set")
    if section_count == 1:
        risks.append("single_section_compression")
    if audio_count >= 2:
        risks.append("cross_recording_thematic_grouping")
    if example_count == 0 and reference_count == 0:
        risks.append("few_support_units_to_trace")
    return risks


def narrative_risks(
    chapter: EditorialChapter,
    *,
    example_kinds: list[str],
    uncertainty_count: int,
) -> list[str]:
    title = chapter.working_title.lower()
    risks: list[str] = []
    if any(kind == "testimony" for kind in example_kinds):
        risks.append("testimony_attribution")
    if chapter.chapter_id == "CH001":
        risks.append("identity_unlearning_address")
    if chapter.chapter_id == "CH016":
        risks.append("death_as_gain_sensitive_register")
    if uncertainty_count:
        risks.append("uncertainty_preservation")
    if "you" in title.split() or "your" in title.split():
        risks.append("direct_second_person_address")
    if not risks:
        risks.append("standard_authorial_voice")
    return risks


def inventory_row(
    chapter: EditorialChapter,
    *,
    book_order: int,
    source_map: SourceMap,
    transcript,
) -> dict[str, Any]:
    idea_ids = assigned_idea_ids_for_chapter(chapter)
    support = chapter_support_ids(chapter)
    src_ids = chapter_src_ids(source_map, chapter, idea_ids)
    lookup = transcript.by_src()
    whole_transcript_words = sum(len(segment.text.split()) for segment in transcript.segments)
    audio = Counter()
    src_words = 0
    src_chars = 0
    missing_src = []
    for src_id in src_ids:
        segment = lookup.get(src_id)
        if segment is None:
            missing_src.append(src_id)
            continue
        audio[segment.source_id] += 1
        src_words += len(segment.text.split())
        src_chars += len(segment.text)
    examples_by_id = {item.example_id: item for item in source_map.examples}
    example_kinds = [
        str(getattr(examples_by_id.get(example_id), "kind", "") or "")
        for example_id in support["example_ids"]
    ]
    output = estimate_manuscript_output(len(idea_ids), len(chapter.sections))
    complexity = editorial_complexity(
        idea_count=len(idea_ids),
        section_count=len(chapter.sections),
        src_count=len(src_ids),
        chapter_id=chapter.chapter_id,
    )
    return {
        "chapter_id": chapter.chapter_id,
        "working_title": chapter.working_title,
        "book_order": book_order,
        "section_count": len(chapter.sections),
        "section_ids": [section.section_id for section in chapter.sections],
        "idea_count": len(idea_ids),
        "idea_ids": list(idea_ids),
        "example_count": len(support["example_ids"]),
        "example_ids": support["example_ids"],
        "example_kinds": example_kinds,
        "reference_count": len(support["reference_ids"]),
        "reference_ids": support["reference_ids"],
        "uncertainty_count": len(support["uncertainty_ids"]),
        "uncertainty_ids": support["uncertainty_ids"],
        "src_count": len(src_ids),
        "src_ids": list(src_ids),
        "missing_src_ids": missing_src,
        "audio_distribution": dict(audio),
        "audio_file_count": len(audio),
        "estimated_source_context": {
            "hydrated_src_words": src_words,
            "hydrated_src_chars": src_chars,
            "whole_transcript_words_not_injected": whole_transcript_words,
            "targeted_hydration_only": True,
        },
        "estimated_output_tokens": {
            "expected": output["expected_output_tokens"],
            "conservative": output["conservative_output_tokens"],
        },
        "editorial_complexity": complexity,
        "coverage_risks": coverage_risks(
            idea_count=len(idea_ids),
            src_count=len(src_ids),
            section_count=len(chapter.sections),
            audio_count=len(audio),
            example_count=len(support["example_ids"]),
            reference_count=len(support["reference_ids"]),
        ),
        "narrative_attribution_risks": narrative_risks(
            chapter,
            example_kinds=example_kinds,
            uncertainty_count=len(support["uncertainty_ids"]),
        ),
        "generation_status": STATUS_PENDING,
        "validation_status": "NOT_STARTED",
        "planned_is_not_covered": True,
        "secrets_included": False,
    }


def remaining_chapters(
    plan: EditorialPlan,
    source_map: SourceMap,
    transcript,
    *,
    exclude_chapter_id: str = ACCEPTED_CHAPTER,
) -> list[dict[str, Any]]:
    rows = []
    for index, chapter in enumerate(plan.chapters, start=1):
        if chapter.chapter_id == exclude_chapter_id:
            continue
        rows.append(
            inventory_row(
                chapter,
                book_order=index,
                source_map=source_map,
                transcript=transcript,
            )
        )
    return rows


def remaining_chapters_inventory(
    corpus: CanonicalCorpus | None = None,
) -> dict[str, Any]:
    corpus = corpus or load_canonical_corpus()
    rows = remaining_chapters(corpus.plan, corpus.source_map, corpus.transcript)
    ids = [row["chapter_id"] for row in rows]
    accepted_in_queue = ACCEPTED_CHAPTER in ids
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    book_order = [row["book_order"] for row in rows]
    if len(rows) != REMAINING_CHAPTER_COUNT:
        raise BookScaleUpPreparation4220Error(
            f"Remaining inventory has {len(rows)} chapters, expected "
            f"{REMAINING_CHAPTER_COUNT}."
        )
    if accepted_in_queue:
        raise BookScaleUpPreparation4220Error(
            f"{ACCEPTED_CHAPTER} must be excluded from the generation queue."
        )
    if duplicates:
        raise BookScaleUpPreparation4220Error(
            f"Duplicate remaining chapter IDs: {duplicates}"
        )
    if book_order != sorted(book_order):
        raise BookScaleUpPreparation4220Error("Remaining chapters are not in book order.")
    return {
        "phase": PHASE,
        "accepted_chapter_excluded": ACCEPTED_CHAPTER,
        "accepted_chapter_generation_status": STATUS_ACCEPTED,
        "accepted_chapter_validation_status": (
            "EDITORIAL_ACCEPTED_NOT_SEMANTICALLY_CERTIFIED"
        ),
        "remaining_chapter_count": len(rows),
        "expected_remaining_chapter_count": REMAINING_CHAPTER_COUNT,
        "duplicate_ids": duplicates,
        "book_order_preserved": True,
        "total_remaining_sections": sum(row["section_count"] for row in rows),
        "total_remaining_ideas": sum(row["idea_count"] for row in rows),
        "total_remaining_examples": sum(row["example_count"] for row in rows),
        "total_remaining_references": sum(row["reference_count"] for row in rows),
        "total_remaining_uncertainties": sum(row["uncertainty_count"] for row in rows),
        "chapters": rows,
        "coverage_not_inferred_from_plan": True,
        "secrets_included": False,
    }


__all__ = [
    "chapter_src_ids",
    "chapter_support_ids",
    "inventory_row",
    "remaining_chapters",
    "remaining_chapters_inventory",
]
