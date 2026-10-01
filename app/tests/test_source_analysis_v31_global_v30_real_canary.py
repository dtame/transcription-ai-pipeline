"""Phase 3B.7.7A.46 — FakeAI / offline. 0 réseau réel. 0 publication source_map."""

from __future__ import annotations

import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.writer import source_map_path
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    FUTURE_AUTHORIZATION_SCOPE,
)
from app.source_analysis_v31_global_v30_exact_preflight.fakeai import production_inventory
from app.source_analysis_v31_global_v30_exact_preflight.inventory import load_exact_windows
from app.source_analysis_v31_global_reuse_output.fixture import all_distinct_reuse_transport
from app.source_analysis_v31_global_v30_grammar_canary.constants import (
    AUTHORIZATION_SCOPE as A44_SCOPE,
)
from app.source_analysis_v31_global_v30_real_canary.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    A39_STATUS_PRESERVED,
    A40_STATUS_PRESERVED,
    A41_STATUS_PRESERVED,
    A42_STATUS_PRESERVED,
    A43_STATUS_PRESERVED,
    A44_STATUS_PRESERVED,
    A45_NORMALIZED_INPUT_HASH,
    A45_REQUEST_HASH,
    A45_STATUS_PRESERVED,
    AUTHORIZATION_SCOPE,
    CONNECT_TIMEOUT_SECONDS,
    EXPECTED_IDEA,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MODEL,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    READ_TIMEOUT_SECONDS,
    READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    SOURCE_MAP_PUBLICATION_AUTHORIZED,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v30_real_canary.engine import (
    CountingAnthropicEngine,
    describe_engine,
)
from app.source_analysis_v31_global_v30_real_canary.guard import (
    GlobalRealCanaryError,
    OneShotCallGuard,
    reject_contract_drift,
    reject_openai,
    reject_publication_path,
    validate_authorization_scope,
    validate_project_name,
    validate_ready_windows,
)
from app.source_analysis_v31_global_v30_real_canary.isolation import (
    assert_analyzer_not_wired,
    assert_network_isolation,
)
from app.source_analysis_v31_global_v30_real_canary.preflight import run_preflight
from app.source_analysis_v31_global_v30_real_canary.runner import (
    dry_run_canary,
    run_global_v30_real_canary,
)
from app.source_analysis_v31_global_v30_real_canary.validate import (
    interpret_production_response,
)
from app.source_analysis_v31_global_preflight.constants import READY_WINDOWS


