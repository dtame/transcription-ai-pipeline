"""Verdict / reason-code compatibility matrix. Structural vs semantic layers."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b274.reasons import classify_reason_payload
from app.book_semantic_gate_4b275.catalog import EMPTY_REASON_VERDICTS, RESERVATION_VERDICTS
from app.book_semantic_gate_4b275.constants import PHASE

STRUCTURAL_CASES = (
    {
        "name": "supported_with_blocking_reason",
        "classification": CLASS_SUPPORTED,
        "codes": ["NEW_FACT"],
        "expect": "FAIL",
        "layer": "structural_compliance",
    },
    {
        "name": "questionable_without_reason",
        "classification": CLASS_QUESTIONABLE,
        "codes": [],
        "expect": "FAIL",
        "layer": "structural_compliance",
    },
    {
        "name": "unsupported_without_reason",
        "classification": CLASS_UNSUPPORTED,
        "codes": [],
        "expect": "FAIL",
        "layer": "structural_compliance",
    },
    {
        "name": "unknown_code",
        "classification": CLASS_UNSUPPORTED,
        "codes": ["INVENTED_CAUSAL_LINK"],
        "expect": "FAIL",
        "layer": "structural_compliance",
    },
    {
        "name": "misspelled_code",
        "classification": CLASS_QUESTIONABLE,
        "codes": ["NEW_CAUSAL_LIK"],
        "expect": "FAIL",
        "layer": "structural_compliance",
    },
    {
        "name": "wrong_case",
        "classification": CLASS_QUESTIONABLE,
        "codes": ["new_causal_link"],
        "expect": "FAIL",
        "layer": "structural_compliance",
    },
    {
        "name": "valid_code_structurally_ok",
        "classification": CLASS_UNSUPPORTED,
        "codes": ["NEW_CAUSAL_LINK"],
        "expect": "PASS",
        "layer": "structural_compliance",
    },
    {
        "name": "valid_code_semantically_inconsistent",
        "classification": CLASS_QUESTIONABLE,
        "codes": ["INVENTED_EXAMPLE"],
        "expect": "PASS",
        "layer": "semantic_coherence_diagnostic_only",
        "note": (
            "A catalog code on a reservation is structurally valid even when "
            "the named problem type does not fit the claim. Semantic fit is "
            "not treated as a deterministic FAIL."
        ),
    },
)

SEMANTIC_FIT_HEURISTICS = {
    "NEW_CAUSAL_LINK": "claim asserts a because/therefore/as-a-result relation",
    "NEW_IMPLICATION": "claim asserts a meaning, origin, or 'which means' extension",
    "INVENTED_EXAMPLE": "claim contains an illustrative case or scene",
    "REFERENCE_COMPLETION": "claim completes a partial REF/citation",
    "REFERENCE_EXPANSION": "claim expands a supplied reference",
    "UNCERTAINTY_STRENGTHENED": "claim raises modality, quantity, or completeness",
    "NEW_FACT": "claim asserts a fact absent from evidence",
    "EVIDENCE_MISMATCH": "cited handles do not actually support the claim",
}


def verdict_reason_code_matrix() -> dict[str, Any]:
    rows = []
    passed = True
    for item in STRUCTURAL_CASES:
        result = classify_reason_payload(
            classification=item["classification"],
            reasons=item["codes"],
        )
        ok = result["status"] == item["expect"]
        passed = passed and ok
        rows.append(
            {
                "name": item["name"],
                "classification": item["classification"],
                "codes": list(item["codes"]),
                "layer": item["layer"],
                "expected": item["expect"],
                "observed": result["status"],
                "ok": ok,
                "errors": result.get("errors"),
                "note": item.get("note"),
                "silently_accepted_unknown": result.get("silently_accepted_unknown"),
            }
        )
    compatibility = []
    for verdict in (CLASS_SUPPORTED, CLASS_QUESTIONABLE, CLASS_UNSUPPORTED, CLASS_NON_SUBSTANTIVE):
        for code in REASON_CODES:
            if verdict in EMPTY_REASON_VERDICTS:
                structural = "FAIL_REASONS_FORBIDDEN"
            elif verdict in RESERVATION_VERDICTS:
                structural = "PASS_IF_CATALOG_MEMBER"
            else:
                structural = "UNREACHABLE"
            compatibility.append(
                {
                    "verdict": verdict,
                    "code": code,
                    "structural": structural,
                    "semantic_fit": "DIAGNOSTIC_NOT_DETERMINISTIC",
                }
            )
    return {
        "phase": PHASE,
        "structural_cases": rows,
        "structural_passed": passed,
        "compatibility": compatibility,
        "layers": {
            "structural_compliance": (
                "Unknown, missing, forbidden, misspelled, or wrong-case codes "
                "FAIL acceptance. Deterministic."
            ),
            "semantic_coherence": (
                "A catalog code whose named problem type does not fit the "
                "claim is structurally valid. Fit requires human or model "
                "interpretation and is diagnostic-only."
            ),
        },
        "semantic_fit_heuristics": SEMANTIC_FIT_HEURISTICS,
        "causal_code_on_non_causal_reservation": "PASS_STRUCTURALLY_DIAGNOSTIC_ONLY",
        "reference_code_without_reference": "PASS_STRUCTURALLY_DIAGNOSTIC_ONLY",
        "invented_example_code_without_example": "PASS_STRUCTURALLY_DIAGNOSTIC_ONLY",
        "secrets_included": False,
    }


__all__ = ["SEMANTIC_FIT_HEURISTICS", "STRUCTURAL_CASES", "verdict_reason_code_matrix"]
