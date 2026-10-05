"""Local 2.0.2 contract, coverage, and evidence validation. No repair."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b212.policy import apply_acceptance_policy_202
from app.book_semantic_gate_4b212.validator import validate_response_202
from app.book_semantic_gate_4b215.constants import (
    CHAPTER_ID,
    H11_EVIDENCE,
    PHASE,
    REQUIRED_UNIT_IDS,
    SELECTED_CASE_HANDLE,
    TARGET_UNIT_ID,
    TRANSPORT_VERSION,
)
from app.book_semantic_gate_4b23.constants import CLASS_QUESTIONABLE, CLASS_UNSUPPORTED
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b29.validator import parse_raw_response


def parse_saved_response(raw: Any) -> dict[str, Any]:
    parsed, errors = parse_raw_response(raw)
    if errors:
        return {
            "json_parse": "FAIL",
            "parsed": parsed,
            "error": errors[0],
            "errors": errors,
            "repaired": False,
        }
    if not isinstance(parsed, Mapping):
        return {
            "json_parse": "FAIL",
            "parsed": parsed,
            "error": "not_object",
            "errors": ["not_object"],
            "repaired": False,
        }
    return {
        "json_parse": "PASS",
        "parsed": parsed,
        "error": None,
        "errors": [],
        "repaired": False,
    }


def validate_contract(
    raw: Any,
    prepared: Mapping[str, Any],
    *,
    allowed_evidence: Sequence[str] | None = None,
) -> dict[str, Any]:
    allowed = list(allowed_evidence or prepared.get("evidence_handles") or H11_EVIDENCE)
    parsed_meta = parse_saved_response(raw)
    validation = validate_response_202(
        parsed_meta.get("parsed") if parsed_meta.get("json_parse") == "PASS" else raw,
        prepared,
        allowed_evidence=allowed,
        expected_chapter=CHAPTER_ID,
    )
    errors = list(validation.get("errors") or [])
    return {
        "phase": PHASE,
        "contract": "book-semantic-validator-2.0.2-candidate",
        "transport": TRANSPORT_VERSION,
        "json_parse": parsed_meta.get("json_parse"),
        "parse_error": parsed_meta.get("error"),
        "ok": bool(validation.get("ok")),
        "status": "PASS" if validation.get("ok") else "FAIL",
        "technical_conformance": validation.get("technical_conformance"),
        "errors": errors,
        "parsed": validation.get("parsed"),
        "verdicts": validation.get("verdicts") or [],
        "required_unit_ids": list(validation.get("required_unit_ids") or REQUIRED_UNIT_IDS),
        "derived_paragraph_classification": validation.get("derived_paragraph_classification"),
        "derived_counts": validation.get("derived_counts"),
        "does_not_complete_missing_units": True,
        "does_not_repair_reason_codes": True,
        "does_not_rewrite_model_response": True,
        "repaired": False,
        "secrets_included": False,
    }


def unit_coverage_validation(
    validation: Mapping[str, Any],
    *,
    required_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    required = list(required_ids or REQUIRED_UNIT_IDS)
    verdicts = list(validation.get("verdicts") or [])
    seen = [str(item.get("unit_id") or "") for item in verdicts]
    missing = [uid for uid in required if uid not in seen]
    extras = [uid for uid in seen if uid not in required]
    duplicates = sorted({uid for uid in seen if uid and seen.count(uid) > 1})
    unknown_reasons = [
        code
        for item in verdicts
        for code in (item.get("r") or [])
        if code not in REASON_CODES
    ]
    coverage_ok = not missing and not extras and not duplicates and bool(seen)
    return {
        "phase": PHASE,
        "required_unit_ids": required,
        "returned_unit_ids": seen,
        "missing_units": missing,
        "duplicate_units": duplicates,
        "unknown_units": extras,
        "unknown_reason_codes": unknown_reasons,
        "all_units_present": not missing and not extras,
        "identifiers_correct": extras == [] and duplicates == [],
        "ok": coverage_ok and not unknown_reasons,
        "status": "PASS" if coverage_ok and not unknown_reasons else "FAIL",
        "secrets_included": False,
    }


def evidence_validation(
    validation: Mapping[str, Any],
    *,
    allowed_handles: Sequence[str] | None = None,
) -> dict[str, Any]:
    allowed = set(allowed_handles or H11_EVIDENCE)
    cited: list[str] = []
    invalid: list[str] = []
    for item in validation.get("verdicts") or []:
        for handle in item.get("ev") or []:
            cited.append(str(handle))
            if handle not in allowed:
                invalid.append(str(handle))
    errors = [
        str(error)
        for error in (validation.get("errors") or [])
        if "unknown_evidence_handle" in str(error) or "invalid_handle" in str(error)
    ]
    ok = not invalid and not errors
    return {
        "phase": PHASE,
        "allowed_handles": sorted(allowed),
        "cited_handles": sorted(set(cited)),
        "invalid_evidence_references": invalid,
        "invented_handles": invalid,
        "errors": errors,
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "secrets_included": False,
    }


def extract_target_verdict(validation: Mapping[str, Any]) -> dict[str, Any]:
    for item in validation.get("verdicts") or []:
        if str(item.get("unit_id") or "") == TARGET_UNIT_ID:
            return dict(item)
    return {}


def extract_global_verdict(parsed: Mapping[str, Any] | None) -> str | None:
    if not isinstance(parsed, Mapping):
        return None
    top = str(parsed.get("v") or "") or None
    paragraph = None
    for para in parsed.get("pr") or []:
        if str(para.get("h") or "") == SELECTED_CASE_HANDLE:
            paragraph = str(para.get("v") or "") or None
            break
    return top or paragraph


def apply_policy(
    prepared: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    coverage = validate_prepared_coverage(prepared)
    policy = apply_acceptance_policy_202(prepared, coverage, validation)
    kinds = [str(item.get("k") or "") for item in (validation.get("verdicts") or [])]
    return {
        **policy,
        "phase": PHASE,
        "preparation_ok": bool(coverage.get("ok")),
        "contract_ok": bool(validation.get("ok")),
        "unit_kinds": kinds,
        "unsupported_present": CLASS_UNSUPPORTED in kinds,
        "questionable_present": CLASS_QUESTIONABLE in kinds,
        "derived_paragraph_classification": validation.get("derived_paragraph_classification"),
        "production_cache_acceptance": False,
        "publication_authorized": False,
        "review_does_not_accept_cache": True,
        "secrets_included": False,
    }


__all__ = [
    "apply_policy",
    "evidence_validation",
    "extract_global_verdict",
    "extract_target_verdict",
    "parse_saved_response",
    "unit_coverage_validation",
    "validate_contract",
]
