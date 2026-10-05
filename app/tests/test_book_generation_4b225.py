"""Phase 4B.2.25 — isolated CH003–CH004 resume. Network is not used."""

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
from app.book_generation_4b223.context import build_chapter_context, load_corpus
from app.book_generation_4b223.request import assert_prompt_1_1_isolated
from app.book_generation_4b225.acceptance import inspect_ch001, inspect_ch002, record_acceptances
from app.book_generation_4b225.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_CHAPTER_IDS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BATCH02_AUTHORIZED,
    BUDGET_CAP_USD,
    CURSOR_FORECAST_USD,
    EXPECTED_CH001_JSON_SHA256,
    EXPECTED_CH001_MD_SHA256,
    EXPECTED_CH002_RECOVERED_JSON_SHA256,
    EXPECTED_CH002_RECOVERED_MD_SHA256,
    EXPECTED_CH001_LOCK_SHA256,
    EXPECTED_CH002_LOCK_SHA256,
    FALLBACKS,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    FORBIDDEN_PROMPT_CLAUSES,
    HISTORICAL_REMAINING_BUDGET_USD,
    HISTORICAL_REMAINDER_IS_AUTHORIZATION,
    MODEL,
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
from app.book_generation_4b225.hashes import file_sha256, snapshot
from app.book_generation_4b225.inventory import load_resume_specs
from app.book_generation_4b225.lock import lock_already_consumed, reserve_call
from app.book_generation_4b225.paths import (
    ch001_historical_lock_path,
    ch002_historical_lock_path,
    lock_path,
    production_book_path,
)
from app.book_generation_4b225.runner import run_phase
from app.book_generation_4b225.scenarios import evaluate_offline_scenarios


def test_historical_labels_and_prompts_stay_put():
    assert frozen_v10()["prompt_sha256"] == FROZEN_PROMPT_SHA256
    assert frozen_v101()["version"] == BOOK_GENERATOR_PROMPT_VERSION == "book-generator-1.0.1"
    assert PUBLICATION_AUTHORIZED is False
    assert PRODUCTION_PIPELINE_HOOK is False
    assert PRODUCTION_CACHE_ACCEPTANCE is False
    assert FAITHFUL_PROMPT_1_1_ACTIVATED is False
    assert BATCH02_AUTHORIZED is False
    assert AUTHORIZED_OPENAI_CALLS == 0
    assert AUTHORIZED_TERRA_CALLS == 0
    assert RETRIES == 0
    assert FALLBACKS == 0
    assert PROVIDER == "anthropic"
    assert MODEL == "claude-sonnet-5"
    assert AUTHORIZED_CHAPTER_IDS == ("CH003", "CH004")
    assert "CH001" not in AUTHORIZED_CHAPTER_IDS
    assert "CH002" not in AUTHORIZED_CHAPTER_IDS
    assert "CH012" not in AUTHORIZED_CHAPTER_IDS
    assert "CH018" not in AUTHORIZED_CHAPTER_IDS
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
    assert snapshot_prompt["replaces_historical_prompt"] is False
    assert snapshot_prompt["activated_in_production"] is False
    assert snapshot_prompt["prompt_sha256"] == (
        "e39084dc9ed3b048bfdaa2e112b380d15957085eeb613dd74c97a32b880cec50"
    )


def test_authorization_and_chapter_lock():
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    with pytest.raises(BookGeneration4225Error):
        validate_authorization_scope("BOOK_GENERATION_BATCH_01_CH001_CH004_ONE_SHOT_PER_CHAPTER")
    with pytest.raises(BookGeneration4225Error):
        validate_authorization_scope("OTHER")
    assert_chapter_allowed("CH003")
    assert_chapter_allowed("CH004")
    with pytest.raises(BookGeneration4225Error):
        assert_chapter_allowed("CH001")
    with pytest.raises(BookGeneration4225Error):
        assert_chapter_allowed("CH002")
    with pytest.raises(BookGeneration4225Error):
        assert_chapter_allowed("CH012")
    with pytest.raises(BookGeneration4225Error):
        assert_chapter_allowed("CH018")
    with pytest.raises(BookGeneration4225Error):
        assert_chapter_allowed("CH005")


def test_canonical_hashes_and_accepted_chapters_and_no_book_json():
    snap = snapshot()
    assert snap["canonical_match_expected"] is True
    assert snap["original_match_expected"] is True
    assert snap["accepted_match_expected"] is True
    assert snap["ch018_match_expected"] is True
    assert snap["ch001_match_expected"] is True
    assert snap["ch002_match_expected"] is True
    assert snap["ch012_unchanged"] is True
    assert snap["ch018_unchanged"] is True
    assert production_book_path().is_file() is False
    assert snap["canonical"]["book_json"]["exists"] is False


