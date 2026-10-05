"""Interruption recovery around reservation, send, validation, REVIEW, and BLOCK."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.book_generation_bridge_4b214.budget import BudgetGuard
from app.book_generation_bridge_4b214.constants import (
    INTERRUPTION_POINTS,
    INTERRUPT_AFTER_BLOCK,
    INTERRUPT_AFTER_REVIEW,
    INTERRUPT_AFTER_SEND,
    LEDGER_GLOBAL,
    LEDGER_SEMANTIC_GATE,
    PHASE,
)
from app.book_generation_bridge_4b214.orchestrator import run_bridge_chapter
from app.book_generation_integration_4b213.cache import IsolatedChapterCache
from app.book_generation_integration_4b213.fakeai import FakeSemanticTransport


def _scenario_for(point: str) -> str:
    if point == INTERRUPT_AFTER_REVIEW:
        return "questionable"
    if point == INTERRUPT_AFTER_BLOCK:
        return "invented_causality"
    return "fully_supported"


def interruption_recovery() -> dict[str, Any]:
    rows = []
    ok = True
    for point in INTERRUPTION_POINTS:
        cache = IsolatedChapterCache()
        budget = BudgetGuard(
            ceilings={
                LEDGER_SEMANTIC_GATE: Decimal("5"),
                LEDGER_GLOBAL: Decimal("10"),
            },
            per_operation_ceiling=Decimal("0.25"),
        )
        scenario = _scenario_for(point)
        interrupted = run_bridge_chapter(
            scenario=scenario,
            cache=cache,
            budget=budget,
            interrupt_at=point,
            semantic=FakeSemanticTransport(scenario),
        )
        resumed = run_bridge_chapter(
            scenario=scenario,
            cache=cache,
            budget=BudgetGuard(
                ceilings={
                    LEDGER_SEMANTIC_GATE: Decimal("5"),
                    LEDGER_GLOBAL: Decimal("10"),
                },
                per_operation_ceiling=Decimal("0.25"),
            ),
            semantic=FakeSemanticTransport(scenario),
        )
        automatic_retry = bool(interrupted.get("automatic_retry"))
        treated_free = interrupted.get("treated_as_free") is True
        if point == INTERRUPT_AFTER_SEND:
            if interrupted.get("send_uncertain") is not True:
                ok = False
            if treated_free:
                ok = False
        if automatic_retry:
            ok = False
        if interrupted.get("production_cache_write") or resumed.get("production_cache_write"):
            ok = False
        if resumed.get("accepted_without_validation"):
            ok = False
        rows.append(
            {
                "interrupt_at": point,
                "scenario": scenario,
                "interrupted": bool(interrupted.get("interrupted")),
                "interrupted_decision": interrupted.get("decision"),
                "sent": bool(interrupted.get("sent")),
                "send_uncertain": bool(interrupted.get("send_uncertain")),
                "treated_as_free": treated_free,
                "automatic_retry": automatic_retry,
                "resume_decision": resumed.get("decision"),
                "production_cache_write": False,
                "real_provider_calls": 0,
                "source": "FAKEAI_SIMULATED",
            }
        )
    return {
        "phase": PHASE,
        "ok": ok,
        "cases": rows,
        "no_automatic_second_call_after_uncertain_send": all(
            not item["automatic_retry"] for item in rows
        ),
        "interrupt_after_send_not_free": all(
            not item["treated_as_free"] for item in rows
        ),
        "no_real_calls": True,
        "secrets_included": False,
    }


__all__ = ["interruption_recovery"]
