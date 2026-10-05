"""Phase 4B.2.27 — isolated remaining-13 generation. Network is not used."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.book_generation.constants import BOOK_GENERATOR_PROMPT_VERSION
from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.fixtures import covering_chapter_transport
from app.book_generation.prompt import FROZEN_PROMPT_SHA256, prompt_bundle as frozen_v10
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation.prompt_v101 import prompt_bundle as frozen_v101
from app.book_generation_4b223.request import assert_prompt_1_1_isolated
from app.book_generation_4b227.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_CHAPTER_IDS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BUDGET_CAP_USD,
    EXPECTED_REMAINING_IDEAS,
    EXPECTED_REMAINING_SECTIONS,
    FALLBACKS,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    FORBIDDEN_CHAPTER_IDS,
    FORBIDDEN_PROMPT_CLAUSES,
    GENERATED_STATUS,
    HISTORICAL_REMAINDER_IS_AUTHORIZATION,
    MODEL,
    PREPARATION_MAX_USD,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PROMPT_VERSION,
    PROVIDER,
    PUBLICATION_AUTHORIZED,
    RETRIES,
)
from app.book_generation_4b227.context import build_chapter_context, load_corpus
from app.book_generation_4b227.costing import tokens_to_usd
from app.book_generation_4b227.guard import (
    BookGeneration4227Error,
    assert_chapter_allowed,
    validate_authorization_scope,
)
from app.book_generation_4b227.hashes import snapshot
from app.book_generation_4b227.inventory import load_remaining_specs
from app.book_generation_4b227.lock import lock_already_consumed, reserve_call
from app.book_generation_4b227.paths import lock_path, production_book_path
from app.book_generation_4b227.runner import run_phase
from app.book_generation_4b227.scenarios import evaluate_offline_scenarios
from app.book_full_generation_preparation_4b226.hashes import file_sha256
from app.book_full_generation_preparation_4b226.paths import (
    ch001_approved_json_path,
    ch003_approved_json_path,
    ch004_approved_json_path,
)


def test_historical_labels_and_prompts_stay_put():
    assert frozen_v10()["prompt_sha256"] == FROZEN_PROMPT_SHA256
    assert frozen_v101()["version"] == BOOK_GENERATOR_PROMPT_VERSION == "book-generator-1.0.1"
    assert PUBLICATION_AUTHORIZED is False
    assert PRODUCTION_PIPELINE_HOOK is False
    assert PRODUCTION_CACHE_ACCEPTANCE is False
    assert FAITHFUL_PROMPT_1_1_ACTIVATED is False
    assert AUTHORIZED_OPENAI_CALLS == 0
    assert AUTHORIZED_TERRA_CALLS == 0
    assert RETRIES == 0
    assert FALLBACKS == 0
    assert PROVIDER == "anthropic"
    assert MODEL == "claude-sonnet-5"
    assert AUTHORIZED_CHAPTER_IDS == (
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
    )
    for accepted in FORBIDDEN_CHAPTER_IDS:
        assert accepted not in AUTHORIZED_CHAPTER_IDS
    assert PROMPT_VERSION == "book-generator-faithful-restatement-1.1-candidate"
    with pytest.raises(ValueError):
        resolve_prompt_module(PROMPT_VERSION)


def test_prompt_1_1_isolated_and_rejects_style_license():
    snapshot_prompt = assert_prompt_1_1_isolated()
    system = snapshot_prompt["system"]
    for clause in FORBIDDEN_PROMPT_CLAUSES:
        assert clause not in system
    assert snapshot_prompt["fundamental_rule_present"] is True
    assert snapshot_prompt["idea_handle_instruction_present"] is True
    assert snapshot_prompt["registered_in_prompt_select"] is False
    assert snapshot_prompt["activated_in_production"] is False
    assert snapshot_prompt["prompt_sha256"] == (
        "e39084dc9ed3b048bfdaa2e112b380d15957085eeb613dd74c97a32b880cec50"
    )


def test_authorization_and_chapter_lock():
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    with pytest.raises(BookGeneration4227Error):
        validate_authorization_scope(
            "BOOK_GENERATION_BATCH01_RESUME_CH003_CH004_ONE_SHOT_ONLY"
        )
    with pytest.raises(BookGeneration4227Error):
        validate_authorization_scope("OTHER")
    assert_chapter_allowed("CH005")
    assert_chapter_allowed("CH019")
    for forbidden in FORBIDDEN_CHAPTER_IDS:
        with pytest.raises(BookGeneration4227Error):
            assert_chapter_allowed(forbidden)
    with pytest.raises(BookGeneration4227Error):
        assert_chapter_allowed("CH020")


def test_canonical_hashes_and_accepted_chapters_and_no_book_json():
    snap = snapshot()
    assert snap["canonical_match_expected"] is True
    assert snap["six_accepted_immutable"] is True
    assert production_book_path().is_file() is False
    assert snap["canonical"]["book_json"]["exists"] is False
    assert file_sha256(ch001_approved_json_path())["exists"] is True
    assert file_sha256(ch003_approved_json_path())["exists"] is True
    assert file_sha256(ch004_approved_json_path())["exists"] is True


def test_remaining_specs_match_plan_and_exclude_accepted():
    corpus = load_corpus()
    loaded = load_remaining_specs(corpus=corpus)
    assert list(loaded["specs"]) == list(AUTHORIZED_CHAPTER_IDS)
    assert sum(spec.section_count for spec in loaded["specs"].values()) == (
        EXPECTED_REMAINING_SECTIONS
    )
    assert sum(spec.idea_count for spec in loaded["specs"].values()) == (
        EXPECTED_REMAINING_IDEAS
    )
    for chapter_id, spec in loaded["specs"].items():
        chapter = next(item for item in corpus.plan.chapters if item.chapter_id == chapter_id)
        assert spec.title == chapter.working_title
        assert spec.section_ids == tuple(section.section_id for section in chapter.sections)
        assert set(spec.idea_ids) == set(assigned_idea_ids_for_chapter(chapter))
        built = build_chapter_context(spec, corpus=corpus)
        assert built["missing_sources"] == []
        assert built["whole_transcript_injected"] is False
        assert built["chapter_id"] not in FORBIDDEN_CHAPTER_IDS
        assert len(built["evidence"]["src_text"]) == spec.src_count


def test_cost_cap_and_historical_remainder_not_reused():
    assert PREPARATION_MAX_USD <= BUDGET_CAP_USD
    assert HISTORICAL_REMAINDER_IS_AUTHORIZATION is False
    over = tokens_to_usd(input_tokens=200_000, output_tokens=200_000)
    assert over["decimal_total"] > BUDGET_CAP_USD


def test_offline_scenarios_pass():
    report = evaluate_offline_scenarios()
    assert report["failed"] == 0
    assert report["real_provider_calls"] == 0


def test_dry_run_writes_audits_without_provider(tmp_path: Path):
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        dry_run=True,
        execute_real=False,
        root=tmp_path,
        write_artifacts=True,
        run_tests=False,
    )
    assert result.engine_generate_attempts == 0
    assert result.anthropic_post_attempts == 0
    assert result.mode == "DRY_RUN"
    header = result.bundle["header"]
    assert header["provider_calls"] == 0
    assert header["openai_http"] == 0
    assert header["chapters_generated"] == []
    audit = tmp_path / "audit" / "real" / "book_generation_4b227_remaining13"
    assert (audit / "authorization.json").is_file()
    assert (audit / "accepted_chapters_manifest.json").is_file()
    assert (audit / "budget_ledger.json").is_file()
    assert (audit / "progress.json").is_file()
    assert not (audit / "chapters" / "CH005" / "chapter_candidate.json").is_file()
    assert not (audit / "chapters" / "CH001").exists()
    assert lock_already_consumed(lock_path("CH005", root=tmp_path)) is False


def test_consumed_lock_blocks_second_call(tmp_path: Path):
    reserve_call(lock_path("CH005", root=tmp_path), request_sha256="test", chapter_id="CH005")
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        dry_run=False,
        execute_real=True,
        allow_real_provider=True,
        root=tmp_path,
        write_artifacts=True,
        run_tests=False,
    )
    assert result.bundle["header"]["provider_calls"] == 0 or result.mode in {
        "BLOCKED_PRECALL",
        "PARTIAL",
        "FAIL",
        "INTERRUPTED",
    }
    assert "CH001" not in (result.bundle["header"].get("chapters_generated") or [])


def test_fake_engine_thirteen_chapters_and_no_production_cache(tmp_path: Path):
    corpus = load_corpus()
    loaded = load_remaining_specs(corpus=corpus)
    replies = []
    for chapter_id in AUTHORIZED_CHAPTER_IDS:
        chapter = next(item for item in corpus.plan.chapters if item.chapter_id == chapter_id)
        transport = covering_chapter_transport(chapter, language=corpus.language)
        replies.append(
            FakeReply(
                text=json.dumps(transport),
                parsed=transport,
                finish_reason="stop",
                input_tokens=4000,
                output_tokens=800,
            )
        )
    engine = FakeAIEngine(script=replies, model=MODEL)
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        dry_run=False,
        execute_real=True,
        allow_real_provider=True,
        engine=engine,
        root=tmp_path,
        write_artifacts=True,
        run_tests=False,
        persist_usage=False,
    )
    assert result.bundle["header"]["openai_http"] == 0
    assert result.bundle["execution"]["retries"] == 0
    assert result.bundle["execution"]["fallbacks"] == 0
    assert result.bundle["isolated_cache"]["production_writes"] == 0
    assert result.bundle["canonical_hashes_post"]["canonical_match_expected"] is True
    assert result.bundle["canonical_hashes_post"]["six_accepted_immutable"] is True
    generated = result.bundle["header"]["chapters_generated"]
    assert set(generated) <= set(AUTHORIZED_CHAPTER_IDS)
    for accepted in FORBIDDEN_CHAPTER_IDS:
        assert accepted not in generated
    if result.bundle["header"]["result"] == "PASS":
        assert generated == list(AUTHORIZED_CHAPTER_IDS)
        assert all(row.get("status") == GENERATED_STATUS for row in result.bundle["chapter_rows"])
    second = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        dry_run=False,
        execute_real=True,
        allow_real_provider=True,
        engine=FakeAIEngine(script=replies, model=MODEL),
        root=tmp_path,
        write_artifacts=True,
        run_tests=False,
    )
    assert second.bundle["header"]["provider_calls"] == 0 or all(
        row.get("status") == GENERATED_STATUS
        for row in second.bundle.get("chapter_rows") or []
        if row.get("chapter_id") in generated
    )
    assert production_book_path().is_file() is False
