"""Phase 4A.3.5 — FakeAI / offline. Real network only in authorized CLI execute."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.editorial_planner_canary_4a35.accountability import exact_accountability
from app.editorial_planner_canary_4a35.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_IDEA_COUNT,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    HISTORICAL_A33_REQUEST_SHA256,
    HISTORICAL_A3_REQUEST_SHA256,
    HISTORICAL_PROMPT,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    TRANSPORT_VERSION,
)
from app.editorial_planner_canary_4a35.guard import (
    PlannerCanaryError,
    validate_authorization_scope,
)
from app.editorial_planner_canary_4a35.identity import precall_identity
from app.editorial_planner_canary_4a35.language import language_audit
from app.editorial_planner_canary_4a35.runner import run_canary
from app.editorial_planner_canary_4a35.validate import interpret_production_response
from app.editorial_planner_forensics_4a34.constants import A3_CANDIDATE_SHA256
from app.editorial_planner_forensics_4a34.coverage_stress import run_coverage_stress
from app.editorial_planner_forensics_4a34.identity import (
    compare_historical_prompt,
    compare_schema,
    file_sha256,
)
from app.editorial_planner_forensics_4a34.payload import (
    build_production_payload,
    build_production_request,
)
from app.editorial_planner_language_policy_4a32.language import load_language_provenance
from app.editorial_planner_forensics_4a34.paths import a3_candidate_path
from app.editorial_planning.constants import PUBLICATION_AUTHORIZED
from app.editorial_planning.fixtures import covering_transport
from app.editorial_planning.guard import assert_analyzer_untouched, assert_offline_package
from app.editorial_planning.pipeline import load_published_source_map
from app.editorial_planning.prompt import prompt_bundle as prompt_10
from app.editorial_planning.prompt_v101 import prompt_bundle as prompt_101
from app.editorial_planning.prompt_v102 import prompt_bundle as prompt_102
from app.editorial_planning.settings import frozen_production_settings
from app.editorial_planning.writer import editorial_plan_path
from app.file_utils import content_hash


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _fake_transport():
    source_map, *_rest = load_published_source_map(PROJECT_NAME)
    return covering_transport(
        source_map,
        chapter_count=12,
        exclude_ids=("IDEA286",),
        reuse_idea="IDEA001",
    )


class TestFrozenContracts:
    def test_prompt_schema_transport_and_historical_candidate(self):
        assert PROMPT_VERSION == "editorial-planner-1.0.2"
        assert HISTORICAL_PROMPT == "editorial-planner-1.0"
        assert TRANSPORT_VERSION == "editorial-plan-transport-1.0"
        assert PRODUCTION_MAX_OUTPUT_TOKENS == 65536
        assert frozen_production_settings().max_output_tokens == 16384
        assert PUBLICATION_AUTHORIZED is False
        assert_offline_package()
        assert_analyzer_untouched()
        schema = compare_schema()
        historical = compare_historical_prompt()
        assert schema["identity"] == "MATCH"
        assert historical["identity"] == "MATCH"
        assert historical["historical_prompt_mutated"] == "NO"
        v10 = prompt_10()
        v101 = prompt_101("en")
        v102 = prompt_102("en")
        assert v10["prompt_sha256"] != v101["prompt_sha256"]
        assert v101["prompt_sha256"] != v102["prompt_sha256"]
        assert "COMPLETUDE EXHAUSTIVE DES IDEA" in v102["system"]
        assert "AUTO-VERIFICATION DE SORTIE" in v102["system"]
        assert "IDEA007" not in v102["system"]
        assert "IDEA008" not in v102["instructions"]
        assert "sinners" not in v102["system"].lower()
        candidate = a3_candidate_path()
        if candidate.is_file():
            assert file_sha256(candidate) == A3_CANDIDATE_SHA256


class TestPrecallIdentity:
    def test_language_resolved_from_production_path_not_hardcoded(self):
        source_map, *_rest = load_published_source_map(PROJECT_NAME)
        provenance = load_language_provenance(source_map)
        assert provenance["canonical_document_language"] == "en"
        assert provenance["blocked"] is False
        identity = precall_identity()
        assert identity["language_hardcoded"] is False
        assert identity["canonical_document_language"] == provenance[
            "canonical_document_language"
        ]
        assert identity["canonical_language_source"] == "transcript.language.primary"

    def test_request_sha256_matches_phase4a34(self):
        identity = precall_identity()
        assert identity["blocked_precall"] is False, identity.get("block_reason")
        assert identity["schema_identity"] == "MATCH"
        assert identity["prompt_identity"] == "MATCH"
        assert identity["request_identity"] == "MATCH"
        assert identity["actual_request_sha256"] == EXPECTED_REQUEST_SHA256
        assert identity["actual_request_sha256"] != HISTORICAL_A3_REQUEST_SHA256
        assert identity["actual_request_sha256"] != HISTORICAL_A33_REQUEST_SHA256
        assert identity["request_changed_from_a3"] is True
        assert identity["request_changed_from_a33"] is True
        assert identity["request_determinism"] is True
        assert identity["max_tokens"] == PRODUCTION_MAX_OUTPUT_TOKENS
        assert identity["model"] == MODEL
        assert identity["thinking_present_in_payload"] is False
        assert identity["effort_present_in_payload"] is False
        assert identity["source_map_sha256"] == EXPECTED_SOURCE_MAP_SHA256
        assert identity["coverage"]["idea_count"] == EXPECTED_IDEA_COUNT
        assert identity["coverage"]["unknown_input_refs"] == 0
        assert identity["coverage"]["pass"] is True
        assert identity["prompt"] == "editorial-planner-1.0.2"
        assert identity["expected_idea_count"] == EXPECTED_IDEA_COUNT
        assert identity["fakeai_coverage_stress_status"] == "PASS"
        assert identity["idea_specific_prompting"] is False
        assert identity["content_specific_prompting"] is False

    def test_production_payload_v102_path(self):
        source_map, *_rest = load_published_source_map(PROJECT_NAME)
        language = load_language_provenance(source_map)["canonical_document_language"]
        first = build_production_payload(
            source_map, canonical_document_language=language
        )
        second = build_production_payload(
            source_map, canonical_document_language=language
        )
        encoded = json.dumps(first, ensure_ascii=False, separators=(",", ":"))
        assert content_hash(encoded) == EXPECTED_REQUEST_SHA256
        assert first == second
        assert first["max_tokens"] == 65536
        assert first["model"] == MODEL
        assert "thinking" not in first
        request = build_production_request(
            source_map, canonical_document_language=language
        )
        assert request.max_output_tokens == 65536
        assert request.thinking_mode == "provider_default"
        assert request.effort is None
        assert request.metadata["prompt_version"] == "editorial-planner-1.0.2"
        assert request.metadata["expected_idea_count"] == len(source_map.ideas)
        assert f"CANONICAL_DOCUMENT_LANGUAGE\n{language}\n" in request.prompt
        assert f"EXPECTED_IDEA_COUNT\n{len(source_map.ideas)}\n" in request.prompt
        assert frozen_production_settings().max_output_tokens == 16384


class TestAccountability:
    def test_exactly_once_from_covering_transport(self):
        source_map, raw, digest, path = load_published_source_map(PROJECT_NAME)
        language = load_language_provenance(source_map)["canonical_document_language"]
        transport = covering_transport(
            source_map, exclude_ids=("IDEA286",), reuse_idea="IDEA001"
        )
        result = interpret_production_response(
            transport,
            source_map=source_map,
            source_map_sha256=digest,
            source_map_bytes=len(raw),
            source_map_path_value=str(path).replace("\\", "/"),
            raw_text=json.dumps(transport, ensure_ascii=False),
            canonical_document_language=language,
        )
        acc = result["accountability"]
        assert acc["status"] == "PASS"
        assert acc["exactly_once"] is True
        assert acc["silent_omissions"] == 0
        assert acc["duplicate_primary_ids"] == []
        assert acc["actual_explicit_count"] == EXPECTED_IDEA_COUNT
        assert acc["excluded_count"] == 1
        assert acc["idea007_explicit"] is True
        assert acc["idea008_explicit"] is True
        assert result["plan"]["metadata"]["prompt_version"] == "editorial-planner-1.0.2"

    def test_omission_fails_equation(self):
        source_map, raw, digest, path = load_published_source_map(PROJECT_NAME)
        language = load_language_provenance(source_map)["canonical_document_language"]
        transport = covering_transport(source_map)
        for chapter in transport.get("chapters") or []:
            for section in chapter.get("sections") or []:
                section["i"] = [
                    idea_id
                    for idea_id in section.get("i") or []
                    if idea_id not in {"IDEA007", "IDEA008"}
                ]
        result = interpret_production_response(
            transport,
            source_map=source_map,
            source_map_sha256=digest,
            source_map_bytes=len(raw),
            source_map_path_value=str(path).replace("\\", "/"),
            raw_text=json.dumps(transport, ensure_ascii=False),
            canonical_document_language=language,
        )
        acc = exact_accountability(
            result.get("plan"), source_map, transport=result.get("transport")
        )
        assert acc["status"] == "FAIL"
        assert acc["silent_omissions"] == 2
        assert "IDEA007" in acc["missing_ids"]
        assert "IDEA008" in acc["missing_ids"]


class TestFakeAICoverageStress:
    def test_existing_a34_scenarios_still_pass(self):
        source_map, *_rest = load_published_source_map(PROJECT_NAME)
        result = run_coverage_stress(source_map)
        assert result["status"] == "PASS"
        by_name = {row["scenario"]: row for row in result["scenarios"]}
        assert by_name["286_assigned"]["pass"] is True
        assert by_name["285_assigned_1_deferred"]["pass"] is True
        assert by_name["285_assigned_1_excluded"]["pass"] is True
        assert by_name["284_assigned_2_omitted"]["pass"] is True
        assert by_name["duplicate_disposition"]["pass"] is True
        assert by_name["unknown_idea"]["pass"] is True
        assert by_name["reuse_plus_primary"]["pass"] is True
        assert by_name["shuffled_complete_coverage"]["pass"] is True


class TestAuthorization:
    def test_wrong_scope_rejected(self):
        with pytest.raises(PlannerCanaryError):
            validate_authorization_scope(
                "EDITORIAL_PLANNER_4A33_ONE_REAL_ENGLISH_PRODUCTION_CANARY_ONLY"
            )

    def test_dry_run_zero_calls(self, tmp_path):
        result = run_canary(
            dry_run=True,
            execute_real=False,
            authorization_scope=AUTHORIZATION_SCOPE,
            allow_real_provider=False,
            root=tmp_path,
            write_artifacts=True,
        )
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0
        header = result.bundle["header"]
        assert header["actual_provider_calls"] == 0
        assert header["result"] == "DRY_RUN"
        assert header["request_identity"] == "MATCH"
        assert header["canonical_document_language"] == "en"
        assert header["prompt"] == "editorial-planner-1.0.2"
        assert header["publication_eligible"] == "NO"
        assert header["editorial_plan_json"] == "NOT PUBLISHED"
        audit = tmp_path / "audit" / "real" / "editorial_planner_4a35"
        assert (audit / "editorial_planner_4a35_precall_identity.json").is_file()
        assert not editorial_plan_path(PROJECT_NAME, sortie_dir=tmp_path).is_file()
        assert not editorial_plan_path(PROJECT_NAME).is_file()


class TestFakeExecute:
    def test_fake_engine_one_call_no_publication(self, tmp_path):
        transport = _fake_transport()
        engine = FakeAIEngine(
            script=[
                FakeReply(
                    parsed=transport,
                    text=json.dumps(transport, ensure_ascii=False),
                    finish_reason="end_turn",
                    input_tokens=2000,
                    output_tokens=4000,
                    thinking_tokens=100,
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
        header = result.bundle["header"]
        assert engine.call_count == 1
        assert result.engine_generate_attempts == 1
        assert result.anthropic_post_attempts == 1
        assert header["structured_parse"] == "PASS"
        assert header["transport_decoder"] == "PASS"
        assert header["canonical_reconstruction"] == "PASS"
        assert header["deterministic_replay"] == "PASS"
        assert header["silent_omissions"] == 0
        assert header["idea_coverage"] == "286 / 286"
        assert header["idea007_disposition"] in {"ASSIGNED", "DEFERRED", "EXCLUDED"}
        assert header["idea008_disposition"] in {"ASSIGNED", "DEFERRED", "EXCLUDED"}
        assert header["editorial_plan_json"] == "NOT PUBLISHED"
        assert header["publication_eligible"] in {"YES", "NO"}
        assert not editorial_plan_path(PROJECT_NAME, sortie_dir=tmp_path).is_file()
        assert not editorial_plan_path(PROJECT_NAME).is_file()
        audit = tmp_path / "audit" / "real" / "editorial_planner_4a35"
        assert (audit / "editorial_planner_4a35_provider_evidence.json").is_file()
        assert (audit / "editorial_planner_4a35_idea_accountability.json").is_file()
        assert (audit / "editorial_plan_candidate.json").is_file()
        assert (
            tmp_path
            / "audit"
            / "PHASE_4A35_EDITORIAL_PLANNER_FINAL_CONTROLLED_PRODUCTION_CANARY_REPORT.md"
        ).is_file()
        language = result.bundle["language"]
        assert language["editorial_language_match"] in {"PASS", "REVIEW", "FAIL"}
        assert language["translated"] is False
        assert language["second_provider_call"] is False


class TestSavedProductionReplay:
    def test_persisted_response_replays_offline_when_present(self):
        raw_path = (
            Path("audit")
            / "real"
            / "editorial_planner_4a35"
            / "editorial_planner_4a35_raw_structured_response.json"
        )
        if not raw_path.is_file():
            pytest.skip("A.3.5 persisted response absent")
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        parsed = payload.get("parsed")
        assert payload.get("repaired") is False
        assert payload.get("translated") is False
        source_map, raw, digest, path = load_published_source_map(PROJECT_NAME)
        language = load_language_provenance(source_map)["canonical_document_language"]
        first = interpret_production_response(
            parsed,
            source_map=source_map,
            source_map_sha256=digest,
            source_map_bytes=len(raw),
            source_map_path_value=str(path).replace("\\", "/"),
            raw_text=payload.get("text"),
            canonical_document_language=language,
        )
        second = interpret_production_response(
            parsed,
            source_map=source_map,
            source_map_sha256=digest,
            source_map_bytes=len(raw),
            source_map_path_value=str(path).replace("\\", "/"),
            raw_text=payload.get("text"),
            canonical_document_language=language,
        )
        assert first["structured_parse"] == "PASS"
        assert first["transport_decoder"] == "PASS"
        assert first["canonical_reconstruction"] == "PASS"
        assert first["deterministic_replay"] == "PASS"
        assert first["plan_sha256"] == second["plan_sha256"]
        assert first["plan"]["metadata"]["prompt_version"] == "editorial-planner-1.0.2"
        lang = language_audit(first["plan"], canonical_document_language=language)
        assert lang["editorial_language_match"] in {"PASS", "REVIEW", "FAIL"}
        assert not editorial_plan_path(PROJECT_NAME).is_file()


class TestCli:
    def test_cli_rejects_wrong_scope(self):
        from app.editorial_planner_canary_4a35.__main__ import main

        assert main(["--authorization-scope", "wrong", "--dry-run"]) == 2
