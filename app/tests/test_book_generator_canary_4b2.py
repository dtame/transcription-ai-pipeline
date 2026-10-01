"""Phase 4B.2 — FakeAI / offline. Real network only in authorized CLI execute."""

from __future__ import annotations

import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.book_generation.constants import PUBLICATION_AUTHORIZED
from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.evidence import build_chapter_evidence
from app.book_generation.fixtures import covering_chapter_transport
from app.book_generation.hydrate import load_clean_transcript_index
from app.book_generation.language import resolve_canonical_language
from app.book_generation.pipeline import materialize_chapter
from app.book_generation.schema import schema_identity
from app.book_generation.settings import frozen_production_settings
from app.book_generation.writer import candidate_sha256, production_book_absent
from app.book_generator_canary_4b2.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_EDITORIAL_PLAN_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    MODEL,
    PHASE_4B1_ADAPTED_SCHEMA_BYTES,
    PHASE_4B1_CH016_EVIDENCE_SHA256,
    PHASE_4B1_CH016_MAX_OUTPUT,
    PHASE_4B1_CH016_REQUEST_SHA256,
    PHASE_4B1_RAW_SCHEMA_BYTES,
    PHASE_4B1_RAW_SCHEMA_SHA256,
    PROJECT_NAME,
    PROMPT_VERSION,
    TARGET_CHAPTER_ID,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.book_generator_canary_4b2.guard import (
    BookGeneratorCanaryError,
    OneShotCallGuard,
    validate_authorization_scope,
)
from app.book_generator_canary_4b2.identity import precall_identity
from app.book_generator_canary_4b2.review import (
    idea_coverage_review,
    paragraph_provenance_review,
)
from app.book_generator_canary_4b2.runner import run_canary
from app.book_generator_canary_4b2.validate import interpret_production_response
from app.editorial_planning.pipeline import (
    load_published_editorial_plan,
    load_published_source_map,
)
from app.source_analysis.errors import MaxRealCallsExceededError


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestFrozenContracts:
    def test_schema_identity_matches_4b1(self):
        schema = schema_identity()
        assert schema["raw_schema_bytes"] == PHASE_4B1_RAW_SCHEMA_BYTES
        assert schema["adapted_schema_bytes"] == PHASE_4B1_ADAPTED_SCHEMA_BYTES
        assert schema["raw_schema_sha256"] == PHASE_4B1_RAW_SCHEMA_SHA256
        assert schema["raw_schema_bytes"] == 1035
        assert schema["adapted_schema_bytes"] == 1128

    def test_settings_thinking_disabled(self):
        settings = frozen_production_settings()
        assert settings.model == MODEL
        assert settings.thinking_mode == THINKING_MODE
        assert settings.thinking_mode == "disabled"
        assert PROMPT_VERSION == "book-generator-1.0"
        assert TRANSPORT_VERSION == "book-generation-transport-1.0"
        assert PUBLICATION_AUTHORIZED is False
        assert production_book_absent(PROJECT_NAME)


class TestPrecallIdentity:
    def test_ch016_request_identity(self):
        identity = precall_identity()
        assert identity["blocked_precall"] is False, identity.get("block_reason")
        assert identity["target_chapter_id"] == TARGET_CHAPTER_ID
        assert identity["smallest_is_ch016"] is True
        assert identity["canonical_document_language"] == "en"
        assert identity["schema_identity"] == "MATCH"
        assert identity["request_sha256"] == PHASE_4B1_CH016_REQUEST_SHA256
        assert identity["request_determinism"] is True
        assert identity["evidence_sha256"] == PHASE_4B1_CH016_EVIDENCE_SHA256
        assert identity["recommended_max_output"] == PHASE_4B1_CH016_MAX_OUTPUT
        assert identity["source_map_sha256_pre"] == EXPECTED_SOURCE_MAP_SHA256
        assert identity["editorial_plan_sha256_pre"] == EXPECTED_EDITORIAL_PLAN_SHA256
        assert identity["hydration"]["complete"] is True
        assert identity["hydration"]["unknown_src_count"] == 0
        assert identity["hydration"]["missing_src_count"] == 0
        assert identity["content_audit"]["chapter_id_match"] is True
        assert identity["content_audit"]["all_planned_sections"] is True
        assert identity["content_audit"]["all_assigned_ideas"] is True
        assert identity["request"]["idea_set_exact"] is True
        assert identity["request"]["section_set_exact"] is True

    def test_authorization_scope(self):
        assert (
            validate_authorization_scope(AUTHORIZATION_SCOPE) == AUTHORIZATION_SCOPE
        )
        with pytest.raises(BookGeneratorCanaryError):
            validate_authorization_scope("WRONG")


