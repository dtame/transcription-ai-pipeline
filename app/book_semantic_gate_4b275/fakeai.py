"""Offline FakeAI, diagnostic, and additional fixtures. Not Terra quality."""

from __future__ import annotations

from typing import Any

from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
from app.book_semantic_gate_4b274.fakeai import (
    _claims_covering,
    _compact,
    _validate,
    historical_ten_case_protection,
    reason_code_fixtures,
)
from app.book_semantic_gate_4b274.coverage import validate_coverage
from app.book_semantic_gate_4b275.constants import PHASE, PROJECT_NAME
from app.book_semantic_gate_4b275.coverage import validate_compact_payload_113
from app.book_semantic_gate_4b275.diagnostic import extract_failure_diagnostic
from app.book_semantic_gate_4b275.matrix import verdict_reason_code_matrix
from app.book_semantic_gate_4b275.unknown import diagnose_unknown_codes


def _payload(
    text: str,
    *,
    kind: str,
    reasons: list[str] | None = None,
    note: str | None = None,
    start: int | None = None,
    end: int | None = None,
    evidence: list[str] | None = None,
    extra_claims: list[dict[str, Any]] | None = None,
    drop_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    body = _compact(
        text,
        kind=kind,
        reasons=reasons,
        note=note,
        start=start,
        end=end,
        evidence=evidence,
    )
    if extra_claims:
        body["pr"][0]["c"].extend(extra_claims)
    for field in drop_fields:
        body.pop(field, None)
    return body


def additional_fixtures() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []

    def add(name: str, ok: bool, **extra: Any) -> None:
        cases.append({"name": name, "ok": ok, **extra})

    rhetorical = "Now then:"
    rhetorical_payload = _payload(
        rhetorical,
        kind=CLASS_NON_SUBSTANTIVE,
        reasons=[],
        evidence=[],
    )
    rhetorical_payload["pr"][0]["v"] = CLASS_NON_SUBSTANTIVE
    rhetorical_result = validate_compact_payload_113(
        rhetorical_payload,
        paragraph_texts={"hX": rhetorical},
        required_handles=["hX"],
        paragraph_kinds={"hX": "connective"},
    )
    add(
        "rhetorical_non_substantive",
        rhetorical_result["status"] == "PASS",
        status=rhetorical_result["status"],
    )

    asserted = "Therefore the origin is a new agent."
    asserted_payload = _payload(
        asserted,
        kind=CLASS_NON_SUBSTANTIVE,
        reasons=[],
        evidence=[],
    )
    asserted_result = validate_compact_payload_113(
        asserted_payload,
        paragraph_texts={"hX": asserted},
        required_handles=["hX"],
        paragraph_kinds={"hX": "substantive"},
    )
    add(
        "rhetorical_containing_assertion",
        asserted_result["status"] == "FAIL"
        and any("non_substantive_escape_hatch" in str(item) for item in asserted_result["errors"]),
        status=asserted_result["status"],
    )

    transition = "We turn next to the attested point."
    transition_payload = _payload(
        transition,
        kind=CLASS_SUPPORTED,
        reasons=[],
        evidence=["SRC001"],
    )
    transition_result = _validate(transition_payload, transition)
    add(
        "legitimate_editorial_transition",
        transition_result["status"] == "PASS",
        status=transition_result["status"],
    )

    new_conclusion = "Thus a new conclusion follows that the evidence never stated."
    conclusion_payload = _payload(
        new_conclusion,
        kind=CLASS_UNSUPPORTED,
        reasons=["NEW_CONCLUSION"],
        note="New conclusion.",
        evidence=[],
    )
    conclusion_result = validate_compact_payload_113(
        conclusion_payload,
        paragraph_texts={"hX": new_conclusion},
        required_handles=["hX"],
        paragraph_kinds={"hX": "substantive"},
    )
    add(
        "transition_introducing_new_conclusion",
        conclusion_result["status"] == "PASS",
        status=conclusion_result["status"],
    )

    origin = "This comes from an unnamed source."
    origin_payload = _payload(
        origin,
        kind=CLASS_QUESTIONABLE,
        reasons=["NEW_IMPLICATION"],
        note="Origin not attested.",
        evidence=[],
    )
    origin_result = validate_compact_payload_113(
        origin_payload,
        paragraph_texts={"hX": origin},
        required_handles=["hX"],
        paragraph_kinds={"hX": "substantive"},
    )
    add(
        "unsupported_origin",
        origin_result["status"] == "PASS",
        status=origin_result["status"],
    )

    implicit = "The speaker assigned this to an absent agent."
    implicit_payload = _payload(
        implicit,
        kind=CLASS_UNSUPPORTED,
        reasons=["NEW_FACT"],
        note="Attribution absent.",
        evidence=[],
    )
    implicit_result = validate_compact_payload_113(
        implicit_payload,
        paragraph_texts={"hX": implicit},
        required_handles=["hX"],
        paragraph_kinds={"hX": "substantive"},
    )
    add(
        "implicit_attribution",
        implicit_result["status"] == "PASS",
        status=implicit_result["status"],
    )

    unknown = diagnose_unknown_codes(CLASS_UNSUPPORTED, ["INVENTED_CAUSAL_LINK"])
    add(
        "unknown_reason_code",
        unknown["acceptance"] == "FAIL" and unknown["silently_rewritten"] is False,
        status=unknown["acceptance"],
    )

    matrix = verdict_reason_code_matrix()
    inconsistent = next(
        item
        for item in matrix["structural_cases"]
        if item["name"] == "valid_code_semantically_inconsistent"
    )
    add(
        "valid_but_inconsistent_reason_code",
        inconsistent["ok"] and inconsistent["observed"] == "PASS",
        status=inconsistent["observed"],
    )

    missing = diagnose_unknown_codes(CLASS_QUESTIONABLE, [])
    add(
        "missing_reason_code",
        missing["acceptance"] == "FAIL",
        status=missing["acceptance"],
    )

    incomplete_text = "Alpha because beta."
    incomplete_claims = _claims_covering(incomplete_text, "Alpha", "beta")
    incomplete = validate_coverage(incomplete_text, incomplete_claims)
    add(
        "valid_but_incomplete_span",
        incomplete["status"] == "FAIL",
        status=incomplete["status"],
    )

    punct_text = "Alpha, beta."
    punct_claims = _claims_covering(punct_text, "Alpha", "beta")
    punct = validate_coverage(punct_text, punct_claims)
    add(
        "admissible_punctuation",
        punct["status"] == "PASS",
        status=punct["status"],
    )

    connective_text = "Yes however no."
    connective_claims = _claims_covering(connective_text, "Yes", "no")
    connective = validate_coverage(connective_text, connective_claims)
    add(
        "omitted_logical_connective",
        connective["status"] == "FAIL",
        status=connective["status"],
    )

    partial_text = "A supported clause remains readable."
    partial_payload = _payload(
        partial_text,
        kind=CLASS_QUESTIONABLE,
        reasons=["INVENTED_CAUSAL_LINK"],
        note="Unknown code.",
        drop_fields=("sc",),
    )
    partial_diag = extract_failure_diagnostic(
        partial_payload,
        paragraph_texts={"hX": partial_text},
        required_handles=["hX"],
        paragraph_kinds={"hX": "substantive"},
    )
    add(
        "partially_exploitable_json",
        partial_diag["acceptance"] == "FAIL"
        and bool(partial_diag["diagnostic"]["analyzable_propositions"])
        and "sc" in str(partial_diag["diagnostic"]["missing_fields"]),
        acceptance=partial_diag["acceptance"],
    )
    add(
        "diagnostic_retained_on_compliance_fail",
        partial_diag["diagnostic_is_not_acceptance"] is True
        and partial_diag["acceptance"] == "FAIL"
        and partial_diag["diagnostic"]["unknown_reason_codes"] == ["INVENTED_CAUSAL_LINK"],
        acceptance=partial_diag["acceptance"],
    )
    add(
        "production_cache_unmodified",
        production_book_absent(PROJECT_NAME) is True,
        absent=True,
    )

    passed = all(item["ok"] for item in cases)
    return {
        "phase": PHASE,
        "cases": cases,
        "passed": passed,
        "fakeai_not_terra_quality": True,
    }


def run_offline_fixtures(*, root=None) -> dict[str, Any]:
    reasons = reason_code_fixtures()
    historical = historical_ten_case_protection(root=root)
    additional = additional_fixtures()
    positives = historical.get("positives_accepted")
    negatives = historical.get("negatives_blocked")
    passed = (
        bool(reasons.get("passed"))
        and bool(additional.get("passed"))
        and positives == 6
        and negatives == 4
        and all((historical.get("protected") or {}).values())
        and historical.get("validator_1_1_2_status") == "PASS"
    )
    return {
        "phase": PHASE,
        "reason_codes": reasons,
        "additional": additional,
        "historical": historical,
        "fakeai_positives": positives,
        "fakeai_negatives": negatives,
        "passed": passed,
        "fakeai_not_terra_quality": True,
    }


__all__ = ["additional_fixtures", "run_offline_fixtures"]
