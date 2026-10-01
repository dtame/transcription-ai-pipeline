"""Structural semantic-response validation and deterministic replay."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.accept import apply_acceptance, canonical_audit
from app.book_semantic_gate_4b23.claims import claim_offsets_valid, uncovered_spans
from app.book_semantic_gate_4b23.transport import SemanticTransportError, decode_transport
from app.book_semantic_gate_4b24.constants import (
    CLASSIFICATIONS,
    SCORED_CASE_ORDER,
)
from app.book_semantic_gate_4b24.payload import case_id_for_handle
from app.file_utils import content_hash
import json


def validate_semantic_response(
    parsed: Mapping[str, Any] | None,
    *,
    required_handles: Sequence[str],
    paragraph_texts: Mapping[str, str],
    allowed_handles: Sequence[str] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    parse_status = "PASS" if isinstance(parsed, Mapping) else "FAIL"
    try:
        decoded = decode_transport(parsed) if isinstance(parsed, Mapping) else None
        transport_status = "PASS"
        transport_error = None
    except SemanticTransportError as exc:
        decoded = None
        transport_status = "FAIL"
        transport_error = str(exc)
        errors.append(str(exc))

    acceptance = apply_acceptance(
        parsed if isinstance(parsed, Mapping) else None,
        required_handles=required_handles,
        paragraph_texts=paragraph_texts,
        allowed_handles=allowed_handles,
        deterministic_validator_pass=True,
    )
    decoded_rows = []
    if decoded is not None:
        decoded_rows = list(decoded.get("paragraph_results") or [])
    else:
        decoded_rows = list(acceptance.get("paragraph_results") or [])
    returned = [str(row.get("paragraph_handle") or "") for row in decoded_rows]
    by_handle = {
        str(row.get("paragraph_handle") or ""): row
        for row in (acceptance.get("paragraph_results") or [])
    }
    missing = [handle for handle in required_handles if handle not in by_handle]
    unknown = [handle for handle in returned if handle and handle not in set(required_handles)]
    seen: set[str] = set()
    duplicates: list[str] = []
    for handle in returned:
        if not handle:
            continue
        if handle in seen:
            duplicates.append(handle)
        seen.add(handle)

    span_errors: list[str] = []
    for handle in required_handles:
        row = by_handle.get(handle)
        if row is None:
            continue
        text = str(paragraph_texts.get(handle) or "")
        claims = list(row.get("claim_results") or [])
        if not claims:
            span_errors.append(f"{handle}: no claims")
            continue
        for claim in claims:
            if text and not claim_offsets_valid(text, claim):
                span_errors.append(f"{handle}: invalid span {claim.get('claim_index')}")
            classification = str(claim.get("classification") or "")
            if classification not in CLASSIFICATIONS:
                span_errors.append(f"{handle}: invalid class {classification}")
        gaps = uncovered_spans(text, claims) if text else []
        if gaps:
            span_errors.append(f"{handle}: coverage gap {gaps}")

    unknown_handles = list(acceptance.get("unknown_handles") or [])
    structural_ok = (
        parse_status == "PASS"
        and transport_status == "PASS"
        and not missing
        and not unknown
        and not duplicates
        and not span_errors
        and not unknown_handles
        and not acceptance.get("errors")
    )
    # Acceptance errors include cache-policy FAIL for QUESTIONABLE/UNSUPPORTED
    # claims. Those are expected on this historical benchmark. Structural
    # validation only requires decode, coverage, spans, classes, and handles.
    structural_pass = (
        parse_status == "PASS"
        and transport_status == "PASS"
        and not missing
        and not unknown
        and not duplicates
        and not span_errors
        and len(unknown_handles) == 0
        and all(handle in by_handle for handle in required_handles)
    )
    return {
        "json_parse": parse_status,
        "transport_decode": transport_status,
        "transport_error": transport_error,
        "case_coverage": (
            "PASS" if not missing and len(returned) >= len(required_handles) else "FAIL"
        ),
        "required_handles": list(required_handles),
        "returned_handles": returned,
        "missing_cases": missing,
        "unknown_cases": unknown,
        "duplicate_results": duplicates,
        "span_validation": "PASS" if not span_errors else "FAIL",
        "span_errors": span_errors,
        "unknown_handles": unknown_handles,
        "unknown_handle_count": len(unknown_handles),
        "acceptance": {
            "verdict": acceptance.get("verdict"),
            "cache_acceptance": acceptance.get("cache_acceptance"),
            "review_required": acceptance.get("review_required"),
            "errors": list(acceptance.get("errors") or []),
            "summary_counts": acceptance.get("summary_counts"),
        },
        "canonical": canonical_audit(acceptance),
        "decoded": decoded,
        "paragraph_results": acceptance.get("paragraph_results") or [],
        "structural_pass": structural_pass,
        "structural_ok_including_policy": structural_ok,
        "errors": errors + span_errors,
    }


def map_handle_results(paragraph_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    mapped = []
    for row in paragraph_results:
        handle = str(row.get("paragraph_handle") or "")
        try:
            case_id = case_id_for_handle(handle)
        except KeyError:
            case_id = ""
        mapped.append({**dict(row), "case_id": case_id, "opaque_handle": handle})
    return {str(item.get("opaque_handle") or ""): item for item in mapped}


def replay_canonical(canonical: Mapping[str, Any]) -> str:
    return content_hash(json.dumps(dict(canonical), ensure_ascii=False, sort_keys=True))


def deterministic_replay(
    parsed: Mapping[str, Any] | None,
    *,
    required_handles: Sequence[str],
    paragraph_texts: Mapping[str, str],
    allowed_handles: Sequence[str] | None = None,
) -> dict[str, Any]:
    first = validate_semantic_response(
        parsed,
        required_handles=required_handles,
        paragraph_texts=paragraph_texts,
        allowed_handles=allowed_handles,
    )
    second = validate_semantic_response(
        parsed,
        required_handles=required_handles,
        paragraph_texts=paragraph_texts,
        allowed_handles=allowed_handles,
    )
    first_hash = replay_canonical(first.get("canonical") or {})
    second_hash = replay_canonical(second.get("canonical") or {})
    return {
        "pass": first_hash == second_hash and bool(first.get("canonical")),
        "first_sha256": first_hash,
        "second_sha256": second_hash,
        "identical": first_hash == second_hash,
    }


__all__ = [
    "deterministic_replay",
    "map_handle_results",
    "replay_canonical",
    "validate_semantic_response",
]
