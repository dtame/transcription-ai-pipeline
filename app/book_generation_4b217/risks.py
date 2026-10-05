"""Offline editorial risk flags. Not a semantic verdict."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.book_generation_4b217.constants import (
    EXPECTED_UNCERTAINTY_ID,
    PHASE,
    TARGET_CHAPTER_ID,
)

_CAUSAL = re.compile(
    r"\b(necessarily proves|this proves that|this means that every|"
    r"guarantees that|the cause of every)\b",
    re.IGNORECASE,
)
_TECHNICAL = re.compile(r"\b(?:SRC|IDEA|SEC|CH|P)\d{2,}\b")
_ISAIAH_RESOLVED = re.compile(
    r"isaiah\s+2[68]\s*:\s*3\b(?![^.]{0,80}(?:or|versus|unclear|uncertain))",
    re.IGNORECASE,
)


def editorial_risk_flags(
    *,
    candidate,
    evidence: Mapping[str, Any],
    coverage: Mapping[str, Any],
) -> dict[str, Any]:
    flags: list[dict[str, Any]] = []
    prose = []
    if candidate is not None:
        for section in candidate.sections:
            for paragraph in section.paragraphs:
                prose.append(str(paragraph.text or ""))
    text = "\n".join(prose)
    if _CAUSAL.search(text):
        flags.append(
            {
                "code": "INTERPRETIVE_TRANSITION",
                "severity": "review",
                "detail": "A transition may introduce necessity, proof, or guarantee.",
            }
        )
    if _TECHNICAL.search(text):
        flags.append(
            {
                "code": "TECHNICAL_IDENTIFIER_IN_PROSE",
                "severity": "review",
                "detail": "A SourceMap or plan identifier appears in manuscript prose.",
            }
        )
    unc_ids = {row.get("id") for row in evidence.get("uncertainties") or []}
    if EXPECTED_UNCERTAINTY_ID in unc_ids:
        cited = False
        if candidate is not None:
            for section in candidate.sections:
                for paragraph in section.paragraphs:
                    if EXPECTED_UNCERTAINTY_ID in paragraph.uncertainty_refs:
                        cited = True
        if not cited:
            flags.append(
                {
                    "code": "UNC029_NOT_CITED",
                    "severity": "elevated",
                    "detail": "UNC029 must remain an uncertainty, not a resolved reference.",
                }
            )
        if _ISAIAH_RESOLVED.search(text) and "or" not in text.lower():
            flags.append(
                {
                    "code": "UNC029_POSSIBLY_RESOLVED",
                    "severity": "elevated",
                    "detail": "Isaiah 26/28 may have been resolved without justification.",
                }
            )
    missing = list(coverage.get("important_missing") or [])
    if missing:
        flags.append(
            {
                "code": "COVERAGE_HEURISTIC_GAP",
                "severity": "review",
                "detail": "Offline heuristic did not represent: " + ",".join(missing),
                "ids": missing,
            }
        )
    flags.append(
        {
            "code": "THEMATIC_REGROUP_ACROSS_RECORDINGS",
            "severity": "observation",
            "authorized": True,
            "detail": "AUDIO003 and AUDIO004 material is grouped by the EditorialPlan.",
        }
    )
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "flags": flags,
        "semantic_fidelity_validated": False,
        "not_a_terra_verdict": True,
        "secrets_included": False,
    }


__all__ = ["editorial_risk_flags"]
