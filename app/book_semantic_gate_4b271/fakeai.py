"""Offline FakeAI fixtures for 4B.2.7.1 calibration. Not Terra quality."""

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
)
from app.book_semantic_gate_4b261.evidence import load_4b26_bundle
from app.book_semantic_gate_4b262.fakeai import interpret_ten_case_compact
from app.book_semantic_gate_4b262.contract import validate_compact_payload
from app.book_semantic_gate_4b271.constants import (
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    PHASE,
)
from app.book_semantic_gate_4b271.coverage import validate_compact_payload_111


def _compact(
    text: str,
    *,
    kind: str,
    reasons: list[str] | None = None,
    note: str | None = None,
    start: int | None = None,
    end: int | None = None,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    claim: dict[str, Any] = {
        "i": 0,
        "s": 0 if start is None else start,
        "e": len(text) if end is None else end,
        "k": kind,
        "ev": list(evidence or ["SRC001"]),
        "r": list(reasons or []),
    }
    if note:
        claim["n"] = note
    counts = {
        "SUPPORTED": 0,
        "QUESTIONABLE": 0,
        "UNSUPPORTED": 0,
        "NON_SUBSTANTIVE": 0,
    }
    counts[kind] = 1
    verdict = "FAIL" if kind == CLASS_UNSUPPORTED else (
        "REVIEW" if kind == CLASS_QUESTIONABLE else "PASS"
    )
    return {
        "ch": "CH016",
        "v": verdict,
        "pr": [
            {
                "h": "hX",
                "v": kind,
                "c": [claim],
                "ev": list(claim["ev"]),
                "r": list(claim["r"]),
            }
        ],
        "sc": {
            "supported": counts["SUPPORTED"],
            "questionable": counts["QUESTIONABLE"],
            "unsupported": counts["UNSUPPORTED"],
            "non_substantive": counts["NON_SUBSTANTIVE"],
        },
        "uh": [],
        "rr": kind == CLASS_QUESTIONABLE,
    }


def fixture_semantic_equivalence() -> dict[str, Any]:
    text = "There is no appointed hour available to fear."
    parsed = _compact(text, kind=CLASS_SUPPORTED, evidence=["IDEA001"])
    return {
        "name": "semantic_equivalence_of_attested_absence",
        "evidence": "there is no set time",
        "text": text,
        "parsed": parsed,
        "expect_class": CLASS_SUPPORTED,
        "note": "Generic restatement. Not an h01 gold label.",
    }


def fixture_new_causality() -> dict[str, Any]:
    text = "Fear is visible because the strategy still works."
    parsed = _compact(
        text,
        kind=CLASS_QUESTIONABLE,
        reasons=["NEW_CAUSAL_LINK"],
        note="Because-clause is not in evidence.",
    )
    return {
        "name": "new_causality",
        "text": text,
        "parsed": parsed,
        "expect_class": CLASS_QUESTIONABLE,
        "expect_reasons": ["NEW_CAUSAL_LINK"],
    }


def fixture_invented_example() -> dict[str, Any]:
    text = "Death as gain is not a verse quoted at funerals."
    parsed = _compact(
        text,
        kind=CLASS_UNSUPPORTED,
        reasons=["INVENTED_EXAMPLE"],
        note="Funeral illustration absent.",
    )
    return {
        "name": "invented_example",
        "text": text,
        "parsed": parsed,
        "expect_class": CLASS_UNSUPPORTED,
        "expect_reasons": ["INVENTED_EXAMPLE"],
    }


def fixture_reference_completion() -> dict[str, Any]:
    text = "1 Corinthians 15 so the sting is already gone."
    parsed = _compact(
        text,
        kind=CLASS_QUESTIONABLE,
        reasons=["REFERENCE_COMPLETION"],
        note="Sting wording completes a partial reference.",
    )
    return {
        "name": "reference_completion",
        "text": text,
        "parsed": parsed,
        "expect_class": CLASS_QUESTIONABLE,
        "expect_reasons": ["REFERENCE_COMPLETION"],
    }


def fixture_new_implication() -> dict[str, Any]:
    text = "The difference was not doctrine known, but Christ practiced."
    parsed = _compact(
        text,
        kind=CLASS_UNSUPPORTED,
        reasons=["NEW_CONCLUSION"],
        note="New contrast-conclusion.",
    )
    return {
        "name": "new_implication",
        "text": text,
        "parsed": parsed,
        "expect_class": CLASS_UNSUPPORTED,
        "expect_reasons": ["NEW_CONCLUSION"],
    }


def fixture_missing_reason_code() -> dict[str, Any]:
    text = "An unsupported extension."
    parsed = _compact(
        text,
        kind=CLASS_QUESTIONABLE,
        reasons=[],
        note="Reservation without a reason code.",
    )
    return {
        "name": "missing_reason_code",
        "text": text,
        "parsed": parsed,
        "expect_111_status": "FAIL",
    }


def _validate(parsed: Mapping[str, Any], text: str) -> dict[str, Any]:
    return validate_compact_payload_111(
        parsed,
        paragraph_texts={"hX": text},
        required_handles=["hX"],
        paragraph_kinds={"hX": "substantive"},
    )


def run_calibration_fixtures() -> dict[str, Any]:
    rows = [
        fixture_semantic_equivalence(),
        fixture_new_causality(),
        fixture_invented_example(),
        fixture_reference_completion(),
        fixture_new_implication(),
        fixture_missing_reason_code(),
    ]
    results = []
    passed = True
    for row in rows:
        text = str(row["text"])
        parsed = dict(row["parsed"])
        validation = _validate(parsed, text)
        expected_status = row.get("expect_111_status")
        para = (parsed.get("pr") or [{}])[0]
        kind = str(para.get("v") or "")
        if row["name"] == "missing_reason_code":
            ok = "hX: reason_code_missing" in (validation.get("reason_code_warnings") or [])
        elif expected_status:
            ok = validation.get("status") == expected_status
        else:
            ok = validation.get("status") == "PASS"
            if row.get("expect_class"):
                ok = ok and kind == row["expect_class"]
            if row.get("expect_reasons"):
                got = list((para.get("c") or [{}])[0].get("r") or [])
                ok = ok and got == row["expect_reasons"]
        passed = passed and ok
        results.append(
            {
                "name": row["name"],
                "ok": ok,
                "validation_status": validation.get("status"),
                "class": (parsed.get("pr") or [{}])[0].get("v"),
            }
        )
    return {
        "phase": PHASE,
        "fixtures": results,
        "passed": passed,
        "fakeai_not_terra_quality": True,
        "h01_gold_label_not_hardcoded": True,
    }


def historical_ten_case_protection(*, root=None) -> dict[str, Any]:
    bundle = load_4b26_bundle(root=root)
    ten = interpret_ten_case_compact(dict(bundle.get("payload") or {}), root=root)
    score = dict(ten.get("score") or {})
    return {
        "phase": PHASE,
        "positives_accepted": score.get("positives_accepted"),
        "negatives_blocked": score.get("negatives_blocked"),
        "funeral_blocked": score.get("funeral_blocked"),
        "connective_blocked": score.get("connective_blocked"),
        "p3_blocked": score.get("p3_blocked"),
        "p8_blocked": score.get("p8_blocked"),
        "negative_ids": list(NEGATIVE_CASE_IDS),
        "positive_ids": list(POSITIVE_CASE_IDS),
        "protected": {
            FUNERAL_CASE_ID: bool(score.get("funeral_blocked")),
            CONNECTIVE_CASE_ID: bool(score.get("connective_blocked")),
            P3_CASE_ID: bool(score.get("p3_blocked")),
            P8_CASE_ID: bool(score.get("p8_blocked")),
        },
        "historical_catalog_passed": bool(run_fakeai_catalog().get("passed")),
        "fakeai_not_terra_quality": True,
        "labels_unmodified": True,
    }


def frozen_1_1_still_flags_terra_periods(payload: Mapping[str, Any], text: str) -> dict[str, Any]:
    result = validate_compact_payload(
        payload,
        paragraph_texts={"h01": text},
        required_handles=["h01"],
        paragraph_kinds={"h01": "substantive"},
    )
    refined = validate_compact_payload_111(
        payload,
        paragraph_texts={"h01": text},
        required_handles=["h01"],
        paragraph_kinds={"h01": "substantive"},
    )
    return {
        "frozen_1_1_status": result.get("status"),
        "frozen_1_1_coverage_errors": result.get("coverage_errors"),
        "candidate_1_1_1_status": refined.get("status"),
        "candidate_1_1_1_coverage_errors": refined.get("coverage_errors"),
        "frozen_contract_not_mutated": True,
    }


__all__ = [
    "fixture_invented_example",
    "fixture_missing_reason_code",
    "fixture_new_causality",
    "fixture_new_implication",
    "fixture_reference_completion",
    "fixture_semantic_equivalence",
    "frozen_1_1_still_flags_terra_periods",
    "historical_ten_case_protection",
    "run_calibration_fixtures",
]
