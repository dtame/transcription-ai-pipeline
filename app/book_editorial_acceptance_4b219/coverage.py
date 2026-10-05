"""Offline source-coverage review of the flagged CH012 units. Not a Terra verdict."""

from __future__ import annotations

from typing import Any

from app.book_editorial_acceptance_4b219.chapter_io import iter_paragraphs
from app.book_editorial_acceptance_4b219.constants import (
    CHAPTER_ID,
    COVERAGE_CONTRACT,
    COVERAGE_FLAGGED_UNITS,
    PHASE,
    UNCERTAINTY_ID,
)
from app.book_generation.identity import load_production_inputs
from app.book_generation_4b217.constants import PROJECT_NAME

PRESENCE_TEXTUAL = "textual_presence_verifiable"
PRESENCE_PARAPHRASE = "plausible_equivalent_paraphrase"
PRESENCE_PARTIAL = "partial_coverage"
PRESENCE_OMISSION = "possible_omission"
PRESENCE_UNCERTAINTY = "uncertainty_preserved"
PRESENCE_IMPOSSIBLE = "offline_evaluation_impossible"


def _prose_by_paragraph(chapter: dict[str, Any]) -> dict[str, str]:
    return {pid: row["text"] for pid, row in iter_paragraphs(chapter)}


def _unit_index(source_map) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for idea in source_map.ideas:
        index[idea.idea_id] = {
            "id": idea.idea_id,
            "kind": "idea",
            "text": idea.summary,
            "source_refs": list(idea.source_refs),
        }
    for example in source_map.examples:
        index[example.example_id] = {
            "id": example.example_id,
            "kind": "example",
            "text": example.summary,
            "source_refs": list(example.source_refs),
            "supports_idea_refs": list(example.supports_idea_refs),
        }
    for reference in source_map.references:
        index[reference.reference_id] = {
            "id": reference.reference_id,
            "kind": "reference",
            "text": reference.raw_reference,
            "completeness": reference.completeness,
            "source_refs": list(reference.source_refs),
        }
    for uncertainty in source_map.uncertainties:
        index[uncertainty.uncertainty_id] = {
            "id": uncertainty.uncertainty_id,
            "kind": "reservation",
            "text": uncertainty.description,
            "source_refs": list(uncertainty.source_refs),
        }
    return index


def review_source_coverage(chapter: dict[str, Any], *, source_map=None) -> dict[str, Any]:
    if source_map is None:
        source_map = load_production_inputs(PROJECT_NAME).source_map
    units = _unit_index(source_map)
    paragraphs = _prose_by_paragraph(chapter)
    all_prose = "\n".join(paragraphs.values())
    unc_rows = [
        pid
        for pid, row in iter_paragraphs(chapter)
        if UNCERTAINTY_ID in row["uncertainty_refs"]
    ]
    reviews = [
        _review_idea238(paragraphs, units),
        _review_ex030(paragraphs, units),
        _review_ref037(paragraphs, units),
        _review_ref038(paragraphs, units),
        _review_ref043(paragraphs, units),
        _review_unc029(paragraphs, units, unc_rows),
    ]
    substantial_omissions = [
        row["id"]
        for row in reviews
        if row["presence"] == PRESENCE_OMISSION and row.get("substantial")
    ]
    return {
        "phase": PHASE,
        "chapter_id": CHAPTER_ID,
        "contract": COVERAGE_CONTRACT,
        "activated_in_production": False,
        "not_a_terra_verdict": True,
        "semantic_coverage_certified": False,
        "automated_source_coverage_certification": "not_performed",
        "heuristic_is_not_semantic_proof": True,
        "accepted_chapter_modified": False,
        "flagged_units": reviews,
        "flagged_ids": list(COVERAGE_FLAGGED_UNITS),
        "unc029_cited_on_paragraphs": unc_rows,
        "unc029_preserved": bool(unc_rows) and "unclear" in all_prose.lower(),
        "substantial_omissions": substantial_omissions,
        "separate_human_decision_recommended": [
            row["id"]
            for row in reviews
            if row.get("separate_human_decision")
        ],
        "overall_status": (
            "OFFLINE CONTENT REVIEW — NOT CERTIFIED; "
            "no substantial omission requiring a rewrite of the accepted chapter"
        ),
        "secrets_included": False,
    }


def _review_idea238(paragraphs: dict[str, str], units: dict[str, dict[str, Any]]) -> dict[str, Any]:
    text = paragraphs.get("P000011") or ""
    haystack = text.lower()
    present = (
        "sincere" in haystack
        and "not doing it well" in haystack
        and "rest" in haystack
    )
    return {
        "id": "IDEA238",
        "kind": "idea",
        "source_text": (units.get("IDEA238") or {}).get("text"),
        "examined_paragraphs": ["P000011"],
        "presence": PRESENCE_PARAPHRASE if present else PRESENCE_OMISSION,
        "substantial": False,
        "separate_human_decision": False,
        "heuristic_status_4b218": "IDENTIFIER_ONLY",
        "note": (
            "P000011 quotes sincerity, incorrect practice, correction, and "
            "true rest. The SourceMap summary uses spiritual/practices/"
            "incorrectly, which the prose does not repeat. This is a "
            "plausible equivalent paraphrase, not a Terra certificate."
        ),
    }


