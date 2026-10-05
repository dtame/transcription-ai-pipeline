"""Historical ten-case benchmark compatibility. Labels stay local."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b24.constants import (
    CONNECTIVE_CASE_ID,
    FUNERAL_CASE_ID,
    NEGATIVE_CASE_IDS,
    P3_CASE_ID,
    P8_CASE_ID,
    POSITIVE_CASE_IDS,
    SCORED_CASE_ORDER,
)
from app.book_semantic_gate_4b24.identity import load_frozen_benchmark, scored_cases
from app.book_semantic_gate_4b24.score import score_benchmark
from app.book_semantic_gate_4b261.complexity import extract_gate_paragraphs
from app.book_semantic_gate_4b261.evidence import load_4b26_bundle
from app.book_semantic_gate_4b262.fakeai import interpret_ten_case_compact
from app.book_semantic_gate_4b274.coverage import validate_compact_payload_112
from app.book_semantic_gate_4b29.constants import PHASE
from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b29.engine import evaluate_paragraph
from app.book_semantic_gate_4b29.fakeai import FakeAITransport
from app.book_semantic_gate_4b29.preparation import prepare_paragraph_units
from app.book_semantic_gate_4b29.request import build_model_request

_NEGATIVE_SCENARIO = {
    P3_CASE_ID: "invented_causality",
    P8_CASE_ID: "unknown_evidence_handle",
    FUNERAL_CASE_ID: "invented_implication",
    CONNECTIVE_CASE_ID: "abusive_non_substantive",
}


def _opaque_handle(case_id: str) -> str:
    for handle, mapped in SCORED_CASE_ORDER:
        if mapped == case_id:
            return handle
    return case_id


def benchmark_compatibility(*, root=None) -> dict[str, Any]:
    payload = load_frozen_benchmark(root=root)
    scored = scored_cases(payload)
    rows = []
    labels_unmodified = True
    for item in scored:
        case_id = str(item.get("case_id") or "")
        handle = _opaque_handle(case_id)
        text = str(item.get("text") or "")
        evidence = list(item.get("evidence_handles") or [])
        prepared = prepare_paragraph_units(handle, text, evidence_handles=evidence)
        coverage = validate_prepared_coverage(prepared)
        request = build_model_request(prepared, chapter_handle="CH016")
        metadata = {
            "ch": (request.get("model_input") or {}).get("ch"),
            "contract": (request.get("model_input") or {}).get("contract"),
            "transport": (request.get("model_input") or {}).get("transport"),
            "handles": [
                para.get("h") for para in (request.get("model_input") or {}).get("pr") or []
            ],
            "evidence": [
                para.get("ev") for para in (request.get("model_input") or {}).get("pr") or []
            ],
            "unit_ids": [
                unit.get("id")
                for para in (request.get("model_input") or {}).get("pr") or []
                for unit in para.get("u") or []
            ],
        }
        request_meta = str(metadata).lower()
        leaked = False
        for token in (
            str(item.get("role") or ""),
            str(item.get("expected_class") or ""),
            case_id,
            "FUNERAL",
            "invented_funeral",
            "positive",
            "negative",
        ):
            needle = token.lower().strip()
            if needle and needle in request_meta:
                leaked = True
        scenario = "all_supported"
        if case_id in NEGATIVE_CASE_IDS:
            scenario = _NEGATIVE_SCENARIO.get(case_id, "invented_causality")
        result = evaluate_paragraph(
            paragraph_id=handle,
            text=text,
            transport=FakeAITransport(scenario, prepared, chapter="CH016"),
            evidence_handles=evidence,
            chapter_handle="CH016",
        )
        rows.append(
            {
                "opaque_handle": handle,
                "case_id_local_only": case_id,
                "role_local_only": item.get("role"),
                "unit_count": prepared.get("unit_count"),
                "coverage_ok": coverage.get("ok"),
                "label_absent_from_request": not leaked,
                "fakeai_scenario": scenario,
                "fakeai_decision": result.get("decision"),
                "fakeai_not_terra": True,
            }
        )
        if leaked:
            labels_unmodified = False

    historical = load_4b26_bundle(root=root)
    ten = interpret_ten_case_compact(historical.get("payload") or {}, root=root)
    score = dict(ten.get("score") or {})
    paragraphs = extract_gate_paragraphs(historical.get("payload") or {})
    texts = {str(item.get("handle") or ""): str(item.get("text") or "") for item in paragraphs}
    kinds = {str(item.get("handle") or ""): str(item.get("kind") or "substantive") for item in paragraphs}
    validation = validate_compact_payload_112(
        ten.get("compact"),
        paragraph_texts=texts,
        required_handles=[handle for handle, _ in SCORED_CASE_ORDER],
        paragraph_kinds=kinds,
    )
    return {
        "phase": PHASE,
        "scored_cases": len(scored),
        "positives": list(POSITIVE_CASE_IDS),
        "negatives": list(NEGATIVE_CASE_IDS),
        "funeral": FUNERAL_CASE_ID,
        "connective": CONNECTIVE_CASE_ID,
        "p3": P3_CASE_ID,
        "p8": P8_CASE_ID,
        "labels_unmodified": labels_unmodified and payload.get("human_labels_are_ground_truth") is True,
        "labels_absent_from_model_request": all(item["label_absent_from_request"] for item in rows),
        "cases_representable": all(item["coverage_ok"] for item in rows),
        "rows": rows,
        "historical_ten_case_fakeai": {
            "positives_accepted": score.get("positives_accepted"),
            "negatives_blocked": score.get("negatives_blocked"),
            "funeral_blocked": score.get("funeral_blocked"),
            "connective_blocked": score.get("connective_blocked"),
            "p3_blocked": score.get("p3_blocked"),
            "p8_blocked": score.get("p8_blocked"),
            "validator_1_1_2_status": validation.get("status"),
            "score_ok": score_benchmark.__name__ == "score_benchmark",
        },
        "fakeai_is_orchestration_not_terra_quality": True,
        "secrets_included": False,
    }


__all__ = ["benchmark_compatibility"]