def _fake_engine(payload):
    return FakeAIEngine(
        script=[
            FakeReply(
                text=json.dumps(payload, ensure_ascii=False),
                parsed=payload,
                finish_reason="end_turn",
                input_tokens=67146,
                output_tokens=13112,
                thinking_tokens=0,
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestHistoricalFreeze:
    def test_history_and_contract(self):
        assert A34_STATUS_PRESERVED == "PASS"
        assert A35_STATUS_PRESERVED == "FAIL"
        assert A36_STATUS_PRESERVED == "PASS"
        assert A37_STATUS_PRESERVED == "PASS"
        assert A38_STATUS_PRESERVED == "FAIL"
        assert A39_STATUS_PRESERVED == "PASS"
        assert A40_STATUS_PRESERVED == "FAIL"
        assert A41_STATUS_PRESERVED == "PASS"
        assert A42_STATUS_PRESERVED == "PASS"
        assert A43_STATUS_PRESERVED == "PASS"
        assert A44_STATUS_PRESERVED == "PASS"
        assert A45_STATUS_PRESERVED == "PASS"
        assert PHASE == "3B.7.7A.46"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"
        assert RELATION_QUALITY_TECHNICAL_DEBT == "YES"
        assert SOURCE_MAP_PUBLICATION_AUTHORIZED is False
        assert READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY == "YES"
        assert AUTHORIZATION_SCOPE == FUTURE_AUTHORIZATION_SCOPE
        assert not source_map_path(PROJECT_NAME).is_file()
        assert SCHEMA_RAW_BYTES == 1583
        assert SCHEMA_ADAPTED_BYTES == 1831
        assert SCHEMA_HASH == (
            "822397b642b0e1724e29686962caab32bff63effe18f05bff26b404bad9b2a90"
        )
        assert PROMPT_VERSION == "global-consolidation-3.0"
        assert TRANSPORT_VERSION == "global-consolidation-transport-3.0"
        assert MODEL == "claude-sonnet-5"
        assert THINKING_MODE == "disabled"
        assert PRODUCTION_MAX_OUTPUT_TOKENS == 48000
        assert CONNECT_TIMEOUT_SECONDS == 30.0
        assert READ_TIMEOUT_SECONDS == 600.0


class TestGuards:
    def test_authorization_scope(self):
        assert validate_authorization_scope(AUTHORIZATION_SCOPE) == AUTHORIZATION_SCOPE
        with pytest.raises(GlobalRealCanaryError):
            validate_authorization_scope(A44_SCOPE)
        with pytest.raises(GlobalRealCanaryError):
            validate_authorization_scope("GLOBAL_CONSOLIDATION_3_0_REAL_CANARY")

    def test_project_windows_and_contract(self):
        assert validate_project_name(PROJECT_NAME) == PROJECT_NAME
        with pytest.raises(GlobalRealCanaryError):
            validate_project_name("other_project")
        assert validate_ready_windows(READY_WINDOWS) == tuple(READY_WINDOWS)
        with pytest.raises(GlobalRealCanaryError):
            validate_ready_windows(READY_WINDOWS[:-1])
        reject_contract_drift(
            prompt_version=PROMPT_VERSION,
            transport_version=TRANSPORT_VERSION,
            schema_hash=SCHEMA_HASH,
            model=MODEL,
            thinking_mode=THINKING_MODE,
            max_output=PRODUCTION_MAX_OUTPUT_TOKENS,
        )
        with pytest.raises(GlobalRealCanaryError):
            reject_contract_drift(
                prompt_version=PROMPT_VERSION,
                transport_version=TRANSPORT_VERSION,
                schema_hash=SCHEMA_HASH,
                model="claude-opus-5",
                thinking_mode=THINKING_MODE,
                max_output=PRODUCTION_MAX_OUTPUT_TOKENS,
            )
        with pytest.raises(GlobalRealCanaryError):
            reject_openai("openai")
        reject_publication_path("audit/real/global_consolidation_v30_a46/candidate.json")
        with pytest.raises(Exception):
            reject_publication_path("analysis/source_map.json")

    def test_one_shot_guard(self):
        class _Engine:
            def generate(self, request):
                return "ok"

        class _Req:
            max_output_tokens = PRODUCTION_MAX_OUTPUT_TOKENS
            thinking_mode = THINKING_MODE
            metadata = {"stage": "source_analysis_v31_global_v30_real_canary", "window_id": "GLOBAL"}

        guard = OneShotCallGuard(max_calls=1)
        assert guard.guarded_generate(_Engine(), _Req()) == "ok"
        with pytest.raises(Exception):
            guard.guarded_generate(_Engine(), _Req())


class TestIsolation:
    def test_tests_and_a45_cannot_post(self):
        assert_network_isolation()
        assert_analyzer_not_wired()
        described = describe_engine(object())
        assert described["is_fake"] is False or described["class_name"]


class TestExactIdentity:
    def test_preflight_matches_a45_hashes(self):
        preflight = run_preflight(PROJECT_NAME, authorization_scope=AUTHORIZATION_SCOPE)
        assert preflight["ok"] is True
        assert preflight["normalized_input_hash"] == A45_NORMALIZED_INPUT_HASH
        assert preflight["request_hash"] == A45_REQUEST_HASH
        assert preflight["request_identity"] == "MATCH"
        assert preflight["estimated_input"] <= 80000
        assert preflight["hard_output"] <= 33600
        observed = (preflight["inventory"] or {}).get("observed") or {}
        assert observed["total_records"] == 623
        assert observed["IDEA"] == 286
        dry = dry_run_canary(PROJECT_NAME, authorization_scope=AUTHORIZATION_SCOPE)
        assert dry["actual_real_provider_calls"] == 0
        assert dry["request_identity"] == A45_REQUEST_HASH


class TestOfflineInterpretation:
    def test_all_distinct_reuse_accountability(self):
        windows = load_exact_windows()
        transcript = load_clean_transcript(PROJECT_NAME)
        inventory = production_inventory(windows["normalized"], transcript)
        transport = all_distinct_reuse_transport(inventory)
        interpreted = interpret_production_response(
            transport, inventory=inventory, signature="a46-offline"
        )
        assert interpreted["decoder"] == "PASS"
        assert interpreted["handle_validation"] == "PASS"
        assert interpreted["idea_accountability"] == f"{EXPECTED_IDEA} / {EXPECTED_IDEA}"
        assert interpreted["SINGLE_MEMBER_WITH_V"] == 0
        assert interpreted["NON_IDEA_IN_MEMBERS"] == 0
        assert interpreted["canonical_reconstruction"] == "PASS"
        assert interpreted["canonical_validation"] == "PASS"
        assert interpreted["deterministic_replay"] == "PASS"


class TestRunner:
    def test_wrong_scope_blocked(self):
        result = run_global_v30_real_canary(
            PROJECT_NAME,
            dry_run=True,
            authorization_scope=A44_SCOPE,
        )
        assert result.blocked_precall is True
        assert result.anthropic_post_attempts == 0

    def test_dry_run_zero_calls(self):
        result = run_global_v30_real_canary(
            PROJECT_NAME,
            dry_run=True,
            authorization_scope=AUTHORIZATION_SCOPE,
        )
        assert result.accepted is True
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0
        assert result.dry_run["request_identity"] == A45_REQUEST_HASH

    def test_fake_execute_one_call_no_publication(self):
        windows = load_exact_windows()
        transcript = load_clean_transcript(PROJECT_NAME)
        inventory = production_inventory(windows["normalized"], transcript)
        transport = all_distinct_reuse_transport(inventory)
        result = run_global_v30_real_canary(
            PROJECT_NAME,
            dry_run=False,
            execute_real=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            allow_real_provider=False,
            engine=_fake_engine(transport),
            persist_evidence=False,
        )
        assert result.engine_generate_attempts == 1
        assert result.anthropic_post_attempts <= 1
        assert (result.execution or {}).get("source_map") == "NOT PUBLISHED"
        assert not source_map_path(PROJECT_NAME).is_file()
        assert (result.execution or {}).get("idea_accountability") == "286 / 286"
        assert CountingAnthropicEngine is not type(_fake_engine(transport))
