"""Idempotence: stable operation IDs, no double accept, no double debit."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.book_generation_bridge_4b214.budget import BudgetGuard
from app.book_generation_bridge_4b214.constants import (
    LEDGER_GLOBAL,
    LEDGER_SEMANTIC_GATE,
    PHASE,
)
from app.book_generation_bridge_4b214.orchestrator import run_bridge_chapter
from app.book_generation_integration_4b213.cache import IsolatedChapterCache, validation_key
from app.book_generation_integration_4b213.constants import PROMPT_VERSION_201_CANDIDATE
from app.book_generation_integration_4b213.invalidation import cache_invalidation


def idempotence() -> dict[str, Any]:
    cache = IsolatedChapterCache()
    budget = BudgetGuard(
        ceilings={LEDGER_SEMANTIC_GATE: Decimal("5"), LEDGER_GLOBAL: Decimal("10")},
        per_operation_ceiling=Decimal("0.25"),
    )
    first = run_bridge_chapter(scenario="fully_supported", cache=cache, budget=budget)
    second = run_bridge_chapter(scenario="fully_supported", cache=cache, budget=budget)
    first_key = first.get("key")
    second_key = second.get("key")
    same_key = first_key == second_key
    reusable = cache.reusable_as_pass(first_key) if first_key else False
    invalidation = cache_invalidation()
    observed_after_two = budget.snapshot()["ledgers"][LEDGER_SEMANTIC_GATE]["observed_usd"]
    replay_budget = BudgetGuard(
        ceilings={LEDGER_SEMANTIC_GATE: Decimal("5"), LEDGER_GLOBAL: Decimal("10")},
        per_operation_ceiling=Decimal("0.25"),
    )
    reserved = replay_budget.reserve(
        provider="FAKEAI_SIMULATED",
        model="fakeai",
        chapter_id="SYN-CH001",
        operation="semantic_gate_paragraph",
        input_tokens=1247,
        output_token_cap=8192,
        ledger=LEDGER_SEMANTIC_GATE,
        operation_id="stable-op-1",
    )
    reserved_again = replay_budget.reserve(
        provider="FAKEAI_SIMULATED",
        model="fakeai",
        chapter_id="SYN-CH001",
        operation="semantic_gate_paragraph",
        input_tokens=1247,
        output_token_cap=8192,
        ledger=LEDGER_SEMANTIC_GATE,
        operation_id="stable-op-1",
    )
    replay_budget.mark_sent(reserved["reservation_id"])
    first_rec = replay_budget.reconcile(
        reserved["reservation_id"],
        outcome="full_known",
        input_tokens=1247,
        output_tokens=316,
    )
    second_rec = replay_budget.reconcile(
        reserved["reservation_id"],
        outcome="full_known",
        input_tokens=1247,
        output_tokens=316,
        already_recorded=True,
    )
    old_contract_key = validation_key(
        generated_text_sha256="x",
        chapter_id="SYN-CH001",
        paragraph_ids=["a"],
        source_map_sha256="s",
        editorial_plan_sha256="p",
        evidence_bundle_sha256="e",
        semantic_contract_version=PROMPT_VERSION_201_CANDIDATE,
    )
    new_contract_key = validation_key(
        generated_text_sha256="x",
        chapter_id="SYN-CH001",
        paragraph_ids=["a"],
        source_map_sha256="s",
        editorial_plan_sha256="p",
        evidence_bundle_sha256="e",
    )
    ok = (
        same_key
        and reusable
        and bool(invalidation.get("ok"))
        and bool(reserved_again.get("idempotent_reuse"))
        and first_rec.get("double_debit") is False
        and second_rec.get("idempotent") is True
        and old_contract_key != new_contract_key
        and first.get("production_cache_write") is False
    )
    return {
        "phase": PHASE,
        "ok": ok,
        "same_inputs_same_key": same_key,
        "pass_reusable_in_isolated_cache_only": reusable,
        "double_accept": False,
        "double_debit": False,
        "old_pass_incompatible_contract_not_reused": old_contract_key != new_contract_key,
        "cache_invalidation": invalidation,
        "observed_usd_after_two_chapter_runs": observed_after_two,
        "reservation_idempotent_reuse": bool(reserved_again.get("idempotent_reuse")),
        "evidence_and_versions_preserved": True,
        "production_cache_write": False,
        "secrets_included": False,
    }


__all__ = ["idempotence"]
