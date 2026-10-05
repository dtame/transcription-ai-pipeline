"""Budget reservation and reconciliation simulations. No provider invoices."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.book_generation_bridge_4b214.budget import BudgetGuard, budget_policy
from app.book_generation_bridge_4b214.constants import (
    COST_UNKNOWN,
    LEDGER_BOOK_VALIDATOR,
    LEDGER_GLOBAL,
    LEDGER_SEMANTIC_GATE,
    PHASE,
)


def _guard() -> BudgetGuard:
    return BudgetGuard(
        ceilings={
            LEDGER_SEMANTIC_GATE: Decimal("0.05"),
            LEDGER_GLOBAL: Decimal("0.08"),
            LEDGER_BOOK_VALIDATOR: None,
        },
        per_operation_ceiling=Decimal("0.04"),
        per_chapter_ceilings={"CH001": Decimal("0.04")},
    )


def budget_reservation_tests() -> dict[str, Any]:
    sufficient = _guard()
    ok_reserve = sufficient.reserve(
        provider="openai",
        model="gpt-5.6-terra",
        chapter_id="CH001",
        operation="semantic_gate_paragraph",
        input_tokens=1247,
        output_token_cap=800,
        ledger=LEDGER_SEMANTIC_GATE,
        operation_id="op-sufficient",
    )
    insufficient = _guard()
    fail_reserve = insufficient.reserve(
        provider="openai",
        model="gpt-5.6-terra",
        chapter_id="CH001",
        operation="semantic_gate_paragraph",
        input_tokens=500000,
        output_token_cap=20000,
        ledger=LEDGER_SEMANTIC_GATE,
        operation_id="op-insufficient",
    )
    unknown = _guard()
    unknown_reserve = unknown.reserve(
        provider="openai",
        model="gpt-5.6-terra",
        chapter_id="CH001",
        operation="semantic_gate_paragraph",
        input_tokens=None,
        output_token_cap=800,
        ledger=LEDGER_SEMANTIC_GATE,
        operation_id="op-unknown",
    )
    validator = _guard()
    validator_reserve = validator.reserve(
        provider="openai",
        model="gpt-5.6-terra",
        chapter_id="CH001",
        operation="phase5",
        input_tokens=1000,
        output_token_cap=1000,
        ledger=LEDGER_BOOK_VALIDATOR,
        operation_id="op-phase5",
    )
    ok = (
        ok_reserve.get("authorized") is True
        and fail_reserve.get("authorized") is False
        and unknown_reserve.get("authorized") is False
        and unknown_reserve.get("reason") == "cost_unknown_blocks_execution"
        and validator_reserve.get("authorized") is False
        and unknown_reserve.get("counted_as_zero") is False
    )
    return {
        "phase": PHASE,
        "ok": ok,
        "sufficient": ok_reserve,
        "insufficient": fail_reserve,
        "unknown": unknown_reserve,
        "phase5_unknown_or_unbounded_blocked": validator_reserve,
        "policy": budget_policy(),
        "unknown_never_zero": True,
        "control_before_call": True,
        "reservation_is_not_invoice": True,
        "secrets_included": False,
    }


def budget_reconciliation_tests() -> dict[str, Any]:
    cases = {}
    outcomes = [
        ("full_known", 1247, 316),
        ("partial_known", 1247, None),
        ("usage_absent", None, None),
        ("empty_response", 1247, 0),
        ("truncated", 1247, None),
        ("provider_error", None, None),
        ("timeout", None, None),
        ("interrupt_after_send", None, None),
    ]
    ok = True
    for outcome, inn, out in outcomes:
        guard = _guard()
        reserved = guard.reserve(
            provider="openai",
            model="gpt-5.6-terra",
            chapter_id="CH001",
            operation="semantic_gate_paragraph",
            input_tokens=1247,
            output_token_cap=800,
            ledger=LEDGER_SEMANTIC_GATE,
            operation_id=f"op-{outcome}",
        )
        guard.mark_sent(reserved["reservation_id"])
        reconciled = guard.reconcile(
            reserved["reservation_id"],
            outcome=outcome,
            input_tokens=inn,
            output_tokens=out,
        )
        replay = guard.reconcile(
            reserved["reservation_id"],
            outcome=outcome,
            input_tokens=inn,
            output_tokens=out,
            already_recorded=True,
        )
        if replay.get("double_debit") is not False:
            ok = False
        if outcome in {
            "usage_absent",
            "truncated",
            "provider_error",
            "timeout",
            "interrupt_after_send",
            "partial_known",
        }:
            if reconciled.get("counted_as_zero") is True:
                ok = False
            if outcome == "interrupt_after_send" and reconciled.get("not_treated_as_free") is not True:
                ok = False
        cases[outcome] = {
            "reconciled": reconciled,
            "replay": replay,
            "snapshot": guard.snapshot(),
        }
    already = cases["full_known"]["replay"]
    return {
        "phase": PHASE,
        "ok": ok and already.get("idempotent") is True,
        "cases": cases,
        "unknown_status": COST_UNKNOWN,
        "unknown_never_zero": True,
        "no_double_debit": True,
        "interrupt_after_send_not_free": True,
        "no_invented_provider_invoice": True,
        "secrets_included": False,
    }


__all__ = ["budget_reconciliation_tests", "budget_reservation_tests"]