class TestEvidenceAndHydration:
    def test_evidence_extraction_and_hydration(self):
        identity = precall_identity()
        evidence = identity["evidence"]
        assert (evidence.get("chapter") or {}).get("id") == TARGET_CHAPTER_ID
        assert len(evidence.get("sections") or []) == len(
            identity["expected_chapter_sections"]
        )
        assert [row["id"] for row in evidence["ideas"]] == identity[
            "expected_chapter_ideas"
        ]
        hydrated = [row["id"] for row in evidence.get("src_text") or []]
        assert set(hydrated) == set(evidence.get("src") or [])
        index = load_clean_transcript_index(PROJECT_NAME)
        lookup = index.by_src()
        for src_id in hydrated:
            assert src_id in lookup
            assert lookup[src_id].text


class TestDecodeReconstructValidator:
    def test_covering_transport_roundtrip(self):
        plan, *_rest = load_published_editorial_plan(PROJECT_NAME)
        source_map, *_map = load_published_source_map(PROJECT_NAME)
        chapter = next(item for item in plan.chapters if item.chapter_id == TARGET_CHAPTER_ID)
        index = load_clean_transcript_index(PROJECT_NAME)
        language = resolve_canonical_language(
            source_map_primary_language=source_map.primary_language,
            transcript_primary_language=index.primary_language,
        )
        evidence = build_chapter_evidence(
            plan,
            source_map,
            chapter,
            language=language,
            hydrate=True,
            transcript_index=index,
        )
        transport = covering_chapter_transport(chapter)
        first, validation, digest = materialize_chapter(
            transport,
            plan,
            source_map,
            chapter,
            language=language,
            allowed_handles=evidence.get("allowed"),
        )
        second, _validation2, digest2 = materialize_chapter(
            transport,
            plan,
            source_map,
            chapter,
            language=language,
            allowed_handles=evidence.get("allowed"),
        )
        assert digest == digest2
        assert candidate_sha256(first.to_dict()) == digest
        assert validation.status != "FAIL"
        assert first.chapter_id == TARGET_CHAPTER_ID
        assert [section.section_id for section in first.sections] == [
            section.section_id for section in chapter.sections
        ]
        represented = {
            idea_id
            for section in first.sections
            for paragraph in section.paragraphs
            for idea_id in paragraph.idea_refs
        }
        assert set(assigned_idea_ids_for_chapter(chapter)) <= represented
        contract = interpret_production_response(
            transport,
            plan=plan,
            source_map=source_map,
            chapter=chapter,
            language=language,
            allowed_handles=list(evidence.get("allowed") or []),
        )
        assert contract["structured_parse"] == "PASS"
        assert contract["transport_decoder"] == "PASS"
        assert contract["canonical_reconstruction"] == "PASS"
        assert contract["deterministic_replay"] == "PASS"
        assert contract["section_coverage"] == "PASS"
        assert contract["section_order"] == "PASS"
        coverage = idea_coverage_review(first.to_dict(), chapter, evidence)
        assert coverage["MISSING"] == 0
        provenance = paragraph_provenance_review(first.to_dict(), evidence, source_map)
        assert provenance["UNSUPPORTED"] == 0


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
        assert (tmp_path / "audit" / "real" / "book_generator_4b2").is_dir()

    def test_fake_execute_does_not_publish_book(self, tmp_path):
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
        assert result.bundle["header"]["ready_for_full_real_book_generation"] == "NO"


class TestSavedRealResponseReplay:
    def test_saved_raw_response_replays_identically(self):
        from app.book_generator_canary_4b2.paths import canary_audit_dir

        raw_path = canary_audit_dir() / "book_generator_4b2_raw_structured_response.json"
        if not raw_path.is_file():
            pytest.skip("real canary raw response not present")
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        parsed = raw.get("parsed")
        assert isinstance(parsed, dict)
        plan, *_rest = load_published_editorial_plan(PROJECT_NAME)
        source_map, *_map = load_published_source_map(PROJECT_NAME)
        chapter = next(
            item for item in plan.chapters if item.chapter_id == TARGET_CHAPTER_ID
        )
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
        assert first["candidate_sha256"] == (
            "51635cedf7fee34b34fd80466c2361968494e2e98c15d861682401bddd2aaad5"
        )
        assert production_book_absent(PROJECT_NAME)
