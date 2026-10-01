"""Score Terra results against frozen 4B.2.3 human labels."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.claims import paragraph_verdict_from_claims
from app.book_semantic_gate_4b24.constants import (
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    CONNECTIVE_CASE_ID,
    EXPECTED_NEGATIVE_CASES,
    EXPECTED_POSITIVE_CASES,
    EXPECTED_SCORED_CASES,
    FUNERAL_CASE_ID,
    NEGATIVE_CASE_IDS,
    P3_CASE_ID,
    P8_CASE_ID,
    POSITIVE_CASE_IDS,
)
from app.book_semantic_gate_4b24.payload import case_id_for_handle


def _blocked(classification: str) -> bool:
    return classification in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED}


def score_case(
    case: Mapping[str, Any],
    result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    expected_class = str(case.get("expected_class") or "")
    accepted = [str(item) for item in case.get("accepted_classes") or []]
    expected_reasons = [str(item) for item in case.get("expected_reason_codes") or []]
    role = str(case.get("role") or "")
    if result is None:
        return {
            "case_id": case.get("case_id"),
            "role": role,
            "opaque_handle": None,
            "expected_class": expected_class,
            "accepted_classes": accepted,
            "expected_reason_codes": expected_reasons,
            "terra_class": None,
            "terra_reasons": [],
            "terra_explanations": [],
            "present": False,
            "blocked": False,
            "verdict_compatible": False,
            "reason_compatible": False,
            "false_rejection": False,
            "false_negative": False,
            "partial_clause_detected": None,
        }
    claims = list(result.get("claim_results") or [])
    terra_class = str(
        result.get("verdict")
        or paragraph_verdict_from_claims(
            [str(claim.get("classification") or "") for claim in claims]
        )
    )
    terra_reasons: list[str] = []
    explanations: list[str] = []
    for claim in claims:
        terra_reasons.extend(str(item) for item in claim.get("reason_codes") or [])
        text = str(claim.get("explanation") or "").strip()
        if text:
            explanations.append(text)
    terra_reasons.extend(str(item) for item in result.get("reason_codes") or [])
    terra_reasons = list(dict.fromkeys(terra_reasons))
    blocked = _blocked(terra_class)
    verdict_compatible = terra_class in accepted if accepted else terra_class == expected_class
    reason_compatible = True
    if expected_reasons:
        reason_compatible = any(code in expected_reasons for code in terra_reasons)
    false_rejection = role == "positive" and terra_class != CLASS_SUPPORTED
    false_negative = role == "negative" and terra_class == CLASS_SUPPORTED
    clause = str(case.get("clause") or "")
    partial = None
    if clause and claims:
        clause_hit = False
        core_supported = False
        for claim in claims:
            claim_text = str(claim.get("claim_text") or "")
            classification = str(claim.get("classification") or "")
            if clause.lower() in claim_text.lower() or (
                classification in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED}
            ):
                if clause.lower() in claim_text.lower() or clause.lower() in str(
                    claim.get("explanation") or ""
                ).lower():
                    clause_hit = True
            if classification == CLASS_SUPPORTED and clause.lower() not in claim_text.lower():
                core_supported = True
        if role == "negative" and case.get("case_id") in {P3_CASE_ID, P8_CASE_ID}:
            partial = blocked and (clause_hit or not false_negative)
            if core_supported and not blocked:
                partial = False
    return {
        "case_id": case.get("case_id"),
        "role": role,
        "opaque_handle": result.get("opaque_handle") or result.get("paragraph_handle"),
        "expected_class": expected_class,
        "accepted_classes": accepted,
        "expected_reason_codes": expected_reasons,
        "terra_class": terra_class,
        "terra_reasons": terra_reasons,
        "terra_explanations": explanations,
        "clause": clause or None,
        "present": True,
        "blocked": blocked,
        "verdict_compatible": verdict_compatible,
        "reason_compatible": reason_compatible if role == "negative" else True,
        "false_rejection": false_rejection,
        "false_negative": false_negative,
        "partial_clause_detected": partial,
        "claims": claims,
    }


def score_benchmark(
    *,
    cases: Sequence[Mapping[str, Any]],
    paragraph_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_case: dict[str, Mapping[str, Any]] = {}
    for row in paragraph_results:
        handle = str(row.get("opaque_handle") or row.get("paragraph_handle") or "")
        try:
            case_id = str(row.get("case_id") or case_id_for_handle(handle))
        except KeyError:
            continue
        by_case[case_id] = row
    scored = [score_case(case, by_case.get(str(case.get("case_id") or ""))) for case in cases]
    positives = [row for row in scored if row["role"] == "positive"]
    negatives = [row for row in scored if row["role"] == "negative"]
    positive_accepted = sum(1 for row in positives if row["terra_class"] == CLASS_SUPPORTED)
    positive_false_q = sum(
        1 for row in positives if row["terra_class"] == CLASS_QUESTIONABLE
    )
    positive_false_u = sum(
        1 for row in positives if row["terra_class"] == CLASS_UNSUPPORTED
    )
    negative_blocked = sum(1 for row in negatives if row["blocked"])
    negative_missed = sum(1 for row in negatives if row["false_negative"])
    reason_compatible = sum(1 for row in negatives if row["reason_compatible"] and row["blocked"])
    present = sum(1 for row in scored if row["present"])
    verdict_correct = sum(
        1
        for row in scored
        if (row["role"] == "positive" and row["terra_class"] == CLASS_SUPPORTED)
        or (row["role"] == "negative" and row["blocked"])
    )
    funeral = next((row for row in scored if row["case_id"] == FUNERAL_CASE_ID), None)
    connective = next((row for row in scored if row["case_id"] == CONNECTIVE_CASE_ID), None)
    p3 = next((row for row in scored if row["case_id"] == P3_CASE_ID), None)
    p8 = next((row for row in scored if row["case_id"] == P8_CASE_ID), None)
    return {
        "cases": EXPECTED_SCORED_CASES,
        "positive_cases": EXPECTED_POSITIVE_CASES,
        "negative_cases": EXPECTED_NEGATIVE_CASES,
        "present": present,
        "positive_accepted": positive_accepted,
        "positive_false_rejections": sum(1 for row in positives if row["false_rejection"]),
        "positive_false_questionable": positive_false_q,
        "positive_false_unsupported": positive_false_u,
        "negative_blocked": negative_blocked,
        "negative_false_negatives": negative_missed,
        "verdict_accuracy": (
            round(verdict_correct / EXPECTED_SCORED_CASES, 6) if EXPECTED_SCORED_CASES else 0
        ),
        "negative_recall": (
            round(negative_blocked / EXPECTED_NEGATIVE_CASES, 6)
            if EXPECTED_NEGATIVE_CASES
            else 0
        ),
        "positive_specificity": (
            round(positive_accepted / EXPECTED_POSITIVE_CASES, 6)
            if EXPECTED_POSITIVE_CASES
            else 0
        ),
        "reason_code_compatible": reason_compatible,
        "reason_code_compatible_of": EXPECTED_NEGATIVE_CASES,
        "small_sample_warning": (
            "10 cases are an engineering canary, not a statistical "
            "model-quality benchmark."
        ),
        "funeral": funeral,
        "connective": connective,
        "p3": p3,
        "p8": p8,
        "rows": scored,
        "positive_case_ids": list(POSITIVE_CASE_IDS),
        "negative_case_ids": list(NEGATIVE_CASE_IDS),
    }


def classify_canary(
    *,
    terra_calls: int,
    sonnet_calls: int,
    retries: int,
    fallbacks: int,
    structural_pass: bool,
    label_leakage: int,
    score: Mapping[str, Any],
    replay_pass: bool,
    inputs_unchanged: bool,
    test_failures: int,
    http_success: bool | None,
    called_despite_leak: bool = False,
) -> str:
    if terra_calls == 0:
        return "BLOCKED_PRECALL"
    if called_despite_leak or label_leakage:
        return "FAIL"
    if terra_calls != 1 or sonnet_calls != 0 or retries != 0 or fallbacks != 0:
        return "FAIL"
    if http_success is not True or not structural_pass:
        return "FAIL"
    if int(score.get("present") or 0) != EXPECTED_SCORED_CASES:
        return "FAIL"
    if int(score.get("negative_false_negatives") or 0) > 0:
        return "FAIL"
    clean = (
        int(score.get("positive_accepted") or 0) == EXPECTED_POSITIVE_CASES
        and int(score.get("positive_false_rejections") or 0) == 0
        and int(score.get("negative_blocked") or 0) == EXPECTED_NEGATIVE_CASES
        and int(score.get("reason_code_compatible") or 0) == EXPECTED_NEGATIVE_CASES
        and bool((score.get("funeral") or {}).get("blocked"))
        and bool((score.get("connective") or {}).get("blocked"))
        and bool((score.get("p3") or {}).get("blocked"))
        and bool((score.get("p8") or {}).get("blocked"))
        and replay_pass
        and inputs_unchanged
        and test_failures == 0
    )
    if clean:
        return "PASS"
    if int(score.get("negative_blocked") or 0) == EXPECTED_NEGATIVE_CASES:
        return "PARTIAL"
    return "FAIL"


__all__ = ["classify_canary", "score_benchmark", "score_case"]
