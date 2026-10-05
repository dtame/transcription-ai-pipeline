"""Offline FakeAI for compact 1.1. Not Terra quality. No network."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_semantic_gate_4b23.fakeai import run_fakeai_catalog
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
from app.book_semantic_gate_4b261.fakeai import (
    catalog_and_invariants,
    interpret_compact_simulation,
    interpret_recorded_empty,
    simulated_compact_ten_case,
)
from app.book_semantic_gate_4b262.constants import (
    CLASS_SUPPORTED,
    SELECTED_CASE_HANDLE,
)
from app.book_semantic_gate_4b262.contract import (
    expand_candidate_to_historical,
    unnecessary_duplication_absent,
    validate_compact_payload,
)


def simulated_compact_single_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    paragraphs = extract_gate_paragraphs(payload)
    by_handle = {str(item.get("handle") or ""): item for item in paragraphs}
    para = by_handle[SELECTED_CASE_HANDLE]
    text = str(para.get("text") or "")
    claim = {
        "i": 0,
        "s": 0,
        "e": len(text),
        "k": CLASS_SUPPORTED,
        "ev": list(para.get("src") or para.get("ref") or [])[:2],
        "r": [],
    }
    return {
        "ch": "CH016",
        "v": "PASS",
        "pr": [
            {
                "h": SELECTED_CASE_HANDLE,
                "v": CLASS_SUPPORTED,
                "c": [claim],
                "ev": list(claim["ev"]),
                "r": [],
            }
        ],
        "sc": {
            "supported": 1,
            "questionable": 0,
            "unsupported": 0,
            "non_substantive": 0,
        },
        "uh": [],
        "rr": False,
    }


def interpret_single_case_simulation(
    payload: Mapping[str, Any],
    *,
    root=None,
) -> dict[str, Any]:
    compact = simulated_compact_single_case(payload)
    paragraphs = extract_gate_paragraphs(payload)
    texts = {
        str(item.get("handle") or ""): str(item.get("text") or "") for item in paragraphs
    }
    kinds = {
        str(item.get("handle") or ""): str(item.get("kind") or "substantive")
        for item in paragraphs
    }
    validation = validate_compact_payload(
        compact,
        paragraph_texts=texts,
        required_handles=[SELECTED_CASE_HANDLE],
        paragraph_kinds=kinds,
    )
    return {
        "compact": compact,
        "validation": validation,
        "no_unnecessary_duplication": unnecessary_duplication_absent(compact),
        "fakeai_not_terra_quality": True,
    }


def interpret_ten_case_compact(
    payload: Mapping[str, Any],
    *,
    root=None,
) -> dict[str, Any]:
    compact = simulated_compact_ten_case(payload)
    paragraphs = extract_gate_paragraphs(payload)
    texts = {
        str(item.get("handle") or ""): str(item.get("text") or "") for item in paragraphs
    }
    kinds = {
        str(item.get("handle") or ""): str(item.get("kind") or "substantive")
        for item in paragraphs
    }
    validation = validate_compact_payload(
        compact,
        paragraph_texts=texts,
        required_handles=[handle for handle, _ in SCORED_CASE_ORDER],
        paragraph_kinds=kinds,
    )
    expanded = expand_candidate_to_historical(compact, paragraph_texts=texts)
    from app.book_semantic_gate_4b24.validate import validate_semantic_response

    historical = validate_semantic_response(
        expanded,
        required_handles=list(texts),
        paragraph_texts=texts,
    )
    rows = list(historical.get("paragraph_results") or [])
    benchmark = load_frozen_benchmark(root=root)
    score = score_benchmark(cases=scored_cases(benchmark), paragraph_results=rows)
    return {
        "compact": compact,
        "validation": validation,
        "no_unnecessary_duplication": unnecessary_duplication_absent(compact),
        "score": {
            "positives_accepted": score.get("positive_accepted"),
            "negatives_blocked": score.get("negative_blocked"),
            "negative_false_negatives": score.get("negative_false_negatives"),
            "funeral_blocked": bool((score.get("funeral") or {}).get("blocked")),
            "connective_blocked": bool((score.get("connective") or {}).get("blocked")),
            "p3_blocked": bool((score.get("p3") or {}).get("blocked")),
            "p8_blocked": bool((score.get("p8") or {}).get("blocked")),
        },
        "historical_ids": {
            "positives": list(POSITIVE_CASE_IDS),
            "negatives": list(NEGATIVE_CASE_IDS),
            "funeral": FUNERAL_CASE_ID,
            "connective": CONNECTIVE_CASE_ID,
            "p3": P3_CASE_ID,
            "p8": P8_CASE_ID,
        },
        "fakeai_not_terra_quality": True,
    }


def catalog() -> dict[str, Any]:
    historical = run_fakeai_catalog()
    return {
        **catalog_and_invariants(),
        "historical_catalog_passed": bool(historical.get("passed")),
        "empty_recorded": interpret_recorded_empty(),
    }


__all__ = [
    "catalog",
    "interpret_single_case_simulation",
    "interpret_ten_case_compact",
    "simulated_compact_single_case",
]
