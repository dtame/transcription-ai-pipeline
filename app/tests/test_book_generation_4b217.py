"""Phase 4B.2.17 — isolated CH012 faithful pilot. Network is not used."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.book_editorial_alignment_4b216.constants import FAITHFUL_PROMPT_VERSION
from app.book_generation.constants import BOOK_GENERATOR_PROMPT_VERSION
from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.fixtures import covering_chapter_transport
from app.book_generation.prompt import FROZEN_PROMPT_SHA256, prompt_bundle as frozen_v10
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation.prompt_v101 import prompt_bundle as frozen_v101
from app.book_generation_4b217.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BUDGET_CAP_USD,
    FALLBACKS,
    FORBIDDEN_PROMPT_CLAUSES,
    HISTORICAL_4B215_STATUS,
    HISTORICAL_4B216_STATUS,
    HISTORICAL_PROMPT,
    MODEL,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PROMPT_VERSION,
    PROVIDER,
    PUBLICATION_AUTHORIZED,
    RETRIES,
    TARGET_CHAPTER_ID,
)
from app.book_generation_4b217.context import (
    build_ch012_evidence,
    chapter_from_plan,
    load_canonical_corpus,
)
from app.book_generation_4b217.costing import reserve_budget, tokens_to_usd
from app.book_generation_4b217.guard import (
    BookGeneration4217Error,
    consume_remote_lock,
    validate_authorization_scope,
)
from app.book_generation_4b217.hashes import snapshot
from app.book_generation_4b217.paths import lock_path, production_book_path
from app.book_generation_4b217.request import assert_faithful_prompt_isolated
from app.book_generation_4b217.runner import run_phase
from app.book_generation_4b217.scenarios import evaluate_offline_scenarios


def test_historical_labels_and_prompts_stay_put():
    assert HISTORICAL_PROMPT == BOOK_GENERATOR_PROMPT_VERSION == "book-generator-1.0.1"
    assert frozen_v10()["prompt_sha256"] == FROZEN_PROMPT_SHA256
    assert frozen_v101()["version"] == "book-generator-1.0.1"
    assert HISTORICAL_4B215_STATUS == "PARTIAL"
    assert HISTORICAL_4B216_STATUS == "PASS"
    assert PUBLICATION_AUTHORIZED is False
    assert PRODUCTION_PIPELINE_HOOK is False
    assert PRODUCTION_CACHE_ACCEPTANCE is False
    assert AUTHORIZED_OPENAI_CALLS == 0
    assert AUTHORIZED_TERRA_CALLS == 0
    assert RETRIES == 0
    assert FALLBACKS == 0
    assert PROVIDER == "anthropic"
    assert MODEL == "claude-sonnet-5"
    assert TARGET_CHAPTER_ID == "CH012"
    assert PROMPT_VERSION == FAITHFUL_PROMPT_VERSION
    with pytest.raises(ValueError):
        resolve_prompt_module(PROMPT_VERSION)


def test_faithful_prompt_rejects_historical_style_license():
    snapshot_prompt = assert_faithful_prompt_isolated()
    system = snapshot_prompt["system"]
    for clause in FORBIDDEN_PROMPT_CLAUSES:
        assert clause not in system
    assert snapshot_prompt["fundamental_rule_present"] is True
    assert snapshot_prompt["registered_in_prompt_select"] is False
    assert snapshot_prompt["replaces_historical_prompt"] is False


def test_authorization_and_chapter_lock():
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    with pytest.raises(BookGeneration4217Error):
        validate_authorization_scope("OTHER")
    from app.book_generation_4b217.guard import assert_chapter_allowed

    assert_chapter_allowed("CH012")
    with pytest.raises(BookGeneration4217Error):
        assert_chapter_allowed("CH016")


def test_canonical_hashes_and_no_book_json():
    snap = snapshot()
    assert snap["canonical_match_expected"] is True
    assert production_book_path().is_file() is False
    assert snap["canonical"]["book_json"]["exists"] is False


def test_ch012_evidence_is_isolated_and_has_src():
    inputs, index, language = load_canonical_corpus()
    chapter = chapter_from_plan(inputs.plan)
    evidence = build_ch012_evidence(
        inputs.plan,
        inputs.source_map,
        chapter,
        language=language,
        transcript_index=index,
    )
    assert evidence["chapter"]["id"] == "CH012"
    idea_ids = [row["id"] for row in evidence["ideas"]]
    assert len(idea_ids) == 11
    assert set(idea_ids) == set(assigned_idea_ids_for_chapter(chapter))
    assert [row["id"] for row in evidence["sections"]] == [
        "SEC047",
        "SEC048",
        "SEC049",
        "SEC050",
    ]
    assert any(row["id"] == "UNC029" for row in evidence["uncertainties"])
    assert evidence["src_text"]
    other = [item.chapter_id for item in inputs.plan.chapters if item.chapter_id != "CH012"]
    blob = json.dumps(evidence)
    assert "CH016" not in (evidence.get("chapter") or {}).get("id", "")
    for chapter_id in other:
        assert (evidence.get("chapter") or {}).get("id") != chapter_id
    assert "High stylistic freedom" not in blob


def test_cost_cap_blocks_over_budget():
    over = tokens_to_usd(input_tokens=80_000, output_tokens=20_000)
    assert over["decimal_total"] > BUDGET_CAP_USD
    identity = {
        "payload": {
            "system": "x" * 400_000,
            "messages": [{"role": "user", "content": "y" * 400_000}],
        }
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
    assert result.bundle["provider_response_metadata"]["invented_response"] is False
    assert (tmp_path / "audit" / "real" / "book_generation_4b217_ch012" / "preflight.json").is_file()
    assert (tmp_path / "audit" / "real" / "book_generation_4b217_ch012" / "cost_preflight.json").is_file()
    assert not lock_path(root=tmp_path).exists()


def test_consumed_lock_blocks_second_call(tmp_path: Path):
    consume_remote_lock(
        path=lock_path(root=tmp_path),
        phase="4B.2.17",
        scope=AUTHORIZATION_SCOPE,
    )
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
    inputs, index, language = load_canonical_corpus()
    chapter = chapter_from_plan(inputs.plan)
    transport = covering_chapter_transport(chapter, language=language)
    engine = FakeAIEngine(
        script=[FakeReply(text=json.dumps(transport), finish_reason="stop")],
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
    candidate = result.bundle.get("chapter_candidate")
    if candidate:
        assert candidate["chapter_id"] == "CH012"
        assert [section["section_id"] for section in candidate["sections"]] == [
            "SEC047",
            "SEC048",
            "SEC049",
            "SEC050",
        ]
    # A second execute must not call again.
    second = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        dry_run=False,
        execute_real=True,
        allow_real_provider=True,
        engine=FakeAIEngine(
            script=[FakeReply(text=json.dumps(transport), finish_reason="stop")],
            model=MODEL,
        ),
        root=tmp_path,
        write_artifacts=True,
        run_tests=False,
    )
    assert second.bundle["header"]["provider_calls"] == 0
    assert second.bundle["preflight"]["block_reason"] == "PROVIDER_CALL_ALREADY_CONSUMED"
