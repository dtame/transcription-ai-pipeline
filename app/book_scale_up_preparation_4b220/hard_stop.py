"""Operational hard-stop conditions for the future first remaining chapter."""

from __future__ import annotations

from typing import Any

from app.book_scale_up_preparation_4b220.constants import (
    ACCEPTED_CHAPTER,
    AUTHORIZED_SPEND_USD,
    FAITHFUL_PROMPT_1_1,
    PHASE,
)
from app.book_scale_up_preparation_4b220.guard import (
    BookScaleUpPreparation4220Error,
    reject_automatic_paid_retry,
    reject_cap_exceeded,
    reject_missing_authorization,
    reject_prompt_fallback,
    reject_unknown_cost,
)
from app.book_scale_up_preparation_4b220.prompt_select import resolve_isolated_prompt


def evaluate_hard_stops(
    *,
    authorized: bool = False,
    cost_status: str = "known",
    theoretical_maximum_usd: float | None = None,
    cap_usd: float | None = None,
    missing_sources: list[str] | None = None,
    json_valid: bool = True,
    truncated: bool = False,
    missing_idea_handles: list[str] | None = None,
    invented_idea_handles: list[str] | None = None,
    invalid_src: list[str] | None = None,
    prompt_version: str = FAITHFUL_PROMPT_1_1,
    prompt_available: bool = True,
    retry_requested: bool = False,
    publication_requested: bool = False,
    ch012_mutated: bool = False,
    canonical_mismatch: bool = False,
) -> dict[str, Any]:
    stops: list[str] = []
    if canonical_mismatch:
        stops.append("canonical_hash_mismatch")
    if ch012_mutated:
        stops.append("ch012_immutable_violation")
    if missing_sources:
        stops.append("mandatory_source_missing")
    if not authorized:
        stops.append("missing_authorization")
    if cost_status == "UNKNOWN" or theoretical_maximum_usd is None:
        stops.append("cost_unknown")
    if (
        cap_usd is not None
        and theoretical_maximum_usd is not None
        and theoretical_maximum_usd > cap_usd
    ):
        stops.append("cost_cap_exceeded")
    if not json_valid:
        stops.append("invalid_json")
    if truncated:
        stops.append("truncated_output")
    if missing_idea_handles:
        stops.append("idea_handles_missing_from_paragraph_evidence")
    if invented_idea_handles:
        stops.append("invented_idea_handles")
    if invalid_src:
        stops.append("invalid_src")
    if prompt_version == FAITHFUL_PROMPT_1_1 and not prompt_available:
        stops.append("prompt_1_1_unavailable_no_fallback")
    if retry_requested:
        stops.append("automatic_paid_retry")
    if publication_requested:
        stops.append("publication_forbidden")
    return {
        "phase": PHASE,
        "blocked": bool(stops),
        "stops": stops,
        "accepted_chapter_protected": ACCEPTED_CHAPTER,
        "authorized_spend_usd": float(AUTHORIZED_SPEND_USD),
        "must_stop_without_additional_call": True,
    }


def operational_hard_stop_conditions() -> dict[str, Any]:
    rows = [
        {
            "id": "missing_authorization",
            "action": "STOP",
            "probe": "reject_missing_authorization",
        },
        {
            "id": "cost_unknown",
            "action": "STOP",
            "probe": "reject_unknown_cost",
        },
        {
            "id": "cost_cap_exceeded",
            "action": "STOP",
            "probe": "reject_cap_exceeded",
        },
        {
            "id": "automatic_paid_retry",
            "action": "STOP",
            "probe": "reject_automatic_paid_retry",
        },
        {
            "id": "prompt_1_1_unavailable_no_fallback",
            "action": "STOP",
            "probe": "reject_prompt_fallback",
        },
        {
            "id": "mandatory_source_missing",
            "action": "STOP",
            "probe": "missing_sources_block_context",
        },
        {
            "id": "idea_handles_missing_from_paragraph_evidence",
            "action": "STOP",
            "probe": "detect_missing_idea_handles",
        },
        {
            "id": "invented_idea_handles",
            "action": "STOP",
            "probe": "detect_invented_idea_handles",
        },
        {
            "id": "invalid_src",
            "action": "STOP",
            "probe": "detect_invalid_src",
        },
        {
            "id": "invalid_or_truncated_json",
            "action": "STOP",
            "probe": "detect_invalid_or_truncated",
        },
        {
            "id": "ch012_or_canonical_mutation",
            "action": "STOP",
            "probe": "hash_guards",
        },
        {
            "id": "publication",
            "action": "STOP",
            "probe": "publication_forbidden",
        },
    ]
    probes = {
        "missing_authorization": _probe(reject_missing_authorization),
        "cost_unknown": _probe(reject_unknown_cost),
        "cost_cap_exceeded": _probe(reject_cap_exceeded),
        "automatic_paid_retry": _probe(reject_automatic_paid_retry),
        "prompt_fallback_forbidden": _probe(
            lambda: reject_prompt_fallback(FAITHFUL_PROMPT_1_1, "book-generator-1.0.1")
        ),
        "activation_blocked_this_phase": _probe(
            lambda: resolve_isolated_prompt(
                FAITHFUL_PROMPT_1_1,
                activate=True,
                authorization_scope="FUTURE",
                cost_authorization_present=True,
            )
        ),
    }
    return {
        "phase": PHASE,
        "conditions": rows,
        "probes": probes,
        "operational": all(item["raised"] for item in probes.values()),
        "no_additional_call_after_stop": True,
        "secrets_included": False,
    }


def _probe(fn) -> dict[str, Any]:
    try:
        fn()
    except BookScaleUpPreparation4220Error as exc:
        return {"raised": True, "message": str(exc)}
    return {"raised": False, "message": ""}


__all__ = ["evaluate_hard_stops", "operational_hard_stop_conditions"]
