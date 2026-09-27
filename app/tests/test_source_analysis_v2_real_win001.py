"""Phase 3B.7.7A.15 — FakeAI / offline guards. 0 réseau réel."""

from __future__ import annotations

import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis_local_v2.fixtures import v2_success_transport
from app.source_analysis_thinking_contract.canary import (
    GrammarCanaryAuthorizationError,
    run_semantic_win001_canary,
)
from app.source_analysis_v2_real_win001.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_ANALYSIS_SIGNATURE,
    EXPECTED_OWNED_SRC_COUNT,
    EXPECTED_WINDOW_INPUT_HASH,
    EXPECTED_WORD_COUNT,
    PHASE,
    WINDOW_ID,
)
from app.source_analysis_v2_real_win001.guard import (
    OneShotCallGuard,
    RealWin001Error,
    validate_authorization_scope,
    validate_target,
)
from app.source_analysis_v2_real_win001.preflight import openai_dependency_status
from app.source_analysis_v2_real_win001.runner import run_real_v2_win001


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _rich_transport(owned_src: str) -> dict:
    base = v2_success_transport(owned_src=owned_src)
    records = list(base["records"])
    records.insert(
        3,
        {
            "k": "IDEA",
            "v": "Faith remains a crossing practice, not a slogan.",
            "s": [owned_src],
            "l": [0],
            "m": ["claim", "supporting"],
        },
    )
    # RELATION was [2, 1]; after insert it still points at IDEA indexes 2 and 1.
    base["records"] = records
    return base


def _fake_engine(owned_src: str):
    transport = _rich_transport(owned_src)
    return FakeAIEngine(
        script=[
            FakeReply(
                text=json.dumps(transport, ensure_ascii=False),
                parsed=transport,
                finish_reason="end_turn",
                input_tokens=20000,
                output_tokens=800,
                thinking_tokens=0,
                request_id="fake-a15",
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )


class TestA12SemanticCanaryStillBlocked:
    def test_thinking_contract_runner_still_raises(self):
        with pytest.raises(GrammarCanaryAuthorizationError):
            run_semantic_win001_canary()


class TestGuards:
    def test_wrong_scope_fails_before_network(self):
        with pytest.raises(RealWin001Error):
            validate_authorization_scope(None)
        with pytest.raises(RealWin001Error):
            validate_authorization_scope("SMALL_V21_WIN001_ONLY")
        result = run_real_v2_win001(
            "fixture",
            dry_run=True,
            authorization_scope="WRONG",
        )
        assert result.accepted is False
        assert result.blocked_precall is True
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0

    def test_forbidden_windows_rejected(self):
        for window_id in ("WIN002", "WIN003", "WIN007"):
            with pytest.raises(RealWin001Error):
                validate_target(window_id)
            result = run_real_v2_win001(
                "fixture",
                dry_run=True,
                authorization_scope=AUTHORIZATION_SCOPE,
                window_id=window_id,
            )
            assert result.accepted is False
            assert result.engine_generate_attempts == 0


class TestIdentityAndDependency:
    def test_openai_is_present(self):
        status = openai_dependency_status()
        assert status["intended_dependency"] is True
        assert status["present_in_active_venv"] is True
        assert status["production_semantics_changed"] is False

    def test_future_identity_matches_a14(self):
        from app.source_analysis_v2_real_win001.window import (
            load_candidate_win001,
            verify_win001_identity,
        )

        bundle = load_candidate_win001()
        identity = verify_win001_identity(bundle)
        assert identity["analysis_signature"] == EXPECTED_ANALYSIS_SIGNATURE
        assert identity["owned_src_count"] == EXPECTED_OWNED_SRC_COUNT
        assert identity["word_count"] == EXPECTED_WORD_COUNT
        assert identity["input_hash"] == EXPECTED_WINDOW_INPUT_HASH
        assert identity["context_src_count"] == 0
        assert identity["cache"] == "MISS"


class TestDryRunAndFakeExecute:
    def test_dry_run_zero_provider(self, tmp_path):
        result = run_real_v2_win001(
            "pastoral_retreat_v2_validation",
            dry_run=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            window_id=WINDOW_ID,
            artifact_sortie_dir=tmp_path,
            write_artifacts=True,
            tests="offline",
        )
        assert result.accepted is True
        assert result.mode == "DRY_RUN"
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0
        assert result.preflight["analysis_signature"] == EXPECTED_ANALYSIS_SIGNATURE
        assert result.preflight["thinking_mode"] == "disabled"
        assert result.preflight["timeouts"]["read_timeout_seconds"] == 1800.0
        assert result.preflight["timeouts"]["connect_timeout_seconds"] == 30.0
        assert (
            tmp_path
            / "pastoral_retreat_v2_validation"
            / "audit"
            / "source_analysis_v2_real_win001_preflight.json"
        ).is_file()

    def test_fake_execute_one_generate(self, tmp_path):
        from app.source_analysis_v2_real_win001.window import load_candidate_win001

        bundle = load_candidate_win001()
        owned = bundle["window"].owned_src_refs[0]
        engine = _fake_engine(owned)
        result = run_real_v2_win001(
            "pastoral_retreat_v2_validation",
            dry_run=False,
            execute_real=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            window_id=WINDOW_ID,
            engine=engine,
            allow_real_provider=False,
            artifact_sortie_dir=tmp_path,
            write_artifacts=True,
        )
        assert result.engine_generate_attempts == 1
        assert result.anthropic_post_attempts == 0
        assert result.execution["structured_parse"] == "PASS"
        assert result.execution["v2_decoder"] == "PASS"
        assert result.execution["v2_validator"] == "PASS"
        assert result.execution["thinking_tokens"] == 0
        assert result.execution["win002_authorized"] is False
        assert result.execution["source_map"] == "NOT PUBLISHED"
        assert not (
            tmp_path / "pastoral_retreat_v2_validation" / "analysis" / "windows" / "WIN001"
        ).exists()
        assert not (
            tmp_path / "pastoral_retreat_v2_validation" / "analysis" / "source_map.json"
        ).exists()

    def test_second_generate_refused(self):
        from app.ai.contracts import AIRequest

        engine = FakeAIEngine(
            script=[FakeReply(text="{}", parsed={}, finish_reason="stop")] * 2,
            retry_policy=no_delay_policy(max_attempts=1),
        )
        guard = OneShotCallGuard(max_calls=1)
        request = AIRequest(prompt="x")
        guard.guarded_generate(engine, request)
        from app.source_analysis.errors import MaxRealCallsExceededError

        with pytest.raises(MaxRealCallsExceededError):
            guard.guarded_generate(engine, request)


class TestPhaseConstants:
    def test_phase_and_scope(self):
        assert PHASE == "3B.7.7A.15"
        assert AUTHORIZATION_SCOPE == "SMALL_V21_V2_WIN001_ONLY"
        assert WINDOW_ID == "WIN001"
