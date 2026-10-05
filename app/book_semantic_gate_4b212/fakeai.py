"""FakeAI negative fixtures for contract 2.0.2. Simulated only. Not Terra quality."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b210.units import inspect_prepared_case
from app.book_semantic_gate_4b212.constants import (
    DECISION_BLOCK,
    DECISION_PASS,
    DECISION_REVIEW,
    FIXTURE_KIND,
    PHASE,
    SELECTED_CASE_HANDLE,
)
from app.book_semantic_gate_4b212.policy import apply_acceptance_policy_202
from app.book_semantic_gate_4b212.validator import validate_response_202

FAKEAI_SOURCE = "FAKEAI_SIMULATED"


def _ids(prepared: Mapping[str, Any]) -> list[str]:
    return [str(unit.get("unit_id") or "") for unit in prepared.get("units") or []]


def _evidence(prepared: Mapping[str, Any]) -> list[str]:
    return list(prepared.get("evidence_handles") or [])


def _row(
    unit_id: str,
    kind: str,
    *,
    evidence: list[str] | None = None,
    reasons: list[str] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": unit_id,
        "k": kind,
        "ev": list(evidence or []),
        "r": list(reasons or []),
    }
    if note:
        row["n"] = note
    return row


def _payload(prepared: Mapping[str, Any], rows: list[dict[str, Any]], *, chapter: str = "CH016") -> dict[str, Any]:
    return {
        "ch": chapter,
        "pr": [{"h": str(prepared.get("paragraph_id") or ""), "u": rows}],
    }


def _supported_rows(prepared: Mapping[str, Any]) -> list[dict[str, Any]]:
    ev = _evidence(prepared)[:1]
    return [_row(uid, CLASS_SUPPORTED, evidence=ev) for uid in _ids(prepared)]


def _replace(prepared: Mapping[str, Any], target: str, row: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for uid in _ids(prepared):
        if uid == target:
            rows.append(row)
        else:
            rows.append(_row(uid, CLASS_SUPPORTED, evidence=_evidence(prepared)[:1]))
    return rows


def build_scenario_payload(name: str, prepared: Mapping[str, Any]) -> Any:
    ids = _ids(prepared)
    ev = _evidence(prepared)[:1]
    first = ids[0] if ids else "u00"
    if name == "invented_causality":
        return _payload(
            prepared,
            _replace(
                prepared,
                first,
                _row(
                    first,
                    CLASS_UNSUPPORTED,
                    evidence=ev,
                    reasons=["NEW_CAUSAL_LINK"],
                    note="Invented causality is not in the supplied evidence.",
                ),
            ),
        )
    if name == "invented_implication":
        return _payload(
            prepared,
            _replace(
                prepared,
                first,
                _row(
                    first,
                    CLASS_UNSUPPORTED,
                    evidence=ev,
                    reasons=["NEW_IMPLICATION"],
                    note="Implication is not demonstrated by the evidence.",
                ),
            ),
        )
    if name == "universal_guarantee":
        return _payload(
            prepared,
            _replace(
                prepared,
                first,
                _row(
                    first,
                    CLASS_UNSUPPORTED,
                    evidence=ev,
                    reasons=["UNCERTAINTY_STRENGTHENED"],
                    note="Universal guarantee is not supported.",
                ),
            ),
        )
    if name == "unjustified_strengthening":
        return _payload(
            prepared,
            _replace(
                prepared,
                first,
                _row(
                    first,
                    CLASS_UNSUPPORTED,
                    evidence=ev,
                    reasons=["UNCERTAINTY_STRENGTHENED"],
                    note="Certainty is stronger than the evidence.",
                ),
            ),
        )
    if name == "unsupported_attribution":
        return _payload(
            prepared,
            _replace(
                prepared,
                first,
                _row(
                    first,
                    CLASS_UNSUPPORTED,
                    evidence=ev,
                    reasons=["NEW_FACT"],
                    note="Attribution is not attested.",
                ),
            ),
        )
    if name == "invented_example":
        return _payload(
            prepared,
            _replace(
                prepared,
                first,
                _row(
                    first,
                    CLASS_UNSUPPORTED,
                    evidence=ev,
                    reasons=["INVENTED_EXAMPLE"],
                    note="Example is not in the supplied evidence.",
                ),
            ),
        )
    if name == "legitimate_paraphrase":
        return _payload(prepared, _supported_rows(prepared))
    if name == "faithful_reference":
        return _payload(prepared, _supported_rows(prepared))
    if name == "reference_completed_without_proof":
        return _payload(
            prepared,
            _replace(
                prepared,
                first,
                _row(
                    first,
                    CLASS_UNSUPPORTED,
                    evidence=ev,
                    reasons=["REFERENCE_COMPLETION"],
                    note="Reference remainder is not in the supplied evidence.",
                ),
            ),
        )
    if name == "unknown_reason_code":
        return _payload(
            prepared,
            _replace(
                prepared,
                first,
                _row(
                    first,
                    CLASS_UNSUPPORTED,
                    evidence=ev,
                    reasons=["MADE_UP_CODE"],
                    note="Unknown reason code fixture.",
                ),
            ),
        )
    if name == "unknown_evidence_handle":
        return _payload(
            prepared,
            _replace(
                prepared,
                first,
                _row(first, CLASS_SUPPORTED, evidence=["SRC999999"]),
            ),
        )
    if name == "missing_unit":
        return _payload(prepared, _supported_rows(prepared)[:-1] or [])
    if name == "duplicate_unit":
        rows = _supported_rows(prepared)
        if rows:
            rows.append(dict(rows[0]))
        return _payload(prepared, rows)
    if name == "invalid_classification":
        return _payload(
            prepared,
            _replace(prepared, first, _row(first, "MAYBE", evidence=ev)),
        )
    if name == "operational_value_in_semantic_field":
        return _payload(
            prepared,
            _replace(prepared, first, _row(first, "PASS", evidence=ev)),
        )
    if name == "invalid_json":
        return "{not json"
    if name == "truncated_response":
        return '{"ch":"CH016","pr":['
    if name == "questionable":
        return _payload(
            prepared,
            _replace(
                prepared,
                first,
                _row(
                    first,
                    CLASS_QUESTIONABLE,
                    evidence=ev,
                    reasons=["OTHER"],
                    note="Reservation requires human review.",
                ),
            ),
        )
    if name == "abusive_non_substantive":
        return _payload(
            prepared,
            _replace(prepared, first, _row(first, CLASS_NON_SUBSTANTIVE, evidence=[])),
        )
    if name == "lowercase_classification":
        return _payload(
            prepared,
            _replace(prepared, first, _row(first, "supported", evidence=ev)),
        )
    raise KeyError(name)


SCENARIO_EXPECTATIONS = {
    "invented_causality": DECISION_BLOCK,
    "invented_implication": DECISION_BLOCK,
    "universal_guarantee": DECISION_BLOCK,
    "unjustified_strengthening": DECISION_BLOCK,
    "unsupported_attribution": DECISION_BLOCK,
    "invented_example": DECISION_BLOCK,
    "legitimate_paraphrase": DECISION_PASS,
    "faithful_reference": DECISION_PASS,
    "reference_completed_without_proof": DECISION_BLOCK,
    "unknown_reason_code": DECISION_BLOCK,
    "unknown_evidence_handle": DECISION_BLOCK,
    "missing_unit": DECISION_BLOCK,
    "duplicate_unit": DECISION_BLOCK,
    "invalid_classification": DECISION_BLOCK,
    "operational_value_in_semantic_field": DECISION_BLOCK,
    "invalid_json": DECISION_BLOCK,
    "truncated_response": DECISION_BLOCK,
    "questionable": DECISION_REVIEW,
    "abusive_non_substantive": DECISION_BLOCK,
    "lowercase_classification": DECISION_BLOCK,
}

SCENARIO_NAMES = tuple(SCENARIO_EXPECTATIONS.keys())


def run_negative_fakeai_tests(*, root=None) -> dict[str, Any]:
    inspected = inspect_prepared_case(SELECTED_CASE_HANDLE, root=root)
    prepared = dict(inspected.get("prepared") or {})
    coverage = validate_prepared_coverage(prepared)
    rows = []
    ok = True
    for name in SCENARIO_NAMES:
        payload = build_scenario_payload(name, prepared)
        validation = validate_response_202(
            payload,
            prepared,
            allowed_evidence=list(prepared.get("evidence_handles") or []),
            expected_chapter="CH016",
        )
        policy = apply_acceptance_policy_202(prepared, coverage, validation)
        expected = SCENARIO_EXPECTATIONS[name]
        match = policy.get("decision") == expected
        if not match:
            ok = False
        rows.append(
            {
                "scenario": name,
                "source": FAKEAI_SOURCE,
                "not_terra": True,
                "fixture_kind": FIXTURE_KIND if isinstance(payload, dict) else "RAW_INVALID",
                "decision": policy.get("decision"),
                "expected": expected,
                "contract_ok": validation.get("ok"),
                "errors": validation.get("errors") or [],
                "match": match,
                "does_not_prove_terra_detection": True,
            }
        )
    extra = _no_silent_normalization(prepared)
    extra_ok = all(item.get("blocked") for item in extra)
    return {
        "phase": PHASE,
        "source": FAKEAI_SOURCE,
        "not_terra": True,
        "not_a_terra_validation": True,
        "does_not_claim_terra_can_detect_these_errors": True,
        "scenario_count": len(rows),
        "scenarios": rows,
        "no_silent_normalization": extra,
        "passed": ok and extra_ok and len(rows) == len(SCENARIO_NAMES),
        "does_not_silently_repair": True,
        "secrets_included": False,
    }


def _no_silent_normalization(prepared: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    historical_like = {
        "ch": "CH016",
        "v": "PASS",
        "pr": [
            {
                "h": str(prepared.get("paragraph_id") or ""),
                "v": "PASS",
                "u": _supported_rows(prepared),
            }
        ],
        "sc": {
            "SUPPORTED": len(_ids(prepared)),
            "QUESTIONABLE": 0,
            "UNSUPPORTED": 0,
            "NON_SUBSTANTIVE": 0,
        },
        "uh": [],
        "rr": False,
    }
    cases = {
        "historical_201_shape_not_accepted_as_202": historical_like,
        "pass_not_converted_to_supported": build_scenario_payload(
            "operational_value_in_semantic_field", prepared
        ),
        "lowercase_not_converted_to_uppercase": build_scenario_payload(
            "lowercase_classification", prepared
        ),
        "empty": "",
        "truncated": '{"ch":"CH016"',
    }
    for name, payload in cases.items():
        validation = validate_response_202(payload, prepared, expected_chapter="CH016")
        rows.append(
            {
                "scenario": name,
                "blocked": validation.get("ok") is False,
                "errors": validation.get("errors") or [],
                "not_terra": True,
                "raw_preserved": True if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)[:80],
            }
        )
    return rows


__all__ = [
    "SCENARIO_EXPECTATIONS",
    "SCENARIO_NAMES",
    "build_scenario_payload",
    "run_negative_fakeai_tests",
]
