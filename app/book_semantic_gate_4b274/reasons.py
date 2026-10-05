"""Reason-code catalog audit and compliance policy. No silent remapping."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
from app.book_semantic_gate_4b23.reasons import REASON_CODES, REASON_DEFINITIONS
from app.book_semantic_gate_4b274.constants import (
    OBSERVED_H02_REASON_CODES,
    PHASE,
    REASON_NORMALIZATION_VERSION,
)

# Audit-only diagnostic mapping. Never applied by the validator.
# Never converts a blocking reservation into acceptance.
DIAGNOSTIC_CANDIDATES: dict[str, dict[str, Any]] = {
    "INVENTED_CAUSAL_LINK": {
        "implicit_definition": (
            "A because/therefore relation that the evidence does not support."
        ),
        "canonical_candidate": "NEW_CAUSAL_LINK",
        "semantic_compatibility": "HIGH",
        "information_loss_risk": "LOW",
        "recommended_decision": "KEEP_CATALOG_CLOSED_DIAGNOSE_AS_NEW_CAUSAL_LINK",
        "notes": (
            "Closest catalog match. Do not add INVENTED_CAUSAL_LINK as an alias. "
            "Do not silently rewrite the historical code."
        ),
    },
    "NO_EVIDENCE": {
        "implicit_definition": (
            "The claim has no supplied support, or the cited evidence does not "
            "attest the assertion."
        ),
        "canonical_candidate": "NEW_FACT",
        "alternate_candidates": ["OTHER", "EVIDENCE_MISMATCH"],
        "semantic_compatibility": "PARTIAL",
        "information_loss_risk": "MEDIUM",
        "recommended_decision": "NO_EXACT_MATCH_USE_NEW_FACT_OR_OTHER_WHEN_GENERATING",
        "notes": (
            "No catalog code named NO_EVIDENCE. NEW_FACT fits absent assertions. "
            "OTHER remains the closed-list fallback. EVIDENCE_MISMATCH fits cited "
            "handles that do not actually support the claim. Mapping is ambiguous."
        ),
    },
    "UNJUSTIFIED_STRENGTHENING": {
        "implicit_definition": (
            "Wording that intensifies or exceeds the supplied evidence."
        ),
        "canonical_candidate": "UNCERTAINTY_STRENGTHENED",
        "alternate_candidates": ["SOURCE_MEANING_DISTORTED", "OTHER"],
        "semantic_compatibility": "PARTIAL",
        "information_loss_risk": "MEDIUM",
        "recommended_decision": "NO_EXACT_MATCH_UNCERTAINTY_STRENGTHENED_IS_NARROWER",
        "notes": (
            "UNCERTAINTY_STRENGTHENED covers possibility→certainty, not every "
            "stylistic intensifier. A mere intensifier of an attested phrase is "
            "not automatically strengthening."
        ),
    },
    "UNSUPPORTED_IMPLICATION": {
        "implicit_definition": (
            "An implication or origin/meaning extension not supported by evidence."
        ),
        "canonical_candidate": "NEW_IMPLICATION",
        "semantic_compatibility": "HIGH",
        "information_loss_risk": "LOW",
        "recommended_decision": "KEEP_CATALOG_CLOSED_DIAGNOSE_AS_NEW_IMPLICATION",
        "notes": "Closest catalog match. Do not add an alias.",
    },
    "PARTIAL_REFERENCE_EXPANSION": {
        "implicit_definition": (
            "A supplied fragment is completed beyond what the text actually contains."
        ),
        "canonical_candidate": "REFERENCE_EXPANSION",
        "alternate_candidates": ["REFERENCE_COMPLETION"],
        "semantic_compatibility": "HIGH",
        "information_loss_risk": "LOW",
        "recommended_decision": "KEEP_CATALOG_CLOSED_DIAGNOSE_AS_REFERENCE_EXPANSION",
        "notes": (
            "PREFIX 'PARTIAL' is a lexical variant. Truncated spoken SRC is not "
            "automatically a REF completion."
        ),
    },
}


def analyze_reason_codes(codes: Sequence[str]) -> dict[str, Any]:
    rows = []
    for code in codes:
        in_catalog = code in REASON_CODES
        diagnostic = DIAGNOSTIC_CANDIDATES.get(code)
        rows.append(
            {
                "returned_code": code,
                "in_canonical_catalog": in_catalog,
                "canonical_definition": REASON_DEFINITIONS.get(code),
                "implicit_definition": None
                if in_catalog
                else (diagnostic or {}).get("implicit_definition"),
                "canonical_candidate": code
                if in_catalog
                else (diagnostic or {}).get("canonical_candidate"),
                "semantic_compatibility": "EXACT"
                if in_catalog
                else (diagnostic or {}).get("semantic_compatibility", "NONE"),
                "information_loss_risk": "NONE"
                if in_catalog
                else (diagnostic or {}).get("information_loss_risk", "HIGH"),
                "recommended_decision": "ACCEPT_AS_CATALOG_MEMBER"
                if in_catalog
                else (diagnostic or {}).get(
                    "recommended_decision", "NO_EXACT_MATCH_COMPLIANCE_FAIL"
                ),
                "notes": None
                if in_catalog
                else (diagnostic or {}).get(
                    "notes", "Unknown code. No exact catalog correspondence assumed."
                ),
            }
        )
    return {
        "phase": PHASE,
        "canonical_catalog": list(REASON_CODES),
        "canonical_definitions": dict(REASON_DEFINITIONS),
        "observed_codes": list(codes),
        "matrix": rows,
        "unknown_codes": [code for code in codes if code not in REASON_CODES],
        "all_observed_in_catalog": all(code in REASON_CODES for code in codes),
        "new_causal_link_in_catalog": "NEW_CAUSAL_LINK" in REASON_CODES,
        "new_implication_in_catalog": "NEW_IMPLICATION" in REASON_CODES,
        "exact_correspondence_not_assumed": True,
        "secrets_included": False,
    }


def reason_code_policy() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "catalog_closed": True,
        "catalog": list(REASON_CODES),
        "normalization_version": REASON_NORMALIZATION_VERSION,
        "layers": {
            "A_strict_compliance": {
                "rule": (
                    "A reason code absent from the closed catalog is a compliance "
                    "failure. The payload is structurally invalid."
                ),
                "unknown_code": "FAIL",
                "empty_on_QUESTIONABLE": "FAIL",
                "empty_on_UNSUPPORTED": "FAIL",
                "unexpected_on_SUPPORTED": "FAIL",
                "unexpected_on_NON_SUBSTANTIVE": "FAIL",
                "wrong_case": "FAIL",
                "invented_code": "FAIL",
                "semantically_close_but_absent": "FAIL",
                "multiple_valid_codes": "PASS_STRUCTURALLY",
                "valid_code_wrong_semantic_category": (
                    "PASS_STRUCTURALLY_DIAGNOSTIC_ONLY"
                ),
            },
            "B_analytical_diagnosis": {
                "rule": (
                    "An unknown code may be interpreted in an offline audit to "
                    "understand model intent. Diagnosis does not validate the code."
                ),
                "applies_to_historical_h02": True,
                "does_not_rewrite_raw_response": True,
            },
            "C_optional_normalization": {
                "rule": (
                    "Any normalization must be explicit, versioned, justified, "
                    "and tested. It is audit-only in 4B.2.7.4."
                ),
                "applied_by_validator": False,
                "applied_to_historical_raw_json": False,
                "converts_blocking_reservation_to_acceptance": False,
                "silent_remap_forbidden": True,
                "version": REASON_NORMALIZATION_VERSION,
                "diagnostic_map": {
                    code: item["canonical_candidate"]
                    for code, item in DIAGNOSTIC_CANDIDATES.items()
                },
            },
        },
        "unknown_codes_handling": "COMPLIANCE_FAIL_NO_SILENT_ACCEPTANCE",
        "never_silently_transform_unknown_into_valid": True,
        "never_convert_blocking_reservation_into_acceptance": True,
        "prefer_closed_catalog_with_clear_definitions": True,
        "other_is_the_only_fallback": True,
        "questionable_and_unsupported_require_at_least_one_catalog_code": True,
        "secrets_included": False,
    }


def classify_reason_payload(
    *,
    classification: str,
    reasons: Sequence[str],
) -> dict[str, Any]:
    """Structural reason-code policy. Does not judge semantic category fit."""
    codes = list(reasons)
    unknown = [code for code in codes if code not in REASON_CODES]
    empty = not codes
    errors: list[str] = []
    if classification in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED} and empty:
        errors.append("reason_code_missing")
    if classification in {CLASS_SUPPORTED, CLASS_NON_SUBSTANTIVE} and codes:
        errors.append(f"reasons_forbidden_for_{classification}")
    for code in unknown:
        errors.append(f"unknown_reason_{code}")
    return {
        "classification": classification,
        "codes": codes,
        "unknown": unknown,
        "empty": empty,
        "in_catalog": [code for code in codes if code in REASON_CODES],
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "silently_accepted_unknown": False,
        "normalized": False,
        "normalization_applied": False,
    }


def catalog_audit() -> dict[str, Any]:
    observed = analyze_reason_codes(OBSERVED_H02_REASON_CODES)
    policy = reason_code_policy()
    return {
        "phase": PHASE,
        "observed": observed,
        "policy": policy,
        "historical_raw_codes_unmodified": True,
        "secrets_included": False,
    }


def inspect_payload_reason_codes(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if isinstance(payload, Mapping):
        for para in payload.get("pr") or []:
            handle = str(para.get("h") or "")
            for claim in para.get("c") or []:
                rows.append(
                    {
                        "handle": handle,
                        "index": claim.get("i"),
                        **classify_reason_payload(
                            classification=str(claim.get("k") or ""),
                            reasons=list(claim.get("r") or []),
                        ),
                    }
                )
    unknown = sorted(
        {
            code
            for row in rows
            for code in row.get("unknown") or []
        }
    )
    return {
        "claims": rows,
        "unknown_codes": unknown,
        "any_unknown": bool(unknown),
        "compliance": "FAIL"
        if any(row.get("status") == "FAIL" for row in rows)
        else "PASS",
        "silently_normalized": False,
    }


__all__ = [
    "DIAGNOSTIC_CANDIDATES",
    "analyze_reason_codes",
    "catalog_audit",
    "classify_reason_payload",
    "inspect_payload_reason_codes",
    "reason_code_policy",
]
