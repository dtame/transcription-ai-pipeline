"""Operational hard-stop conditions for future batch generation."""

from __future__ import annotations

from typing import Any

from app.book_batch_preparation_4b222.constants import (
    ACCEPTED_CHAPTERS,
    AUTHORIZED_SPEND_USD,
    FAITHFUL_PROMPT_1_1,
    PHASE,
)
from app.book_batch_preparation_4b222.guard import (
    BookBatchPreparation4222Error,
    reject_automatic_paid_retry,
    reject_cap_exceeded,
    reject_consumed_lock,
    reject_missing_authorization,
    reject_multi_chapter_call,
    reject_prompt_fallback,
    reject_uncertain_lock,
    reject_unknown_cost,
)
from app.book_scale_up_preparation_4b220.prompt_select import resolve_isolated_prompt


def evaluate_hard_stops(
    *,
    authorized: bool = False,
    cost_status: str = "known",
    theoretical_maximum_usd: float | None = None,
    cap_usd: float | None = None,
    json_valid: bool = True,
    truncated: bool = False,
    missing_idea_handles: list[str] | None = None,
    invented_idea_handles: list[str] | None = None,
    invalid_src: list[str] | None = None,
    prompt_version: str = FAITHFUL_PROMPT_1_1,
    prompt_available: bool = True,
    model_changed: bool = False,
    retry_requested: bool = False,
    fallback_requested: bool = False,
    publication_requested: bool = False,
    ch012_mutated: bool = False,
    ch018_mutated: bool = False,
    canonical_mismatch: bool = False,
    lock_consumed: bool = False,
    lock_uncertain: bool = False,
    multi_chapter_call: bool = False,
    remaining_authorization: bool = False,
) -> dict[str, Any]:
    stops: list[str] = []
    if canonical_mismatch:
        stops.append("canonical_hash_mismatch")
    if ch012_mutated:
        stops.append("ch012_immutable_violation")
    if ch018_mutated:
        stops.append("ch018_immutable_violation")
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
    if prompt_version != FAITHFUL_PROMPT_1_1 or not prompt_available:
        stops.append("unauthorized_prompt_change")
    if model_changed:
        stops.append("unauthorized_model_change")
    if retry_requested:
        stops.append("automatic_paid_retry")
    if fallback_requested:
        stops.append("automatic_fallback")
    if publication_requested:
        stops.append("publication_forbidden")
    if lock_consumed:
        stops.append("consumed_lock")
    if lock_uncertain:
        stops.append("uncertain_lock")
    if multi_chapter_call:
        stops.append("multi_chapter_provider_call")
    if authorized and not remaining_authorization:
        stops.append("remaining_authorization_exhausted")
    return {
        "phase": PHASE,
        "blocked": bool(stops),
        "stops": stops,
        "accepted_chapters_protected": list(ACCEPTED_CHAPTERS),
        "authorized_spend_usd": float(AUTHORIZED_SPEND_USD),
        "must_stop_without_additional_call": True,
    }


def operational_hard_stop_conditions() -> dict[str, Any]:
    rows = [
        {"id": "missing_authorization", "action": "STOP"},
        {"id": "cost_unknown", "action": "STOP"},
        {"id": "cost_cap_exceeded", "action": "STOP"},
        {"id": "automatic_paid_retry", "action": "STOP"},
        {"id": "automatic_fallback", "action": "STOP"},
        {"id": "prompt_or_model_change", "action": "STOP"},
        {"id": "invalid_or_truncated_json", "action": "STOP"},
        {"id": "idea_handles_missing_or_invented", "action": "STOP"},
        {"id": "invalid_src", "action": "STOP"},
        {"id": "consumed_lock", "action": "STOP"},
        {"id": "uncertain_lock", "action": "STOP"},
        {"id": "multi_chapter_provider_call", "action": "STOP"},
        {"id": "ch012_or_ch018_or_canonical_mutation", "action": "STOP"},
        {"id": "publication", "action": "STOP"},
    ]
    probes = {
        "missing_authorization": _probe(reject_missing_authorization),
        "cost_unknown": _probe(reject_unknown_cost),
        "cost_cap_exceeded": _probe(reject_cap_exceeded),
        "automatic_paid_retry": _probe(reject_automatic_paid_retry),
        "prompt_fallback_forbidden": _probe(
            lambda: reject_prompt_fallback(FAITHFUL_PROMPT_1_1, "book-generator-1.0.1")
        ),
        "consumed_lock": _probe(reject_consumed_lock),
        "uncertain_lock": _probe(reject_uncertain_lock),
        "multi_chapter_call": _probe(reject_multi_chapter_call),
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
        "no_automatic_paid_retry": True,
        "secrets_included": False,
    }


def _probe(fn) -> dict[str, Any]:
    try:
        fn()
    except BookBatchPreparation4222Error as exc:
        return {"raised": True, "message": str(exc)}
    except Exception as exc:
        return {"raised": True, "message": str(exc)}
    return {"raised": False, "message": ""}


__all__ = ["evaluate_hard_stops", "operational_hard_stop_conditions"]
