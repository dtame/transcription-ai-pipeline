"""Phase 3B.7.7A.28 — FakeAI / offline guards. 0 réseau réel."""

from __future__ import annotations

import json

import pytest

from app.ai.contracts import AIRequest
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis.schema import build_response_schema
from app.source_analysis_local_v3.constants import WINDOW_ANALYSIS_PROMPT_VERSION_V140
from app.source_analysis_local_v3.fixtures import v31_success_transport
from app.source_analysis_local_v3.schema import (
    build_semantic_transport_v31_local_lite_schema,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis_v3_hardened_win001.constants import (
    AUTHORIZATION_SCOPE as A21_SCOPE,
)
from app.source_analysis_v3_hardened_win004.constants import (
    AUTHORIZATION_SCOPE as A24_SCOPE,
)
from app.source_analysis_v3_second_window.constants import (
    AUTHORIZATION_SCOPE as A22_SCOPE,
)
from app.source_analysis_v31_real_win004.constants import (
    AUTHORIZATION_SCOPE as A27_SCOPE,
    EXPECTED_ANALYSIS_SIGNATURE as A27_SIGNATURE,
)
from app.source_analysis_v31_remaining_windows.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_WINDOW_IDS,
    EXECUTION_ORDER,
    EXPECTED_SCHEMA_HASH,
    PHASE,
    WINDOW_SPECS,
)
from app.source_analysis_v31_remaining_windows.guard import (
    OneShotCallGuard,
    PhaseCallGuard,
    RemainingWindowsError,
    validate_authorization_scope,
    validate_provider,
    validate_target,
)
from app.source_analysis_v31_remaining_windows.payload import (
    assert_schema_identity,
    measure_schema,
)
from app.source_analysis_v31_remaining_windows.runner import run_remaining_windows
from app.source_analysis_v31_remaining_windows.window import (
    load_candidate_plan,
    verify_all_windows,
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _fake_engine_for_plan(bundle, replies=1):
    script = []
    for window_id in EXECUTION_ORDER[:replies]:
        owned = bundle["windows"][window_id].owned_src_refs[0]
        payload = v31_success_transport(owned_src=owned)
        script.append(
            FakeReply(
                text=json.dumps(payload, ensure_ascii=False),
                parsed=payload,
                finish_reason="end_turn",
                input_tokens=48000,
                output_tokens=2100,
                thinking_tokens=0,
                request_id=f"fake-a28-{window_id}",
            )
        )
    return FakeAIEngine(script=script, retry_policy=no_delay_policy(max_attempts=1))


class TestGuards:
    def test_authorization_scope_exact(self):
        with pytest.raises(RemainingWindowsError):
            validate_authorization_scope(None)
        for scope in (A21_SCOPE, A22_SCOPE, A24_SCOPE, A27_SCOPE, "WRONG"):
            with pytest.raises(RemainingWindowsError):
                validate_authorization_scope(scope)
        assert validate_authorization_scope(AUTHORIZATION_SCOPE) == AUTHORIZATION_SCOPE

    def test_forbidden_windows_rejected_before_network(self):
        for window_id in ("WIN001", "WIN004", "WIN996"):
            with pytest.raises(RemainingWindowsError):
                validate_target(window_id)
            result = run_remaining_windows(
                "fixture",
                dry_run=True,
                authorization_scope=AUTHORIZATION_SCOPE,
                window_id=window_id,
            )
            assert result.accepted is False
            assert result.blocked_precall is True
            assert result.engine_generate_attempts == 0
            assert result.anthropic_post_attempts == 0

    def test_authorized_windows_accepted(self):
        for window_id in AUTHORIZED_WINDOW_IDS:
            assert validate_target(window_id) == window_id

    def test_provider_guard(self):
        with pytest.raises(RemainingWindowsError):
            validate_provider(provider="openai", model="claude-sonnet-5")
        with pytest.raises(RemainingWindowsError):
            validate_provider(provider="anthropic", model="claude-opus-4")
        validate_provider(provider="anthropic", model="claude-sonnet-5")

    def test_phase_guard_refuses_sixth_and_overlap(self):
        guard = PhaseCallGuard(max_calls=5)
        for window_id in EXECUTION_ORDER:
            guard.begin(window_id)
            guard.end()
        with pytest.raises(MaxRealCallsExceededError):
            guard.begin("WIN002")
        one = PhaseCallGuard(max_calls=5)
        one.begin("WIN002")
        with pytest.raises(RemainingWindowsError):
            one.begin("WIN003")


class TestIdentityAndSchema:
    def test_schema_identity(self):
        measured = measure_schema()
        assert measured["raw_bytes"] == 588
        assert measured["adapted_bytes"] == 650
        assert measured["raw_hash"] == EXPECTED_SCHEMA_HASH
        assert measured["raw_hash"] == semantic_transport_v31_local_lite_fingerprint()
        assert_schema_identity(measured)
        assert build_semantic_transport_v31_local_lite_schema() != build_response_schema()

    def test_all_seven_windows_match_a26_and_a7(self):
        bundle = load_candidate_plan()
        verified = verify_all_windows(bundle)
        assert verified["WIN001"]["owned_src_count"] == 1195
        assert verified["WIN004"]["owned_src_count"] == 1180
        assert verified["WIN004"]["analysis_signature"] == A27_SIGNATURE
        assert verified["WIN004"]["local_input_estimate"] == 23046
        for window_id, spec in WINDOW_SPECS.items():
            row = verified[window_id]
            assert row["first_owned_src_ref"] == spec["first_owned_src"]
            assert row["last_owned_src_ref"] == spec["last_owned_src"]
            assert row["owned_src_count"] == spec["owned_src_count"]
            assert row["word_count"] == spec["word_count"]
            assert row["input_hash"] == spec["input_hash"]
            assert row["analysis_signature"] == spec["analysis_signature"]
            assert row["local_input_estimate"] == spec["local_input_estimate"]
            assert row["local_input_estimate"] <= 35000
            assert row["cache"] == "MISS"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V140 == "window-analysis-1.4.0"


class TestDryRunAndFakeExecute:
    def test_dry_run_zero_provider(self, tmp_path):
        result = run_remaining_windows(
            "pastoral_retreat_v2_validation",
            dry_run=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            artifact_sortie_dir=tmp_path,
            write_artifacts=True,
            tests="offline",
        )
        assert result.accepted is True
        assert result.mode == "DRY_RUN"
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0
        windows = result.preflight["windows"]
        assert list(windows) == list(EXECUTION_ORDER)
        for window_id, row in windows.items():
            assert row["cache"]["status"] == "MISS"
            assert row["dry_run_twice"]["deterministic"] is True
            assert row["local_input_estimate"] == WINDOW_SPECS[window_id]["local_input_estimate"]
        assert result.preflight["thinking_mode"] == "disabled"
        assert result.preflight["prompt_version"] == "window-analysis-1.4.0"
        assert result.preflight["transport"] == "semantic-transport-v3.1-local-lite"
        assert (
            tmp_path
            / "pastoral_retreat_v2_validation"
            / "audit"
            / "source_analysis_v31_remaining_windows_preflight.json"
        ).is_file()

    def test_stop_on_first_failure_does_not_call_later_windows(self, tmp_path):
        bundle = load_candidate_plan()
        engine = _fake_engine_for_plan(bundle, replies=5)
        result = run_remaining_windows(
            "pastoral_retreat_v2_validation",
            dry_run=False,
            execute_real=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            engine=engine,
            allow_real_provider=False,
            artifact_sortie_dir=tmp_path,
            write_artifacts=True,
        )
        assert "WIN002" in result.windows
        assert result.engine_generate_attempts == 1
        assert result.anthropic_post_attempts == 0
        assert result.stopped_at == "WIN002"
        assert "WIN003" not in result.windows
        assert "WIN005" not in result.windows
        assert result.ready_after_count == 2
        assert not (
            tmp_path
            / "pastoral_retreat_v2_validation"
            / "analysis"
            / "source_map.json"
        ).exists()

    def test_one_attempt_window_guard(self):
        engine = FakeAIEngine(
            script=[FakeReply(text="{}", parsed={}, finish_reason="stop")] * 2,
            retry_policy=no_delay_policy(max_attempts=1),
        )
        guard = OneShotCallGuard(max_calls=1)
        request = AIRequest(prompt="x")
        guard.guarded_generate(engine, request)
        with pytest.raises(MaxRealCallsExceededError):
            guard.guarded_generate(engine, request)

    def test_phase_constant(self):
        assert PHASE == "3B.7.7A.28"

    def test_network_isolation_fixture_active(self, no_ai_network):
        assert no_ai_network is None
