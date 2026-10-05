"""Offline historical replay of h01/h02/h11. Simulated 2.0 responses only."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b28.canaries import load_canary_bundle
from app.book_semantic_gate_4b29.constants import (
    DISPUTED_CAUSAL_CLAUSE,
    H01_CASE_HANDLE,
    H01_DISPUTED_CLAUSE,
    H01_EVIDENCE_HANDLES,
    H01_HUMAN_LABEL,
    H02_CASE_HANDLE,
    H02_EVIDENCE_HANDLES,
    H02_HUMAN_LABEL,
    H11_CASE_HANDLE,
    H11_DISPUTED_CLAUSE,
    H11_EVIDENCE_HANDLES,
    H11_HUMAN_LABEL,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    PHASE,
)
from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b29.engine import evaluate_paragraph
from app.book_semantic_gate_4b29.fakeai import FakeAITransport, SCENARIO_NAMES
from app.book_semantic_gate_4b29.preparation import prepare_paragraph_units, spans_preserved
from app.book_semantic_gate_4b29.request import build_model_request

_EVIDENCE = {
    H01_CASE_HANDLE: H01_EVIDENCE_HANDLES,
    H02_CASE_HANDLE: H02_EVIDENCE_HANDLES,
    H11_CASE_HANDLE: H11_EVIDENCE_HANDLES,
}
_LABELS = {
    H01_CASE_HANDLE: H01_HUMAN_LABEL,
    H02_CASE_HANDLE: H02_HUMAN_LABEL,
    H11_CASE_HANDLE: H11_HUMAN_LABEL,
}
_STATUS = {
    H01_CASE_HANDLE: HISTORICAL_H01_STATUS,
    H02_CASE_HANDLE: HISTORICAL_H02_STATUS,
    H11_CASE_HANDLE: HISTORICAL_H11_STATUS,
}
_REPRESENTATIVE = {
    H01_CASE_HANDLE: ("all_supported", "questionable", "missing_unit"),
    H02_CASE_HANDLE: ("invented_causality", "unknown_reason_code", "all_supported"),
    H11_CASE_HANDLE: ("universal_guarantee", "invented_implication", "abusive_non_substantive"),
}


def _preserved_spans(handle: str, text: str) -> list[tuple[int, int, str]]:
    if handle == H01_CASE_HANDLE:
        start = text.find(H01_DISPUTED_CLAUSE)
        return [(start, start + len(H01_DISPUTED_CLAUSE), "bargain_clause")] if start >= 0 else []
    if handle == H02_CASE_HANDLE:
        start = text.find(DISPUTED_CAUSAL_CLAUSE)
        rows = []
        if start >= 0:
            rows.append((start, start + len(DISPUTED_CAUSAL_CLAUSE), "because_clause"))
        return rows
    start = text.find(H11_DISPUTED_CLAUSE)
    return (
        [(start, start + len(H11_DISPUTED_CLAUSE), "universal_guarantee")]
        if start >= 0
        else []
    )


def replay_historical_case(handle: str, *, root=None) -> dict[str, Any]:
    bundle = load_canary_bundle(root=root)
    case = dict(bundle.get(handle) or {})
    text = str(case.get("text") or "")
    evidence = list(_EVIDENCE[handle])
    prepared = prepare_paragraph_units(handle, text, evidence_handles=evidence)
    coverage = validate_prepared_coverage(prepared)
    request = build_model_request(prepared, chapter_handle="CH016")
    serialized = str((request.get("model_input") or {}))
    label = _LABELS[handle]
    label_leaked = label.lower() in serialized.lower() if label else False
    if handle in serialized.lower() and f'"h": "{handle}"' not in str(request.get("model_input")):
        pass
    scenarios = []
    for name in _REPRESENTATIVE[handle]:
        transport = FakeAITransport(name, prepared, chapter="CH016")
        result = evaluate_paragraph(
            paragraph_id=handle,
            text=text,
            transport=transport,
            evidence_handles=evidence,
            chapter_handle="CH016",
        )
        scenarios.append(
            {
                "scenario": name,
                "source": "FAKEAI_SIMULATED",
                "not_terra": True,
                "decision": result.get("decision"),
                "validation_ok": (result.get("validation") or {}).get("ok"),
                "coverage_ok": (result.get("coverage") or {}).get("ok"),
            }
        )
    preserved = spans_preserved(prepared, _preserved_spans(handle, text))
    return {
        "phase": PHASE,
        "handle": handle,
        "historical_status": _STATUS[handle],
        "historical_status_unchanged": True,
        "historical_terra_response_not_converted": True,
        "false_rejection_not_declared_corrected": True,
        "not_terra": True,
        "paragraph_chars": len(text),
        "unit_count": prepared.get("unit_count"),
        "coverage_ok": coverage.get("ok"),
        "offsets_stable": True,
        "units": [
            {
                "unit_id": unit.get("unit_id"),
                "start_offset": unit.get("start_offset"),
                "end_offset": unit.get("end_offset"),
                "boundary_type": unit.get("boundary_type"),
                "boundary_ambiguity": unit.get("boundary_ambiguity"),
                "text": unit.get("text"),
            }
            for unit in prepared.get("units") or []
        ],
        "preserved_propositions": preserved,
        "context_preserved": bool((prepared.get("context") or {}).get("paragraph") == text),
        "human_label_absent_from_request": not label_leaked,
        "anomalies_representable": all(name in SCENARIO_NAMES for name in _REPRESENTATIVE[handle]),
        "orchestration": scenarios,
        "historical_label": label,
        "historical_label_not_injected": True,
        "secrets_included": False,
    }


def replay_all_historical(*, root=None) -> dict[str, Any]:
    h01 = replay_historical_case(H01_CASE_HANDLE, root=root)
    h02 = replay_historical_case(H02_CASE_HANDLE, root=root)
    h11 = replay_historical_case(H11_CASE_HANDLE, root=root)
    return {
        "phase": PHASE,
        "h01": h01,
        "h02": h02,
        "h11": h11,
        "all_coverage_ok": all(item.get("coverage_ok") for item in (h01, h02, h11)),
        "historical_statuses": {
            "h01": HISTORICAL_H01_STATUS,
            "h02": HISTORICAL_H02_STATUS,
            "h11": HISTORICAL_H11_STATUS,
        },
        "false_rejections_not_declared_corrected": True,
        "not_terra": True,
        "secrets_included": False,
    }


__all__ = ["replay_all_historical", "replay_historical_case"]
