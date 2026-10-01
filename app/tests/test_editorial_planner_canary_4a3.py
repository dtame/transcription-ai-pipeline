"""Phase 4A.3 — FakeAI / offline. Real network only in authorized CLI execute."""

from __future__ import annotations

import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.editorial_planner_canary_4a3.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_IDEA_COUNT,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    HISTORICAL_PROPOSED_MAX_OUTPUT,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    TRANSPORT_VERSION,
)
from app.editorial_planner_canary_4a3.guard import (
    PlannerCanaryError,
    validate_authorization_scope,
)
from app.editorial_planner_canary_4a3.identity import precall_identity
from app.editorial_planner_canary_4a3.runner import run_canary
from app.editorial_planner_canary_4a3.validate import interpret_production_response
from app.editorial_planner_preflight_4a2.payload import (
    build_production_payload,
    build_production_request,
)
from app.editorial_planning.constants import (
    HARD_MAX_OUTPUT_TOKENS,
    PROPOSED_MAX_OUTPUT_TOKENS,
    PUBLICATION_AUTHORIZED,
)
from app.editorial_planning.fixtures import covering_transport
from app.editorial_planning.guard import assert_analyzer_untouched, assert_offline_package
from app.editorial_planning.pipeline import load_published_source_map
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


class TestFrozenHistoricalSettings:
    def test_phase4a1_max_output_not_mutated(self):
        assert PROPOSED_MAX_OUTPUT_TOKENS == 16384
        assert HISTORICAL_PROPOSED_MAX_OUTPUT == 16384
        assert HARD_MAX_OUTPUT_TOKENS == 32000
        assert frozen_production_settings().max_output_tokens == 16384
        assert PRODUCTION_MAX_OUTPUT_TOKENS == 65536
        assert PRODUCTION_MAX_OUTPUT_TOKENS != PROPOSED_MAX_OUTPUT_TOKENS
        assert PUBLICATION_AUTHORIZED is False
        assert_offline_package()
        assert_analyzer_untouched()


class TestPrecallIdentity:
    def test_request_sha256_matches_phase4a2(self):
        identity = precall_identity()
        assert identity["blocked_precall"] is False, identity.get("block_reason")
        assert identity["schema_identity"] == "MATCH"
        assert identity["prompt_identity"] == "MATCH"
        assert identity["request_identity"] == "MATCH"
        assert identity["actual_request_sha256"] == EXPECTED_REQUEST_SHA256
        assert identity["max_tokens"] == PRODUCTION_MAX_OUTPUT_TOKENS
        assert identity["max_tokens"] != 16384
        assert identity["model"] == MODEL
        assert identity["thinking_present_in_payload"] is False
        assert identity["effort_present_in_payload"] is False
        assert identity["source_map_sha256"] == EXPECTED_SOURCE_MAP_SHA256
        assert identity["coverage"]["idea_count"] == EXPECTED_IDEA_COUNT
        assert identity["coverage"]["pass"] is True
        assert identity["historical_settings_unchanged"] is True

    def test_production_payload_override_path(self):
        source_map, *_rest = load_published_source_map(PROJECT_NAME)
        payload = build_production_payload(
            source_map, max_output_tokens=PRODUCTION_MAX_OUTPUT_TOKENS
        )
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        assert content_hash(encoded) == EXPECTED_REQUEST_SHA256
        assert payload["max_tokens"] == 65536
        assert payload["model"] == MODEL
        assert "thinking" not in payload
        request = build_production_request(
            source_map, max_output_tokens=PRODUCTION_MAX_OUTPUT_TOKENS
        )
        assert request.max_output_tokens == 65536
        assert request.thinking_mode == "provider_default"
        assert request.effort is None
        assert request.model == MODEL
        assert frozen_production_settings().max_output_tokens == 16384


