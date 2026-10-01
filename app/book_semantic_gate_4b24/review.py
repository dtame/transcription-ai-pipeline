"""Human comparison of Terra output against frozen labels."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b24.constants import (
    CONNECTIVE_CASE_ID,
    FUNERAL_CASE_ID,
    P3_CASE_ID,
    P8_CASE_ID,
)

_EDITORIAL = re.compile(
    r"\b(rewrite|rephrase|better wording|as an editor|i would change)\b",
    re.I,
)
_THEOLOGIAN = re.compile(
    r"\b(as a theologian|doctrinally|systematic theology|bible commentary)\b",
    re.I,
)
_EXTERNAL = re.compile(
    r"\b(it is well known|commonly quoted|everyone knows|from memory|"
    r"the rest of the chapter|the full verse)\b",
    re.I,
)


def _explanations(row: Mapping[str, Any] | None) -> list[str]:
    if not row:
        return []
    return [str(item) for item in row.get("terra_explanations") or [] if str(item).strip()]


def _quality(explanations: Sequence[str]) -> dict[str, Any]:
    blob = "\n".join(explanations)
    lengths = [len(item) for item in explanations]
    return {
        "count": len(explanations),
        "max_chars": max(lengths) if lengths else 0,
        "editorial_language": bool(_EDITORIAL.search(blob)),
        "theologian_language": bool(_THEOLOGIAN.search(blob)),
        "external_knowledge_markers": bool(_EXTERNAL.search(blob)),
        "evidence_bounded_markers": (
            "evidence" in blob.lower()
            or "supplied" in blob.lower()
            or "not in" in blob.lower()
            or "unsupported" in blob.lower()
        ),
        "samples": list(explanations)[:8],
    }


def review_terra_output(
    score: Mapping[str, Any],
    *,
    structural: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = list(score.get("rows") or [])
    funeral = score.get("funeral") or {}
    connective = score.get("connective") or {}
    p3 = score.get("p3") or {}
    p8 = score.get("p8") or {}
    all_explanations = []
    for row in rows:
        all_explanations.extend(_explanations(row))
    quality = _quality(all_explanations)
    p8_explanations = "\n".join(_explanations(p8)).lower()
    external_rescue = False
    if p8.get("terra_class") == "SUPPORTED":
        external_rescue = True
    if any(
        marker in p8_explanations
        for marker in (
            "from memory",
            "well known verse",
            "full 1 corinthians",
            "i know the verse",
        )
    ):
        external_rescue = True
    rationale = "ACCEPTABLE"
    if quality["editorial_language"] or quality["theologian_language"]:
        rationale = "CALIBRATION"
    if not quality["evidence_bounded_markers"] and all_explanations:
        rationale = "CALIBRATION"
    if quality["external_knowledge_markers"]:
        rationale = "CALIBRATION"
    if not all_explanations:
        rationale = "MISSING"
    return {
        "method": "manual_comparison_against_frozen_human_labels",
        "human_labels_remain_ground_truth": True,
        "terra_did_not_redefine_labels": True,
        "funeral_case": {
            "case_id": FUNERAL_CASE_ID,
            "blocked": bool(funeral.get("blocked")),
            "terra_class": funeral.get("terra_class"),
            "terra_reasons": funeral.get("terra_reasons"),
            "expected": "blocked + INVENTED_EXAMPLE compatible",
        },
        "connective_case": {
            "case_id": CONNECTIVE_CASE_ID,
            "blocked": bool(connective.get("blocked")),
            "terra_class": connective.get("terra_class"),
            "terra_reasons": connective.get("terra_reasons"),
            "expected": "blocked + NEW_ARGUMENT / NEW_CONCLUSION / NEW_IMPLICATION",
        },
        "p3_case": {
            "case_id": P3_CASE_ID,
            "blocked": bool(p3.get("blocked")),
            "partial_clause_detected": p3.get("partial_clause_detected"),
            "terra_class": p3.get("terra_class"),
            "terra_reasons": p3.get("terra_reasons"),
            "expected": "blocked; core support must not force SUPPORTED",
        },
        "p8_case": {
            "case_id": P8_CASE_ID,
            "blocked": bool(p8.get("blocked")),
            "partial_clause_detected": p8.get("partial_clause_detected"),
            "terra_class": p8.get("terra_class"),
            "terra_reasons": p8.get("terra_reasons"),
            "external_knowledge_rescue": external_rescue,
            "expected": "blocked; remembered 1 Corinthians 15 wording is not evidence",
        },
        "rationale_quality": rationale,
        "rationale_details": quality,
        "span_validation": (structural or {}).get("span_validation"),
        "notes": [
            "10 cases are an engineering canary, not a statistical model-quality benchmark.",
            "Terra output is evaluated against frozen human labels; labels are not updated.",
        ],
    }


__all__ = ["review_terra_output"]
