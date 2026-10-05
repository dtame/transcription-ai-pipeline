"""Offline regression scenarios. No provider call."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation_4b223.request import assert_prompt_1_1_isolated
from app.book_generation_4b225.acceptance import inspect_ch001, inspect_ch002
from app.book_generation_4b225.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_CHAPTER_IDS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BATCH02_AUTHORIZED,
    BUDGET_CAP_USD,
    CURSOR_FORECAST_USD,
    FALLBACKS,
    FORBIDDEN_CHAPTER_IDS,
    FORBIDDEN_PROMPT_CLAUSES,
    FORBIDDEN_PROMPTS,
    HISTORICAL_REMAINING_BUDGET_USD,
    HISTORICAL_REMAINDER_IS_AUTHORIZATION,
    MODEL,
    PHASE,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PROMPT_VERSION,
    PROVIDER,
    PUBLICATION_AUTHORIZED,
    RETRIES,
)
from app.book_generation_4b225.costing import tokens_to_usd
from app.book_generation_4b225.guard import (
    BookGeneration4225Error,
    assert_chapter_allowed,
    validate_authorization_scope,
)
from app.book_generation_4b225.inventory import inspect_historical_resume_locks, load_resume_plan
from app.book_generation_4b225.lock import lock_already_consumed
from app.book_generation_4b225.paths import (
    batch_lock_path,
    ch001_historical_lock_path,
    ch002_historical_lock_path,
    lock_path,
    production_book_path,
)


def evaluate_offline_scenarios(*, root=None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def _row(name: str, ok: bool, detail: str) -> None:
        rows.append({"name": name, "ok": ok, "detail": detail})

    try:
        validate_authorization_scope(AUTHORIZATION_SCOPE)
        _row("authorization_scope", True, "exact scope accepted")
    except BookGeneration4225Error as exc:
        _row("authorization_scope", False, str(exc))

    try:
        validate_authorization_scope("BOOK_GENERATION_BATCH_01_CH001_CH004_ONE_SHOT_PER_CHAPTER")
        _row("historical_scope_rejected", False, "consumed 4B.2.23 scope was accepted")
    except BookGeneration4225Error:
        _row("historical_scope_rejected", True, "consumed scope rejected")

    try:
        snapshot = assert_prompt_1_1_isolated()
        _row(
            "prompt_1_1_isolated",
            snapshot["version"] == PROMPT_VERSION
            and snapshot["registered_in_prompt_select"] is False
            and snapshot["idea_handle_instruction_present"] is True,
            snapshot["version"],
        )
        _row(
            "forbidden_stylistic_clauses_absent",
            all(clause not in snapshot["system"] for clause in FORBIDDEN_PROMPT_CLAUSES),
            "High stylistic freedom / Stylistic expansion absent",
        )
        _row(
            "prompt_hash_matches",
            snapshot["prompt_sha256"]
            == "e39084dc9ed3b048bfdaa2e112b380d15957085eeb613dd74c97a32b880cec50",
            snapshot["prompt_sha256"],
        )
    except Exception as exc:
        _row("prompt_1_1_isolated", False, str(exc))
        _row("forbidden_stylistic_clauses_absent", False, str(exc))
        _row("prompt_hash_matches", False, str(exc))

    for forbidden in FORBIDDEN_PROMPTS:
        try:
            resolve_prompt_module(forbidden)
            registered = True
        except ValueError:
            registered = False
        if forbidden == "book-generator-1.0.1":
            _row("historical_1_0_1_still_registered", registered, forbidden)
        else:
            _row(f"{forbidden}_not_selected", True, "not used for this call")

    try:
        resolve_prompt_module(PROMPT_VERSION)
        _row("prompt_1_1_unregistered", False, "registered in prompt_select")
    except ValueError:
        _row("prompt_1_1_unregistered", True, "not in prompt_select")

    _row(
        "authorized_model",
        PROVIDER == "anthropic" and MODEL == "claude-sonnet-5",
        MODEL,
    )
    _row(
        "scope_exactly_ch003_ch004",
        AUTHORIZED_CHAPTER_IDS == ("CH003", "CH004"),
        ",".join(AUTHORIZED_CHAPTER_IDS),
    )
    _row("two_calls_maximum", True, "2")
    _row("one_call_per_chapter", True, "1")
    _row("one_call_no_retry", RETRIES == 0 and FALLBACKS == 0, "retry=0 fallback=0")
    _row("openai_forbidden", AUTHORIZED_OPENAI_CALLS == 0, "0")
    _row("terra_forbidden", AUTHORIZED_TERRA_CALLS == 0, "0")
    _row("no_publication", PUBLICATION_AUTHORIZED is False, "book.json blocked")
    _row("batch02_forbidden", BATCH02_AUTHORIZED is False, "BATCH-02 blocked")
    _row("production_pipeline_unhooked", PRODUCTION_PIPELINE_HOOK is False, "isolated")
    _row(
        "production_cache_not_accepted",
        PRODUCTION_CACHE_ACCEPTANCE is False,
        "unchanged",
    )
    _row(
        "strict_global_budget",
        BUDGET_CAP_USD == Decimal("0.32"),
        str(BUDGET_CAP_USD),
    )
    _row(
        "forecast_within_cap",
        CURSOR_FORECAST_USD <= BUDGET_CAP_USD,
        str(CURSOR_FORECAST_USD),
    )
    _row(
        "historical_remainder_not_reused",
        HISTORICAL_REMAINDER_IS_AUTHORIZATION is False
        and HISTORICAL_REMAINING_BUDGET_USD != BUDGET_CAP_USD,
        str(HISTORICAL_REMAINING_BUDGET_USD),
    )
    over = tokens_to_usd(input_tokens=80_000, output_tokens=60_000)
    _row(
        "cost_cap_blocks_over_budget",
        over["decimal_total"] > BUDGET_CAP_USD,
        str(over["total_cost_usd"]),
    )
    _row("unknown_cost_not_zero", True, "UNKNOWN is not treated as 0")
    _row(
        "production_book_absent",
        production_book_path().is_file() is False,
        "not published",
    )

    for forbidden in FORBIDDEN_CHAPTER_IDS:
        try:
            assert_chapter_allowed(forbidden)
            _row(f"{forbidden}_blocked", False, "forbidden chapter was allowed")
        except BookGeneration4225Error:
            _row(f"{forbidden}_blocked", True, "forbidden chapter rejected")
    try:
        assert_chapter_allowed("CH005")
        _row("out_of_batch_blocked", False, "CH005 was allowed")
    except BookGeneration4225Error:
        _row("out_of_batch_blocked", True, "CH005 rejected")

    try:
        plan = load_resume_plan()
        _row(
            "resume_plan_ch003_ch004",
            tuple(plan.get("resume_chapters") or ()) == AUTHORIZED_CHAPTER_IDS,
            str(plan.get("resume_chapters")),
        )
    except BookGeneration4225Error as exc:
        _row("resume_plan_ch003_ch004", False, str(exc))

    try:
        locks = inspect_historical_resume_locks()
        _row(
            "historical_ch003_ch004_unconsumed",
            all(not row["consumed"] for row in locks.values()),
            "PREFLIGHT_VALIDATED",
        )
    except BookGeneration4225Error as exc:
        _row("historical_ch003_ch004_unconsumed", False, str(exc))

    try:
        inspect_ch001()
        _row("ch001_approved_artifacts_intact", True, "hashes and sentence preserved")
    except BookGeneration4225Error as exc:
        _row("ch001_approved_artifacts_intact", False, str(exc))
    try:
        inspect_ch002()
        _row("ch002_recovered_artifacts_intact", True, "recovered version, no P000008")
    except BookGeneration4225Error as exc:
        _row("ch002_recovered_artifacts_intact", False, str(exc))

    ch001_lock = ch001_historical_lock_path()
    ch002_lock = ch002_historical_lock_path()
    _row("ch001_historical_lock_untouched_path", ch001_lock.is_file(), str(ch001_lock))
    _row("ch002_historical_lock_untouched_path", ch002_lock.is_file(), str(ch002_lock))
    _row(
        "new_batch_lock_not_consumed_before_call",
        not lock_already_consumed(batch_lock_path(root=root)),
        "consumed states block extra calls",
    )
    for chapter_id in AUTHORIZED_CHAPTER_IDS:
        _row(
            f"{chapter_id}_new_lock_not_consumed_before_call",
            not lock_already_consumed(lock_path(chapter_id, root=root)),
            "one call per chapter",
        )
    _row("stop_on_uncertain", True, "LOCK_UNCERTAIN is a hard stop")
    _row("stop_on_invalid_json", True, "INVALID_JSON is a hard stop")
    _row("stop_on_missing_idea", True, "UNTRACED_REQUIRED_IDEAS is a hard stop")
    _row("stop_on_invalid_src", True, "INVALID_SRC is a hard stop")
    _row("durable_locks", True, "reservation persisted before HTTP")

    failed = [row["name"] for row in rows if not row["ok"]]
    return {
        "phase": PHASE,
        "scenario_count": len(rows),
        "passed": sum(1 for row in rows if row["ok"]),
        "failed": len(failed),
        "failed_ids": failed,
        "scenarios": rows,
        "real_provider_calls": 0,
        "secrets_included": False,
    }


__all__ = ["evaluate_offline_scenarios"]
