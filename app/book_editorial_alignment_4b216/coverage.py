"""
Candidate source-coverage control.

A unit is covered only when its content is represented in the prose.
An identifier in metadata is not coverage.
This control is not activated in production and is not a Terra verdict.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from app.book_editorial_alignment_4b216.constants import (
    COVERAGE_CONTRACT_VERSION,
    COVERAGE_CONTROL_ACTIVATED,
    PHASE,
)

COVERAGE_KINDS = (
    "idea",
    "reasoning",
    "example",
    "reference",
    "reservation",
)
_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return [token for token in _TOKEN.findall((text or "").lower()) if len(token) > 3]


def content_represented(source_text: str, prose: str, *, minimum_ratio: float = 0.6) -> bool:
    tokens = _tokens(source_text)
    if not tokens:
        return False
    present = set(_tokens(prose))
    hits = sum(1 for token in tokens if token in present)
    return (hits / len(tokens)) >= minimum_ratio


def assess_unit(
    unit: Mapping[str, Any],
    prose: str,
    metadata_ids: Sequence[str],
) -> dict[str, Any]:
    unit_id = str(unit.get("id") or "")
    source_text = str(unit.get("text") or "")
    represented = content_represented(source_text, prose)
    identifier_only = unit_id in set(metadata_ids) and not represented
    if represented:
        status = "COVERED"
    elif identifier_only:
        status = "IDENTIFIER_ONLY"
    else:
        status = "NOT_COVERED"
    return {
        "id": unit_id,
        "kind": unit.get("kind"),
        "status": status,
        "content_represented": represented,
        "identifier_listed_in_metadata": unit_id in set(metadata_ids),
        "identifier_alone_is_not_coverage": True,
    }


def assess_coverage(
    units: Sequence[Mapping[str, Any]],
    prose: str,
    metadata_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    listed = list(metadata_ids or [])
    rows = [assess_unit(unit, prose, listed) for unit in units]
    by_kind: dict[str, dict[str, int]] = {}
    for kind in COVERAGE_KINDS:
        kind_rows = [row for row in rows if row["kind"] == kind]
        by_kind[kind] = {
            "required": len(kind_rows),
            "covered": sum(1 for row in kind_rows if row["status"] == "COVERED"),
            "identifier_only": sum(
                1 for row in kind_rows if row["status"] == "IDENTIFIER_ONLY"
            ),
            "not_covered": sum(1 for row in kind_rows if row["status"] == "NOT_COVERED"),
        }
    important_missing = [
        row["id"] for row in rows if row["status"] in {"NOT_COVERED", "IDENTIFIER_ONLY"}
    ]
    return {
        "phase": PHASE,
        "contract": COVERAGE_CONTRACT_VERSION,
        "activated_in_production": COVERAGE_CONTROL_ACTIVATED,
        "not_a_terra_verdict": True,
        "units": rows,
        "by_kind": by_kind,
        "important_missing": important_missing,
        "pass": not important_missing,
    }


def source_coverage_contract() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "version": COVERAGE_CONTRACT_VERSION,
        "activated_in_production": COVERAGE_CONTROL_ACTIVATED,
        "production_pipeline_hook": False,
        "not_a_second_semantic_gate": True,
        "not_a_terra_verdict": True,
        "rule": (
            "An idea, reasoning, example, reference, or reservation is covered "
            "only when its content is represented in the chapter prose. "
            "Listing its SourceMap or EditorialPlan identifier in metadata is not coverage."
        ),
        "kinds": list(COVERAGE_KINDS),
        "identifiers_reused": ["IDEA", "EX", "REF", "UNC", "SRC", "CH", "SEC"],
        "content_test": (
            "Distinctive tokens longer than three characters from the source "
            "statement must appear in the prose at a ratio of at least 0.6. "
            "This ratio is a candidate offline heuristic, not a model judgment."
        ),
        "omission_of_an_important_element_fails_coverage": True,
        "does_not_convert_unsupported_to_supported": True,
        "does_not_replace_semantic_gate": True,
        "applied_to_a_generated_chapter_in_this_phase": False,
        "reason_not_applied": "No chapter was generated.",
        "secrets_included": False,
    }


__all__ = [
    "COVERAGE_KINDS",
    "assess_coverage",
    "content_represented",
    "source_coverage_contract",
]
