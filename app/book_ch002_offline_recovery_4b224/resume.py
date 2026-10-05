"""BATCH-01 resume plan for CH003 and CH004. Not an authorization. Not executed."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.book_ch002_offline_recovery_4b224.chapter_io import load_json
from app.book_ch002_offline_recovery_4b224.constants import (
    BATCH_ID,
    CONSUMED_4B223_SCOPE,
    EXPECTED_PROMPT_1_1_SHA256,
    HISTORICAL_BATCH01_CAP_USD,
    HISTORICAL_BATCH01_COST_USD,
    HISTORICAL_CH001_COST_USD,
    HISTORICAL_CH002_COST_USD,
    HISTORICAL_CH003_PREFLIGHT_MAX_USD,
    HISTORICAL_CH004_PREFLIGHT_MAX_USD,
    MODEL,
    PHASE,
    PROMPT_VERSION,
    PROVIDER,
    RESUME_CHAPTER_IDS,
    RESUME_THEORETICAL_MAXIMUM_USD,
    TARGET_CHAPTER_ID,
)
from app.book_ch002_offline_recovery_4b224.paths import (
    batch01_chapter_dir,
    batch01_ledger_path,
    original_lock_file,
)
from app.book_generation_4b223.lock import lock_already_consumed, read_lock


def build_resume_plan(*, recovery_succeeded: bool) -> dict[str, Any]:
    ledger = load_json(batch01_ledger_path())
    locks = {
        chapter_id: read_lock(original_lock_file(chapter_id)) or {}
        for chapter_id in ("CH001", "CH002", "CH003", "CH004")
    }
    costs = {}
    for chapter_id in RESUME_CHAPTER_IDS:
        path = batch01_chapter_dir(chapter_id) / "cost_preflight.json"
        costs[chapter_id] = load_json(path)
    ch002_future_calls = (
        "excluded_unless_new_explicit_human_decision"
        if recovery_succeeded
        else "requires_new_explicit_human_decision_if_regeneration_is_requested"
    )
    proposed_cap = RESUME_THEORETICAL_MAXIMUM_USD
    return {
        "phase": PHASE,
        "batch_id": BATCH_ID,
        "executed_this_phase": False,
        "previous_authorization_reusable": False,
        "consumed_authorization_scope": CONSUMED_4B223_SCOPE,
        "remaining_4b223_budget_is_not_authorization": True,
        "historical_facts_unmodified": {
            "CH001": {
                "status": "GENERATED",
                "call_consumed": True,
                "lock_state": locks["CH001"].get("state"),
                "actual_cost_usd": float(HISTORICAL_CH001_COST_USD),
            },
            "CH002": {
                "status": "FAILED",
                "call_consumed": True,
                "lock_state": locks["CH002"].get("state"),
                "actual_cost_usd": float(HISTORICAL_CH002_COST_USD),
                "include_in_future_calls": ch002_future_calls,
            },
            "CH003": {
                "status": "NOT_STARTED",
                "call_consumed": lock_already_consumed(original_lock_file("CH003")),
                "lock_state": locks["CH003"].get("state"),
                "actual_cost_usd": 0,
            },
            "CH004": {
                "status": "NOT_STARTED",
                "call_consumed": lock_already_consumed(original_lock_file("CH004")),
                "lock_state": locks["CH004"].get("state"),
                "actual_cost_usd": 0,
            },
            "batch_historical_cost_usd": float(HISTORICAL_BATCH01_COST_USD),
            "batch_original_cap_usd": float(HISTORICAL_BATCH01_CAP_USD),
            "ledger_remaining_budget_usd": ledger.get("remaining_budget_usd"),
        },
        "resume_chapters": list(RESUME_CHAPTER_IDS),
        "exclude_from_resume_calls": [
            "CH001",
            TARGET_CHAPTER_ID if recovery_succeeded else None,
        ],
        "model": f"{PROVIDER}/{MODEL}",
        "prompt": PROMPT_VERSION,
        "prompt_sha256": EXPECTED_PROMPT_1_1_SHA256,
        "prompt_globally_activated": False,
        "updated_forecast": {
            "CH003_theoretical_maximum_usd": float(HISTORICAL_CH003_PREFLIGHT_MAX_USD),
            "CH004_theoretical_maximum_usd": float(HISTORICAL_CH004_PREFLIGHT_MAX_USD),
            "resume_theoretical_maximum_usd": float(proposed_cap),
            "pricing": "Anthropic official pricing/model documentation, 2026-09-18",
            "input_usd_per_1m": 2.0,
            "output_usd_per_1m": 10.0,
            "unknown_is_not_zero": True,
            "historical_remaining_budget_usd": ledger.get("remaining_budget_usd"),
            "historical_remaining_budget_is_authorization": False,
        },
        "preconditions": [
            "Canonical SourceMap, EditorialPlan, and clean transcript hashes still match.",
            "CH012 and CH018 remain immutable.",
            "CH001 and CH002 original artifacts remain immutable.",
            "CH003 and CH004 locks remain unconsumed (PREFLIGHT_VALIDATED).",
            "A new explicit human authorization names CH003 and CH004 only.",
            "The 4B.2.23 remaining budget is not treated as that authorization.",
            "Prompt 1.1 remains an isolated explicit selection.",
        ],
        "call_limits": {
            "max_chapters": 2,
            "max_calls": 2,
            "max_calls_per_chapter": 1,
            "retries": 0,
            "fallbacks": 0,
            "openai": 0,
            "terra": 0,
            "thinking": "disabled",
        },
        "financial_limits": {
            "authorized_spend_this_phase_usd": 0.0,
            "proposed_future_cap_usd": float(proposed_cap),
            "proposed_future_cap_is_not_authorized": True,
            "do_not_use_historical_remainder_as_cap": True,
        },
        "stop_conditions": [
            "INVALID_JSON",
            "INVALID_CONTRACT",
            "COST_UNKNOWN",
            "ACTUAL_COST_EXCEEDS_THEORETICAL_MAXIMUM",
            "LOCK_CONSUMED",
            "LOCK_UNCERTAIN",
            "CANONICAL_HASH_MISMATCH",
            "ANY_PROVIDER_OTHER_THAN_AUTHORIZED_ANTHROPIC_SONNET",
        ],
        "locking": {
            "new_authorization_required": True,
            "do_not_reset_ch001_lock": True,
            "do_not_reset_ch002_lock": True,
            "do_not_reuse_batch01_authorization": True,
            "ch003_lock_state": locks["CH003"].get("state"),
            "ch004_lock_state": locks["CH004"].get("state"),
            "ch003_consumed": lock_already_consumed(original_lock_file("CH003")),
            "ch004_consumed": lock_already_consumed(original_lock_file("CH004")),
        },
        "human_authorization_required": True,
        "this_plan_is_not_authorization": True,
        "do_not_execute": True,
        "secrets_included": False,
    }


def money(value: Decimal | float) -> str:
    return f"{Decimal(str(value))} USD"


__all__ = ["build_resume_plan", "money"]
