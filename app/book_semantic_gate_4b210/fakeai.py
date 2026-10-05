"""FakeAI contract tests for Semantic Gate 2.0. Simulated only. Not Terra quality."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_semantic_gate_4b28.canaries import load_canary_bundle
from app.book_semantic_gate_4b29.engine import evaluate_paragraph
from app.book_semantic_gate_4b29.fakeai import (
    FakeAITransport,
    SCENARIO_NAMES,
    wrap_simulated,
)
from app.book_semantic_gate_4b29.interface import RecordedResponseTransport
from app.book_semantic_gate_4b29.preparation import prepare_paragraph_units
from app.book_semantic_gate_4b29.validator import validate_response_20
from app.book_semantic_gate_4b210.constants import (
    H01_EVIDENCE_HANDLES,
    PHASE,
    SELECTED_CASE_HANDLE,
)
from app.book_semantic_gate_4b210.evidence import selected_evidence_records

EXPECTED_BLOCK = {
    "invented_causality",
    "invented_implication",
    "universal_guarantee",
    "missing_unit",
    "duplicate_unit",
    "unknown_unit",
    "unknown_reason_code",
    "unknown_evidence_handle",
    "incoherent_global_verdict",
    "invalid_json",
    "truncated_response",
    "abusive_non_substantive",
}
EXPECTED_REVIEW = {"questionable"}
EXPECTED_PASS = {"all_supported", "legitimate_paraphrase"}


def run_fakeai_contract_tests(*, root=None) -> dict[str, Any]:
    bundle = load_canary_bundle(root=root)
    text = str((bundle.get(SELECTED_CASE_HANDLE) or {}).get("text") or "")
    evidence = list(H01_EVIDENCE_HANDLES)
    prepared = prepare_paragraph_units(
        SELECTED_CASE_HANDLE,
        text,
        evidence_handles=evidence,
    )
    records = selected_evidence_records(root=root)
    rows = []
    ok = True
    for name in SCENARIO_NAMES:
        transport = FakeAITransport(name, prepared, chapter="CH016")
        result = evaluate_paragraph(
            paragraph_id=SELECTED_CASE_HANDLE,
            text=text,
            transport=transport,
            evidence_handles=evidence,
            evidence_records=records,
            chapter_handle="CH016",
        )
        decision = result.get("decision")
        validation = dict(result.get("validation") or {})
        expected = "PASS"
        if name in EXPECTED_BLOCK:
            expected = "BLOCK"
        elif name in EXPECTED_REVIEW:
            expected = "REVIEW"
        elif name in EXPECTED_PASS:
            expected = "PASS"
        match = decision == expected if name not in EXPECTED_PASS else decision in {"PASS", "REVIEW"}
        if name in EXPECTED_PASS:
            match = decision in {"PASS", "REVIEW"}
        elif name in EXPECTED_REVIEW:
            match = decision == "REVIEW"
        else:
            match = decision == "BLOCK"
        if not match:
            ok = False
        rows.append(
            {
                "scenario": name,
                "source": "FAKEAI_SIMULATED",
                "not_terra": True,
                "decision": decision,
                "expected": expected if name not in EXPECTED_PASS else "PASS_OR_REVIEW",
                "validation_ok": validation.get("ok"),
                "errors": validation.get("errors") or [],
                "match": match,
            }
        )
    extra = _extra_invalid_payloads(prepared)
    extra_ok = all(item.get("blocked") for item in extra)
    return {
        "phase": PHASE,
        "source": "FAKEAI_SIMULATED",
        "not_terra": True,
        "not_a_terra_validation": True,
        "scenario_count": len(rows),
        "scenarios": rows,
        "extra_invalid": extra,
        "passed": ok and extra_ok and len(rows) == len(SCENARIO_NAMES),
        "does_not_silently_repair": True,
        "secrets_included": False,
    }


def _extra_invalid_payloads(prepared: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    cases = {
        "empty_response": "",
        "truncated_object": '{"ch":"CH016","v":"PASS"',
        "forbidden_offset_field": {
            "ch": "CH016",
            "v": "PASS",
            "pr": [{"h": SELECTED_CASE_HANDLE, "v": "SUPPORTED", "u": [], "s": 0}],
            "sc": {
                "supported": 0,
                "questionable": 0,
                "unsupported": 0,
                "non_substantive": 0,
            },
            "uh": [],
            "rr": False,
        },
    }
    for name, payload in cases.items():
        validation = validate_response_20(payload, prepared, expected_chapter="CH016")
        recorded = RecordedResponseTransport(payload)
        raw = recorded.evaluate({})
        wrapped = wrap_simulated(raw, name)
        rows.append(
            {
                "scenario": name,
                "source": wrapped.get("source"),
                "blocked": validation.get("ok") is False,
                "errors": validation.get("errors") or [],
                "not_terra": True,
            }
        )
    return rows


__all__ = ["EXPECTED_BLOCK", "EXPECTED_PASS", "EXPECTED_REVIEW", "run_fakeai_contract_tests"]
