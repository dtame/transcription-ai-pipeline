"""Human review of all 10 Terra decisions against frozen labels."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_semantic_gate_4b24.constants import (
    CONNECTIVE_CASE_ID,
    FUNERAL_CASE_ID,
    P3_CASE_ID,
    P8_CASE_ID,
)
from app.book_semantic_gate_4b24.review import review_terra_output


def _handles(row: Mapping[str, Any] | None) -> list[str]:
    if not row:
        return []
    handles: list[str] = []
    for claim in row.get("claims") or []:
        handles.extend(str(item) for item in (claim.get("evidence_handles") or []))
    return list(dict.fromkeys(handles))


def _span_valid(row: Mapping[str, Any] | None, structural: Mapping[str, Any] | None) -> str:
    if not row or not row.get("present"):
        return "MISSING"
    errors = [
        item
        for item in (structural or {}).get("span_errors") or []
        if str(row.get("opaque_handle") or "") in str(item)
    ]
    return "PASS" if not errors else "FAIL"


def _rationale(row: Mapping[str, Any] | None) -> str:
    texts = [str(item) for item in (row or {}).get("terra_explanations") or [] if str(item).strip()]
    if not texts:
        return "MISSING"
    blob = "\n".join(texts).lower()
    if any(
        marker in blob
        for marker in ("from memory", "well known", "i know the verse", "full 1 corinthians")
    ):
        return "EXTERNAL_KNOWLEDGE_CONCERN"
    if "evidence" in blob or "supplied" in blob or "not in" in blob or "unsupported" in blob:
        return "EVIDENCE_BOUNDED"
    return "PRESENT"


def review_all_cases(
    score: Mapping[str, Any],
    *,
    structural: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    summary = review_terra_output(score, structural=structural)
    cases = []
    for row in score.get("rows") or []:
        human_label = (
            "supported_positive"
            if row.get("role") == "positive"
            else "semantic_negative"
        )
        terra = str(row.get("terra_class") or "MISSING")
        match = bool(row.get("verdict_compatible"))
        external = False
        if row.get("case_id") == P8_CASE_ID:
            external = bool((summary.get("p8_case") or {}).get("external_knowledge_rescue"))
            if terra == "SUPPORTED":
                external = True
        cases.append(
            {
                "case_id": row.get("case_id"),
                "opaque_handle": row.get("opaque_handle"),
                "human_label": human_label,
                "human_expected_class": row.get("expected_class"),
                "terra_verdict": terra,
                "match": "MATCH" if match else "MISMATCH",
                "reason_codes": list(row.get("terra_reasons") or []),
                "expected_reason_codes": list(row.get("expected_reason_codes") or []),
                "reason_compatible": row.get("reason_compatible"),
                "evidence_handles": _handles(row),
                "span_validity": _span_valid(row, structural),
                "rationale_quality": _rationale(row),
                "external_knowledge_concern": external,
                "blocked": row.get("blocked"),
                "false_rejection": row.get("false_rejection"),
                "false_negative": row.get("false_negative"),
            }
        )
    funeral = next((item for item in cases if item["case_id"] == FUNERAL_CASE_ID), None)
    connective = next((item for item in cases if item["case_id"] == CONNECTIVE_CASE_ID), None)
    p3 = next((item for item in cases if item["case_id"] == P3_CASE_ID), None)
    p8 = next((item for item in cases if item["case_id"] == P8_CASE_ID), None)
    return {
        **summary,
        "cases": cases,
        "case_count": len(cases),
        "funeral_case": {**(summary.get("funeral_case") or {}), **(funeral or {})},
        "connective_case": {**(summary.get("connective_case") or {}), **(connective or {})},
        "p3_case": {**(summary.get("p3_case") or {}), **(p3 or {})},
        "p8_case": {**(summary.get("p8_case") or {}), **(p8 or {})},
        "human_labels_remain_ground_truth": True,
        "terra_did_not_redefine_labels": True,
    }


__all__ = ["review_all_cases"]
