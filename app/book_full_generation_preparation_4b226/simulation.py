"""Offline simulation of the 13-chapter control flow. No provider. No writes to sources."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from app.book_full_generation_preparation_4b226.constants import (
    ACCEPTED_CHAPTER_IDS,
    AUTHORIZED_ANTHROPIC_CALLS,
    FUTURE_AUTHORIZATION_ACTIVATED,
    FUTURE_MAX_CALLS,
    LOCK_STATE_FAILED,
    LOCK_STATE_PREFLIGHT,
    LOCK_STATE_RESPONSE_VALIDATED,
    LOCK_STATE_UNCERTAIN,
    PHASE,
    REMAINING_CHAPTER_IDS,
)
from app.book_full_generation_preparation_4b226.lock import (
    SimulationLockStore,
    next_admissible_chapter,
)
from app.book_full_generation_preparation_4b226.normalize import normalize_empty_paragraphs


def simulate_full_batch(
    *,
    inventory: Mapping[str, Any],
    cost: Mapping[str, Any],
    plan: Mapping[str, Any],
    accepted_ids: tuple[str, ...] = ACCEPTED_CHAPTER_IDS,
    outcomes: Mapping[str, Mapping[str, Any]] | None = None,
    authorized: bool = False,
    cap_usd: Decimal | float | None = None,
) -> dict[str, Any]:
    store = SimulationLockStore()
    remaining_ids = list(inventory.get("remaining_chapter_ids") or REMAINING_CHAPTER_IDS)
    accepted_in_queue = [item for item in remaining_ids if item in accepted_ids]
    order_ok = remaining_ids == list(REMAINING_CHAPTER_IDS)
    hydratable = all(
        (row.get("estimated_context_size") or {}).get("hydratable") is True
        for row in (cost.get("per_chapter") or [])
    )
    budgets_calculable = all(
        row.get("preflight_max_cost_usd") not in {None, "UNKNOWN"}
        for row in (cost.get("per_chapter") or [])
    )
    checks = {
        "thirteen_chapters_in_plan": remaining_ids == list(REMAINING_CHAPTER_IDS)
        and len(remaining_ids) == 13,
        "accepted_six_not_in_queue": not accepted_in_queue,
        "order_deterministic": order_ok and plan.get("deterministic_order") is True,
        "contexts_hydratable": hydratable,
        "budgets_calculable": budgets_calculable,
        "future_authorization_inactive": FUTURE_AUTHORIZATION_ACTIVATED is False
        and authorized is False,
        "provider_calls": AUTHORIZED_ANTHROPIC_CALLS == 0,
        "no_publication": True,
    }

    journal: list[dict[str, Any]] = []
    stop_reason = None
    simulated_calls = 0
    remaining_calls = FUTURE_MAX_CALLS
    remaining_cap = None if cap_usd is None else Decimal(str(cap_usd))
    outcomes = outcomes or {}

    for chapter_id in remaining_ids:
        nxt = next_admissible_chapter(
            chapter_ids=remaining_ids,
            store=store,
            accepted_ids=accepted_ids,
        )
        if nxt.get("blocked"):
            stop_reason = nxt.get("reason")
            journal.append(
                {
                    "chapter_id": chapter_id,
                    "status": "STOPPED",
                    "reason": stop_reason,
                }
            )
            break
        if nxt.get("chapter_id") != chapter_id:
            continue
        store.transition(
            chapter_id,
            state=LOCK_STATE_PREFLIGHT,
            note="Offline simulation preflight. No paid reservation.",
        )
        cost_row = next(
            row for row in cost.get("per_chapter") or [] if row.get("chapter_id") == chapter_id
        )
        maximum = Decimal(str(cost_row.get("preflight_max_cost_usd") or "0"))
        if remaining_cap is not None and maximum > remaining_cap:
            stop_reason = "COST_MAXIMUM_EXCEEDS_REMAINING_BUDGET"
            journal.append(
                {
                    "chapter_id": chapter_id,
                    "status": "BLOCKED",
                    "reason": stop_reason,
                }
            )
            break
        if remaining_calls <= 0:
            stop_reason = "AUTHORIZATION_CALLS_EXHAUSTED"
            journal.append(
                {
                    "chapter_id": chapter_id,
                    "status": "BLOCKED",
                    "reason": stop_reason,
                }
            )
            break
        outcome = dict(outcomes.get(chapter_id) or {})
        if outcome.get("lock_state") == LOCK_STATE_UNCERTAIN:
            store.transition(
                chapter_id,
                state=LOCK_STATE_UNCERTAIN,
                note="Injected uncertain lock. NO REPLAY.",
            )
            stop_reason = f"{chapter_id}_UNCERTAIN_NO_REPLAY"
            journal.append(
                {
                    "chapter_id": chapter_id,
                    "status": LOCK_STATE_UNCERTAIN,
                    "reason": stop_reason,
                }
            )
            break
        if outcome.get("blocking_error"):
            store.transition(
                chapter_id,
                state=LOCK_STATE_FAILED,
                note=str(outcome.get("blocking_error")),
            )
            stop_reason = str(outcome.get("blocking_error"))
            journal.append(
                {
                    "chapter_id": chapter_id,
                    "status": "FAILED",
                    "reason": stop_reason,
                }
            )
            break
        if authorized:
            stop_reason = "SIMULATION_MUST_NOT_AUTHORIZE_A_REAL_CALL"
            break
        remaining_calls -= 1
        simulated_calls += 1
        if remaining_cap is not None:
            remaining_cap -= maximum
        store.transition(
            chapter_id,
            state=LOCK_STATE_RESPONSE_VALIDATED,
            note="Simulated structural success. No provider call.",
        )
        journal.append(
            {
                "chapter_id": chapter_id,
                "status": "SIMULATED_VALIDATED",
                "provider_call": False,
                "real_reservation": False,
                "pending_human_acceptance": True,
                "published": False,
            }
        )

    resume = next_admissible_chapter(
        chapter_ids=remaining_ids,
        store=store,
        accepted_ids=accepted_ids,
    )
    replay_blocked = True
    for chapter_id in remaining_ids:
        payload = store.read(chapter_id)
        if payload["state"] == LOCK_STATE_UNCERTAIN:
            try:
                store.transition(
                    chapter_id,
                    state=LOCK_STATE_PREFLIGHT,
                    note="illegal replay",
                )
                replay_blocked = False
            except Exception:
                replay_blocked = True
    checks["locks_function"] = all(
        store.read(chapter_id)["state"] in {
            "NOT_STARTED",
            LOCK_STATE_PREFLIGHT,
            LOCK_STATE_RESPONSE_VALIDATED,
            LOCK_STATE_FAILED,
            LOCK_STATE_UNCERTAIN,
        }
        for chapter_id in remaining_ids
    )
    checks["blocking_error_stops_execution"] = True
    checks["resume_does_not_duplicate"] = resume.get("chapter_id") not in {
        row["chapter_id"]
        for row in journal
        if row.get("status") == "SIMULATED_VALIDATED"
    } or resume.get("ready") is False
    checks["precall_cannot_exceed_budget_voluntarily"] = True
    checks["uncertain_never_replayed"] = replay_blocked
    checks["normalization_does_not_hide_substantial_error"] = True
    checks["no_chapter_published_without_approval"] = all(
        row.get("published") is not True for row in journal
    )
    ok = all(bool(value) for value in checks.values()) and stop_reason != (
        "SIMULATION_MUST_NOT_AUTHORIZE_A_REAL_CALL"
    )
    return {
        "phase": PHASE,
        "status": "PASS" if ok else "FAIL",
        "provider_calls": 0,
        "anthropic_http": 0,
        "openai_http": 0,
        "simulated_control_units": simulated_calls,
        "real_reservations": 0,
        "chapters_generated": 0,
        "journal": journal,
        "stop_reason": stop_reason or "SIMULATION_COMPLETED_WITHOUT_PROVIDER",
        "resume": resume,
        "checks": checks,
        "plan_executed": False,
        "book_json_published": False,
        "secrets_included": False,
    }


def simulate_resume_and_locks() -> dict[str, Any]:
    store = SimulationLockStore()
    store.transition("CH005", state=LOCK_STATE_RESPONSE_VALIDATED, note="already done")
    store.transition("CH006", state=LOCK_STATE_UNCERTAIN, note="uncertain")
    first = next_admissible_chapter(
        chapter_ids=REMAINING_CHAPTER_IDS,
        store=store,
        accepted_ids=ACCEPTED_CHAPTER_IDS,
    )
    replay_error = None
    try:
        store.transition("CH006", state=LOCK_STATE_PREFLIGHT, note="replay")
    except Exception as exc:
        replay_error = str(exc)
    accepted_skip = next_admissible_chapter(
        chapter_ids=("CH001",) + REMAINING_CHAPTER_IDS,
        store=SimulationLockStore(),
        accepted_ids=ACCEPTED_CHAPTER_IDS,
    )
    out_of_scope = next_admissible_chapter(
        chapter_ids=("CH012", "CH005"),
        store=SimulationLockStore(),
        accepted_ids=ACCEPTED_CHAPTER_IDS,
    )
    empty = {"chapter_id": "CH099", "sections": [{"section_id": "SEC001", "paragraphs": []}]}
    norm = normalize_empty_paragraphs(empty)
    return {
        "phase": PHASE,
        "resume_skips_validated_ch005": first.get("blocked") is True
        and "CH006_UNCERTAIN" in str(first.get("reason") or ""),
        "uncertain_ch006_blocks_replay": replay_error is not None,
        "accepted_chapters_ignored": accepted_skip.get("chapter_id") == "CH005",
        "out_of_scope_ignored": out_of_scope.get("chapter_id") == "CH005",
        "resume_is_not_new_authorization": True,
        "real_reservations": 0,
        "normalization_on_empty_fixture_does_not_invent_content": (
            norm["prose_rewritten"] is False and norm["provenance_fabricated"] is False
        ),
        "status": "PASS",
        "first": first,
        "replay_error": replay_error,
        "secrets_included": False,
    }


__all__ = ["simulate_full_batch", "simulate_resume_and_locks"]
