"""Preparatory editorial reading review. Not a semantic certificate."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.book_generation_4b221.constants import (
    PHASE,
    REVIEW_NO_ISSUE,
    REVIEW_POTENTIAL,
    REVIEW_RECOMMENDED,
    REVIEW_UNDETERMINED,
    TARGET_CHAPTER_ID,
)

_EXTERNAL_FRAME = re.compile(
    r"\b("
    r"the speaker explained|the speaker recounted|he told the audience|"
    r"the speaker said|the preacher said|the author recalled|"
    r"the speaker emphasized|the preacher described|according to the speaker|"
    r"the speaker taught|he taught that"
    r")\b",
    re.IGNORECASE,
)
_FIRST_PERSON = re.compile(r"\b(I|me|my|mine|we|our|ours)\b")
_SECOND_PERSON = re.compile(r"\b(you|your|yours)\b", re.IGNORECASE)
_CAUSAL = re.compile(
    r"\b(necessarily proves|this proves that|this means that every|"
    r"guarantees that|the cause of every|therefore it follows that)\b",
    re.IGNORECASE,
)
_STRENGTHENED = re.compile(
    r"\b(always|never|must always|the only way|it is certain that)\b",
    re.IGNORECASE,
)
_TECHNICAL = re.compile(r"\b(?:SRC|IDEA|SEC|CH|P)\d{2,}\b")


def _classify(code: str) -> str:
    if code in {"ADDED_CAUSALITY", "STRENGTHENED_CLAIM", "POSSIBLE_OMISSION"}:
        return REVIEW_POTENTIAL
    if code in {"CONFERENCE_REPORT_FRAME", "TECHNICAL_IDENTIFIER_IN_PROSE"}:
        return REVIEW_RECOMMENDED
    if code in {"ATTRIBUTION_UNCERTAIN"}:
        return REVIEW_UNDETERMINED
    return REVIEW_RECOMMENDED


def editorial_readiness_review(
    *,
    candidate,
    chapter,
    structural: Mapping[str, Any],
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    paragraphs: list[dict[str, Any]] = []
    if candidate is not None:
        for section in candidate.sections:
            for paragraph in section.paragraphs:
                paragraphs.append(
                    {
                        "paragraph_id": paragraph.paragraph_id,
                        "section_id": section.section_id,
                        "text": str(paragraph.text or ""),
                    }
                )
    text = "\n".join(row["text"] for row in paragraphs)
    first_person = bool(_FIRST_PERSON.search(text))
    second_person = bool(_SECOND_PERSON.search(text))
    frames = sorted({match.group(0) for match in _EXTERNAL_FRAME.finditer(text)})
    if frames:
        observations.append(
            {
                "code": "CONFERENCE_REPORT_FRAME",
                "classification": _classify("CONFERENCE_REPORT_FRAME"),
                "detail": "Conference-report phrasing may designate the main author: "
                + "; ".join(frames),
            }
        )
    if _CAUSAL.search(text):
        observations.append(
            {
                "code": "ADDED_CAUSALITY",
                "classification": _classify("ADDED_CAUSALITY"),
                "detail": "A transition may introduce necessity, proof, or guarantee.",
            }
        )
    if _STRENGTHENED.search(text):
        observations.append(
            {
                "code": "STRENGTHENED_CLAIM",
                "classification": _classify("STRENGTHENED_CLAIM"),
                "detail": "Absolute wording may strengthen a source claim.",
            }
        )
    if _TECHNICAL.search(text):
        observations.append(
            {
                "code": "TECHNICAL_IDENTIFIER_IN_PROSE",
                "classification": _classify("TECHNICAL_IDENTIFIER_IN_PROSE"),
                "detail": "A SourceMap or plan identifier appears in manuscript prose.",
            }
        )
    missing = list((structural.get("checks") or {}).get("ideas_missing_from_paras_e") or [])
    if missing:
        observations.append(
            {
                "code": "POSSIBLE_OMISSION",
                "classification": _classify("POSSIBLE_OMISSION"),
                "detail": "Planned IDEA handles are absent from paras[].e: "
                + ",".join(missing)
                + ". Handle absence is not repaired automatically.",
            }
        )
    if candidate is None:
        observations.append(
            {
                "code": "NO_CANDIDATE",
                "classification": REVIEW_UNDETERMINED,
                "detail": "No chapter candidate is available for editorial reading.",
            }
        )
    if not observations:
        observations.append(
            {
                "code": "PREPARATORY_READING_ONLY",
                "classification": REVIEW_NO_ISSUE,
                "detail": (
                    "No deterministic conference-report, causality, or identifier "
                    "anomaly was flagged. This is not a fidelity certificate."
                ),
            }
        )
    ranks = {
        REVIEW_POTENTIAL: 3,
        REVIEW_UNDETERMINED: 2,
        REVIEW_RECOMMENDED: 1,
        REVIEW_NO_ISSUE: 0,
    }
    overall = max(
        (row.get("classification") or REVIEW_UNDETERMINED for row in observations),
        key=lambda item: ranks.get(item, 0),
    )
    titles = []
    if chapter is not None:
        titles = [section.working_title for section in chapter.sections]
    potential = [
        row for row in observations if row.get("classification") == REVIEW_POTENTIAL
    ]
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "overall_classification": overall,
        "readability": (
            f"{len(paragraphs)} paragraphs across "
            f"{len(getattr(candidate, 'sections', []) or [])} sections. "
            "Offline readability only."
        ),
        "section_organization": titles,
        "authorial_voice": {
            "first_person_observed": first_person,
            "second_person_observed": second_person,
            "conference_report_frames": frames,
            "classification": (
                REVIEW_RECOMMENDED if frames else REVIEW_NO_ISSUE
                if candidate is not None
                else REVIEW_UNDETERMINED
            ),
        },
        "testimonies": REVIEW_UNDETERMINED,
        "references": REVIEW_UNDETERMINED,
        "transitions": REVIEW_RECOMMENDED if any(
            row.get("code") == "ADDED_CAUSALITY" for row in observations
        ) else REVIEW_NO_ISSUE,
        "repetitions": REVIEW_UNDETERMINED,
        "observations": observations,
        "potential_substantive_issues": potential,
        "semantic_certification": "NOT PERFORMED",
        "automatic_correction": False,
        "terra_used": False,
        "human_acceptance": "PENDING",
        "secrets_included": False,
    }


__all__ = ["editorial_readiness_review"]
