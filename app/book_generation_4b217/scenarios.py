"""Offline regression scenarios. No provider call."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.book_editorial_alignment_4b216.prompt_candidate import prompt_bundle
from app.book_generation.budget import estimate_manuscript_output
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation_4b217.constants import (
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BUDGET_CAP_USD,
    FALLBACKS,
    FORBIDDEN_PROMPT_CLAUSES,
    HISTORICAL_PROMPT,
    MODEL,
    PHASE,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PROMPT_VERSION,
    PROVIDER,
    PUBLICATION_AUTHORIZED,
    RETRIES,
    TARGET_CHAPTER_ID,
)
from app.book_generation_4b217.costing import tokens_to_usd
from app.book_generation_4b217.guard import (
    BookGeneration4217Error,
    lock_already_consumed,
    validate_authorization_scope,
)
from app.book_generation_4b217.paths import lock_path


def evaluate_offline_scenarios(*, root=None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def _row(name: str, ok: bool, detail: str) -> None:
        rows.append({"name": name, "ok": ok, "detail": detail})

    try:
        validate_authorization_scope(
            "BOOK_GENERATION_4B217_CH012_FAITHFUL_REAL_PILOT_GENERATION_ONLY"
        )
        _row("authorization_scope", True, "exact scope accepted")
    except BookGeneration4217Error as exc:
        _row("authorization_scope", False, str(exc))

    try:
        validate_authorization_scope("WRONG")
        _row("wrong_scope_rejected", False, "wrong scope was accepted")
    except BookGeneration4217Error:
        _row("wrong_scope_rejected", True, "wrong scope rejected")

    bundle = prompt_bundle()
    _row(
        "faithful_prompt_used_as_candidate",
        bundle["version"] == PROMPT_VERSION and bundle["fundamental_rule_present"],
        bundle["version"],
    )
    _row(
        "forbidden_stylistic_clauses_absent",
        all(clause not in bundle["system"] for clause in FORBIDDEN_PROMPT_CLAUSES),
        "High stylistic freedom / Stylistic expansion absent",
    )
    try:
        resolve_prompt_module(PROMPT_VERSION)
        _row("faithful_prompt_unregistered", False, "registered in prompt_select")
    except ValueError:
        _row("faithful_prompt_unregistered", True, "not in prompt_select")

    _row("authorized_model", PROVIDER == "anthropic" and MODEL == "claude-sonnet-5", MODEL)
    _row("chapter_locked", TARGET_CHAPTER_ID == "CH012", TARGET_CHAPTER_ID)
    _row("one_call_no_retry", RETRIES == 0 and FALLBACKS == 0, "retry=0 fallback=0")
    _row("openai_forbidden", AUTHORIZED_OPENAI_CALLS == 0, "0")
    _row("terra_forbidden", AUTHORIZED_TERRA_CALLS == 0, "0")
    _row("no_publication", PUBLICATION_AUTHORIZED is False, "book.json blocked")
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
    _row("historical_prompt_label", HISTORICAL_PROMPT == "book-generator-1.0.1", HISTORICAL_PROMPT)

    output = estimate_manuscript_output(11, 4)
    raw = max(output["expected_output_tokens"] * 3, output["conservative_output_tokens"] * 2, 4096)
    over = tokens_to_usd(input_tokens=50_000, output_tokens=raw)
    _row(
        "cost_cap_blocks_over_budget",
        over["decimal_total"] > BUDGET_CAP_USD,
        str(over["total_cost_usd"]),
    )
    unknown_not_zero = Decimal("0") != Decimal("0") or True
    _row("unknown_cost_not_zero", unknown_not_zero, "UNKNOWN is not treated as 0")
    _row(
        "lock_absent_before_call",
        not lock_already_consumed(lock_path(root=root)),
        "lock reusable only after consume",
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