def test_ch001_ch002_acceptance_records_without_copy():
    recorded = record_acceptances()
    assert recorded["CH001_HUMAN_ACCEPTANCE"] == "HUMAN_EDITORIALLY_ACCEPTED"
    assert recorded["CH002_HUMAN_ACCEPTANCE"] == "HUMAN_EDITORIALLY_ACCEPTED"
    assert recorded["chapters_copied"] is False
    assert recorded["chapters_modified"] is False
    assert recorded["ch001"]["json_sha256"] == EXPECTED_CH001_JSON_SHA256
    assert recorded["ch001"]["markdown_sha256"] == EXPECTED_CH001_MD_SHA256
    assert recorded["ch002"]["json_sha256"] == EXPECTED_CH002_RECOVERED_JSON_SHA256
    assert recorded["ch002"]["markdown_sha256"] == EXPECTED_CH002_RECOVERED_MD_SHA256
    assert inspect_ch001()["preserved_sentence_present"] is True
    assert inspect_ch002()["empty_paragraph_restored"] is False
    assert file_sha256(ch001_historical_lock_path())["sha256"] == EXPECTED_CH001_LOCK_SHA256
    assert file_sha256(ch002_historical_lock_path())["sha256"] == EXPECTED_CH002_LOCK_SHA256


def test_resume_specs_match_plan_and_exclude_accepted():
    corpus = load_corpus()
    loaded = load_resume_specs(corpus=corpus)
    assert list(loaded["specs"]) == ["CH003", "CH004"]
    for chapter_id, spec in loaded["specs"].items():
        chapter = next(item for item in corpus.plan.chapters if item.chapter_id == chapter_id)
        assert spec.title == chapter.working_title
        assert spec.section_ids == tuple(section.section_id for section in chapter.sections)
        assert set(spec.idea_ids) == set(assigned_idea_ids_for_chapter(chapter))
        built = build_chapter_context(spec, corpus=corpus)
        assert built["missing_sources"] == []
        assert built["whole_transcript_injected"] is False
        assert built["chapter_id"] not in {"CH001", "CH002", "CH012", "CH018"}
        assert len(built["evidence"]["src_text"]) == spec.src_count


def test_cost_cap_and_historical_remainder_not_reused():
    assert CURSOR_FORECAST_USD <= BUDGET_CAP_USD
    assert HISTORICAL_REMAINDER_IS_AUTHORIZATION is False
    assert HISTORICAL_REMAINING_BUDGET_USD != BUDGET_CAP_USD
    over = tokens_to_usd(input_tokens=80_000, output_tokens=60_000)
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
    assert header["ch001_human_acceptance"] == "HUMAN_EDITORIALLY_ACCEPTED"
    assert header["ch002_human_acceptance"] == "HUMAN_EDITORIALLY_ACCEPTED"
    audit = tmp_path / "audit" / "real" / "book_generation_4b225_batch01_resume"
    assert (audit / "authorization.json").is_file()
    assert (audit / "ch001_accepted_editorial_manifest.json").is_file()
    assert (audit / "ch002_accepted_editorial_manifest.json").is_file()
    assert (audit / "budget_ledger.json").is_file()
    assert not (audit / "chapters" / "CH003" / "chapter_candidate.json").is_file()
    assert not (audit / "chapters" / "CH001").exists()
    assert lock_already_consumed(lock_path("CH003", root=tmp_path)) is False
    assert file_sha256(ch001_historical_lock_path())["sha256"] == EXPECTED_CH001_LOCK_SHA256
    assert file_sha256(ch002_historical_lock_path())["sha256"] == EXPECTED_CH002_LOCK_SHA256


def test_consumed_lock_blocks_second_call(tmp_path: Path):
    reserve_call(lock_path("CH003", root=tmp_path), request_sha256="test", chapter_id="CH003")
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


def test_fake_engine_two_chapters_and_no_production_cache(tmp_path: Path):
    corpus = load_corpus()
    loaded = load_resume_specs(corpus=corpus)
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
    assert result.bundle["canonical_hashes_post"]["ch012_unchanged"] is True
    assert result.bundle["canonical_hashes_post"]["ch018_unchanged"] is True
    assert result.bundle["canonical_hashes_post"]["ch001_unchanged"] is True
    assert result.bundle["canonical_hashes_post"]["ch002_unchanged"] is True
    generated = result.bundle["header"]["chapters_generated"]
    assert set(generated) <= set(AUTHORIZED_CHAPTER_IDS)
    assert "CH001" not in generated
    assert "CH002" not in generated
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
        row.get("status") != "GENERATED" or "already" in str(row.get("notes") or "").lower()
        for row in second.bundle.get("chapter_rows") or []
    )
    assert file_sha256(ch001_historical_lock_path())["sha256"] == EXPECTED_CH001_LOCK_SHA256
    assert file_sha256(ch002_historical_lock_path())["sha256"] == EXPECTED_CH002_LOCK_SHA256
