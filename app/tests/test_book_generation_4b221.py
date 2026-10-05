"""Phase 4B.2.21 — isolated CH018 one-shot. Network is not used."""

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
from app.book_generation_4b221.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BUDGET_CAP_USD,
    EXPECTED_IDEA_IDS,
    EXPECTED_SECTION_IDS,
    FALLBACKS,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    FORBIDDEN_PROMPT_CLAUSES,
    MODEL,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PROMPT_VERSION,
    PROVIDER,
    PUBLICATION_AUTHORIZED,
    RETRIES,
    TARGET_CHAPTER_ID,
)
from app.book_generation_4b221.context import build_ch018_context, chapter_from_plan, load_corpus
from app.book_generation_4b221.costing import reserve_budget, tokens_to_usd
from app.book_generation_4b221.guard import (
    BookGeneration4221Error,
    assert_chapter_allowed,
    validate_authorization_scope,
)
from app.book_generation_4b221.hashes import snapshot
from app.book_generation_4b221.lock import lock_already_consumed, reserve_call
from app.book_generation_4b221.paths import lock_path, production_book_path
from app.book_generation_4b221.request import assert_prompt_1_1_isolated
from app.book_generation_4b221.runner import run_phase
from app.book_generation_4b221.scenarios import evaluate_offline_scenarios


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
    assert TARGET_CHAPTER_ID == "CH018"
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


def test_authorization_and_chapter_lock():
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    with pytest.raises(BookGeneration4221Error):
        validate_authorization_scope("OTHER")
    assert_chapter_allowed("CH018")
    with pytest.raises(BookGeneration4221Error):
        assert_chapter_allowed("CH012")
    with pytest.raises(BookGeneration4221Error):
        assert_chapter_allowed("CH016")


def test_canonical_hashes_and_ch012_and_no_book_json():
    snap = snapshot()
    assert snap["canonical_match_expected"] is True
    assert snap["original_match_expected"] is True
    assert snap["accepted_match_expected"] is True
    assert snap["ch012_unchanged"] is True
    assert production_book_path().is_file() is False
    assert snap["canonical"]["book_json"]["exists"] is False


def test_ch018_evidence_is_isolated_and_has_src():
    corpus = load_corpus()
    chapter = chapter_from_plan(corpus.plan)
    built = build_ch018_context(corpus=corpus)
    evidence = built["evidence"]
    assert evidence["chapter"]["id"] == "CH018"
    idea_ids = [row["id"] for row in evidence["ideas"]]
    assert len(idea_ids) == 11
    assert set(idea_ids) == set(EXPECTED_IDEA_IDS)
    assert set(idea_ids) == set(assigned_idea_ids_for_chapter(chapter))
    assert [row["id"] for row in evidence["sections"]] == list(EXPECTED_SECTION_IDS)
    assert len(evidence["src_text"]) == 79
    assert built["missing_sources"] == []
    assert built["whole_transcript_injected"] is False
    assert (evidence.get("chapter") or {}).get("id") != "CH012"


def test_cost_cap_blocks_over_budget():
    over = tokens_to_usd(input_tokens=80_000, output_tokens=20_000)
    assert over["decimal_total"] > BUDGET_CAP_USD
    identity = {
        "payload": {
            "system": "x" * 400_000,
            "messages": [{"role": "user", "content": "y" * 400_000}],
        },
        "thinking_mode": "disabled",
    }
    reserved = reserve_budget(identity, idea_count=11, section_count=4)
    assert reserved["blocked"] is True
    assert reserved["unknown_is_not_zero"] is True


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
    header = result.bundle["header"]
    assert header["provider_calls"] == 0
    assert header["openai_http"] == 0
    assert header["chapter"] == "CH018"
    audit = tmp_path / "audit" / "real" / "book_generation_4b221_ch018"
    assert (audit / "preflight.json").is_file()
    assert (audit / "cost_preflight.json").is_file()
    assert (audit / "prompt_manifest.json").is_file()
    assert not (audit / "chapter_candidate.json").is_file()
    assert lock_already_consumed(lock_path(root=tmp_path)) is False


def test_consumed_lock_blocks_second_call(tmp_path: Path):
    reserve_call(lock_path(root=tmp_path), request_sha256="test")
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        dry_run=False,
        execute_real=True,
        allow_real_provider=True,
        root=tmp_path,
        write_artifacts=True,
        run_tests=False,
    )
    assert result.mode == "BLOCKED_PRECALL"
    assert result.bundle["header"]["provider_calls"] == 0
    assert result.bundle["preflight"]["block_reason"] == "PROVIDER_CALL_ALREADY_CONSUMED"


def test_fake_engine_one_call_and_no_production_cache(tmp_path: Path):
    corpus = load_corpus()
    chapter = chapter_from_plan(corpus.plan)
    transport = covering_chapter_transport(chapter, language=corpus.language)
    engine = FakeAIEngine(
        script=[
            FakeReply(
                text=json.dumps(transport),
                parsed=transport,
                finish_reason="stop",
            )
        ],
        model=MODEL,
    )
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
    candidate = result.bundle.get("chapter_candidate")
    if candidate:
        assert candidate["chapter_id"] == "CH018"
        assert [section["section_id"] for section in candidate["sections"]] == list(
            EXPECTED_SECTION_IDS
        )
    second = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        dry_run=False,
        execute_real=True,
        allow_real_provider=True,
        engine=FakeAIEngine(
            script=[
                FakeReply(
                    text=json.dumps(transport),
                    parsed=transport,
                    finish_reason="stop",
                )
            ],
            model=MODEL,
        ),
        root=tmp_path,
        write_artifacts=True,
        run_tests=False,
    )
    assert second.bundle["header"]["provider_calls"] == 0
    assert second.bundle["preflight"]["block_reason"] == "PROVIDER_CALL_ALREADY_CONSUMED"
