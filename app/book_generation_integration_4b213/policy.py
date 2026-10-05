"""Chapter-level PASS / BLOCK / REVIEW. Distinct from Terra classifications."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_generation_integration_4b213.constants import (
    DECISION_BLOCK,
    DECISION_PASS,
    DECISION_REVIEW,
    PHASE,
    PRODUCTION_CACHE_ACCEPTANCE,
)
from app.book_semantic_gate_4b212.policy import apply_acceptance_policy_202


def apply_paragraph_policy(
    prepared: Mapping[str, Any],
    coverage: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    policy = apply_acceptance_policy_202(prepared, coverage, validation)
    policy["phase"] = PHASE
    policy["production_cache_acceptance"] = False
    policy["isolated_acceptance_candidate"] = policy.get("decision") == DECISION_PASS
    return policy


def apply_chapter_policy(paragraph_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    reasons: list[str] = []
    decisions = [str(item.get("decision") or "") for item in paragraph_results]
    if not paragraph_results:
        return {
            "phase": PHASE,
            "decision": DECISION_BLOCK,
            "reasons": ["no_paragraph_results"],
            "production_cache_acceptance": False,
            "isolated_acceptance_candidate": False,
            "presented_as_validated_chapter": False,
            "missing_response_never_pass": True,
            "secrets_included": False,
        }
    if any(item.get("raw") is None and item.get("interrupted") is not True for item in paragraph_results):
        missing = [
            str(item.get("paragraph_id") or "")
            for item in paragraph_results
            if item.get("raw") is None and not item.get("interrupted")
        ]
        if missing:
            reasons.append("missing_response:" + ",".join(missing))
    if any(not item.get("structure_ok", True) for item in paragraph_results):
        reasons.append("structure_invalid")
    if any(not item.get("evidence_ok", True) for item in paragraph_results):
        reasons.append("evidence_invalid")
    if DECISION_BLOCK in decisions or reasons:
        decision = DECISION_BLOCK
        if DECISION_BLOCK in decisions:
            reasons.append("paragraph_block")
    elif DECISION_REVIEW in decisions:
        decision = DECISION_REVIEW
        reasons.append("paragraph_review")
    elif all(item == DECISION_PASS for item in decisions):
        decision = DECISION_PASS
    else:
        decision = DECISION_BLOCK
        reasons.append("non_pass_without_explicit_decision")
    unique = list(dict.fromkeys(reasons))
    return {
        "phase": PHASE,
        "decision": decision,
        "reasons": unique,
        "paragraph_decisions": decisions,
        "production_cache_acceptance": PRODUCTION_CACHE_ACCEPTANCE,
        "isolated_acceptance_candidate": decision == DECISION_PASS,
        "presented_as_validated_chapter": False,
        "review_is_not_pass": True,
        "block_is_not_pass": True,
        "missing_response_never_pass": True,
        "secrets_included": False,
    }


def policy_document() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "pass": [
            "all substantive units SUPPORTED",
            "contract 2.0.2 VALID",
            "evidence valid",
            "coverage complete",
            "no blocking anomaly",
            "no missing response",
        ],
        "review": [
            "at least one QUESTIONABLE proposition",
            "no UNSUPPORTED",
            "no technical blocking anomaly",
            "REVIEW is never a validated chapter",
        ],
        "block": [
            "at least one UNSUPPORTED",
            "invalid contract",
            "invalid evidence",
            "invalid coverage",
            "critical technical anomaly",
            "missing response",
        ],
        "missing_response_never_pass": True,
        "production_cache_acceptance": False,
        "secrets_included": False,
    }


__all__ = ["apply_chapter_policy", "apply_paragraph_policy", "policy_document"]
