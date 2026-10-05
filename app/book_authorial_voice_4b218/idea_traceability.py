"""Offline IDEA-handle diagnosis. Does not rewrite the provider response."""

from __future__ import annotations

from typing import Any

from app.book_authorial_voice_4b218.chapter_io import iter_paragraphs
from app.book_authorial_voice_4b218.constants import (
    EXPECTED_IDEA_COUNT,
    FAITHFUL_PROMPT_1_0_VERSION,
    FAITHFUL_PROMPT_1_1_VERSION,
    HISTORICAL_PROMPT_V101,
    PHASE,
    TARGET_CHAPTER_ID,
)
from app.book_generation.evidence import classify_handle
from app.book_generation.identity import load_production_inputs
from app.book_generation_4b217.constants import PROJECT_NAME, TARGET_CHAPTER_ID as CH012
from app.book_generation.coverage import assigned_idea_ids_for_chapter, chapter_by_id


def diagnose_idea_traceability(chapter: dict[str, Any]) -> dict[str, Any]:
    paragraph_e: list[str] = []
    paragraph_ideas: list[str] = []
    section_ideas: list[str] = []
    for section in chapter.get("sections") or []:
        section_ideas.extend(section.get("idea_refs") or [])
        for paragraph in section.get("paragraphs") or []:
            paragraph_e.extend(paragraph.get("evidence_handles") or [])
            paragraph_ideas.extend(paragraph.get("idea_refs") or [])
    e_kinds = {}
    for handle in paragraph_e:
        kind = classify_handle(handle)
        e_kinds[kind] = e_kinds.get(kind, 0) + 1
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "provider_response_modified": False,
        "ideas_expected": EXPECTED_IDEA_COUNT,
        "ideas_in_section_metadata": sorted(set(section_ideas)),
        "ideas_in_section_metadata_count": len(set(section_ideas)),
        "ideas_in_paragraph_idea_refs": sorted(set(paragraph_ideas)),
        "ideas_in_paragraph_evidence": [
            handle for handle in paragraph_e if classify_handle(handle) == "IDEA"
        ],
        "paragraph_evidence_kinds": e_kinds,
        "possible_causes": [
            {
                "id": "prompt_1_0_candidate",
                "likely": True,
                "detail": (
                    f"{FAITHFUL_PROMPT_1_0_VERSION} asked for IDEA content in "
                    "the prose 'not merely by its identifier in metadata' and "
                    "did not require IDEA handles in paras[].e. "
                    f"{HISTORICAL_PROMPT_V101} required each assigned IDEA to "
                    "appear via its IDEA handle."
                ),
            },
            {
                "id": "schema_e_accepts_src",
                "likely": True,
                "detail": (
                    "paras[].e accepts any allowed handle. SRC handles satisfy "
                    "the schema and resolve to source_refs. Reconstruct copies "
                    "IDEA refs only from IDEA-classified handles in e."
                ),
            },
            {
                "id": "context_preparation",
                "likely": False,
                "detail": (
                    "The 4B.2.17 evidence bundle included the 11 IDEA ids in "
                    "allowed handles and in section metadata. Preparation did "
                    "not omit IDEA identifiers."
                ),
            },
            {
                "id": "model_compliance_with_1_0",
                "likely": True,
                "detail": (
                    "The model cited SRC handles and preserved UNC029. That "
                    "matches the 1.0-candidate wording more than the historical "
                    "validator contract."
                ),
            },
            {
                "id": "contract_incompatibility",
                "likely": True,
                "detail": (
                    "The production validator still requires planned IDEA "
                    "handles on paragraphs. The 1.0-candidate prompt de-emphasized "
                    "those handles. The 4B.2.17 FAIL on 11/0 ideas is that "
                    "incompatibility, not a missing SourceMap idea."
                ),
            },
        ],
        "primary_diagnosis": (
            "Prompt-validator incompatibility: 1.0-candidate asked for content "
            "representation; the historical output contract still accounts "
            "ideas by handle in paras[].e."
        ),
        "correction_in_1_1": (
            f"{FAITHFUL_PROMPT_1_1_VERSION} asks for IDEA handles in paras[].e "
            "when the correspondence is clear, and forbids invented mappings."
        ),
        "automatic_injection_forbidden": True,
        "identifier_alone_is_not_coverage": True,
        "secrets_included": False,
    }


def propose_idea_mappings(
    chapter: dict[str, Any],
    *,
    source_map=None,
    plan=None,
) -> dict[str, Any]:
    if source_map is None or plan is None:
        inputs = load_production_inputs(PROJECT_NAME)
        source_map = source_map or inputs.source_map
        plan = plan or inputs.plan
    editorial = chapter_by_id(plan, CH012)
    planned = list(assigned_idea_ids_for_chapter(editorial))
    idea_src = {
        item.idea_id: set(item.source_refs)
        for item in source_map.ideas
        if item.idea_id in set(planned)
    }
    proposals = []
    confirmed = []
    unresolved = []
    for idea_id in planned:
        wanted = idea_src.get(idea_id) or set()
        matches = []
        for paragraph_id, row in iter_paragraphs(chapter):
            have = set(row["source_refs"])
            overlap = sorted(wanted.intersection(have))
            if overlap:
                matches.append(
                    {
                        "paragraph_id": paragraph_id,
                        "section_id": row["section_id"],
                        "shared_src": overlap,
                        "idea_src": sorted(wanted),
                        "complete_overlap": wanted.issubset(have),
                    }
                )
        if not matches:
            unresolved.append(idea_id)
            proposals.append(
                {
                    "idea_id": idea_id,
                    "status": "UNRESOLVED",
                    "applied_to_chapter": False,
                    "paragraphs": [],
                    "justification": "No shared SRC with any CH012 paragraph.",
                }
            )
            continue
        proposals.append(
            {
                "idea_id": idea_id,
                "status": "PROPOSED",
                "applied_to_chapter": False,
                "paragraphs": matches,
                "justification": (
                    "Explicit SRC overlap between the SourceMap idea and the "
                    "paragraph source_refs. Not injected into evidence_handles. "
                    "Not a semantic certificate."
                ),
            }
        )
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "ideas_planned": planned,
        "confirmed": confirmed,
        "proposed": [row["idea_id"] for row in proposals if row["status"] == "PROPOSED"],
        "unresolved": unresolved,
        "mappings": proposals,
        "written_into_paragraph_evidence": False,
        "provider_response_modified": False,
        "not_a_coverage_certificate": True,
        "secrets_included": False,
    }


__all__ = ["diagnose_idea_traceability", "propose_idea_mappings"]
