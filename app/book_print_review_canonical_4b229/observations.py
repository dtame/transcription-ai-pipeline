"""Preserve 4B.2.28 editorial observations by reference. Do not resolve them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.book_print_review_canonical_4b229.constants import (
    EXPECTED_CONTINUITY_OBSERVATIONS,
    EXPECTED_REFERENCE_OBSERVATIONS,
    EXPECTED_STRENGTHENED_OBSERVATIONS,
    OBSERVATION_CONTINUITY_REL,
    OBSERVATION_EDITORIAL_REL,
    OBSERVATION_REFERENCES_REL,
    OBSERVATION_REPORT_REL,
    OBSERVATION_STRENGTHENED_REL,
    PHASE,
    STRENGTHENED_CLAIM_CHAPTER_IDS,
)
from app.book_print_review_canonical_4b229.guard import BookPrintReviewCanonical4229Error
from app.book_print_review_canonical_4b229.paths import historical_rel


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BookPrintReviewCanonical4229Error(f"Editorial observation file missing: {path}. STOP.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BookPrintReviewCanonical4229Error(f"Editorial observation file is not an object: {path}.")
    return payload


def load_editorial_observations(*, root: Path | None = None) -> dict[str, Any]:
    strengthened_path = historical_rel(OBSERVATION_STRENGTHENED_REL, root=root)
    references_path = historical_rel(OBSERVATION_REFERENCES_REL, root=root)
    continuity_path = historical_rel(OBSERVATION_CONTINUITY_REL, root=root)
    editorial_path = historical_rel(OBSERVATION_EDITORIAL_REL, root=root)
    report_path = historical_rel(OBSERVATION_REPORT_REL, root=root)
    strengthened = _load(strengthened_path)
    references = _load(references_path)
    continuity = _load(continuity_path)
    editorial = _load(editorial_path)
    historical = list(references.get("historical_observations") or [])
    similar = list(references.get("similar_observations_in_new_chapters") or [])
    reference_count = len(historical) + len(similar)
    strengthened_count = int(
        strengthened.get("observation_count")
        or len(strengthened.get("observations") or [])
    )
    continuity_count = int(
        continuity.get("observation_count")
        or len(continuity.get("observations") or [])
    )
    if strengthened_count != EXPECTED_STRENGTHENED_OBSERVATIONS:
        raise BookPrintReviewCanonical4229Error(
            f"Strengthened observations {strengthened_count} ≠ "
            f"{EXPECTED_STRENGTHENED_OBSERVATIONS}. STOP."
        )
    if reference_count != EXPECTED_REFERENCE_OBSERVATIONS:
        raise BookPrintReviewCanonical4229Error(
            f"Reference/example observations {reference_count} ≠ "
            f"{EXPECTED_REFERENCE_OBSERVATIONS}. STOP."
        )
    if continuity_count != EXPECTED_CONTINUITY_OBSERVATIONS:
        raise BookPrintReviewCanonical4229Error(
            f"Continuity observations {continuity_count} ≠ "
            f"{EXPECTED_CONTINUITY_OBSERVATIONS}. STOP."
        )
    chapters = list(strengthened.get("chapter_ids") or STRENGTHENED_CLAIM_CHAPTER_IDS)
    if not chapters:
        chapters = list(STRENGTHENED_CLAIM_CHAPTER_IDS)
    return {
        "phase": PHASE,
        "preserved": True,
        "interpreted_as_confirmed_errors": False,
        "texts_modified_to_resolve_them": False,
        "strengthened_formulations": {
            "count": strengthened_count,
            "chapter_ids": list(STRENGTHENED_CLAIM_CHAPTER_IDS),
            "path": str(strengthened_path).replace("\\", "/"),
        },
        "references_and_examples": {
            "count": reference_count,
            "historical_count": len(historical),
            "similar_count": len(similar),
            "path": str(references_path).replace("\\", "/"),
        },
        "continuity": {
            "count": continuity_count,
            "path": str(continuity_path).replace("\\", "/"),
        },
        "audit_links": [
            str(strengthened_path).replace("\\", "/"),
            str(references_path).replace("\\", "/"),
            str(continuity_path).replace("\\", "/"),
            str(editorial_path).replace("\\", "/"),
            str(report_path).replace("\\", "/"),
        ],
        "editorial_summary_path": str(editorial_path).replace("\\", "/"),
        "phase_4b228_report_path": str(report_path).replace("\\", "/"),
        "secrets_included": False,
    }


__all__ = ["load_editorial_observations"]
