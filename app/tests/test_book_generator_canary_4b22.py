"""Phase 4B.2.2 — FakeAI / offline. Real network only in authorized CLI execute."""

from __future__ import annotations

import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.book_generation.cache import ChapterCache
from app.book_generation.constants import (
    BOOK_GENERATOR_PROMPT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION_V10,
    BOOK_GENERATOR_VALIDATOR_VERSION,
    PUBLICATION_AUTHORIZED,
)
from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.evidence import build_chapter_evidence
from app.book_generation.fixtures import (
    covering_chapter_transport,
    empty_text_transport,
    whitespace_text_transport,
)
from app.book_generation.hydrate import load_clean_transcript_index
from app.book_generation.language import resolve_canonical_language
from app.book_generation.pipeline import materialize_chapter
from app.book_generation.prompt import FROZEN_PROMPT_SHA256, prompt_bundle as prompt_bundle_v10
from app.book_generation.prompt_v101 import prompt_bundle as prompt_bundle_v101
from app.book_generation.schema import schema_identity
from app.book_generation.settings import frozen_production_settings
from app.book_generation.writer import production_book_absent
from app.book_generator_canary_4b22.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_CACHE_SIGNATURE_V10,
    EXPECTED_CACHE_SIGNATURE_V101,
    EXPECTED_EDITORIAL_PLAN_SHA256,
    EXPECTED_EVIDENCE_SHA256,
    EXPECTED_MAX_OUTPUT,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    HISTORICAL_REQUEST_SHA256,
    MODEL,
    PHASE_4B1_ADAPTED_SCHEMA_BYTES,
    PHASE_4B1_RAW_SCHEMA_BYTES,
    PHASE_4B1_RAW_SCHEMA_SHA256,
    PROJECT_NAME,
    PROMPT_VERSION,
    TARGET_CHAPTER_ID,
    THINKING_MODE,
    TRANSPORT_VERSION,
    VALIDATOR_VERSION,
)
from app.book_generator_canary_4b22.guard import (
    BookGeneratorCanaryError,
    OneShotCallGuard,
    validate_authorization_scope,
)
from app.book_generator_canary_4b22.identity import (
    precall_identity,
    verify_local_validator_hardening,
    verify_prompt_contracts,
)
from app.book_generator_canary_4b22.runner import run_canary
from app.book_generator_canary_4b22.validate import interpret_production_response
from app.editorial_planning.pipeline import (
    load_published_editorial_plan,
    load_published_source_map,
)
from app.source_analysis.errors import MaxRealCallsExceededError


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestFrozenContracts:
    def test_versions_and_schema(self):
        schema = schema_identity()
        assert schema["raw_schema_bytes"] == PHASE_4B1_RAW_SCHEMA_BYTES
        assert schema["adapted_schema_bytes"] == PHASE_4B1_ADAPTED_SCHEMA_BYTES
        assert schema["raw_schema_sha256"] == PHASE_4B1_RAW_SCHEMA_SHA256
        assert schema["raw_schema_bytes"] == 1035
        assert schema["adapted_schema_bytes"] == 1128
        settings = frozen_production_settings()
        assert settings.model == MODEL
        assert settings.thinking_mode == THINKING_MODE
        assert PROMPT_VERSION == "book-generator-1.0.1"
        assert BOOK_GENERATOR_PROMPT_VERSION == "book-generator-1.0.1"
        assert BOOK_GENERATOR_PROMPT_VERSION_V10 == "book-generator-1.0"
        assert TRANSPORT_VERSION == "book-generation-transport-1.0"
        assert VALIDATOR_VERSION == "book-generation-validator-1.0.1"
        assert BOOK_GENERATOR_VALIDATOR_VERSION == "book-generation-validator-1.0.1"
        assert PUBLICATION_AUTHORIZED is False
        assert production_book_absent(PROJECT_NAME)


