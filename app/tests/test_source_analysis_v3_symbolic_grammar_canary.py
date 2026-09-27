"""Phase 3B.7.7A.18 — FakeAI / offline. 0 réseau. 0 WIN001 réel."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.ultra_compact_schema import SEMANTIC_TRANSPORT_VERSION
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    build_window_system_prompt,
    window_prompt_sha256,
)
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.prompt import build_window_system_prompt_v12
from app.source_analysis_local_v2.schema import compare_v1_v2_schemas
from app.source_analysis_local_v3.prompt import build_window_system_prompt_v13
from app.source_analysis_local_v3.schema import measure_v3_schema_pair
from app.source_analysis_local_v3.synthetic import measure_v3_worst_case
from app.source_analysis_output_ceiling_review.constants import PROMPT_10_SHA, PROMPT_11_SHA
from app.source_analysis.canonical_vocabulary import (
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
)
from app.source_analysis_thinking_contract.canary import (
    GrammarCanaryAuthorizationError,
    run_grammar_canary,
    run_semantic_win001_canary,
)
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis_v2_grammar_canary.constants import (
    EXPECTED_ADAPTED_SCHEMA_BYTES as V2_ADAPTED,
)
from app.source_analysis_v2_grammar_canary.constants import (
    EXPECTED_RAW_SCHEMA_BYTES as V2_RAW,
)
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_WINDOW_ID,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    PHASE,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    SYNTHETIC_SRC_IDS,
    SYNTHETIC_WORST_CASE_LOCAL_TOKENS,
)
from app.source_analysis_v3_symbolic_grammar_canary.fixture import (
    build_synthetic_fixture,
    expected_valid_transport,
)
from app.source_analysis_v3_symbolic_grammar_canary.guard import (
    SymbolicGrammarCanaryError,
    assert_synthetic_identity,
    validate_authorization_scope,
)
from app.source_analysis_v3_symbolic_grammar_canary.handles import inspect_handle_metrics
from app.source_analysis_v3_symbolic_grammar_canary.payload import (
    assert_schema_metrics,
    build_audited_request,
    measure_v3_schema_bytes,
)
from app.source_analysis_v3_symbolic_grammar_canary.runner import (
    dry_run_canary,
    run_symbolic_handle_grammar_canary,
)
from app.source_analysis_v3_symbolic_grammar_canary.writer import write_canary_artifacts
from app.source_analysis_v3_symbolic_handles.constants import PHASE as A17_PHASE


def _fake_engine(payload=None):
    transport = payload or expected_valid_transport()
    return FakeAIEngine(
        script=[
            FakeReply(
                text=json.dumps(transport, ensure_ascii=False),
                parsed=transport,
                finish_reason="end_turn",
                input_tokens=90,
                output_tokens=70,
                thinking_tokens=0,
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestHistoricalFreeze:
    def test_a17_and_a12_remain_offline(self):
        assert A17_PHASE == "3B.7.7A.17"
        with pytest.raises(GrammarCanaryAuthorizationError):
            run_grammar_canary(execute_real=True)
        with pytest.raises(GrammarCanaryAuthorizationError):
            run_semantic_win001_canary()

    def test_prompt_1_0_and_1_1_byte_identical(self):
        sha11 = window_prompt_sha256(
            build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION)
        )
        sha10 = window_prompt_sha256(
            build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION_V10)
        )
        assert sha11 == PROMPT_11_SHA
        assert sha10 == PROMPT_10_SHA

    def test_prompt_1_2_and_1_3_not_mutated(self):
        first = build_window_system_prompt_v12("en")
        second = build_window_system_prompt_v12("en")
        assert first == second
        v13_a = build_window_system_prompt_v13("en")
        v13_b = build_window_system_prompt_v13("en")
        assert v13_a == v13_b
        assert "HANDLE RULES" in v13_a

    def test_transport_v1_v2_unchanged_and_v3_matches_a17(self):
        comparison = compare_v1_v2_schemas()
        assert comparison["v2_generic"]["raw_bytes"] == V2_RAW == 559
        assert comparison["v2_generic"]["adapted_bytes"] == V2_ADAPTED == 621
        assert SEMANTIC_TRANSPORT_VERSION == "semantic-transport-v1"
        measured = measure_v3_schema_pair()
        assert measured["raw_bytes"] == EXPECTED_RAW_SCHEMA_BYTES == 588
        assert measured["adapted_bytes"] == EXPECTED_ADAPTED_SCHEMA_BYTES == 650

    def test_generation_c_unchanged(self):
        hashes = generation_c_hashes()
        assert hashes["raw_sha256"] == GENERATION_C_RAW_SHA256_3B43
        assert hashes["anthropic_sha256"] == GENERATION_C_ANTHROPIC_SHA256_3B43

    def test_production_planner_and_budgets(self):
        assert PLANNER_VERSION == "window-planner-v2.0"
        assert PRODUCTION_MAX_OUTPUT_TOKENS == 32000
        assert CANARY_MAX_OUTPUT_TOKENS == 1024
        worst = measure_v3_worst_case()
        assert worst["local_tokens"] == SYNTHETIC_WORST_CASE_LOCAL_TOKENS
        assert worst["headroom_to_32000"] == 19815


class TestAuthorizationAndGuard:
    def test_missing_scope_fails_before_network(self):
        with pytest.raises(SymbolicGrammarCanaryError):
            validate_authorization_scope(None)
        result = run_symbolic_handle_grammar_canary(
            "fixture",
            dry_run=True,
            authorization_scope="WRONG",
        )
        assert result.accepted is False
        assert result.mode == "REJECTED"
        assert result.engine_generate_attempts == 0

    def test_win001_and_v2_scopes_rejected(self):
        for scope in (
            "SMALL_V21_V2_WIN001_ONLY",
            "V2_GRAMMAR_CONFIG_CANARY_ONLY",
            "WIN001_ONLY",
        ):
            result = run_symbolic_handle_grammar_canary(
                "fixture",
                dry_run=True,
                authorization_scope=scope,
            )
            assert result.accepted is False
            assert result.engine_generate_attempts == 0

    def test_forbidden_identities(self):
        with pytest.raises(SymbolicGrammarCanaryError):
            assert_synthetic_identity(
                window_id="WIN001",
                transcript_id="TR_CANARY_H",
                src_ids=SYNTHETIC_SRC_IDS,
            )
        with pytest.raises(SymbolicGrammarCanaryError):
            assert_synthetic_identity(
                window_id=CANARY_WINDOW_ID,
                transcript_id="TR001",
                src_ids=SYNTHETIC_SRC_IDS,
            )
        with pytest.raises(SymbolicGrammarCanaryError):
            assert_synthetic_identity(
                window_id=CANARY_WINDOW_ID,
                transcript_id="TR_CANARY_H",
                src_ids=("SRC000001", "SRC000002", "SRC000003", "SRC000004"),
            )


class TestSyntheticFixtureAndPayload:
    def test_fixture_is_synthetic_only(self):
        fixture = build_synthetic_fixture()
        assert fixture.transcript.transcript_id == "TR_CANARY_H"
        assert fixture.window.window_id == CANARY_WINDOW_ID
        assert fixture.window.owned_src_refs == SYNTHETIC_SRC_IDS
        blob = " ".join(segment.text for segment in fixture.transcript.segments)
        assert "pastoral" not in blob.lower()
        assert "WIN001" not in blob
        assert "SRC000001" not in blob

    def test_schema_metrics_match_a17(self):
        metrics = measure_v3_schema_bytes()
        assert metrics["matches_expected"] is True
        assert metrics["matches_a17_fingerprint"] is True
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
        assert audit["max_tokens"] == 1024
        assert audit["schema_version"] == "semantic-transport-v3"
        assert "effort" not in (payload.get("output_config") or {})
        dumped = json.dumps(payload)
        assert "budget_tokens" not in dumped
        assert "task_budget" not in dumped
        assert "WIN001" not in dumped
        assert "SRC000001" not in dumped
        assert "SRC998001" in built["request"].prompt
        assert "HANDLE RULES" in (built["request"].system_prompt or "")


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
        assert first["prompt_hash"] == second["prompt_hash"]
        assert first["synthetic_fixture_hash"] == second["synthetic_fixture_hash"]
        assert first["actual_real_provider_calls"] == 0
        assert second["actual_real_provider_calls"] == 0
        assert first["payload_audit"]["thinking_type"] == "disabled"

    def test_runner_default_is_dry_run(self, tmp_path):
        result = run_symbolic_handle_grammar_canary(
            "fixture",
            authorization_scope=AUTHORIZATION_SCOPE,
            sortie_dir=tmp_path,
        )
        assert result.mode == "DRY_RUN"
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0
        assert result.accepted is True


class TestHandleMetrics:
    def test_valid_transport_coverage(self):
        metrics = inspect_handle_metrics(expected_valid_transport())
        assert metrics["counts"]["idea_to_topic"] >= 1
        assert metrics["counts"]["relation_to_idea"] >= 1
        assert metrics["counts"]["example_to_idea"] >= 1
        assert metrics["counts"]["unknown"] == 0
        assert metrics["counts"]["wrong_kind"] == 0
        assert metrics["counts"]["duplicate_owners"] == 0
        assert metrics["counts"]["self_relations"] == 0
        assert metrics["counts"]["malformed"] == 0
        assert metrics["numeric_link_regression"] == "NO"

    def test_numeric_links_are_regression(self):
        payload = expected_valid_transport()
        payload["records"][5]["l"] = [3, 2]
        metrics = inspect_handle_metrics(payload)
        assert metrics["numeric_link_regression"] == "YES"
        assert metrics["counts"]["relation_to_idea"] == 0

    def test_wrong_kind_and_unknown_not_repaired(self):
        payload = expected_valid_transport()
        payload["records"][2]["l"] = ["I3"]
        payload["records"][5]["l"] = ["T1", "I1"]
        metrics = inspect_handle_metrics(payload)
        assert metrics["counts"]["wrong_kind"] >= 1
        payload = expected_valid_transport()
        payload["records"][2]["l"] = ["T9"]
        metrics = inspect_handle_metrics(payload)
        assert "T9" in metrics["unknown_handles"]


class TestFakeExecuteIsolation:
    def test_execute_real_without_allow_is_rejected(self, tmp_path):
        result = run_symbolic_handle_grammar_canary(
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
        result = run_symbolic_handle_grammar_canary(
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
        assert result.execution["v3_decoder"] == "PASS"
        assert result.execution["handle_registry"] == "PASS"
        assert result.execution["handle_resolution"] == "PASS"
        assert result.execution["v3_validator"] == "PASS"
        assert result.execution["result"] == "PASS"
        handles = result.execution["handles"]
        assert handles["coverage"]["idea_to_topic"] is True
        assert handles["coverage"]["relation_to_idea"] is True
        assert handles["coverage"]["example_to_idea"] is True
        assert handles["numeric_link_regression"] == "NO"
        assert result.execution["thinking_tokens"] == 0
        assert result.execution["reconstruction"]["source_map_published"] is False
        written = write_canary_artifacts("fixture", result, sortie_dir=tmp_path)
        assert written["execution"].is_file()
        assert written["payload"].is_file()
        assert written["handles"].is_file()
        assert written["report"].is_file()
        report = written["report"].read_text(encoding="utf-8")
        assert "# PHASE 3B.7.7A.18 — SYMBOLIC-HANDLE V3 TINY GRAMMAR CANARY" in report
        assert "REAL WINDOW CALLS = 0" in report
        assert "REAL WIN001 AUTHORIZED = NO" in report
        assert "V3_SYMBOLIC_HANDLE_GRAMMAR_CANARY_ONLY" in report
        assert not (tmp_path / "fixture" / "analysis" / "windows" / "WIN001").exists()
        assert "NOT PUBLISHED" in report

    def test_a18_phase_constant(self):
        assert PHASE == "3B.7.7A.18"
        assert AUTHORIZATION_SCOPE == "V3_SYMBOLIC_HANDLE_GRAMMAR_CANARY_ONLY"


class TestAnalyzerNotWired:
    def test_analyzer_and_main_unwired(self):
        analyzer = Path(r"C:\TranscriptionAI\app\source_analysis\analyzer.py")
        main = Path(r"C:\TranscriptionAI\main.py")
        text = analyzer.read_text(encoding="utf-8")
        assert "source_analysis_v3_symbolic_grammar_canary" not in text
        if main.is_file():
            assert "source_analysis_v3_symbolic_grammar_canary" not in main.read_text(
                encoding="utf-8"
            )
