"""Offline FakeAI for 4B.2.6.1. No engine.generate. No network."""

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
from app.book_semantic_gate_4b24.validate import validate_semantic_response
from app.book_semantic_gate_4b261.candidates import expand_candidate_to_historical
from app.book_semantic_gate_4b261.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
from app.book_semantic_gate_4b261.complexity import extract_gate_paragraphs
from app.book_semantic_gate_4b23.reasons import HISTORICAL_REASON_EXPECTATIONS


def simulated_compact_ten_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Scripted compact decisions. Not Terra quality. Offline only."""
    paragraphs = extract_gate_paragraphs(payload)
    by_handle = {str(item.get("handle") or ""): item for item in paragraphs}
    handle_to_case = {handle: case_id for handle, case_id in SCORED_CASE_ORDER}
    pr: list[dict[str, Any]] = []
    counts = {
        "supported": 0,
        "questionable": 0,
        "unsupported": 0,
        "non_substantive": 0,
    }
    for handle, _case_id in SCORED_CASE_ORDER:
        para = by_handle[handle]
        text = str(para.get("text") or "")
        case_id = handle_to_case[handle]
        if case_id == FUNERAL_CASE_ID:
            kind = CLASS_UNSUPPORTED
            reasons = ["INVENTED_EXAMPLE"]
            note = "Funeral illustration absent from evidence."
        elif case_id == CONNECTIVE_CASE_ID:
            kind = CLASS_UNSUPPORTED
            reasons = ["NEW_CONCLUSION"]
            note = "Doctrine-vs-practice contrast is a new conclusion."
        elif case_id == P3_CASE_ID:
            kind = CLASS_QUESTIONABLE
            reasons = ["NEW_CAUSAL_LINK"]
            note = "Secondary because-clause is not in evidence."
        elif case_id == P8_CASE_ID:
            kind = CLASS_QUESTIONABLE
            reasons = ["REFERENCE_COMPLETION"]
            note = "Sting wording completes partial 1 Cor 15."
        elif case_id in POSITIVE_CASE_IDS:
            kind = CLASS_SUPPORTED
            reasons = []
            note = None
        else:
            kind = CLASS_NON_SUBSTANTIVE
            reasons = []
            note = None
        key = {
            CLASS_SUPPORTED: "supported",
            CLASS_QUESTIONABLE: "questionable",
            CLASS_UNSUPPORTED: "unsupported",
            CLASS_NON_SUBSTANTIVE: "non_substantive",
        }[kind]
        counts[key] += 1
        claim: dict[str, Any] = {
            "i": 0,
            "s": 0,
            "e": len(text),
            "k": kind,
            "ev": list(para.get("src") or para.get("ref") or [])[:2],
            "r": reasons,
        }
        if note:
            claim["n"] = note
        pr.append(
            {
                "h": handle,
                "v": kind,
                "c": [claim],
                "ev": list(claim["ev"]),
                "r": reasons,
            }
        )
    unsupported = counts["unsupported"]
    questionable = counts["questionable"]
    verdict = "FAIL" if unsupported else ("REVIEW" if questionable else "PASS")
    return {
        "ch": "CH016",
        "v": verdict,
        "pr": pr,
        "sc": counts,
        "uh": [],
        "rr": questionable > 0,
    }


def interpret_recorded_empty() -> dict[str, Any]:
    required = [handle for handle, _case in SCORED_CASE_ORDER]
    validation = validate_semantic_response(
        None,
        required_handles=required,
        paragraph_texts={handle: "" for handle in required},
    )
    return {
        "json_parse": validation["json_parse"],
        "case_coverage": validation["case_coverage"],
        "missing_cases": validation["missing_cases"],
        "classifications_issued": 0,
        "cache_acceptance": validation["acceptance"]["cache_acceptance"],
        "missing_is_not_misclassification": True,
    }


def interpret_compact_simulation(
    payload: Mapping[str, Any],
    *,
    root=None,
) -> dict[str, Any]:
    compact = simulated_compact_ten_case(payload)
    paragraphs = extract_gate_paragraphs(payload)
    texts = {str(item.get("handle") or ""): str(item.get("text") or "") for item in paragraphs}
    expanded = expand_candidate_to_historical(compact, paragraph_texts=texts)
    required = list(texts)
    validation = validate_semantic_response(
        expanded,
        required_handles=required,
        paragraph_texts=texts,
    )
    rows = list(validation.get("paragraph_results") or [])
    benchmark = load_frozen_benchmark(root=root)
    score = score_benchmark(cases=scored_cases(benchmark), paragraph_results=rows)
    funeral = score.get("funeral") or {}
    connective = score.get("connective") or {}
    p3 = score.get("p3") or {}
    p8 = score.get("p8") or {}
    return {
        "compact": compact,
        "validation": {
            "json_parse": validation.get("json_parse"),
            "case_coverage": validation.get("case_coverage"),
            "span_validation": validation.get("span_validation"),
            "missing_cases": validation.get("missing_cases"),
        },
        "score": {
            "positives_accepted": score.get("positive_accepted"),
            "negatives_blocked": score.get("negative_blocked"),
            "negative_false_negatives": score.get("negative_false_negatives"),
            "funeral_blocked": bool(funeral.get("blocked")),
            "connective_blocked": bool(connective.get("blocked")),
            "p3_blocked": bool(p3.get("blocked")),
            "p8_blocked": bool(p8.get("blocked")),
        },
        "fakeai_not_terra_quality": True,
    }


def catalog_and_invariants() -> dict[str, Any]:
    catalog = run_fakeai_catalog()
    return {
        "historical_fakeai_passed": bool(catalog.get("passed")),
        "historical_fakeai_count": catalog.get("count"),
        "reason_expectations_frozen": {
            "P3": HISTORICAL_REASON_EXPECTATIONS["4b22_p3"]["reason_codes"],
            "P8": HISTORICAL_REASON_EXPECTATIONS["4b22_p8"]["reason_codes"],
            "FUNERAL": HISTORICAL_REASON_EXPECTATIONS["4b2_p8_funeral"]["reason_codes"],
            "CONNECTIVE": HISTORICAL_REASON_EXPECTATIONS["4b2_p13_connective"][
                "reason_codes"
            ],
        },
        "negative_ids": list(NEGATIVE_CASE_IDS),
        "positive_ids": list(POSITIVE_CASE_IDS),
    }


__all__ = [
    "catalog_and_invariants",
    "interpret_compact_simulation",
    "interpret_recorded_empty",
    "simulated_compact_ten_case",
]
