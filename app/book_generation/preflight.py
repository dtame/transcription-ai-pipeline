"""Exact future requests for small / median / large chapters. Not sent."""

from __future__ import annotations

from typing import Any, Sequence

from app.book_generation.budget import measure_request_budget
from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.evidence import build_chapter_evidence, evidence_identity
from app.book_generation.payload import payload_audit
from app.book_generation.settings import GeneratorSettings
from app.editorial_planning.models import EditorialChapter, EditorialPlan
from app.source_analysis.models import SourceMap


def select_representative_chapters(
    plan: EditorialPlan,
    chapter_rows: Sequence[dict[str, Any]],
) -> dict[str, EditorialChapter]:
    by_id = {chapter.chapter_id: chapter for chapter in plan.chapters}
    ranked = sorted(
        chapter_rows,
        key=lambda row: (
            int(row.get("idea_count") or 0),
            int((row.get("evidence") or {}).get("chars") or 0),
            str(row.get("chapter_id") or ""),
        ),
    )
    if not ranked:
        return {}
    smallest = by_id[str(ranked[0]["chapter_id"])]
    largest = by_id[str(ranked[-1]["chapter_id"])]
    median_row = ranked[len(ranked) // 2]
    median_chapter = by_id[str(median_row["chapter_id"])]
    return {
        "smallest": smallest,
        "median": median_chapter,
        "largest": largest,
    }


def audit_request_content(
    evidence: dict[str, Any],
    chapter: EditorialChapter,
    *,
    language: str,
    all_chapter_ids: Sequence[str],
) -> dict[str, Any]:
    section_ids = [row.get("id") for row in evidence.get("sections") or []]
    planned_sections = [section.section_id for section in chapter.sections]
    idea_ids = [row.get("id") for row in evidence.get("ideas") or []]
    planned_ideas = list(assigned_idea_ids_for_chapter(chapter))
    other_ids = [item for item in all_chapter_ids if item != chapter.chapter_id]
    leaked = [
        other
        for other in other_ids
        if any(
            (row.get("id") == other)
            for row in [evidence.get("chapter") or {}]
        )
    ]
    return {
        "chapter_id_match": (evidence.get("chapter") or {}).get("id") == chapter.chapter_id,
        "all_planned_sections": section_ids == planned_sections,
        "all_assigned_ideas": set(idea_ids) == set(planned_ideas),
        "canonical_language": evidence.get("canonical_document_language") == language,
        "voice_present": bool(evidence.get("voice")),
        "allowed_handles_present": bool(evidence.get("allowed")),
        "traceability_src_present": bool(evidence.get("src")),
        "unrelated_chapter_excluded": not leaked,
        "blocked_listed": isinstance(evidence.get("blocked"), list),
        "whole_transcript_sent": False,
        "full_source_map_sent": False,
    }


def build_preflight_request(
    plan: EditorialPlan,
    source_map: SourceMap,
    chapter: EditorialChapter,
    *,
    language: str,
    hydrate: bool,
    transcript_index,
    settings: GeneratorSettings,
) -> dict[str, Any]:
    evidence = build_chapter_evidence(
        plan,
        source_map,
        chapter,
        language=language,
        hydrate=hydrate,
        transcript_index=transcript_index,
    )
    budget = measure_request_budget(
        evidence,
        settings=settings,
        idea_count=len(assigned_idea_ids_for_chapter(chapter)),
        section_count=len(chapter.sections),
    )
    first = payload_audit(
        evidence,
        settings=settings,
        max_output_tokens=budget["recommended_max_output"],
    )
    second = payload_audit(
        evidence,
        settings=settings,
        max_output_tokens=budget["recommended_max_output"],
    )
    content = audit_request_content(
        evidence,
        chapter,
        language=language,
        all_chapter_ids=[item.chapter_id for item in plan.chapters],
    )
    return {
        "chapter_id": chapter.chapter_id,
        "title": chapter.working_title,
        "section_count": len(chapter.sections),
        "idea_count": len(assigned_idea_ids_for_chapter(chapter)),
        "evidence_sha256": evidence_identity(evidence),
        "request_sha256": first["payload_sha256"],
        "request_sha256_repeat": second["payload_sha256"],
        "determinism": first["payload_sha256"] == second["payload_sha256"],
        "content_audit": content,
        "budget": {
            "provider_adjusted_pessimistic": budget["request"]["provider_adjusted_pessimistic"],
            "recommended_max_output": budget["recommended_max_output"],
            "context_utilization_pessimistic": budget["context_utilization_pessimistic"],
            "context_safe": budget["context_safe"],
            "fallback_triggered": budget["fallback_triggered"],
            "generation_unit": budget["generation_unit"],
        },
        "http_sent": False,
    }