class TestPromptAndValidatorHardening:
    def test_prompt_1_0_unchanged_and_1_0_1_rules(self):
        prompts = verify_prompt_contracts()
        historical = prompt_bundle_v10()
        successor = prompt_bundle_v101()
        assert historical["prompt_sha256"] == FROZEN_PROMPT_SHA256
        assert prompts["historical_identity_match"] is True
        assert prompts["successor_identity_match"] is True
        assert prompts["empty_paragraph_rule"] is True
        assert prompts["connective_rule"] is True
        assert prompts["example_rule"] is True
        assert prompts["example_source_rule"] is True
        assert prompts["pre_return_self_check"] is True
        assert prompts["chain_of_thought_requested"] is False
        assert prompts["ch016_specific_hacks"] is False
        assert successor["prompt_sha256"] != historical["prompt_sha256"]

    def test_validator_rejects_empty_and_whitespace_without_drop(self):
        hardening = verify_local_validator_hardening()
        assert hardening["empty_text_rejected"] is True
        assert hardening["whitespace_text_rejected"] is True
        assert hardening["empty_paragraph_never_dropped"] is True
        source_map = __import__(
            "app.book_generation.fixtures", fromlist=["tiny_book_source_map"]
        ).tiny_book_source_map()
        plan = __import__(
            "app.book_generation.fixtures", fromlist=["tiny_editorial_plan"]
        ).tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        from app.book_generation.fixtures import tiny_transcript_index

        evidence = build_chapter_evidence(
            plan,
            source_map,
            chapter,
            language=source_map.primary_language,
            hydrate=True,
            transcript_index=tiny_transcript_index(source_map),
        )
        empty, empty_val, _ = materialize_chapter(
            empty_text_transport(chapter),
            plan,
            source_map,
            chapter,
            language=source_map.primary_language,
            allowed_handles=evidence.get("allowed"),
        )
        white, white_val, _ = materialize_chapter(
            whitespace_text_transport(chapter),
            plan,
            source_map,
            chapter,
            language=source_map.primary_language,
            allowed_handles=evidence.get("allowed"),
        )
        assert empty_val.status == "FAIL"
        assert white_val.status == "FAIL"
        assert any(p.provider_handle == "empty-text" for s in empty.sections for p in s.paragraphs)
        assert any(
            p.provider_handle == "whitespace-text" for s in white.sections for p in s.paragraphs
        )


class TestPrecallIdentity:
    def test_ch016_hardened_request_identity(self):
        identity = precall_identity()
        assert identity["blocked_precall"] is False, identity.get("block_reason")
        assert identity["target_chapter_id"] == TARGET_CHAPTER_ID
        assert identity["canonical_document_language"] == "en"
        assert identity["schema_identity"] == "MATCH"
        assert identity["request_sha256"] == EXPECTED_REQUEST_SHA256
        assert identity["request_determinism"] is True
        assert identity["request_identity"] == "MATCH"
        assert identity["historical_request_sha256"] == HISTORICAL_REQUEST_SHA256
        assert identity["request_differs_from_historical"] is True
        assert identity["evidence_sha256"] == EXPECTED_EVIDENCE_SHA256
        assert identity["recommended_max_output"] == EXPECTED_MAX_OUTPUT
        assert identity["source_map_sha256_pre"] == EXPECTED_SOURCE_MAP_SHA256
        assert identity["editorial_plan_sha256_pre"] == EXPECTED_EDITORIAL_PLAN_SHA256
        assert identity["hydration"]["complete"] is True
        assert identity["hydration"]["unknown_src_count"] == 0
        assert identity["cache"]["historical"] == EXPECTED_CACHE_SIGNATURE_V10
        assert identity["cache"]["hardened"] == EXPECTED_CACHE_SIGNATURE_V101
        assert identity["cache"]["isolation"] is True
        cache = ChapterCache()
        cache.remember(identity["cache"]["historical"], "historical-candidate")
        assert cache.lookup(identity["cache"]["hardened"]) is None
        assert identity["content_audit"]["whole_transcript_sent"] is False
        assert identity["request"]["idea_set_exact"] is True
        assert identity["request"]["section_set_exact"] is True

    def test_authorization_scope(self):
        assert validate_authorization_scope(AUTHORIZATION_SCOPE) == AUTHORIZATION_SCOPE
        with pytest.raises(BookGeneratorCanaryError):
            validate_authorization_scope("BOOK_GENERATOR_4B2_ONE_REAL_SMALL_CHAPTER_CANARY_ONLY")


