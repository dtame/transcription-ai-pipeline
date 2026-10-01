"""Phase 4A.1 — FakeAI / offline. 0 réseau réel. 0 SourceMap pastoral envoyé."""

from __future__ import annotations

import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.editorial_planner_canary_4a1.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_MAX_OUTPUT_TOKENS,
    MODEL,
    PHASE_4A_ADAPTED_SCHEMA_SHA256,
    PHASE_4A_CONSERVATIVE_OUTPUT_TOKENS,
    PHASE_4A_EXPECTED_OUTPUT_TOKENS,
    PHASE_4A_HARD_OUTPUT_TOKENS,
    PHASE_4A_PROMPT_SHA256,
    PHASE_4A_RAW_SCHEMA_SHA256,
    PRODUCTION_PROPOSED_MAX_OUTPUT,
    PROJECT_NAME,
    PROMPT_VERSION,
    SYNTHETIC_SRC_IDS,
    TRANSPORT_VERSION,
)
from app.editorial_planner_canary_4a1.fixture import build_synthetic_source_map
from app.editorial_planner_canary_4a1.guard import (
    PlannerCanaryError,
    assert_synthetic_source_map,
    validate_authorization_scope,
)
from app.editorial_planner_canary_4a1.identity import precall_identity
from app.editorial_planner_canary_4a1.payload import (
    build_canary_request,
    payload_audit,
)
from app.editorial_planner_canary_4a1.runner import run_canary
from app.editorial_planning.constants import (
    PUBLICATION_AUTHORIZED,
    REAL_PROVIDER_CALLS_THIS_PHASE,
)
from app.editorial_planning.fixtures import covering_transport
from app.editorial_planning.guard import (
    assert_analyzer_untouched,
    assert_no_book_generator,
    assert_offline_package,
)
from app.editorial_planning.writer import editorial_plan_path


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _fake_transport():
    source_map = build_synthetic_source_map()
    return covering_transport(
        source_map,
        chapter_count=2,
        exclude_ids=("IDEA007",),
        reuse_idea="IDEA001",
    )


class TestPhase4ARemainsFrozen:
    def test_planner_package_still_offline(self):
        assert_offline_package()
        assert_analyzer_untouched()
        assert_no_book_generator()
        assert PUBLICATION_AUTHORIZED is False
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0

    def test_precall_identity_matches_phase4a_freeze(self):
        identity = precall_identity()
        assert identity["blocked_precall"] is False
        assert identity["schema_identity"] == "MATCH"
        assert identity["prompt_identity"] == "MATCH"
        assert identity["schema"]["live"]["raw_schema_sha256"] == PHASE_4A_RAW_SCHEMA_SHA256
        assert (
            identity["schema"]["live"]["adapted_schema_sha256"]
            == PHASE_4A_ADAPTED_SCHEMA_SHA256
        )
        assert identity["prompt"]["live"]["prompt_sha256"] == PHASE_4A_PROMPT_SHA256
        assert identity["prompt_version"] == PROMPT_VERSION
        assert identity["transport_version"] == TRANSPORT_VERSION

    def test_production_budget_preserved(self):
        from app.editorial_planner_canary_4a1.runner import production_budget_status

        budget = production_budget_status()
        assert budget["expected_output_tokens"] == PHASE_4A_EXPECTED_OUTPUT_TOKENS
        assert budget["conservative_output_tokens"] == PHASE_4A_CONSERVATIVE_OUTPUT_TOKENS
        assert budget["hard_output_tokens"] == PHASE_4A_HARD_OUTPUT_TOKENS
        assert budget["proposed_max_output"] == PRODUCTION_PROPOSED_MAX_OUTPUT
        assert budget["PRODUCTION_OUTPUT_BUDGET_REVIEW_REQUIRED"] == "YES"
        assert CANARY_MAX_OUTPUT_TOKENS == 4096
        assert CANARY_MAX_OUTPUT_TOKENS != PRODUCTION_PROPOSED_MAX_OUTPUT


class TestSyntheticFixture:
    def test_inventory_and_domain(self):
        source_map = build_synthetic_source_map()
        assert_synthetic_source_map(source_map)
        assert source_map.project_name == PROJECT_NAME
        assert len(source_map.topics) == 3
        assert len(source_map.ideas) == 7
        assert len(source_map.examples) == 2
        assert len(source_map.references) == 2
        assert len(source_map.uncertainties) == 1
        assert tuple(source_map.all_source_refs()) == SYNTHETIC_SRC_IDS
        blob = json.dumps(source_map.to_dict()).lower()
        assert "pastoral" not in blob
        assert "window" not in blob
        assert "chunk" not in blob

    def test_request_is_synthetic_and_omits_thinking(self):
        source_map = build_synthetic_source_map()
        request = build_canary_request(source_map)
        audit = payload_audit(source_map)
        assert request.model == MODEL
        assert request.max_output_tokens == CANARY_MAX_OUTPUT_TOKENS
        assert request.thinking_mode == "provider_default"
        assert request.effort is None
        assert request.thinking_budget_tokens is None
        assert audit["thinking_present"] is False
        assert audit["effort_present"] is False
        assert audit["temperature_present"] is False
        assert audit["production_data_sent"] is False
        assert "pastoral_retreat" not in request.prompt.lower()
        assert "WIN001" not in request.prompt
        assert audit["adapted_schema_in_payload"] is True


class TestAuthorization:
    def test_wrong_scope_rejected(self):
        with pytest.raises(PlannerCanaryError):
            validate_authorization_scope("phase4a-offline-payload-only")

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
        assert result.bundle["header"]["actual_provider_calls"] == 0
        assert result.bundle["header"]["production_data_sent"] == "NO"


class TestFakeExecute:
    def test_fake_engine_one_call_no_publication(self, tmp_path):
        transport = _fake_transport()
        engine = FakeAIEngine(
            script=[
                FakeReply(
                    parsed=transport,
                    text=json.dumps(transport, ensure_ascii=False),
                    finish_reason="end_turn",
                    input_tokens=200,
                    output_tokens=400,
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
        )
        header = result.bundle["header"]
        assert engine.call_count == 1
        assert result.engine_generate_attempts == 1
        assert header["structured_parse"] == "PASS"
        assert header["transport_decoder"] == "PASS"
        assert header["canonical_reconstruction"] == "PASS"
        assert header["deterministic_replay"] == "PASS"
        assert header["silent_omissions"] == 0
        assert header["editorial_plan_json"] == "NOT PUBLISHED"
        assert not editorial_plan_path(PROJECT_NAME, sortie_dir=tmp_path).is_file()
        assert header["ready_for_real_editorial_planner_call"] == "NO"
        contract = result.bundle["contract"]
        assert contract["grouping"]["refs_remain_distinct"] is True
        assert contract["idea_coverage"]["reused"] >= 1
        assert contract["idea_coverage"]["excluded"] == 1
