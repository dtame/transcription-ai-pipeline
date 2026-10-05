"""Local diagnostics for BLOCK / REVIEW. Raw model text is never rewritten."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_semantic_gate_4b29.constants import PHASE


def build_diagnostics(
    *,
    prepared: Mapping[str, Any],
    coverage: Mapping[str, Any],
    request: Mapping[str, Any] | None,
    raw: Any,
    validation: Mapping[str, Any],
    policy: Mapping[str, Any],
    transport_source: str,
) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "decision": policy.get("decision"),
        "reasons": list(policy.get("reasons") or []),
        "prepared_units": [
            {
                "unit_id": unit.get("unit_id"),
                "paragraph_id": unit.get("paragraph_id"),
                "text": unit.get("text"),
                "start_offset": unit.get("start_offset"),
                "end_offset": unit.get("end_offset"),
                "boundary_type": unit.get("boundary_type"),
                "boundary_ambiguity": unit.get("boundary_ambiguity"),
            }
            for unit in prepared.get("units") or []
        ],
        "raw_response": raw,
        "raw_rewritten": False,
        "verdicts": list(validation.get("verdicts") or []),
        "reason_codes": [
            code
            for item in validation.get("verdicts") or []
            for code in (item.get("r") or [])
        ],
        "evidence_handles": [
            handle
            for item in validation.get("verdicts") or []
            for handle in (item.get("ev") or [])
        ],
        "schema_errors": list(validation.get("errors") or []),
        "identifier_errors": [
            error
            for error in validation.get("errors") or []
            if "unit" in error or "id:" in error or "h:" in error
        ],
        "coverage_errors": list(coverage.get("errors") or []),
        "semantic_reservations": list(policy.get("reservations") or []),
        "transport_source": transport_source,
        "not_terra": True,
        "usable_when_contract_fails": True,
        "request_sha256": None if request is None else request.get("request_sha256"),
        "secrets_included": False,
    }


__all__ = ["build_diagnostics"]
