"""Offline FakeAI, reason-code, and coverage fixtures. Not Terra quality."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_semantic_gate_4b23.constants import (
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
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
from app.book_semantic_gate_4b271.fakeai import run_calibration_fixtures
from app.book_semantic_gate_4b274.constants import PHASE
from app.book_semantic_gate_4b274.coverage import (
    KIND_SEPARATOR,
    KIND_SIGNIFICANT,
    KIND_TERMINATOR,
    classify_uncovered_gaps_112,
    uncovered_significant_spans_112,
    validate_compact_payload_112,
    validate_coverage,
)
from app.book_semantic_gate_4b274.reasons import classify_reason_payload


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
        "supported": int(kind == CLASS_SUPPORTED),
        "questionable": int(kind == CLASS_QUESTIONABLE),
        "unsupported": int(kind == CLASS_UNSUPPORTED),
        "non_substantive": 0,
    }
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
        "sc": counts,
        "uh": [],
        "rr": kind == CLASS_QUESTIONABLE,
    }


def _validate(parsed: Mapping[str, Any], text: str) -> dict[str, Any]:
    return validate_compact_payload_112(
        parsed,
        paragraph_texts={"hX": text},
        required_handles=["hX"],
        paragraph_kinds={"hX": "substantive"},
    )


def reason_code_fixtures() -> dict[str, Any]:
    text = "Because the strategy still works, an example is invented."
    cases = [
        {
            "name": "canonical_valid",
            "result": classify_reason_payload(
                classification=CLASS_QUESTIONABLE, reasons=["NEW_CAUSAL_LINK"]
            ),
            "expect": "PASS",
        },
        {
            "name": "unknown_code",
            "result": classify_reason_payload(
                classification=CLASS_UNSUPPORTED, reasons=["INVENTED_CAUSAL_LINK"]
            ),
            "expect": "FAIL",
        },
        {
            "name": "empty_on_questionable",
            "result": classify_reason_payload(
                classification=CLASS_QUESTIONABLE, reasons=[]
            ),
            "expect": "FAIL",
        },
        {
            "name": "empty_on_unsupported",
            "result": classify_reason_payload(
                classification=CLASS_UNSUPPORTED, reasons=[]
            ),
            "expect": "FAIL",
        },
        {
            "name": "unexpected_on_supported",
            "result": classify_reason_payload(
                classification=CLASS_SUPPORTED, reasons=["NEW_FACT"]
            ),
            "expect": "FAIL",
        },
        {
            "name": "multiple_valid_compatible",
            "result": classify_reason_payload(
                classification=CLASS_QUESTIONABLE,
                reasons=["NEW_CAUSAL_LINK", "NEW_IMPLICATION"],
            ),
            "expect": "PASS",
        },
        {
            "name": "valid_code_other_category",
            "result": classify_reason_payload(
                classification=CLASS_UNSUPPORTED, reasons=["INVENTED_EXAMPLE"]
            ),
            "expect": "PASS",
            "note": "Structural PASS. Semantic category fit is diagnostic-only.",
        },
        {
            "name": "close_but_absent",
            "result": classify_reason_payload(
                classification=CLASS_QUESTIONABLE, reasons=["UNSUPPORTED_IMPLICATION"]
            ),
            "expect": "FAIL",
        },
        {
            "name": "invented",
            "result": classify_reason_payload(
                classification=CLASS_UNSUPPORTED, reasons=["MADE_UP_CODE"]
            ),
            "expect": "FAIL",
        },
        {
            "name": "wrong_case",
            "result": classify_reason_payload(
                classification=CLASS_QUESTIONABLE, reasons=["new_causal_link"]
            ),
            "expect": "FAIL",
        },
    ]
    rows = []
    passed = True
    for item in cases:
        ok = item["result"]["status"] == item["expect"]
        if item["name"] == "unknown_code":
            ok = ok and item["result"]["silently_accepted_unknown"] is False
        passed = passed and ok
        rows.append({"name": item["name"], "ok": ok, "status": item["result"]["status"]})
    payload = _compact(
        text,
        kind=CLASS_QUESTIONABLE,
        reasons=["INVENTED_CAUSAL_LINK"],
        note="Unknown code must fail.",
    )
    unknown_payload = _validate(payload, text)
    empty_payload = _validate(
        _compact(text, kind=CLASS_QUESTIONABLE, reasons=[], note="missing code"),
        text,
    )
    return {
        "phase": PHASE,
        "cases": rows,
        "passed": passed,
        "unknown_never_silently_accepted": unknown_payload["status"] == "FAIL",
        "empty_questionable_fails_112": empty_payload["status"] == "FAIL",
        "payload_unknown_errors": unknown_payload.get("reason_code_errors"),
        "normalization_not_applied": True,
    }


def _claims_covering(text: str, *spans: str) -> list[dict[str, int]]:
    claims: list[dict[str, int]] = []
    cursor = 0
    for span in spans:
        start = text.find(span, cursor)
        if start < 0:
            raise ValueError(f"span {span!r} not found in {text!r}")
        claims.append({"s": start, "e": start + len(span)})
        cursor = start + len(span)
    return claims


def coverage_fixtures() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []

    def add(name: str, text: str, claims: list[dict[str, Any]], expect_fail: bool) -> None:
        audit = validate_coverage(text, claims)
        significant = uncovered_significant_spans_112(text, claims)
        ok = (audit["status"] == "FAIL") is expect_fail
        if name == "terminal_period":
            ok = ok and not significant
            classified = classify_uncovered_gaps_112(text, claims)
            ok = ok and any(item["kind"] == KIND_TERMINATOR for item in classified)
        if name == "separator_comma":
            ok = ok and any(
                item["kind"] == KIND_SEPARATOR
                for item in classify_uncovered_gaps_112(text, claims)
            )
        if name in {
            "omitted_word",
            "omitted_negation",
            "omitted_because",
            "omitted_unless",
            "omitted_however",
            "omitted_only_if",
            "omitted_clause",
        }:
            ok = ok and significant and any(
                item["kind"] == KIND_SIGNIFICANT
                for item in classify_uncovered_gaps_112(text, claims)
            )
        cases.append(
            {
                "name": name,
                "ok": ok,
                "status": audit["status"],
                "significant": [list(item) for item in significant],
            }
        )

    add("terminal_period", "Hello world.", _claims_covering("Hello world.", "Hello world"), False)
    add(
        "separator_comma",
        "Alpha, beta.",
        _claims_covering("Alpha, beta.", "Alpha", "beta"),
        False,
    )
    add(
        "separator_semicolon",
        "Alpha; beta.",
        _claims_covering("Alpha; beta.", "Alpha", "beta"),
        False,
    )
    add(
        "em_dash",
        "Alpha — beta.",
        _claims_covering("Alpha — beta.", "Alpha", "beta"),
        False,
    )
    add(
        "colon",
        "Alpha: beta.",
        _claims_covering("Alpha: beta.", "Alpha", "beta"),
        False,
    )
    add(
        "parentheses",
        "Alpha (beta) end.",
        _claims_covering("Alpha (beta) end.", "Alpha", "beta", "end"),
        False,
    )
    add(
        "quotes",
        'Alpha "beta" end.',
        _claims_covering('Alpha "beta" end.', "Alpha", "beta", "end"),
        False,
    )
    add(
        "apostrophe_internal_gap",
        "don't",
        _claims_covering("don't", "don", "t"),
        False,
    )
    add("ellipsis", "Wait…", _claims_covering("Wait…", "Wait"), False)
    add(
        "unicode_space",
        "ab\u00a0cd",
        _claims_covering("ab\u00a0cd", "ab", "cd"),
        False,
    )
    add(
        "omitted_word",
        "Alpha because beta.",
        _claims_covering("Alpha because beta.", "Alpha", "beta"),
        True,
    )
    add("omitted_negation", "Do not go.", _claims_covering("Do not go.", "Do"), True)
    add(
        "omitted_because",
        "True because false.",
        _claims_covering("True because false.", "True", "false"),
        True,
    )
    add(
        "omitted_unless",
        "Stay unless told.",
        _claims_covering("Stay unless told.", "Stay", "told"),
        True,
    )
    add(
        "omitted_however",
        "Yes however no.",
        _claims_covering("Yes however no.", "Yes", "no"),
        True,
    )
    add(
        "omitted_only_if",
        "Go only if ready.",
        _claims_covering("Go only if ready.", "Go", "ready"),
        True,
    )
    add(
        "omitted_clause",
        "First sentence. Second withheld claim.",
        _claims_covering("First sentence. Second withheld claim.", "First sentence"),
        True,
    )
    inverted = validate_coverage("abcd", [{"s": 3, "e": 1}])
    cases.append(
        {
            "name": "inverted_span",
            "ok": inverted["status"] == "FAIL",
            "status": inverted["status"],
            "significant": inverted["significant_intervals"],
        }
    )
    oob = validate_coverage("abcd", [{"s": 0, "e": 9}])
    cases.append(
        {
            "name": "out_of_bounds",
            "ok": oob["status"] == "FAIL",
            "status": oob["status"],
            "significant": oob["significant_intervals"],
        }
    )
    empty = validate_coverage("abcd", [{"s": 1, "e": 1}])
    cases.append(
        {
            "name": "empty_span",
            "ok": empty["status"] == "FAIL",
            "status": empty["status"],
            "significant": empty["significant_intervals"],
        }
    )
    overlap = validate_coverage(
        "abcdef",
        [{"s": 0, "e": 4}, {"s": 2, "e": 6}],
    )
    cases.append(
        {
            "name": "overlaps",
            "ok": overlap["span_validity"]["overlap_inconsistent"] is True
            and overlap["status"] == "PASS",
            "status": overlap["status"],
            "significant": overlap["significant_intervals"],
        }
    )
    add(
        "discontinuous",
        "alpha beta gamma",
        _claims_covering("alpha beta gamma", "alpha", "gamma"),
        True,
    )
    add(
        "adjacent_propositions",
        "One. Two.",
        _claims_covering("One. Two.", "One", "Two"),
        False,
    )
    add(
        "multiline",
        "One.\nTwo.",
        _claims_covering("One.\nTwo.", "One", "Two"),
        False,
    )
    passed = all(item["ok"] for item in cases)
    return {
        "phase": PHASE,
        "cases": cases,
        "passed": passed,
        "punctuation_not_a_bypass_for_propositions": True,
    }


def historical_ten_case_protection(*, root=None) -> dict[str, Any]:
    bundle = load_4b26_bundle(root=root)
    payload = dict(bundle.get("payload") or {})
    ten = interpret_ten_case_compact(payload, root=root)
    score = dict(ten.get("score") or {})
    from app.book_semantic_gate_4b261.complexity import extract_gate_paragraphs

    paragraphs = extract_gate_paragraphs(payload)
    texts = {
        str(item.get("handle") or ""): str(item.get("text") or "")
        for item in paragraphs
    }
    kinds = {
        str(item.get("handle") or ""): str(item.get("kind") or "substantive")
        for item in paragraphs
    }
    from app.book_semantic_gate_4b24.constants import SCORED_CASE_ORDER

    validation = validate_compact_payload_112(
        ten.get("compact"),
        paragraph_texts=texts,
        required_handles=[handle for handle, _ in SCORED_CASE_ORDER],
        paragraph_kinds=kinds,
    )
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
        "validator_1_1_2_status": validation.get("status"),
        "historical_catalog_passed": bool(run_fakeai_catalog().get("passed")),
        "calibration_1_1_1_still_passes": bool(run_calibration_fixtures().get("passed")),
        "fakeai_not_terra_quality": True,
        "labels_unmodified": True,
    }


def run_offline_fixtures(*, root=None) -> dict[str, Any]:
    reasons = reason_code_fixtures()
    coverage = coverage_fixtures()
    historical = historical_ten_case_protection(root=root)
    positives = historical.get("positives_accepted")
    negatives = historical.get("negatives_blocked")
    passed = (
        bool(reasons.get("passed"))
        and bool(coverage.get("passed"))
        and positives == 6
        and negatives == 4
        and all((historical.get("protected") or {}).values())
        and historical.get("validator_1_1_2_status") == "PASS"
    )
    return {
        "phase": PHASE,
        "reason_codes": reasons,
        "coverage": coverage,
        "historical": historical,
        "fakeai_positives": positives,
        "fakeai_negatives": negatives,
        "passed": passed,
        "fakeai_not_terra_quality": True,
    }


__all__ = [
    "coverage_fixtures",
    "historical_ten_case_protection",
    "reason_code_fixtures",
    "run_offline_fixtures",
]
