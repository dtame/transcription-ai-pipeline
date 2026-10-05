"""Phase 4B.2.20 — offline scale-up preparation. Network is not used."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.book_generation.prompt_select import resolve_prompt_module
from app.book_scale_up_preparation_4b220.constants import (
    ACCEPTED_CHAPTER,
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    CONSUMED_4B217_SCOPE,
    CONSUMED_4B218_SCOPE,
    CONSUMED_4B219_SCOPE,
    EXPECTED_FIRST_CHAPTER_ID,
    EXPECTED_FIRST_CHAPTER_IDEA_COUNT,
    EXPECTED_FIRST_CHAPTER_SECTION_COUNT,
    EXPECTED_FIRST_CHAPTER_SECTIONS,
    FAITHFUL_PROMPT_1_0,
    FAITHFUL_PROMPT_1_1,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    PUBLICATION_AUTHORIZED,
    REMAINING_CHAPTER_COUNT,
)
from app.book_scale_up_preparation_4b220.guard import (
    BookScaleUpPreparation4220Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_scale_up_preparation_4b220.hashes import snapshot
from app.book_scale_up_preparation_4b220.paths import (
    accepted_chapter_json_path,
    original_lock_path,
    production_book_path,
)
from app.book_scale_up_preparation_4b220.prompt_select import resolve_isolated_prompt
from app.book_scale_up_preparation_4b220.runner import run_phase
from app.book_scale_up_preparation_4b220.scenarios import evaluate_offline_scenarios


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
    module = resolve_isolated_prompt(FAITHFUL_PROMPT_1_1, activate=False)
    assert module.prompt_bundle()["version"] == FAITHFUL_PROMPT_1_1
    with pytest.raises(BookScaleUpPreparation4220Error):
        resolve_isolated_prompt(FAITHFUL_PROMPT_1_0)
    with pytest.raises(BookScaleUpPreparation4220Error):
        resolve_isolated_prompt(
            FAITHFUL_PROMPT_1_1,
            activate=True,
            authorization_scope="FUTURE",
            cost_authorization_present=True,
        )


def test_consumed_authorizations_cannot_be_reused():
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    with pytest.raises(BookScaleUpPreparation4220Error):
        validate_authorization_scope(CONSUMED_4B217_SCOPE)
    with pytest.raises(BookScaleUpPreparation4220Error):
        validate_authorization_scope(CONSUMED_4B218_SCOPE)
    with pytest.raises(BookScaleUpPreparation4220Error):
        validate_authorization_scope(CONSUMED_4B219_SCOPE)
    with pytest.raises(BookScaleUpPreparation4220Error):
        validate_authorization_scope("WRONG")


def test_canonical_and_ch012_hashes():
    snap = snapshot()
    assert snap["canonical_match_expected"] is True
    assert snap["original_match_expected"] is True
    assert snap["accepted_match_expected"] is True
    assert production_book_path().is_file() is False
    assert original_lock_path().is_file()
    assert accepted_chapter_json_path().is_file()


def test_offline_scenarios_pass():
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=False,
        run_tests=False,
    )
    inventory = result.bundle["remaining_chapters_inventory"]
    selection = result.bundle["first_chapter_selection"]
    context = result.bundle["first_chapter_source_context_manifest"]
    prompt = result.bundle["prompt_11_readiness"]
    contract = result.bundle["generation_contract_matrix"]
    report = evaluate_offline_scenarios(
        inventory=inventory,
        selection=selection,
        context=context,
        prompt=prompt,
        contract=contract,
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
    inventory = result.bundle["remaining_chapters_inventory"]
    assert inventory["remaining_chapter_count"] == REMAINING_CHAPTER_COUNT
    assert ACCEPTED_CHAPTER not in [row["chapter_id"] for row in inventory["chapters"]]
    selection = result.bundle["first_chapter_selection"]
    assert selection["selected_chapter_id"] == EXPECTED_FIRST_CHAPTER_ID
    assert selection["section_count"] == EXPECTED_FIRST_CHAPTER_SECTION_COUNT
    assert selection["idea_count"] == EXPECTED_FIRST_CHAPTER_IDEA_COUNT
    assert list(selection["section_ids"]) == list(EXPECTED_FIRST_CHAPTER_SECTIONS)
    assert result.bundle["prompt_11_readiness"]["activated"] is False
    assert result.bundle["scale_up_progress_manifest"]["any_authorized_false"] is True
    audit = tmp_path / "audit" / "book_scale_up_preparation_4b220"
    assert (audit / "remaining_chapters_inventory.json").is_file()
    assert (audit / "first_chapter_selection.json").is_file()
    assert (audit / "prompt_11_readiness.json").is_file()
    assert (audit / "scale_up_cost_envelope.json").is_file()
    assert not (
        tmp_path / "audit" / "book_authorial_voice_4b218" / "chapter_candidate_authorial_v2.json"
    ).exists()
    assert accepted_chapter_json_path().is_file()
    assert before["accepted_chapter"] == after["accepted_chapter"]
    assert before["original_chapter"] == after["original_chapter"]
    assert before["canonical"] == after["canonical"]
    assert production_book_path().is_file() is False
    again = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=True,
        run_tests=False,
        root=tmp_path,
    )
    assert again.bundle["header"]["result"] == "PASS"
    assert (
        again.bundle["first_chapter_selection"]["selected_chapter_id"]
        == result.bundle["first_chapter_selection"]["selected_chapter_id"]
    )
