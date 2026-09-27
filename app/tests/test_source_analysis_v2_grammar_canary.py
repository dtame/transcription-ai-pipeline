"""Phase 3B.7.7A.13 — FakeAI / offline. 0 réseau. 0 WIN001 réel."""

from __future__ import annotations

import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.ultra_compact_schema import SEMANTIC_TRANSPORT_VERSION
from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    build_window_system_prompt,
    window_prompt_sha256,
)
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.prompt import build_window_system_prompt_v12
from app.source_analysis_local_v2.schema import compare_v1_v2_schemas
from app.source_analysis_output_ceiling_review.constants import PROMPT_10_SHA, PROMPT_11_SHA
from app.source_analysis_thinking_contract.canary import (
    GrammarCanaryAuthorizationError,
    run_grammar_canary,
    run_semantic_win001_canary,
)
from app.source_analysis_thinking_contract.constants import (
    PHASE as A12_PHASE,
    REAL_PROVIDER_CALL_AUTHORIZED,
    REAL_PROVIDER_CALLS_THIS_PHASE,
)
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis.canonical_vocabulary import (
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
)
from app.source_analysis_v2_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_WINDOW_ID,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    PHASE,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    SYNTHETIC_SRC_IDS,
)
from app.source_analysis_v2_grammar_canary.fixture import build_synthetic_fixture
from app.source_analysis_v2_grammar_canary.guard import (
    GrammarCanaryError,
    assert_synthetic_identity,
    validate_authorization_scope,
)
from app.source_analysis_v2_grammar_canary.payload import (
    assert_schema_metrics,
    build_audited_request,
    measure_v2_schema_bytes,
)
from app.source_analysis_v2_grammar_canary.runner import (
    dry_run_canary,
    run_grammar_thinking_canary,
)
from app.source_analysis_v2_grammar_canary.writer import write_canary_artifacts


def _tiny_transport():
    return {
        "theme": "Planning reduces mistakes",
        "intent": "Show that careful planning helps.",
        "ic": "high",
        "aud": "People who make plans.",
        "ac": "medium",
        "records": [
            {
                "k": "TOPIC",
                "v": "Careful planning",
                "s": ["SRC999001"],
                "l": [],
                "m": ["Planning reduces avoidable mistakes."],
            },
            {
                "k": "IDEA",
                "v": "Careful planning reduces avoidable mistakes.",
                "s": ["SRC999001"],
                "l": [0],
                "m": ["claim", "central"],
            },
            {
                "k": "EXAMPLE",
                "v": "Checking the plan twice.",
                "s": ["SRC999002"],
                "l": [1],
                "m": ["anecdote"],
            },
        ],
    }


