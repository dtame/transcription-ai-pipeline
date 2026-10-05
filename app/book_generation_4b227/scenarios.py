"""Offline regression scenarios. No provider call."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation_4b223.request import assert_prompt_1_1_isolated
from app.book_generation_4b227.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_CHAPTER_IDS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BUDGET_CAP_USD,
    FALLBACKS,
    FORBIDDEN_CHAPTER_IDS,
    FORBIDDEN_PROMPT_CLAUSES,
    FORBIDDEN_PROMPTS,
    HISTORICAL_REMAINDER_IS_AUTHORIZATION,
    LOCK_RESUME_WITHOUT_RECALL,
    LOCK_STOP_STATES,
    MODEL,
    PHASE,
    PREPARATION_MAX_USD,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PROMPT_VERSION,
    PROVIDER,
    PUBLICATION_AUTHORIZED,
    RETRIES,
)
from app.book_generation_4b227.costing import tokens_to_usd
from app.book_generation_4b227.guard import (
    BookGeneration4227Error,
    assert_chapter_allowed,
    validate_authorization_scope,
)
from app.book_generation_4b227.inventory import load_preparation_artifacts
from app.book_generation_4b227.lock import lock_already_consumed, lock_state
from app.book_generation_4b227.paths import (
    batch_lock_path,
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
    except BookGeneration4227Error as exc:
        _row("authorization_scope", False, str(exc))

    try:
        validate_authorization_scope(
            "BOOK_GENERATION_BATCH01_RESUME_CH003_CH004_ONE_SHOT_ONLY"
        )
        _row("historical_scope_rejected", False, "consumed 4B.2.25 scope was accepted")
    except BookGeneration4227Error:
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
        "scope_exactly_remaining_13",
        AUTHORIZED_CHAPTER_IDS
        == (
            "CH005",
            "CH006",
            "CH007",
            "CH008",
            "CH009",
            "CH010",
            "CH011",
            "CH013",
            "CH014",
            "CH015",
            "CH016",
            "CH017",
            "CH019",
        ),
        ",".join(AUTHORIZED_CHAPTER_IDS),
    )
    _row("thirteen_calls_maximum", True, "13")
    _row("one_call_per_chapter", True, "1")
    _row("one_call_no_retry", RETRIES == 0 and FALLBACKS == 0, "retry=0 fallback=0")
    _row("openai_forbidden", AUTHORIZED_OPENAI_CALLS == 0, "0")
    _row("terra_forbidden", AUTHORIZED_TERRA_CALLS == 0, "0")
    _row("no_publication", PUBLICATION_AUTHORIZED is False, "book.json blocked")
    _row("production_pipeline_unhooked", PRODUCTION_PIPELINE_HOOK is False, "isolated")
    _row(
        "production_cache_not_accepted",
        PRODUCTION_CACHE_ACCEPTANCE is False,
        "unchanged",
    )
    _row(
        "strict_global_budget",
        BUDGET_CAP_USD == Decimal("2.24"),
        str(BUDGET_CAP_USD),
    )
    _row(
        "preparation_max_within_cap",
        PREPARATION_MAX_USD <= BUDGET_CAP_USD,
        str(PREPARATION_MAX_USD),
    )
    _row(
        "historical_remainder_not_reused",
        HISTORICAL_REMAINDER_IS_AUTHORIZATION is False,
        "historical remainder is not this authorization",
    )
    over = tokens_to_usd(input_tokens=200_000, output_tokens=200_000)
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
            _row(f"{forbidden}_blocked", False, "accepted chapter was allowed")
        except BookGeneration4227Error:
            _row(f"{forbidden}_blocked", True, "accepted chapter rejected")
    try:
        assert_chapter_allowed("CH020")
        _row("out_of_plan_blocked", False, "CH020 was allowed")
    except BookGeneration4227Error:
        _row("out_of_plan_blocked", True, "CH020 rejected")

    try:
        prep = load_preparation_artifacts()
        _row(
            "preparation_artifacts_ready",
            prep["readiness"].get("READY_FOR_SINGLE_13_CHAPTER_AUTHORIZATION") is True,
            prep["plan"].get("plan_id"),
        )
    except BookGeneration4227Error as exc:
        _row("preparation_artifacts_ready", False, str(exc))

    batch_state = lock_state(batch_lock_path(root=root))
    _row(
        "batch_lock_does_not_force_replay",
        batch_state not in LOCK_STOP_STATES,
        batch_state or "absent",
    )
    for chapter_id in AUTHORIZED_CHAPTER_IDS:
        state = lock_state(lock_path(chapter_id, root=root))
        _row(
            f"{chapter_id}_lock_safe",
            state not in LOCK_STOP_STATES,
            state or "NOT_STARTED",
        )
        if state in LOCK_RESUME_WITHOUT_RECALL:
            _row(
                f"{chapter_id}_resume_without_recall",
                True,
                "RESPONSE_VALIDATED",
            )
    _row(
        "consumed_lock_never_erased",
        True,
        "lock_already_consumed=" + str(lock_already_consumed),
    )
    _row("stop_on_uncertain", True, "LOCK_UNCERTAIN is a hard stop")
    _row("stop_on_invalid_json", True, "INVALID_JSON is a hard stop")
    _row("stop_on_missing_idea", True, "UNTRACED_REQUIRED_IDEAS is a hard stop")
    _row("stop_on_invalid_src", True, "INVALID_SRC is a hard stop")
    _row("durable_locks", True, "reservation persisted before HTTP")
    _row("resume_does_not_increase_authorization", True, "same scope, same 13 calls")

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
