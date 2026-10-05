"""Acceptance policy. Distinct from the contract validator. PASS / BLOCK / REVIEW."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
from app.book_semantic_gate_4b29.constants import (
    DECISION_BLOCK,
    DECISION_PASS,
    DECISION_REVIEW,
    MODEL_VERDICT_FAIL,
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


def apply_acceptance_policy(
    prepared: Mapping[str, Any],
    coverage: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    """Map structural and semantic results onto PASS / BLOCK / REVIEW.

    REVIEW never authorizes publication or production-cache acceptance.
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

    parsed = validation.get("parsed") if isinstance(validation.get("parsed"), Mapping) else {}
    if parsed.get("v") == MODEL_VERDICT_FAIL and decision != DECISION_BLOCK:
        decision = DECISION_BLOCK
        reasons.append("model_global_fail")

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
        if parsed.get("rr") is True and decision == DECISION_PASS:
            decision = DECISION_REVIEW
            reasons.append("model_requested_review")

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
    cache_ok = False
    publication_ok = False
    return {
        "phase": PHASE,
        "decision": decision,
        "reasons": unique_reasons,
        "substantive_units_supported": substantive_supported,
        "abusive_non_substantive": abusive,
        "questionable": questionable,
        "ambiguous_boundary": ambiguous,
        "reservations": reservations,
        "production_cache_acceptance": cache_ok,
        "publication_authorized": publication_ok,
        "review_does_not_accept_cache": True,
        "production_cache_policy": PRODUCTION_CACHE_ACCEPTANCE,
        "unambiguous_states": True,
        "secrets_included": False,
    }


def acceptance_policy_document() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "pass": [
            "preparation valid",
            "response conforms to contract 2.0",
            "all substantive units SUPPORTED",
            "NON_SUBSTANTIVE does not mask substantive content",
            "no blocking reservation",
            "no evidence error",
            "no coverage problem",
        ],
        "block": [
            "at least one UNSUPPORTED unit",
            "invalid contract",
            "missing unit",
            "unknown reason code",
            "invalid evidence",
            "coverage error",
            "abusive NON_SUBSTANTIVE",
        ],
        "review": [
            "QUESTIONABLE unit",
            "ambiguous semantic boundary",
            "reservation requiring human analysis",
            "structurally valid but insufficient for automatic acceptance",
        ],
        "review_does_not_authorize_publication": True,
        "review_does_not_accept_production_cache": True,
        "states": [DECISION_PASS, DECISION_BLOCK, DECISION_REVIEW],
        "unambiguous": True,
        "secrets_included": False,
    }


__all__ = ["acceptance_policy_document", "apply_acceptance_policy"]
