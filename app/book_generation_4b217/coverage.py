"""Apply the 4B.2.16 source-coverage candidate to the generated CH012."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_editorial_alignment_4b216.coverage import assess_coverage
from app.book_generation_4b217.constants import (
    COVERAGE_CONTRACT_VERSION,
    PHASE,
    TARGET_CHAPTER_ID,
)


def _prose_from_candidate(candidate) -> str:
    if candidate is None:
        return ""
    chunks = []
    for section in candidate.sections:
        for paragraph in section.paragraphs:
            chunks.append(str(paragraph.text or ""))
    return "\n".join(chunks)


def _metadata_ids(candidate) -> list[str]:
    if candidate is None:
        return []
    ids: list[str] = []
    for section in candidate.sections:
        ids.extend(section.idea_refs)
        for paragraph in section.paragraphs:
            ids.extend(paragraph.evidence_handles)
            ids.extend(paragraph.idea_refs)
            ids.extend(paragraph.example_refs)
            ids.extend(paragraph.reference_refs)
            ids.extend(paragraph.uncertainty_refs)
            ids.extend(paragraph.source_refs)
    return ids


def coverage_units(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for row in evidence.get("ideas") or []:
        units.append({"id": row.get("id"), "kind": "idea", "text": row.get("sum") or ""})
    for row in evidence.get("examples") or []:
        units.append({"id": row.get("id"), "kind": "example", "text": row.get("sum") or ""})
    for row in evidence.get("references") or []:
        units.append(
            {
                "id": row.get("id"),
                "kind": "reference",
                "text": row.get("raw") or row.get("norm") or "",
            }
        )
    for row in evidence.get("uncertainties") or []:
        units.append(
            {
                "id": row.get("id"),
                "kind": "reservation",
                "text": row.get("desc") or "",
            }
        )
    return units


def assess_chapter_coverage(
    *,
    candidate,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    units = coverage_units(evidence)
    prose = _prose_from_candidate(candidate)
    metadata = _metadata_ids(candidate)
    result = assess_coverage(units, prose, metadata)
    result["phase"] = PHASE
    result["chapter_id"] = TARGET_CHAPTER_ID
    result["contract"] = COVERAGE_CONTRACT_VERSION
    result["identifier_coverage"] = {
        "ideas_listed": [row["id"] for row in units if row["kind"] == "idea"],
        "ideas_in_metadata": [
            row["id"]
            for row in result["units"]
            if row["kind"] == "idea" and row["identifier_listed_in_metadata"]
        ],
    }
    result["content_coverage_is_heuristic"] = True
    result["semantic_coverage_certified"] = False
    result["not_a_terra_verdict"] = True
    result["secrets_included"] = False
    return result


__all__ = ["assess_chapter_coverage", "coverage_units"]
