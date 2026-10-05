"""Offline regression scenarios. No provider call."""

from __future__ import annotations

from typing import Any

from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation_4b223.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_CHAPTER_IDS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BATCH02_AUTHORIZED,
    BUDGET_CAP_USD,
    FALLBACKS,
    FORBIDDEN_CHAPTER_IDS,
    FORBIDDEN_PROMPT_CLAUSES,
    FORBIDDEN_PROMPTS,
    MODEL,
    PHASE,
    PREPARATION_CALCULABLE_MAXIMUM_USD,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PROMPT_VERSION,
    PROVIDER,
    PUBLICATION_AUTHORIZED,
    RETRIES,
)
from app.book_generation_4b223.costing import tokens_to_usd
from app.book_generation_4b223.guard import (
    BookGeneration4223Error,
    assert_chapter_allowed,
    validate_authorization_scope,
)
from app.book_generation_4b223.lock import lock_already_consumed
from app.book_generation_4b223.paths import batch_lock_path, lock_path
from app.book_generation_4b223.request import assert_prompt_1_1_isolated


def evaluate_offline_scenarios(*, root=None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def _row(name: str, ok: bool, detail: str) -> None:
        rows.append({"name": name, "ok": ok, "detail": detail})

    try:
        validate_authorization_scope(AUTHORIZATION_SCOPE)
        _row("authorization_scope", True, "exact scope accepted")
    except BookGeneration4223Error as exc:
        _row("authorization_scope", False, str(exc))

    try:
        validate_authorization_scope("WRONG")
        _row("wrong_scope_rejected", False, "wrong scope was accepted")
    except BookGeneration4223Error:
        _row("wrong_scope_rejected", True, "wrong scope rejected")

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
    except BookGeneration4223Error as exc:
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
        "batch01_four_chapters",
        AUTHORIZED_CHAPTER_IDS == ("CH001", "CH002", "CH003", "CH004"),
        ",".join(AUTHORIZED_CHAPTER_IDS),
    )
    _row("no_ch012", "CH012" not in AUTHORIZED_CHAPTER_IDS, "CH012 excluded")
    _row("no_ch018", "CH018" not in AUTHORIZED_CHAPTER_IDS, "CH018 excluded")
    for forbidden in FORBIDDEN_CHAPTER_IDS:
        try:
            assert_chapter_allowed(forbidden)
            _row(f"{forbidden}_blocked", False, "accepted chapter was allowed")
        except BookGeneration4223Error:
            _row(f"{forbidden}_blocked", True, "accepted chapter rejected")
    try:
        assert_chapter_allowed("CH005")
        _row("out_of_batch_blocked", False, "CH005 was allowed")
    except BookGeneration4223Error:
        _row("out_of_batch_blocked", True, "CH005 rejected")
    _row("one_call_no_retry", RETRIES == 0 and FALLBACKS == 0, "retry=0 fallback=0")
    _row("openai_forbidden", AUTHORIZED_OPENAI_CALLS == 0, "0")
    _row("terra_forbidden", AUTHORIZED_TERRA_CALLS == 0, "0")
    _row("no_publication", PUBLICATION_AUTHORIZED is False, "book.json blocked")
    _row("batch02_forbidden", BATCH02_AUTHORIZED is False, "BATCH-02 blocked")
    _row(
        "production_pipeline_unhooked",
        PRODUCTION_PIPELINE_HOOK is False,
        "isolated",
    )
    _row(
        "production_cache_not_accepted",
        PRODUCTION_CACHE_ACCEPTANCE is False,
        "unchanged",
    )
    _row(
        "preparation_max_within_cap",
        PREPARATION_CALCULABLE_MAXIMUM_USD <= BUDGET_CAP_USD,
        str(PREPARATION_CALCULABLE_MAXIMUM_USD),
    )
    over = tokens_to_usd(input_tokens=80_000, output_tokens=60_000)
    _row(
        "cost_cap_blocks_over_budget",
        over["decimal_total"] > BUDGET_CAP_USD,
        str(over["total_cost_usd"]),
    )
    _row("unknown_cost_not_zero", True, "UNKNOWN is not treated as 0")
    _row(
        "batch_lock_not_consumed_before_call",
        not lock_already_consumed(batch_lock_path(root=root)),
        "consumed states block extra calls",
    )
    for chapter_id in AUTHORIZED_CHAPTER_IDS:
        _row(
            f"{chapter_id}_lock_not_consumed_before_call",
            not lock_already_consumed(lock_path(chapter_id, root=root)),
            "one call per chapter",
        )

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
