"""Reuse 4B.2.16 coverage control. Do not invent a Terra verdict."""

from __future__ import annotations

from typing import Any

from app.book_authorial_voice_4b218.chapter_io import iter_paragraphs
from app.book_authorial_voice_4b218.constants import (
    COVERAGE_CONTRACT,
    COVERAGE_FLAGGED_UNITS,
    PHASE,
    TARGET_CHAPTER_ID,
)
from app.book_editorial_alignment_4b216.coverage import assess_coverage, content_represented
from app.book_generation.coverage import assigned_idea_ids_for_chapter, chapter_by_id
from app.book_generation.identity import load_production_inputs
from app.book_generation_4b217.constants import PROJECT_NAME
from app.book_generation_4b217.context import (
    build_ch012_evidence,
    chapter_from_plan,
    load_canonical_corpus,
)
from app.book_generation_4b217.coverage import coverage_units


REVIEW_NOTES: dict[str, dict[str, str]] = {
    "IDEA238": {
        "likely": "POSSIBLE_FALSE_NEGATIVE",
        "note": (
            "P000011 quotes 'you're sincere' / 'you're not doing it well' and "
            "keeps correction plus rest. The heuristic summary uses tokens "
            "such as spiritual/practices/incorrectly that the prose does not "
            "repeat. Identifier is already in section metadata."
        ),
    },
    "EX030": {
        "likely": "POSSIBLE_FALSE_NEGATIVE",
        "note": (
            "P000008 now keeps the ground / broken voice / someone-saw "
            "testimony. The example summary also mentions losing strength, "
            "which sits in neighboring SRC004892/894 not cited on the "
            "paragraph. The heuristic can miss a present testimony."
        ),
    },
    "REF037": {
        "likely": "POSSIBLE_FALSE_NEGATIVE",
        "note": (
            "P000005 names Jude and verse 20. The SourceMap raw form is "
            "'Jude vers 20'. French vers versus English verse can fail the "
            "token ratio. Completeness remains partial; do not complete it."
        ),
    },
    "REF038": {
        "likely": "POSSIBLE_FALSE_NEGATIVE",
        "note": (
            "P000004 names 1 Corinthians 14. The SourceMap raw form is "
            "'1 Corinthiens 14'. French/English spelling can fail the "
            "heuristic. Completeness remains partial."
        ),
    },
    "REF043": {
        "likely": "POSSIBLE_FALSE_NEGATIVE",
        "note": (
            "P000013 quotes the beatitude on hunger and thirst for "
            "righteousness. The raw label uses hungering/thirsting, which "
            "may not match hunger/thirst. Completeness remains partial."
        ),
    },
    "UNC029": {
        "likely": "POSSIBLE_FALSE_NEGATIVE",
        "note": (
            "P000004 still states Isaiah 26 verse 3 versus Isaiah 28 and "
            "keeps the connection unclear. UNC029 remains on the paragraph "
            "uncertainty field. The description tokens confused/speech/"
            "belongs need not appear for the reservation to be preserved."
        ),
    },
}


def _prose(chapter: dict[str, Any]) -> str:
    return "\n".join(row["text"] for _pid, row in iter_paragraphs(chapter))


def review_source_coverage(chapter: dict[str, Any]) -> dict[str, Any]:
    inputs, index, language = load_canonical_corpus()
    editorial = chapter_from_plan(inputs.plan)
    evidence = build_ch012_evidence(
        inputs.plan,
        inputs.source_map,
        editorial,
        language=language,
        transcript_index=index,
    )
    units = coverage_units(evidence)
    metadata: list[str] = []
    for section in chapter.get("sections") or []:
        metadata.extend(section.get("idea_refs") or [])
        for paragraph in section.get("paragraphs") or []:
            metadata.extend(paragraph.get("evidence_handles") or [])
            metadata.extend(paragraph.get("idea_refs") or [])
            metadata.extend(paragraph.get("uncertainty_refs") or [])
            metadata.extend(paragraph.get("source_refs") or [])
    prose = _prose(chapter)
    assessed = assess_coverage(units, prose, metadata)
    flagged = []
    for unit_id in COVERAGE_FLAGGED_UNITS:
        match = next((row for row in assessed["units"] if row["id"] == unit_id), None)
        source_unit = next((row for row in units if row["id"] == unit_id), None)
        note = REVIEW_NOTES.get(unit_id) or {}
        flagged.append(
            {
                "id": unit_id,
                "heuristic_status": None if match is None else match.get("status"),
                "content_represented_heuristic": (
                    None if match is None else match.get("content_represented")
                ),
                "identifier_listed_in_metadata": (
                    None if match is None else match.get("identifier_listed_in_metadata")
                ),
                "source_text": None if source_unit is None else source_unit.get("text"),
                "present_in_prose_review": note.get("likely"),
                "note": note.get("note"),
                "heuristic_recomputed": (
                    content_represented(str((source_unit or {}).get("text") or ""), prose)
                    if source_unit
                    else False
                ),
            }
        )
    unc_rows = [row for _pid, row in iter_paragraphs(chapter) if "UNC029" in row["uncertainty_refs"]]
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "contract": COVERAGE_CONTRACT,
        "activated_in_production": False,
        "not_a_terra_verdict": True,
        "semantic_coverage_certified": False,
        "prose_was_not_changed_to_satisfy_the_heuristic": True,
        "heuristic": assessed,
        "flagged_from_4b217": flagged,
        "unc029_cited_on_paragraphs": [row["paragraph_id"] for row in unc_rows],
        "unc029_preserved": bool(unc_rows) and "unclear" in prose.lower(),
        "planned_ideas": list(assigned_idea_ids_for_chapter(editorial)),
        "editorial_chapter_id": chapter_by_id(inputs.plan, TARGET_CHAPTER_ID).chapter_id,
        "secrets_included": False,
    }


__all__ = ["review_source_coverage"]
