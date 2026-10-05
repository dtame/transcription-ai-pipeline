"""Traceability against canonical artifacts. Missing links are documented, not invented."""

from __future__ import annotations

from typing import Any

from app.book_generation.identity import load_production_inputs
from app.book_generation_bridge_4b214.adapter import (
    adapt_editorial_chapter_without_generation,
    source_map_handle_index,
)
from app.book_generation_bridge_4b214.constants import (
    H01_EVIDENCE_HANDLES,
    PHASE,
    PROJECT_NAME,
    SYNTHETIC_PREFIX,
)
from app.book_generation_bridge_4b214.orchestrator import run_bridge_chapter
from app.book_generation_bridge_4b214.paths import production_transcript_path


def traceability() -> dict[str, Any]:
    inputs = load_production_inputs(PROJECT_NAME, require_expected_identity=True)
    index = source_map_handle_index(inputs.source_map)
    first_chapter = inputs.plan.chapters[0]
    plan_adapt = adapt_editorial_chapter_without_generation(
        inputs.plan,
        inputs.source_map,
        first_chapter.chapter_id,
        identity={
            "source_map_sha256": inputs.source_map_sha256,
            "editorial_plan_sha256": inputs.plan_sha256,
        },
    )
    real_chain_complete = False
    missing_links = [
        "generated_paragraph_text",
        "canonical_paragraph_id",
        "prepared_units_from_generated_text",
        "transcript_SRC_for_generated_paragraph",
    ]
    real_ids_ok = True
    for chapter in inputs.plan.chapters:
        if chapter.chapter_id not in {item.chapter_id for item in inputs.plan.chapters}:
            real_ids_ok = False
        for section in chapter.sections:
            for idea_id in section.idea_refs:
                if idea_id not in index:
                    real_ids_ok = False
            for src in section.source_refs:
                if src not in index:
                    real_ids_ok = False
    fake = run_bridge_chapter(scenario="fully_supported")
    synthetic_chains = []
    for para in fake.get("paragraph_results") or []:
        prepared = dict(para.get("prepared") or {})
        for unit in prepared.get("units") or []:
            synthetic_chains.append(
                {
                    "project": PROJECT_NAME,
                    "chapter_id": para.get("chapter_id"),
                    "section_id": para.get("section_id"),
                    "paragraph_id": para.get("paragraph_id"),
                    "unit_id": unit.get("unit_id"),
                    "evidence_handles": list(para.get("evidence_handles") or []),
                    "synthetic": True,
                    "presented_as_real_src": False,
                }
            )
    transcript_path = str(production_transcript_path()).replace("\\", "/")
    return {
        "phase": PHASE,
        "ok": real_ids_ok and bool(synthetic_chains) and plan_adapt.get("paragraphs_unknown_before_generation"),
        "required_chain": [
            "Project",
            "Chapter",
            "Section",
            "Paragraph",
            "Unit",
            "Evidence",
            "SourceMap",
            "Transcript SRC",
        ],
        "canonical_plan_chapter_id": first_chapter.chapter_id,
        "canonical_section_ids": [section.section_id for section in first_chapter.sections],
        "canonical_idea_ids_resolve_in_source_map": real_ids_ok,
        "generated_paragraphs_exist": False,
        "real_chain_complete": real_chain_complete,
        "missing_links_not_fabricated": missing_links,
        "synthetic_fakeai_chains": synthetic_chains,
        "synthetic_handles_only": all(
            str(handle).startswith(SYNTHETIC_PREFIX)
            for item in synthetic_chains
            for handle in item.get("evidence_handles") or []
        ),
        "historical_h01_handles": list(H01_EVIDENCE_HANDLES),
        "historical_h01_not_used_as_generated_chapter": True,
        "transcript_path": transcript_path,
        "source_map_sha256": inputs.source_map_sha256,
        "editorial_plan_sha256": inputs.plan_sha256,
        "does_not_fabricate_missing_links": True,
        "secrets_included": False,
    }


__all__ = ["traceability"]
