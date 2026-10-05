"""Offline regression scenarios. FakeAI/fixtures only. No provider call."""

from __future__ import annotations

from typing import Any

from app.book_batch_preparation_4b222.constants import (
    ACCEPTED_CHAPTERS,
    ACCEPTED_CH012_ID,
    ACCEPTED_CH018_ID,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_SPEND_USD,
    AUTHORIZED_TERRA_CALLS,
    BATCH_CHAPTERS,
    BATCH_IDS,
    CONSUMED_4B217_SCOPE,
    CONSUMED_4B218_SCOPE,
    CONSUMED_4B219_SCOPE,
    CONSUMED_4B220_SCOPE,
    CONSUMED_4B221_SCOPE,
    EXPECTED_CH018_JSON_SHA256,
    EXPECTED_CH018_MD_SHA256,
    EXPECTED_PROMPT_1_1_SHA256,
    FAITHFUL_PROMPT_1_1,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    PHASE,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PUBLICATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    REMAINING_CHAPTER_COUNT,
    STATUS_ACCEPTED,
    STATUS_GENERATED,
    STATUS_UNCERTAIN,
    TOTAL_CHAPTER_COUNT,
)
from app.book_batch_preparation_4b222.guard import (
    BookBatchPreparation4222Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_batch_preparation_4b222.hard_stop import evaluate_hard_stops
from app.book_batch_preparation_4b222.hashes import snapshot
from app.book_batch_preparation_4b222.orchestrator import (
    next_chapter_to_generate,
    simulate_offline_batch,
)
from app.book_batch_preparation_4b222.paths import production_book_path
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_scale_up_preparation_4b220.prompt_select import prompt_1_1_registered_in_production
from app.book_scale_up_preparation_4b220.scenarios import provenance_fixture_cases


def evaluate_offline_scenarios(
    *,
    inventory: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
    cost: dict[str, Any] | None = None,
    prompt: dict[str, Any] | None = None,
    integrity: dict[str, Any] | None = None,
    progress: dict[str, Any] | None = None,
    root=None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def _row(name: str, ok: bool, detail: str) -> None:
        rows.append({"name": name, "ok": ok, "detail": detail})

    snap = snapshot(root=root)
    remaining_ids = [row["chapter_id"] for row in (inventory or {}).get("chapters") or []]
    planned_ids = [
        chapter_id
        for batch_id in BATCH_IDS
        for chapter_id in BATCH_CHAPTERS[batch_id]
    ]

    _row(
        "ch012_excluded",
        ACCEPTED_CH012_ID not in remaining_ids,
        "CH012 excluded from remaining queue",
    )
    _row(
        "ch018_excluded",
        ACCEPTED_CH018_ID not in remaining_ids,
        "CH018 excluded from remaining queue",
    )
    _row(
        "exactly_17_remaining",
        bool(inventory) and inventory.get("remaining_chapter_count") == REMAINING_CHAPTER_COUNT,
        "17 remaining chapters",
    )
    _row(
        "editorial_order_correct",
        remaining_ids == planned_ids and bool(inventory) and inventory.get("book_order_preserved"),
        "Remaining chapters stay in EditorialPlan order",
    )
    batch_ids = [
        chapter_id
        for batch in (plan or {}).get("batches") or []
        for chapter_id in batch.get("chapter_ids") or []
    ]
    _row(
        "lots_without_duplicates",
        len(batch_ids) == len(set(batch_ids)) == REMAINING_CHAPTER_COUNT,
        "Batch chapter IDs are unique and complete",
    )
    _row(
        "no_forgotten_chapter",
        remaining_ids == planned_ids and not (inventory or {}).get("forgotten_ids"),
        "No remaining chapter omitted",
    )
    per_chapter = (cost or {}).get("per_chapter") or []
    _row(
        "per_chapter_caps",
        all(row.get("proposed_cap_usd") and row.get("authorized_cap_usd") == 0.0 for row in per_chapter),
        "Each remaining chapter has a proposed cap and authorized 0",
    )
    batches = (cost or {}).get("batches") or []
    _row(
        "per_lot_caps",
        all(row.get("proposed_cap_usd") and row.get("authorized_cap_usd") == 0.0 for row in batches),
        "Each lot has a proposed cap and authorized 0",
    )
    generation = (cost or {}).get("generation_17_chapters") or {}
    _row(
        "global_cap",
        generation.get("authorized_cap_usd") == 0.0
        and generation.get("complete_cost") == "UNKNOWN",
        "Global authorized cap is 0; complete cost remains UNKNOWN",
    )
    _row(
        "unknown_cost_blocks",
        evaluate_hard_stops(authorized=True, cost_status="UNKNOWN", remaining_authorization=True)[
            "blocked"
        ]
        is True,
        "UNKNOWN cost is not treated as zero",
    )
    _row(
        "missing_authorization_blocks",
        evaluate_hard_stops(authorized=False, theoretical_maximum_usd=0.1)["blocked"] is True,
        "No batch authorization",
    )
    _row(
        "structural_failure_stops",
        evaluate_hard_stops(
            authorized=True,
            theoretical_maximum_usd=0.1,
            remaining_authorization=True,
            json_valid=False,
        )["blocked"]
        is True,
        "Invalid JSON stops the lot",
    )
    _row(
        "truncated_response_stops",
        evaluate_hard_stops(
            authorized=True,
            theoretical_maximum_usd=0.1,
            remaining_authorization=True,
            truncated=True,
        )["blocked"]
        is True,
        "Truncated output stops the lot",
    )
    _row(
        "invalid_idea_handle_stops",
        evaluate_hard_stops(
            authorized=True,
            theoretical_maximum_usd=0.1,
            remaining_authorization=True,
            invented_idea_handles=["IDEA999"],
        )["blocked"]
        is True,
        "Invalid IDEA handle stops the lot",
    )
    _row(
        "invalid_src_stops",
        evaluate_hard_stops(
            authorized=True,
            theoretical_maximum_usd=0.1,
            remaining_authorization=True,
            invalid_src=["SRC999999"],
        )["blocked"]
        is True,
        "Invalid SRC stops the lot",
    )
    _row(
        "no_automatic_paid_retry",
        evaluate_hard_stops(
            authorized=True,
            theoretical_maximum_usd=0.1,
            remaining_authorization=True,
            retry_requested=True,
        )["blocked"]
        is True,
        "Automatic paid retry is forbidden",
    )
    _row(
        "no_fallback",
        evaluate_hard_stops(
            authorized=True,
            theoretical_maximum_usd=0.1,
            remaining_authorization=True,
            fallback_requested=True,
        )["blocked"]
        is True,
        "Automatic fallback is forbidden",
    )
    _row(
        "consumed_lock_blocks",
        evaluate_hard_stops(
            authorized=True,
            theoretical_maximum_usd=0.1,
            remaining_authorization=True,
            lock_consumed=True,
        )["blocked"]
        is True,
        "Consumed lock cannot be reused",
    )
    _row(
        "uncertain_lock_blocks",
        evaluate_hard_stops(
            authorized=True,
            theoretical_maximum_usd=0.1,
            remaining_authorization=True,
            lock_uncertain=True,
        )["blocked"]
        is True,
        "Uncertain lock blocks another call",
    )
    progress_rows = (progress or {}).get("chapters") or []
    accepted = {
        row["chapter_id"]: row
        for row in progress_rows
        if row.get("status") == STATUS_ACCEPTED
    }
    fake_progress = {
        "chapters": [
            *progress_rows,
            {
                "chapter_id": "CH001",
                "status": STATUS_GENERATED,
                "attempt": {"attempt_id": "fake-offline"},
            },
        ]
    }
    nxt = next_chapter_to_generate(
        chapter_ids=["CH012", "CH018", "CH001", "CH002"],
        progress=fake_progress,
        remaining_authorization_calls=1,
    )
    _row(
        "idempotent_resume",
        nxt.get("chapter_id") == "CH002",
        "Resume skips accepted and already generated chapters",
    )
    _row(
        "preserves_generated_chapters",
        any(item.get("reason") == "already_generated" for item in nxt.get("skipped") or []),
        "Generated chapters are conserved",
    )
    _row(
        "preserves_accepted_chapters",
        ACCEPTED_CH012_ID in accepted and ACCEPTED_CH018_ID in accepted,
        "Accepted chapters remain referenced, not copied",
    )
    _row(
        "canonical_hashes_preserved",
        snap["canonical_match_expected"] is True,
        "SourceMap, EditorialPlan, transcript unchanged",
    )
    _row(
        "ch012_artifacts_preserved",
        snap["accepted_match_expected"] is True and snap["original_match_expected"] is True,
        "CH012 accepted and original hashes match",
    )
    _row(
        "ch018_artifacts_preserved",
        snap.get("ch018_match_expected") is True
        and bool(integrity)
        and integrity.get("json_sha256") == EXPECTED_CH018_JSON_SHA256
        and integrity.get("markdown_sha256") == EXPECTED_CH018_MD_SHA256,
        "CH018 accepted hashes match",
    )
    _row(
        "no_provider_call",
        AUTHORIZED_ANTHROPIC_CALLS == 0
        and AUTHORIZED_OPENAI_CALLS == 0
        and AUTHORIZED_SONNET_CALLS == 0
        and AUTHORIZED_TERRA_CALLS == 0
        and REAL_CHAPTER_GENERATION_AUTHORIZED is False,
        "Zero provider authorization",
    )
    _row(
        "no_publication",
        PUBLICATION_AUTHORIZED is False and production_book_path().exists() is False,
        "book.json unpublished",
    )
    production_unregistered = True
    try:
        resolve_prompt_module(FAITHFUL_PROMPT_1_1)
        production_unregistered = False
    except ValueError:
        production_unregistered = True
    _row(
        "no_global_activation",
        FAITHFUL_PROMPT_1_1_ACTIVATED is False
        and production_unregistered
        and prompt_1_1_registered_in_production() is False
        and bool(prompt)
        and prompt.get("activated") is False
        and prompt.get("hash_match") is True
        and prompt.get("prompt_sha256") == EXPECTED_PROMPT_1_1_SHA256,
        "Prompt 1.1 remains an isolated inactive candidate with matching hash",
    )
    _row(
        "consumed_scopes_rejected",
        all(
            _raises(lambda scope=scope: validate_authorization_scope(scope))
            for scope in (
                CONSUMED_4B217_SCOPE,
                CONSUMED_4B218_SCOPE,
                CONSUMED_4B219_SCOPE,
                CONSUMED_4B220_SCOPE,
                CONSUMED_4B221_SCOPE,
            )
        ),
        "Historical authorizations cannot be reused",
    )
    _row(
        "offline_guards",
        _offline_ok()
        and PRODUCTION_PIPELINE_HOOK is False
        and PRODUCTION_CACHE_ACCEPTANCE is False
        and AUTHORIZED_SPEND_USD == 0,
        "Offline guards hold",
    )
    _row(
        "nineteen_chapters_total",
        bool(inventory) and inventory.get("total_chapters_in_plan") == TOTAL_CHAPTER_COUNT,
        "EditorialPlan still has 19 chapters",
    )
    simulated = simulate_offline_batch(
        chapter_ids=["CH001", "CH002"],
        outcomes={
            "CH001": {
                "json_valid": False,
                "theoretical_maximum_usd": 0.1,
            }
        },
        authorized=True,
        remaining_authorization_calls=2,
        cap_usd=1.0,
    )
    _row(
        "lot_stops_after_structural_failure",
        simulated["stopped"] is not None and simulated["simulated_successful_units"] == 0,
        "Lot stops after the first structural failure",
    )
    uncertain = next_chapter_to_generate
    _row(
        "uncertain_resume_blocked",
        _raises(
            lambda: uncertain(
                chapter_ids=["CH001"],
                progress={
                    "chapters": [
                        {"chapter_id": "CH001", "status": STATUS_UNCERTAIN}
                    ]
                },
                remaining_authorization_calls=1,
            )
        ),
        "Uncertain attempt is not repeated",
    )
    for item in provenance_fixture_cases():
        _row(f"fixture_{item['name']}", item["ok"], item["status"])

    failed = [row["name"] for row in rows if not row["ok"]]
    return {
        "phase": PHASE,
        "passed": len(rows) - len(failed),
        "failed": len(failed),
        "failed_ids": failed,
        "rows": rows,
        "real_provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "not_a_semantic_certificate": True,
        "secrets_included": False,
    }


def _raises(fn) -> bool:
    try:
        fn()
    except (BookBatchPreparation4222Error, ValueError):
        return True
    return False


def _offline_ok() -> bool:
    try:
        assert_offline_only()
    except BookBatchPreparation4222Error:
        return False
    return True


__all__ = ["evaluate_offline_scenarios"]
