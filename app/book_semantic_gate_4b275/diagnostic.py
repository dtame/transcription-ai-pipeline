"""Failure diagnostics distinct from acceptance. Raw payloads are not rewritten."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b261.candidates import recover_claim_text
from app.book_semantic_gate_4b262.contract import (
    REQUIRED_CLAIM_FIELDS,
    REQUIRED_PARAGRAPH_FIELDS,
    REQUIRED_TOP_FIELDS,
    validate_compact_span,
)
from app.book_semantic_gate_4b274.coverage import validate_compact_payload_112
from app.book_semantic_gate_4b274.reasons import classify_reason_payload
from app.book_semantic_gate_4b275.constants import PHASE, PROMPT_VERSION_113
from app.book_semantic_gate_4b275.unknown import diagnose_unknown_codes


def extract_failure_diagnostic(
    payload: Mapping[str, Any] | None,
    *,
    paragraph_texts: Mapping[str, str],
    required_handles: Sequence[str],
    paragraph_kinds: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return (A) acceptance and (B) an exploitable diagnostic. Never equate B with A."""
    validation = validate_compact_payload_112(
        payload,
        paragraph_texts=paragraph_texts,
        required_handles=required_handles,
        paragraph_kinds=paragraph_kinds,
    )
    analyzable: list[dict[str, Any]] = []
    valid_spans: list[dict[str, Any]] = []
    cited: list[dict[str, Any]] = []
    raw_codes: list[str] = []
    unknown_codes: list[str] = []
    reservations: list[dict[str, Any]] = []
    missing_fields: list[str] = []
    unevaluable: list[dict[str, Any]] = []
    if not isinstance(payload, Mapping):
        missing_fields.extend(f"missing_top_{field}" for field in REQUIRED_TOP_FIELDS)
        unevaluable.append({"reason": "payload_missing"})
    else:
        for field in REQUIRED_TOP_FIELDS:
            if field not in payload:
                missing_fields.append(f"missing_top_{field}")
        for para in payload.get("pr") or []:
            handle = str(para.get("h") or "")
            text = str(paragraph_texts.get(handle) or "")
            for field in REQUIRED_PARAGRAPH_FIELDS:
                if field not in para:
                    missing_fields.append(f"{handle}: missing_{field}")
            claims = list(para.get("c") or [])
            if not claims:
                unevaluable.append({"handle": handle, "reason": "no_claims"})
            for claim in claims:
                for field in REQUIRED_CLAIM_FIELDS:
                    if field not in claim:
                        missing_fields.append(f"{handle}: missing_claim_{field}")
                start = claim.get("s")
                end = claim.get("e")
                span = validate_compact_span(text, start, end)
                recovered = ""
                if span.get("valid"):
                    recovered = recover_claim_text(text, int(start), int(end))
                    valid_spans.append(
                        {
                            "handle": handle,
                            "index": claim.get("i"),
                            "s": start,
                            "e": end,
                            "recovered": recovered,
                        }
                    )
                else:
                    unevaluable.append(
                        {
                            "handle": handle,
                            "index": claim.get("i"),
                            "reason": "invalid_span",
                            "errors": span.get("errors"),
                        }
                    )
                kind = str(claim.get("k") or "")
                codes = list(claim.get("r") or [])
                raw_codes.extend(str(code) for code in codes)
                structural = classify_reason_payload(classification=kind, reasons=codes)
                unknown_codes.extend(structural.get("unknown") or [])
                cited.append(
                    {
                        "handle": handle,
                        "index": claim.get("i"),
                        "ev": list(claim.get("ev") or []),
                    }
                )
                if kind in {"QUESTIONABLE", "UNSUPPORTED"}:
                    reservations.append(
                        {
                            "handle": handle,
                            "index": claim.get("i"),
                            "k": kind,
                            "r": codes,
                            "n": claim.get("n"),
                            "unknown": structural.get("unknown"),
                        }
                    )
                analyzable.append(
                    {
                        "handle": handle,
                        "index": claim.get("i"),
                        "k": kind,
                        "s": start,
                        "e": end,
                        "recovered": recovered,
                        "ev": list(claim.get("ev") or []),
                        "r_raw": codes,
                        "r_unknown": structural.get("unknown"),
                        "n": claim.get("n"),
                        "reason_structural": structural["status"],
                        "span_valid": bool(span.get("valid")),
                    }
                )
    unique_unknown = list(dict.fromkeys(unknown_codes))
    unique_raw = list(dict.fromkeys(raw_codes))
    acceptance = "PASS" if validation.get("status") == "PASS" else "FAIL"
    return {
        "phase": PHASE,
        "acceptance": acceptance,
        "structural_compliance": validation.get("status"),
        "coverage_status": "FAIL"
        if validation.get("coverage_errors")
        else "PASS",
        "reason_code_compliance": "FAIL"
        if validation.get("reason_code_errors")
        else "PASS",
        "diagnostic": {
            "analyzable_propositions": analyzable,
            "valid_spans": valid_spans,
            "cited_evidence": cited,
            "raw_reason_codes": unique_raw,
            "unknown_reason_codes": unique_unknown,
            "identifiable_semantic_reservations": reservations,
            "coverage_errors": list(validation.get("coverage_errors") or []),
            "reason_code_errors": list(validation.get("reason_code_errors") or []),
            "missing_fields": missing_fields,
            "unevaluable": unevaluable,
            "unknown_code_diagnostics": [
                diagnose_unknown_codes("UNSUPPORTED", [code])
                for code in unique_unknown
            ],
        },
        "diagnostic_is_not_acceptance": True,
        "raw_payload_unmodified": True,
        "unknown_codes_preserved_verbatim": True,
        "does_not_rewrite_spans": True,
        "candidate_version": PROMPT_VERSION_113,
        "local_structural_rules": "1.1.2_coverage_and_closed_catalog",
        "secrets_included": False,
    }


def diagnostic_failure_behavior() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "outputs": {
            "A_acceptance": {
                "values": ["PASS", "FAIL"],
                "contract_or_coverage_failure_blocks": True,
            },
            "B_diagnostic": {
                "retained_on_fail": [
                    "analyzable propositions",
                    "valid spans",
                    "cited evidence",
                    "raw reason codes",
                    "unknown reason codes",
                    "identifiable semantic reservations",
                    "coverage errors",
                    "missing fields",
                    "unevaluable elements",
                ],
                "never_converted_to_acceptance": True,
                "never_replaces_raw_data": True,
            },
        },
        "structural_versus_semantic": {
            "structural_compliance": "deterministic local FAIL/PASS",
            "semantic_fidelity": (
                "not claimed fully deterministic when interpretation is required"
            ),
        },
        "secrets_included": False,
    }


__all__ = ["diagnostic_failure_behavior", "extract_failure_diagnostic"]