def _fake_engine():
    return FakeAIEngine(
        script=[
            FakeReply(
                text=json.dumps(_tiny_transport(), ensure_ascii=False),
                parsed=_tiny_transport(),
                finish_reason="end_turn",
                input_tokens=80,
                output_tokens=40,
                thinking_tokens=0,
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestA12RemainsFrozen:
    def test_a12_still_blocks_real_canary(self):
        assert A12_PHASE == "3B.7.7A.12"
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_PROVIDER_CALL_AUTHORIZED is False
        with pytest.raises(GrammarCanaryAuthorizationError):
            run_grammar_canary(execute_real=True)
        with pytest.raises(GrammarCanaryAuthorizationError):
            run_semantic_win001_canary()


class TestHistoricalFreeze:
    def test_prompt_1_0_and_1_1_byte_identical(self):
        sha11 = window_prompt_sha256(
            build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION)
        )
        sha10 = window_prompt_sha256(
            build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION_V10)
        )
        assert sha11 == PROMPT_11_SHA
        assert sha10 == PROMPT_10_SHA

    def test_prompt_1_2_not_mutated(self):
        first = build_window_system_prompt_v12("en")
        second = build_window_system_prompt_v12("en")
        assert first == second
        assert "planificateur éditorial" in first

    def test_transport_v2_bytes_unchanged(self):
        comparison = compare_v1_v2_schemas()
        assert comparison["v2_generic"]["raw_bytes"] == EXPECTED_RAW_SCHEMA_BYTES == 559
        assert comparison["v2_generic"]["adapted_bytes"] == EXPECTED_ADAPTED_SCHEMA_BYTES == 621
        assert SEMANTIC_TRANSPORT_VERSION == "semantic-transport-v1"

    def test_generation_c_unchanged(self):
        hashes = generation_c_hashes()
        assert hashes["raw_sha256"] == GENERATION_C_RAW_SHA256_3B43
        assert hashes["anthropic_sha256"] == GENERATION_C_ANTHROPIC_SHA256_3B43

    def test_production_planner_and_granularity(self):
        assert POLICY_VERSION == "window-granularity-1.0"
        assert PLANNER_VERSION == "window-planner-v2.0"
        assert PRODUCTION_MAX_OUTPUT_TOKENS == 32000
        assert CANARY_MAX_OUTPUT_TOKENS == 512
        assert CANARY_MAX_OUTPUT_TOKENS != PRODUCTION_MAX_OUTPUT_TOKENS


class TestAuthorizationAndGuard:
    def test_missing_scope_fails_before_network(self):
        with pytest.raises(GrammarCanaryError):
            validate_authorization_scope(None)
        result = run_grammar_thinking_canary(
            "fixture",
            dry_run=True,
            authorization_scope="WRONG",
        )
        assert result.accepted is False
        assert result.mode == "REJECTED"
        assert result.engine_generate_attempts == 0

    def test_win001_scope_rejected(self):
        result = run_grammar_thinking_canary(
            "fixture",
            dry_run=True,
            authorization_scope="SMALL_V21_V2_WIN001_ONLY",
        )
        assert result.accepted is False
        assert result.engine_generate_attempts == 0

    def test_forbidden_identities(self):
        with pytest.raises(GrammarCanaryError):
            assert_synthetic_identity(
                window_id="WIN001",
                transcript_id="TR_CANARY_G",
                src_ids=SYNTHETIC_SRC_IDS,
            )
        with pytest.raises(GrammarCanaryError):
            assert_synthetic_identity(
                window_id=CANARY_WINDOW_ID,
                transcript_id="TR001",
                src_ids=SYNTHETIC_SRC_IDS,
            )
        with pytest.raises(GrammarCanaryError):
            assert_synthetic_identity(
                window_id=CANARY_WINDOW_ID,
                transcript_id="TR_CANARY_G",
                src_ids=("SRC000001", "SRC000002"),
            )


class TestSyntheticFixtureAndPayload:
    def test_fixture_is_synthetic_only(self):
        fixture = build_synthetic_fixture()
        assert fixture.transcript.transcript_id == "TR_CANARY_G"
        assert fixture.window.window_id == CANARY_WINDOW_ID
        assert fixture.window.owned_src_refs == SYNTHETIC_SRC_IDS
        blob = " ".join(segment.text for segment in fixture.transcript.segments)
        assert "pastoral" not in blob.lower()
        assert "WIN001" not in blob

    def test_schema_metrics_match_baseline(self):
        metrics = measure_v2_schema_bytes()
        assert metrics["matches_expected"] is True
        assert_schema_metrics(metrics)

    def test_payload_conditions(self):
        fixture = build_synthetic_fixture()
        built = build_audited_request(fixture)
        audit = built["audit"]
        payload = built["payload"]
        assert audit["model"] == "claude-sonnet-5"
        assert audit["thinking_type"] == "disabled"
        assert payload["thinking"] == {"type": "disabled"}
        assert audit["effort_present"] is False
        assert audit["budget_tokens_present"] is False
        assert audit["task_budget_present"] is False
        assert audit["temperature_present"] is False
        assert audit["format_present"] is True
        assert audit["format_type"] == "json_schema"
        assert audit["max_tokens"] == 512
        assert "effort" not in (payload.get("output_config") or {})
        assert "budget_tokens" not in json.dumps(payload)
        assert "task_budget" not in json.dumps(payload)
        assert "WIN001" not in json.dumps(payload)
        assert "SRC000001" not in json.dumps(payload)
        assert "SRC999001" in built["request"].prompt


class TestDryRunDeterminism:
    def test_dry_run_twice_identical(self, tmp_path):
        first = dry_run_canary(
            "fixture",
            authorization_scope=AUTHORIZATION_SCOPE,
            sortie_dir=tmp_path,
        )
        second = dry_run_canary(
            "fixture",
            authorization_scope=AUTHORIZATION_SCOPE,
            sortie_dir=tmp_path,
        )
        assert first["request_identity"] == second["request_identity"]
        assert first["schema_hash"] == second["schema_hash"]
        assert first["synthetic_fixture_hash"] == second["synthetic_fixture_hash"]
        assert first["actual_real_provider_calls"] == 0
        assert second["actual_real_provider_calls"] == 0
        assert first["payload_audit"]["thinking_type"] == "disabled"

    def test_runner_default_is_dry_run(self, tmp_path):
        result = run_grammar_thinking_canary(
            "fixture",
            authorization_scope=AUTHORIZATION_SCOPE,
            sortie_dir=tmp_path,
        )
        assert result.mode == "DRY_RUN"
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0
        assert result.accepted is True


class TestFakeExecuteIsolation:
    def test_execute_real_without_allow_is_rejected(self, tmp_path):
        result = run_grammar_thinking_canary(
            "fixture",
            dry_run=False,
            execute_real=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            allow_real_provider=False,
            sortie_dir=tmp_path,
        )
        assert result.mode == "REJECTED"
        assert result.engine_generate_attempts == 0

    def test_fake_execute_parses_and_stays_isolated(self, tmp_path):
        engine = _fake_engine()
        result = run_grammar_thinking_canary(
            "fixture",
            dry_run=False,
            execute_real=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            allow_real_provider=True,
            engine=engine,
            sortie_dir=tmp_path,
            write_artifacts=True,
        )
        assert result.engine_generate_attempts == 1
        assert result.anthropic_post_attempts == 0
        assert result.execution["structured_parse"] == "PASS"
        assert result.execution["v2_decoder"] == "PASS"
        assert result.execution["v2_validator"] == "PASS"
        assert result.execution["deferred_kinds"] == []
        assert result.execution["capacity_signal"] == "absent"
        assert set(result.execution["source_refs"]) <= set(SYNTHETIC_SRC_IDS)
        assert result.execution["thinking_tokens"] == 0
        assert result.execution["finish_reason"] == "end_turn"
        written = write_canary_artifacts("fixture", result, sortie_dir=tmp_path)
        assert written["execution"].is_file()
        assert written["payload"].is_file()
        assert written["report"].is_file()
        report = written["report"].read_text(encoding="utf-8")
        assert "# PHASE 3B.7.7A.13" in report
        assert "REAL WINDOW CALLS = 0" in report
        assert "SEMANTIC WIN001 AUTHORIZED = NO" in report
        assert not (tmp_path / "fixture" / "analysis" / "windows" / "WIN001").exists()
        assert "source_map.json" not in report or "NOT PUBLISHED" in report

    def test_a13_phase_constant(self):
        assert PHASE == "3B.7.7A.13"
        assert AUTHORIZATION_SCOPE == "V2_GRAMMAR_CONFIG_CANARY_ONLY"