class TestEvidenceAndHydration:
    def test_evidence_matches_historical_and_hydrates(self):
        identity = precall_identity()
        evidence = identity["evidence"]
        assert (evidence.get("chapter") or {}).get("id") == TARGET_CHAPTER_ID
        assert [row["id"] for row in evidence["ideas"]] == identity["expected_chapter_ideas"]
        hydrated = [row["id"] for row in evidence.get("src_text") or []]
        assert set(hydrated) == set(evidence.get("src") or [])
        index = load_clean_transcript_index(PROJECT_NAME)
        lookup = index.by_src()
        for src_id in hydrated:
            assert src_id in lookup
            assert lookup[src_id].text


class TestOneShotAndDryRun:
    def test_one_shot_guard(self):
        guard = OneShotCallGuard(max_calls=1)

        class _Engine:
            def generate(self, request):
                return request

        guard.guarded_generate(_Engine(), "one")
        with pytest.raises(MaxRealCallsExceededError):
            guard.guarded_generate(_Engine(), "two")

    def test_dry_run_writes_precall_zero_posts(self, tmp_path):
        result = run_canary(
            dry_run=True,
            execute_real=False,
            authorization_scope=AUTHORIZATION_SCOPE,
            allow_real_provider=False,
            root=tmp_path,
            write_artifacts=True,
        )
        assert result.mode == "DRY_RUN"
        assert result.anthropic_post_attempts == 0
        header = result.bundle["header"]
        assert header["result"] == "DRY_RUN"
        assert header["actual_provider_calls"] == 0
        assert header["book_json"] == "NOT PUBLISHED"
        assert header["production_cache"] == "NOT ACCEPTED"
        assert (tmp_path / "audit" / "real" / "book_generator_4b22").is_dir()

    def test_fake_execute_does_not_publish_or_cache(self, tmp_path):
        plan, *_rest = load_published_editorial_plan(PROJECT_NAME)
        chapter = next(item for item in plan.chapters if item.chapter_id == TARGET_CHAPTER_ID)
        transport = covering_chapter_transport(chapter)
        engine = FakeAIEngine(
            script=[
                FakeReply(
                    parsed=transport,
                    text=json.dumps(transport, ensure_ascii=False),
                    finish_reason="end_turn",
                    input_tokens=2000,
                    output_tokens=800,
                    thinking_tokens=0,
                    model=MODEL,
                )
            ],
            retry_policy=no_delay_policy(max_attempts=1),
        )
        result = run_canary(
            dry_run=False,
            execute_real=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            allow_real_provider=True,
            engine=engine,
            root=tmp_path,
            write_artifacts=True,
            persist_usage=False,
        )
        assert result.engine_generate_attempts == 1
        assert production_book_absent(PROJECT_NAME)
        assert result.bundle["header"]["book_json"] == "NOT PUBLISHED"
        assert result.bundle["header"]["production_cache"] == "NOT ACCEPTED"
        assert result.bundle["header"]["ready_for_full_real_book_generation"] == "NO"
        assert result.bundle["readiness"]["cached_as_production"] is False


class TestReplayWhenPresent:
    def test_saved_raw_response_replays_if_present(self):
        from app.book_generator_canary_4b22.paths import canary_audit_dir

        raw_path = canary_audit_dir() / "book_generator_4b22_raw_structured_response.json"
        if not raw_path.is_file():
            pytest.skip("hardened canary raw response not present yet")
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        parsed = raw.get("parsed")
        assert isinstance(parsed, dict)
        plan, *_rest = load_published_editorial_plan(PROJECT_NAME)
        source_map, *_map = load_published_source_map(PROJECT_NAME)
        chapter = next(item for item in plan.chapters if item.chapter_id == TARGET_CHAPTER_ID)
        identity = precall_identity()
        first = interpret_production_response(
            parsed,
            plan=plan,
            source_map=source_map,
            chapter=chapter,
            language="en",
            allowed_handles=list((identity.get("evidence") or {}).get("allowed") or []),
            provider_raw_sha256=str(raw.get("sha256") or ""),
        )
        second = interpret_production_response(
            parsed,
            plan=plan,
            source_map=source_map,
            chapter=chapter,
            language="en",
            allowed_handles=list((identity.get("evidence") or {}).get("allowed") or []),
            provider_raw_sha256=str(raw.get("sha256") or ""),
        )
        assert first["deterministic_replay"] == "PASS"
        assert first["candidate_sha256"] == second["candidate_sha256"]
        assert production_book_absent(PROJECT_NAME)
        ideas = assigned_idea_ids_for_chapter(chapter)
        assert ideas