class TestAuthorization:
    def test_wrong_scope_rejected(self):
        with pytest.raises(PlannerCanaryError):
            validate_authorization_scope(
                "EDITORIAL_PLANNER_4A2_OFFLINE_PRODUCTION_PREFLIGHT_ONLY"
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
        assert header["max_output"] == 65536
        assert header["publication_eligible"] == "NO"
        assert header["editorial_plan_json"] == "NOT PUBLISHED"
        audit = tmp_path / "audit" / "real" / "editorial_planner_4a3"
        assert (audit / "editorial_planner_4a3_precall_identity.json").is_file()
        assert not editorial_plan_path(PROJECT_NAME, sortie_dir=tmp_path).is_file()


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
        assert header["unknown_idea_refs"] == 0
        assert header["editorial_plan_json"] == "NOT PUBLISHED"
        assert header["publication_eligible"] in {"YES", "NO"}
        assert not editorial_plan_path(PROJECT_NAME, sortie_dir=tmp_path).is_file()
        audit = tmp_path / "audit" / "real" / "editorial_planner_4a3"
        assert (audit / "editorial_planner_4a3_provider_evidence.json").is_file()
        assert (audit / "editorial_plan_candidate.json").is_file()
        assert (tmp_path / "audit" / "PHASE_4A3_EDITORIAL_PLANNER_ONE_REAL_PRODUCTION_CANARY_REPORT.md").is_file()

    def test_replay_from_saved_response_no_network(self, tmp_path):
        source_map, raw, digest, path = load_published_source_map(PROJECT_NAME)
        transport = _fake_transport()
        first = interpret_production_response(
            transport,
            source_map=source_map,
            source_map_sha256=digest,
            source_map_bytes=len(raw),
            source_map_path_value=str(path).replace("\\", "/"),
            raw_text=json.dumps(transport, ensure_ascii=False),
        )
        second = interpret_production_response(
            transport,
            source_map=source_map,
            source_map_sha256=digest,
            source_map_bytes=len(raw),
            source_map_path_value=str(path).replace("\\", "/"),
            raw_text=json.dumps(transport, ensure_ascii=False),
        )
        assert first["structured_parse"] == "PASS"
        assert first["deterministic_replay"] == "PASS"
        assert first["plan_sha256"] == second["plan_sha256"]
        assert first["idea_coverage"]["coverage_complete"] is True


class TestSavedProductionReplay:
    def test_persisted_response_replays_offline(self):
        from pathlib import Path

        raw_path = (
            Path("audit")
            / "real"
            / "editorial_planner_4a3"
            / "editorial_planner_4a3_raw_structured_response.json"
        )
        if not raw_path.is_file():
            pytest.skip("A.3 persisted response absent")
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        parsed = payload.get("parsed")
        assert payload.get("repaired") is False
        source_map, raw, digest, path = load_published_source_map(PROJECT_NAME)
        first = interpret_production_response(
            parsed,
            source_map=source_map,
            source_map_sha256=digest,
            source_map_bytes=len(raw),
            source_map_path_value=str(path).replace("\\", "/"),
            raw_text=payload.get("text"),
        )
        second = interpret_production_response(
            parsed,
            source_map=source_map,
            source_map_sha256=digest,
            source_map_bytes=len(raw),
            source_map_path_value=str(path).replace("\\", "/"),
            raw_text=payload.get("text"),
        )
        assert first["structured_parse"] == "PASS"
        assert first["transport_decoder"] == "PASS"
        assert first["canonical_reconstruction"] == "PASS"
        assert first["deterministic_replay"] == "PASS"
        assert first["idea_coverage"]["coverage_complete"] is True
        assert first["plan_sha256"] == second["plan_sha256"]
        assert first["plan_sha256"] == (
            "abc87e082878e0281689ecc022ed8b40ca318510fc90d960c31795d6186bd95e"
        )
        assert not editorial_plan_path(PROJECT_NAME).is_file()


class TestCli:
    def test_cli_rejects_wrong_scope(self):
        from app.editorial_planner_canary_4a3.__main__ import main

        assert main(["--authorization-scope", "wrong", "--dry-run"]) == 2