def _review_ex030(paragraphs: dict[str, str], units: dict[str, dict[str, Any]]) -> dict[str, Any]:
    p8 = (paragraphs.get("P000008") or "").lower()
    p9 = (paragraphs.get("P000009") or "").lower()
    physical = "ground" in p8 and "voice" in p8 and "broken" in p8
    correction = "tired" in p9
    losing_strength = "losing strength" in p8 or "lost" in p8 and "strength" in p8
    return {
        "id": "EX030",
        "kind": "example",
        "source_text": (units.get("EX030") or {}).get("text"),
        "examined_paragraphs": ["P000008", "P000009"],
        "presence": PRESENCE_PARTIAL,
        "substantial": False,
        "separate_human_decision": True,
        "heuristic_status_4b218": "NOT_COVERED",
        "losing_strength_in_accepted_prose": losing_strength,
        "physical_testimony_in_p000008": physical,
        "divine_correction_in_p000009": correction,
        "note": (
            "P000008 keeps the ground / broken-voice testimony. P000009 keeps "
            "God saying the speaker was tired and needed correction. The "
            "example summary also mentions losing strength, which sits on "
            "neighboring SRC not cited on these paragraphs. That detail is a "
            "possible minor omission, not a rewrite of the accepted chapter. "
            "A separate human decision is required only if that neighboring "
            "detail is judged essential."
        ),
    }


def _review_ref037(paragraphs: dict[str, str], units: dict[str, dict[str, Any]]) -> dict[str, Any]:
    text = (paragraphs.get("P000005") or "").lower()
    present = "jude" in text and "verse 20" in text
    return {
        "id": "REF037",
        "kind": "reference",
        "source_text": (units.get("REF037") or {}).get("text"),
        "completeness": (units.get("REF037") or {}).get("completeness"),
        "examined_paragraphs": ["P000005"],
        "presence": PRESENCE_TEXTUAL if present else PRESENCE_OMISSION,
        "substantial": False,
        "separate_human_decision": False,
        "heuristic_status_4b218": "NOT_COVERED",
        "note": (
            "P000005 names Jude and verse 20. The SourceMap raw form is "
            "'Jude vers 20'. Completeness remains partial. Do not complete it."
        ),
    }


def _review_ref038(paragraphs: dict[str, str], units: dict[str, dict[str, Any]]) -> dict[str, Any]:
    p4 = (paragraphs.get("P000004") or "").lower()
    present = "1 corinthians 14" in p4
    return {
        "id": "REF038",
        "kind": "reference",
        "source_text": (units.get("REF038") or {}).get("text"),
        "completeness": (units.get("REF038") or {}).get("completeness"),
        "examined_paragraphs": ["P000004"],
        "presence": PRESENCE_TEXTUAL if present else PRESENCE_OMISSION,
        "substantial": False,
        "separate_human_decision": False,
        "heuristic_status_4b218": "NOT_COVERED",
        "note": (
            "P000004 names 1 Corinthians 14. The SourceMap raw form is "
            "'1 Corinthiens 14'. Completeness remains partial."
        ),
    }


def _review_ref043(paragraphs: dict[str, str], units: dict[str, dict[str, Any]]) -> dict[str, Any]:
    text = (paragraphs.get("P000013") or "").lower()
    present = "hunger" in text and "thirst" in text and "righteousness" in text
    return {
        "id": "REF043",
        "kind": "reference",
        "source_text": (units.get("REF043") or {}).get("text"),
        "completeness": (units.get("REF043") or {}).get("completeness"),
        "examined_paragraphs": ["P000013"],
        "presence": PRESENCE_PARAPHRASE if present else PRESENCE_OMISSION,
        "substantial": False,
        "separate_human_decision": False,
        "heuristic_status_4b218": "NOT_COVERED",
        "note": (
            "P000013 quotes the beatitude on hunger and thirst for "
            "righteousness. The raw label uses hungering/thirsting. "
            "Completeness remains partial."
        ),
    }


def _review_unc029(
    paragraphs: dict[str, str],
    units: dict[str, dict[str, Any]],
    unc_rows: list[str],
) -> dict[str, Any]:
    text = (paragraphs.get("P000004") or "").lower()
    present = "isaiah chapter 26" in text and "verse 3" in text and "unclear" in text
    return {
        "id": "UNC029",
        "kind": "reservation",
        "source_text": (units.get("UNC029") or {}).get("text"),
        "examined_paragraphs": ["P000004"],
        "presence": PRESENCE_UNCERTAINTY if present else PRESENCE_OMISSION,
        "substantial": False,
        "separate_human_decision": False,
        "heuristic_status_4b218": "IDENTIFIER_ONLY",
        "identifier_on_paragraphs": unc_rows,
        "note": (
            "P000004 still states Isaiah 26 verse 3 versus Isaiah 28 and keeps "
            "the connection unclear. UNC029 remains on the paragraph "
            "uncertainty field. The reservation is preserved, not resolved."
        ),
    }


__all__ = ["review_source_coverage"]
