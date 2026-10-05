"""Phase 4B.2.22 — offline CH018 acceptance and batch readiness. Network is not used."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.book_batch_preparation_4b222.constants import (
    ACCEPTED_CH012_ID,
    ACCEPTED_CH018_ID,
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BATCH_CHAPTERS,
    BATCH_IDS,
    CH018_EX046,
    CH018_IDEAS,
    CH018_SECTIONS,
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
    FIRST_BATCH_ID,
    PUBLICATION_AUTHORIZED,
    REMAINING_CHAPTER_COUNT,
    TOTAL_CHAPTER_COUNT,
)
from app.book_batch_preparation_4b222.ex046 import review_ex046_traceability
from app.book_batch_preparation_4b222.guard import (
    BookBatchPreparation4222Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_batch_preparation_4b222.hard_stop import evaluate_hard_stops
from app.book_batch_preparation_4b222.hashes import snapshot
from app.book_batch_preparation_4b222.integrity import inspect_ch018_integrity
from app.book_batch_preparation_4b222.orchestrator import next_chapter_to_generate
from app.book_batch_preparation_4b222.paths import (
    accepted_chapter_json_path,
    ch018_json_path,
    ch018_md_path,
    original_lock_path,
    production_book_path,
)
from app.book_batch_preparation_4b222.runner import run_phase
from app.book_batch_preparation_4b222.scenarios import evaluate_offline_scenarios
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation_4b221.lock import lock_already_consumed
from app.book_batch_preparation_4b222.paths import ch018_lock_path


def test_offline_authorizations_and_prompt_isolation():
    assert PUBLICATION_AUTHORIZED is False
    assert AUTHORIZED_ANTHROPIC_CALLS == 0
    assert AUTHORIZED_OPENAI_CALLS == 0
    assert AUTHORIZED_SONNET_CALLS == 0
    assert AUTHORIZED_TERRA_CALLS == 0
    assert FAITHFUL_PROMPT_1_1_ACTIVATED is False
    assert_offline_only()
    with pytest.raises(ValueError):
        resolve_prompt_module(FAITHFUL_PROMPT_1_1)


def test_consumed_authorizations_cannot_be_reused():
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    with pytest.raises(BookBatchPreparation4222Error):
        validate_authorization_scope(CONSUMED_4B217_SCOPE)
    with pytest.raises(BookBatchPreparation4222Error):
        validate_authorization_scope(CONSUMED_4B218_SCOPE)
    with pytest.raises(BookBatchPreparation4222Error):
        validate_authorization_scope(CONSUMED_4B219_SCOPE)
    with pytest.raises(BookBatchPreparation4222Error):
        validate_authorization_scope(CONSUMED_4B220_SCOPE)
    with pytest.raises(BookBatchPreparation4222Error):
        validate_authorization_scope(CONSUMED_4B221_SCOPE)
    with pytest.raises(BookBatchPreparation4222Error):
        validate_authorization_scope("WRONG")


def test_canonical_ch012_and_ch018_hashes():
    snap = snapshot()
    assert snap["canonical_match_expected"] is True
    assert snap["original_match_expected"] is True
    assert snap["accepted_match_expected"] is True
    assert snap["ch018_match_expected"] is True
    assert production_book_path().is_file() is False
    assert original_lock_path().is_file()
    assert accepted_chapter_json_path().is_file()
    assert ch018_json_path().is_file()
    assert ch018_md_path().is_file()
    assert lock_already_consumed(ch018_lock_path()) is True


def test_ch018_integrity_and_ex046_review():
    integrity = inspect_ch018_integrity()
    assert integrity["chapter_id_exact"] is True
    assert integrity["sections_exact"] is True
    assert list(integrity["sections"]) == list(CH018_SECTIONS)
    assert integrity["ideas_traced"] is True
    assert integrity["ideas_found"] == list(CH018_IDEAS)
    assert integrity["ex046_in_paras_e"] is False
    assert integrity["json_sha256"] == EXPECTED_CH018_JSON_SHA256
    assert integrity["markdown_sha256"] == EXPECTED_CH018_MD_SHA256
    assert integrity["lock"]["consumed"] is True
    assert integrity["lock"]["reusable"] is False
    review = review_ex046_traceability()
    assert review["example_id"] == CH018_EX046
    assert review["correspondence_established"] is True
    assert review["paras_e_contains_ex046"] is False
    assert review["accepted_json_modified"] is False
    assert review["supporting_src"]
    assert review["matching_paragraphs"]


def test_hard_stops_cover_batch_risks():
    assert evaluate_hard_stops(authorized=False, theoretical_maximum_usd=0.1)["blocked"]
    assert evaluate_hard_stops(
        authorized=True, cost_status="UNKNOWN", remaining_authorization=True
    )["blocked"]
    assert evaluate_hard_stops(
        authorized=True,
        theoretical_maximum_usd=1.0,
        cap_usd=0.2,
        remaining_authorization=True,
    )["blocked"]
    assert evaluate_hard_stops(
        authorized=True,
        theoretical_maximum_usd=0.1,
        remaining_authorization=True,
        retry_requested=True,
    )["blocked"]
    assert evaluate_hard_stops(
        authorized=True,
        theoretical_maximum_usd=0.1,
        remaining_authorization=True,
        fallback_requested=True,
    )["blocked"]
    assert evaluate_hard_stops(
        authorized=True,
        theoretical_maximum_usd=0.1,
        remaining_authorization=True,
        lock_consumed=True,
    )["blocked"]
    assert evaluate_hard_stops(
        authorized=True,
        theoretical_maximum_usd=0.1,
        remaining_authorization=True,
        lock_uncertain=True,
    )["blocked"]
    assert evaluate_hard_stops(
        authorized=True,
        theoretical_maximum_usd=0.1,
        remaining_authorization=True,
        multi_chapter_call=True,
    )["blocked"]


def test_resume_skips_accepted_and_generated():
    nxt = next_chapter_to_generate(
        chapter_ids=["CH012", "CH018", "CH001", "CH002"],
        progress={
            "chapters": [
                {"chapter_id": "CH012", "status": "ACCEPTED"},
                {"chapter_id": "CH018", "status": "ACCEPTED"},
                {
                    "chapter_id": "CH001",
                    "status": "GENERATED",
                    "attempt": {"attempt_id": "offline"},
                },
                {"chapter_id": "CH002", "status": "PENDING"},
            ]
        },
        remaining_authorization_calls=1,
    )
    assert nxt["chapter_id"] == "CH002"
    with pytest.raises(BookBatchPreparation4222Error):
        next_chapter_to_generate(
            chapter_ids=["CH001"],
            progress={"chapters": [{"chapter_id": "CH001", "status": "UNCERTAIN"}]},
            remaining_authorization_calls=1,
        )


def test_offline_scenarios_pass():
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=False,
        run_tests=False,
    )
    report = evaluate_offline_scenarios(
        inventory=result.bundle["remaining_17_chapters_inventory"],
        plan=result.bundle["batch_generation_plan"],
        cost=result.bundle["batch_cost_envelope"],
        prompt={
            "activated": False,
            "hash_match": True,
            "prompt_sha256": EXPECTED_PROMPT_1_1_SHA256,
        },
        integrity=result.bundle["offline_regression_tests"]["ch018_integrity"],
        progress=result.bundle["batch_progress_manifest"],
    )
    assert report["failed"] == 0
    assert report["failed_ids"] == []
    assert report["real_provider_calls"] == 0


def test_phase_writes_isolated_audits_without_touching_accepted(tmp_path: Path):
    before = snapshot()
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=True,
        run_tests=False,
        root=tmp_path,
    )
    after = snapshot()
    assert result.accepted is True
    header = result.bundle["header"]
    assert header["result"] == "PASS"
    assert header["provider_calls"] == 0
    inventory = result.bundle["remaining_17_chapters_inventory"]
    assert inventory["total_chapters_in_plan"] == TOTAL_CHAPTER_COUNT
    assert inventory["accepted_chapter_count"] == 2
    assert inventory["remaining_chapter_count"] == REMAINING_CHAPTER_COUNT
    remaining_ids = [row["chapter_id"] for row in inventory["chapters"]]
    assert ACCEPTED_CH012_ID not in remaining_ids
    assert ACCEPTED_CH018_ID not in remaining_ids
    planned = [chapter for batch_id in BATCH_IDS for chapter in BATCH_CHAPTERS[batch_id]]
    assert remaining_ids == planned
    plan = result.bundle["batch_generation_plan"]
    assert plan["this_phase_executes"] is False
    assert [len(row["chapter_ids"]) for row in plan["batches"]] == [4, 4, 4, 5]
    assert plan["first_batch_id"] == FIRST_BATCH_ID
    cost = result.bundle["batch_cost_envelope"]
    assert cost["generation_17_chapters"]["complete_cost"] == "UNKNOWN"
    assert cost["authorized_spend_usd"] == 0.0
    assert cost["unknown_replaced_by_zero"] is False
    acceptance = result.bundle["ch018_editorial_acceptance"]
    assert acceptance["semantic_certification"] == "not_performed"
    assert acceptance["publication_authorization"] == "not_granted"
    assert acceptance["not_a_digital_signature"] is True
    assert result.bundle["ch018_ex046_traceability_review"]["correspondence_established"] is True
    assert result.bundle["ch018_ex046_traceability_review"]["accepted_json_modified"] is False
    progress = result.bundle["batch_progress_manifest"]
    assert progress["any_authorized_false"] is True
    statuses = {row["chapter_id"]: row["status"] for row in progress["chapters"]}
    assert statuses[ACCEPTED_CH012_ID] == "ACCEPTED"
    assert statuses[ACCEPTED_CH018_ID] == "ACCEPTED"
    assert all(
        statuses[chapter_id] == "PENDING"
        for chapter_id in remaining_ids
    )
    audit = tmp_path / "audit" / "book_batch_preparation_4b222"
    assert (audit / "ch018_editorial_acceptance.json").is_file()
    assert (audit / "ch018_accepted_editorial_manifest.json").is_file()
    assert (audit / "ch018_ex046_traceability_review.json").is_file()
    assert (audit / "remaining_17_chapters_inventory.json").is_file()
    assert (audit / "batch_generation_plan.json").is_file()
    assert (audit / "batch_cost_envelope.json").is_file()
    assert (audit / "batch_authorization_template.json").is_file()
    assert (audit / "batch_progress_manifest.json").is_file()
    assert (audit / "batch_hard_stop_conditions.json").is_file()
    assert (audit / "offline_regression_tests.json").is_file()
    assert (audit / "readiness.json").is_file()
    assert accepted_chapter_json_path().is_file()
    assert ch018_json_path().is_file()
    assert before["accepted_chapter"] == after["accepted_chapter"]
    assert before["accepted_ch018"] == after["accepted_ch018"]
    assert before["original_chapter"] == after["original_chapter"]
    assert before["canonical"] == after["canonical"]
    assert production_book_path().is_file() is False
    assert header["ready_for_first_batch_authorization"] == "YES"
    again = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=True,
        run_tests=False,
        root=tmp_path,
    )
    assert again.bundle["header"]["result"] == "PASS"
    assert again.bundle["batch_generation_plan"]["first_batch_id"] == FIRST_BATCH_ID
