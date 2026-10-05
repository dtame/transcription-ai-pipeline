"""Canonical volume inventory from the frozen EditorialPlan and SourceMap. Read-only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_generation.evidence import build_chapter_evidence, evidence_metrics
from app.book_generation.hydrate import load_clean_transcript_index
from app.book_generation.identity import load_production_inputs
from app.book_generation_bridge_4b214.constants import PHASE, PROJECT_NAME
from app.book_generation_bridge_4b214.paths import production_transcript_path, repo_root


def canonical_volume_inventory(*, root: Path | None = None) -> dict[str, Any]:
    _ = root or repo_root()
    inputs = load_production_inputs(PROJECT_NAME, require_expected_identity=True)
    plan = inputs.plan
    source_map = inputs.source_map
    language = source_map.primary_language
    transcript_path = production_transcript_path()
    index = load_clean_transcript_index(PROJECT_NAME)
    chapters = []
    evidence_rows = []
    total_sections = 0
    total_ideas = 0
    for chapter in plan.chapters:
        section_count = len(chapter.sections)
        idea_count = len(chapter.idea_refs)
        total_sections += section_count
        total_ideas += idea_count
        bundle = build_chapter_evidence(
            plan,
            source_map,
            chapter,
            language=language,
            hydrate=True,
            transcript_index=index,
        )
        metrics = evidence_metrics(bundle)
        chapters.append(
            {
                "chapter_id": chapter.chapter_id,
                "title": chapter.working_title,
                "section_count": section_count,
                "section_ids": [section.section_id for section in chapter.sections],
                "idea_count": idea_count,
                "source_ref_count": len(chapter.source_refs),
                "paragraph_count": None,
                "paragraph_count_status": "UNKNOWN",
                "paragraph_count_counted_as_zero": False,
                "evidence": {
                    "chars": metrics["chars"],
                    "utf8_bytes": metrics["utf8_bytes"],
                    "idea_count": metrics["idea_count"],
                    "src_ref_count": metrics["src_ref_count"],
                    "hydrated_segment_count": metrics["hydrated_segment_count"],
                    "hydrated_src_chars": metrics["hydrated_src_chars"],
                    "sha256": metrics["sha256"],
                },
            }
        )
        evidence_rows.append(metrics["chars"])
    stats = plan.stats.to_dict()
    source_stats = source_map.stats.to_dict()
    return {
        "phase": PHASE,
        "project_name": plan.project_name,
        "language": language,
        "canonical_language": language,
        "chapters": len(plan.chapters),
        "sections": total_sections,
        "ideas_listed_on_chapters": total_ideas,
        "plan_stats": stats,
        "source_map_stats": source_stats,
        "references_available": source_stats.get("reference_count"),
        "examples_available": source_stats.get("example_count"),
        "source_segments_available": source_stats.get("source_segment_count"),
        "paragraphs_generated": None,
        "paragraphs_status": "UNKNOWN",
        "paragraphs_counted_as_zero": False,
        "semantic_units": None,
        "semantic_units_status": "UNKNOWN",
        "semantic_units_counted_as_zero": False,
        "chapter_rows": chapters,
        "evidence_bundle_chars": {
            "min": min(evidence_rows) if evidence_rows else None,
            "max": max(evidence_rows) if evidence_rows else None,
            "mean": (sum(evidence_rows) / len(evidence_rows)) if evidence_rows else None,
            "status": "measured_from_plan_and_source_map_without_generation",
        },
        "transcript": {
            "path": str(transcript_path).replace("\\", "/"),
            "sha256": index.content_sha256,
            "segment_count": len(index.segments),
            "mutated": False,
        },
        "source_map_path": str(inputs.source_map_path).replace("\\", "/"),
        "editorial_plan_path": str(inputs.plan_path).replace("\\", "/"),
        "source_map_sha256": inputs.source_map_sha256,
        "editorial_plan_sha256": inputs.plan_sha256,
        "does_not_invent_paragraph_counts": True,
        "secrets_included": False,
    }


__all__ = ["canonical_volume_inventory"]
