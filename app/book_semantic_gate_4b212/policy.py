"""Acceptance policy 2.0.2. Operational PASS / BLOCK / REVIEW computed in Python."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
from app.book_semantic_gate_4b212.constants import (
    DECISION_BLOCK,
    DECISION_PASS,
    DECISION_REVIEW,
    PHASE,
    PRODUCTION_CACHE_ACCEPTANCE,
)

_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]{4,}")
_CONNECTIVE_WORDS = frozenset(
    {
        "because",
        "unless",
        "however",
        "therefore",
        "although",
        "which",
        "means",
        "and",
        "then",
        "thus",
    }
)


def _unit_is_substantive(text: str) -> bool:
    tokens = [token.lower() for token in _WORD.findall(text or "")]
    content = [token for token in tokens if token not in _CONNECTIVE_WORDS]
    return bool(content)


def apply_acceptance_policy_202(
    prepared: Mapping[str, Any],
    coverage: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    """Map structural and semantic results onto PASS / BLOCK / REVIEW.

    REVIEW never authorizes publication or production-cache acceptance.
    Operational values are not read from the model payload.
    """
    reasons: list[str] = []
    decision = DECISION_PASS
    verdicts = list(validation.get("verdicts") or [])
    units = {str(unit.get("unit_id") or ""): unit for unit in prepared.get("units") or []}

    if not coverage.get("ok"):
        decision = DECISION_BLOCK
        reasons.append("coverage_error")
    if not validation.get("ok"):
        decision = DECISION_BLOCK
        reasons.extend(str(item) for item in validation.get("errors") or ["contract_invalid"])

    kinds = [str(item.get("k") or "") for item in verdicts]
    if CLASS_UNSUPPORTED in kinds:
        decision = DECISION_BLOCK
        reasons.append("unsupported_unit")

    abusive = []
    for item in verdicts:
        if item.get("k") != CLASS_NON_SUBSTANTIVE:
            continue
        unit = units.get(str(item.get("unit_id") or ""))
        text = str((unit or {}).get("text") or "")
        if _unit_is_substantive(text):
            abusive.append(item.get("unit_id"))
    if abusive:
        decision = DECISION_BLOCK
        reasons.append("abusive_non_substantive:" + ",".join(str(item) for item in abusive))

    questionable = CLASS_QUESTIONABLE in kinds
    ambiguous = any(bool(unit.get("boundary_ambiguity")) for unit in units.values())
    reservations = [
        str(item.get("n") or "")
        for item in verdicts
        if item.get("k") in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED} and str(item.get("n") or "").strip()
    ]

    if decision != DECISION_BLOCK:
        if questionable:
            decision = DECISION_REVIEW
            reasons.append("questionable_unit")
        if ambiguous:
            decision = DECISION_REVIEW
            reasons.append("ambiguous_boundary")
        if reservations and decision == DECISION_PASS:
            decision = DECISION_REVIEW
            reasons.append("semantic_reservation")

    substantive_supported = True
    for unit in units.values():
        uid = str(unit.get("unit_id") or "")
        match = next((item for item in verdicts if item.get("unit_id") == uid), None)
        if match is None:
            substantive_supported = False
            continue
        if match.get("k") == CLASS_NON_SUBSTANTIVE and not _unit_is_substantive(str(unit.get("text") or "")):
            continue
        if match.get("k") != CLASS_SUPPORTED:
            substantive_supported = False

    if decision == DECISION_PASS and not (
        coverage.get("ok")
        and validation.get("ok")
        and substantive_supported
        and not abusive
        and not questionable
        and not ambiguous
    ):
        decision = DECISION_REVIEW
        reasons.append("insufficient_for_automatic_acceptance")

    unique_reasons = list(dict.fromkeys(reasons))
    return {
        "phase": PHASE,
        "decision": decision,
        "reasons": unique_reasons,
        "substantive_units_supported": substantive_supported,
        "abusive_non_substantive": abusive,
        "questionable": questionable,
        "ambiguous_boundary": ambiguous,
        "reservations": reservations,
        "production_cache_acceptance": False,
        "publication_authorized": False,
        "review_does_not_accept_cache": True,
        "production_cache_policy": PRODUCTION_CACHE_ACCEPTANCE,
        "operational_decision_computed_by_python": True,
        "model_operational_fields_ignored": True,
        "unambiguous_states": True,
        "secrets_included": False,
    }


def acceptance_policy_document() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "pass": [
            "contract VALID",
            "coverage complete",
            "evidence valid",
            "all substantive propositions SUPPORTED",
            "no QUESTIONABLE",
            "no UNSUPPORTED",
            "NON_SUBSTANTIVE does not mask a real claim",
        ],
        "review": [
            "contract VALID",
            "one or more QUESTIONABLE",
            "no UNSUPPORTED",
            "no other technical block",
            "REVIEW does not accept the production cache",
        ],
        "block": [
            "contract INVALID",
            "coverage invalid",
            "evidence invalid",
            "UNSUPPORTED proposition",
            "invalid reason code",
            "missing unit",
            "duplicate unit",
            "critical technical anomaly",
            "abusive NON_SUBSTANTIVE",
        ],
        "non_substantive_control": (
            "A unit classified NON_SUBSTANTIVE is blocked when its text still "
            "contains a substantial assertion."
        ),
        "review_does_not_authorize_publication": True,
        "review_does_not_accept_production_cache": True,
        "states": [DECISION_PASS, DECISION_BLOCK, DECISION_REVIEW],
        "unambiguous": True,
        "secrets_included": False,
    }


def validate_acceptance_policy_cases(
    *,
    prepared: Mapping[str, Any],
    coverage: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    from app.book_semantic_gate_4b212.validator import validate_response_202

    rows = []
    ok = True
    for case in cases or ():
        validation = validate_response_202(
            case.get("payload"),
            prepared,
            allowed_evidence=list(prepared.get("evidence_handles") or []),
            expected_chapter=str(case.get("chapter") or "CH016"),
        )
        policy = apply_acceptance_policy_202(prepared, coverage, validation)
        expected = str(case.get("expected_decision") or "")
        match = policy.get("decision") == expected
        if not match:
            ok = False
        rows.append(
            {
                "name": case.get("name"),
                "expected": expected,
                "decision": policy.get("decision"),
                "contract_ok": validation.get("ok"),
                "match": match,
            }
        )
    return {
        "phase": PHASE,
        "passed": ok,
        "cases": rows,
        "document": acceptance_policy_document(),
        "secrets_included": False,
    }


__all__ = [
    "acceptance_policy_document",
    "apply_acceptance_policy_202",
    "validate_acceptance_policy_cases",
]
