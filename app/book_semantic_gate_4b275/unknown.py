"""Unknown reason-code policy. Raw codes preserved. Acceptance remains FAIL."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b274.reasons import DIAGNOSTIC_CANDIDATES, classify_reason_payload
from app.book_semantic_gate_4b275.constants import (
    CLOSED_CATALOG_POLICY,
    PHASE,
    REASON_NORMALIZATION_VERSION,
    UNKNOWN_CODE_POLICY,
)


def unknown_reason_code_policy() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "catalog_policy": CLOSED_CATALOG_POLICY,
        "unknown_codes_handling": UNKNOWN_CODE_POLICY,
        "catalog": list(REASON_CODES),
        "rules": {
            "preserve_raw_code": True,
            "mark_non_compliant": True,
            "block_acceptance": True,
            "expose_in_audits": True,
            "separate_diagnostic_correspondence_allowed": True,
        },
        "never": {
            "silently_rewrite_code": True,
            "convert_reservation_to_acceptance": True,
            "modify_raw_response": True,
            "invent_canonical_correspondence_without_justification": True,
        },
        "diagnostic_map_audit_only": {
            code: {
                "canonical_candidate": item["canonical_candidate"],
                "semantic_compatibility": item["semantic_compatibility"],
                "applied_by_validator": False,
                "grants_compliance": False,
            }
            for code, item in DIAGNOSTIC_CANDIDATES.items()
        },
        "normalization_version": REASON_NORMALIZATION_VERSION,
        "normalization_applied_by_validator": False,
        "secrets_included": False,
    }


def diagnose_unknown_codes(
    classification: str,
    codes: Sequence[str],
) -> dict[str, Any]:
    structural = classify_reason_payload(classification=classification, reasons=codes)
    diagnostics = []
    for code in codes:
        if code in REASON_CODES:
            continue
        candidate = DIAGNOSTIC_CANDIDATES.get(code)
        diagnostics.append(
            {
                "raw_code": code,
                "preserved_verbatim": True,
                "in_catalog": False,
                "compliance": "FAIL",
                "canonical_candidate": None
                if candidate is None
                else candidate["canonical_candidate"],
                "correspondence_justified": candidate is not None,
                "grants_compliance": False,
            }
        )
    return {
        "structural": structural,
        "unknown_diagnostics": diagnostics,
        "acceptance": "FAIL" if structural["status"] == "FAIL" else "PASS",
        "raw_codes_unmodified": list(codes),
        "silently_rewritten": False,
    }


def inspect_unknown_in_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if isinstance(payload, Mapping):
        for para in payload.get("pr") or []:
            for claim in para.get("c") or []:
                codes = list(claim.get("r") or [])
                unknown = [code for code in codes if code not in REASON_CODES]
                if unknown:
                    rows.append(
                        {
                            "handle": para.get("h"),
                            "index": claim.get("i"),
                            "classification": claim.get("k"),
                            "raw_codes": codes,
                            "unknown": unknown,
                            "preserved_verbatim": True,
                        }
                    )
    return {
        "unknown_claims": rows,
        "unknown_codes": sorted(
            {code for row in rows for code in row.get("unknown") or []}
        ),
        "any_unknown": bool(rows),
        "acceptance_if_unknown": "FAIL",
        "raw_unmodified": True,
    }


__all__ = [
    "diagnose_unknown_codes",
    "inspect_unknown_in_payload",
    "unknown_reason_code_policy",
]
