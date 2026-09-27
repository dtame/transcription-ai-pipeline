"""
Phase 3B.7.7A.3 — bounded WIN001 retry readiness & cost/risk.

Aucun réseau réel. Aucun retry WIN001. Aucun --execute-real provider.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.errors import AIStructuredOutputError
from app.ai.providers.fake import FakeReply
from app.ai.structured_forensics import (
    FORENSICS_JSON_NAME,
    FORENSICS_RAW_NAME,
    forensics_dir,
    persist_structured_output_forensics,
)
from app.source_analysis.errors import (
    WindowGranularityLimitExceeded,
    WindowSemanticCapacityExceeded,
)
from app.source_analysis.window_analyzer import resolve_window_execution
from app.source_analysis.window_fixtures import (
    WindowMappedFakeAI,
    three_window_fixture,
)
from app.source_analysis.window_granularity import OVERFLOW_TOKEN, POLICY_VERSION
from app.source_analysis.window_granularity_fixtures import (
    bounded_success_transport,
    idea_hard_limit_transport,
    overflow_signal_transport,
)
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis.window_writer import result_path, transport_path
from app.source_analysis.writer import source_map_path
from app.source_analysis_bounded_win001_retry_readiness.constants import (
    AUTHORIZATION_SCOPE,
    DRY_RUN_COMMAND,
    FUTURE_REAL_COMMAND,
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_VERSION,
    WIN001_RETRIED,
)
from app.source_analysis_bounded_win001_retry_readiness.integrity import protected_hashes
from app.source_analysis_bounded_win001_retry_readiness.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
    package_imports_network_clients,
    package_invokes_provider,
)
from app.source_analysis_bounded_win001_retry_readiness.runner import (
    run_bounded_win001_retry_readiness,
)
from app.source_analysis_hybrid_readiness.canary import (
    CanaryAuthorizationError,
    dry_run_win001,
    resolve_canary_prompt_version,
    run_win001_canary,
)
from app.source_analysis_hybrid_readiness.canary_cli import main as canary_cli
from app.source_analysis_hybrid_readiness.constants import (
    AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY,
    AUTHORIZATION_SCOPE_WIN001_ONLY,
)

REAL_AUDIT = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation\audit"
)
REAL_CLEAN = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
    r"\transcripts\clean\transcript_data.json"
)
PROTECTED_BEFORE = protected_hashes(PROJECT_NAME)


def _bounded_engine(transport: dict) -> WindowMappedFakeAI:
    return WindowMappedFakeAI(
        {
            "WIN001": FakeReply(parsed=transport),
            "WIN002": FakeReply(parsed={"records": []}),
            "WIN003": FakeReply(parsed={"records": []}),
        }
    )


def _run_bounded(tmp_path, engine, transcript, plan):
    return run_win001_canary(
        "fixture",
        window_id="WIN001",
        dry_run=False,
        execute_real=True,
        authorization_scope=AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
        engine=engine,
        windows_root_override=tmp_path / "windows",
        sortie_dir=tmp_path,
        transcript=transcript,
        plan=plan,
    )


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOfflineGuards:
    def test_package_has_no_network_imports(self):
        assert package_imports_network_clients() == []
        assert package_invokes_provider() == []
        assert_offline_package()
        assert_analyzer_not_wired()

    def test_phase_authorizes_zero_calls(self):
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert WIN001_RETRIED is False
        assert "execute-real" not in DRY_RUN_COMMAND
        assert "--prompt-version window-analysis-1.1" in FUTURE_REAL_COMMAND
        assert "BOUNDED_WIN001_ONLY" in FUTURE_REAL_COMMAND


class TestPromptSelection:
    def test_historical_scope_stays_1_0(self):
        assert (
            resolve_canary_prompt_version(AUTHORIZATION_SCOPE_WIN001_ONLY)
            == WINDOW_ANALYSIS_PROMPT_VERSION_V10
        )

    def test_bounded_scope_requires_1_1(self):
        assert (
            resolve_canary_prompt_version(AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY)
            == WINDOW_ANALYSIS_PROMPT_VERSION
        )
        with pytest.raises(CanaryAuthorizationError):
            resolve_canary_prompt_version(
                AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY,
                WINDOW_ANALYSIS_PROMPT_VERSION_V10,
            )

    def test_real_provider_without_bounded_1_1_rejected(self):
        result = run_win001_canary(
            PROJECT_NAME,
            window_id="WIN001",
            dry_run=False,
            execute_real=True,
            authorization_scope=AUTHORIZATION_SCOPE_WIN001_ONLY,
            allow_real_provider=True,
        )
        assert result.accepted is False
        assert result.provider_calls == 0
        assert result.engine_generate_attempted is False


class TestFakeAIBoundedRunner:
    def test_exact_runner_success(self, tmp_path):
        transcript, plan = three_window_fixture()
        window = plan.windows[0]
        engine = _bounded_engine(
            bounded_success_transport(owned=window.owned_src_refs)
        )
        result = _run_bounded(tmp_path, engine, transcript, plan)
        root = tmp_path / "windows"
        assert result.accepted is True
        assert result.provider_calls == 1
        assert engine.call_count == 1
        assert result.continued_to_next_window is False
        assert result.execution["generated_windows"] == 1
        assert result.execution["total_windows_in_scope"] == 1
        assert result.execution["ready_windows"] == 1
        assert result.consolidation_called is False
        assert result.source_map_published is False
        assert result.source_analysis_success is False
        assert transport_path("fixture", "WIN001", root=root).is_file()
        assert result_path("fixture", "WIN001", root=root).is_file()
        assert not source_map_path("fixture", sortie_dir=tmp_path).exists()

    def test_capacity_stops_safely(self, tmp_path):
        transcript, plan = three_window_fixture()
        window = plan.windows[0]
        engine = _bounded_engine(
            overflow_signal_transport(owned=window.owned_src_refs)
        )
        result = _run_bounded(tmp_path, engine, transcript, plan)
        root = tmp_path / "windows"
        assert result.provider_calls == 1
        assert engine.call_count == 1
        assert result.execution["failed_windows"] == 1
        assert result.execution["ready_windows"] == 0
        raw = json.loads(
            transport_path("fixture", "WIN001", root=root).read_text(encoding="utf-8")
        )
        assert any(item.get("v") == OVERFLOW_TOKEN for item in raw["records"])
        assert not result_path("fixture", "WIN001", root=root).exists()

    def test_overlimit_stops_safely(self, tmp_path):
        transcript, plan = three_window_fixture()
        window = plan.windows[0]
        engine = _bounded_engine(
            idea_hard_limit_transport(owned=window.owned_src_refs)
        )
        result = _run_bounded(tmp_path, engine, transcript, plan)
        root = tmp_path / "windows"
        assert result.provider_calls == 1
        assert engine.call_count == 1
        assert result.execution["failed_windows"] == 1
        assert transport_path("fixture", "WIN001", root=root).is_file()
        assert not result_path("fixture", "WIN001", root=root).exists()

    def test_parse_failure_preserves_signature_forensics(self, tmp_path):
        transcript, plan = three_window_fixture()
        engine = WindowMappedFakeAI(
            {
                "WIN001": FakeReply(
                    text='{"theme": "cut mid-stream"',
                    output_tokens=12000,
                    finish_reason="stop",
                    request_id="msg_bounded_parse",
                )
            }
        )
        result = _run_bounded(tmp_path, engine, transcript, plan)
        root = tmp_path / "windows"
        window = plan.windows[0]
        bundle = resolve_window_execution(
            window,
            transcript,
            engine=engine,
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
        )
        forensic = forensics_dir(root, "WIN001", bundle.signature)
        assert result.provider_calls == 1
        assert engine.call_count == 1
        assert not transport_path("fixture", "WIN001", root=root).exists()
        payload = json.loads((forensic / FORENSICS_JSON_NAME).read_text(encoding="utf-8"))
        raw = (forensic / FORENSICS_RAW_NAME).read_text(encoding="utf-8")
        assert payload["analysis_signature"] == bundle.signature
        assert payload["finish_reason"] == "stop"
        assert payload["request_id"] == "msg_bounded_parse"
        assert payload["parse_error"]["parse_failure_kind"] == "json_decode"
        assert raw == '{"theme": "cut mid-stream"'
        other = forensics_dir(root, "WIN001", "b" * 64)
        assert not (other / FORENSICS_JSON_NAME).exists()


class TestForensicCollision:
    def test_persist_requires_signature(self):
        error = AIStructuredOutputError("broken")
        with pytest.raises(TypeError):
            persist_structured_output_forensics(
                error=error,
                windows_root=Path("x"),
                window_id="WIN001",
            )

    def test_invalid_signature_rejected(self, tmp_path):
        error = AIStructuredOutputError("broken")
        with pytest.raises(ValueError):
            persist_structured_output_forensics(
                error=error,
                windows_root=tmp_path / "windows",
                window_id="WIN001",
                analysis_signature="../secret",
            )


class TestLocalEnforcement:
    def test_overflow_is_not_ready(self):
        from app.source_analysis.window_granularity import (
            validate_window_transport_granularity,
        )
        from app.source_analysis.window_granularity_fixtures import default_window

        transcript, window = default_window()
        with pytest.raises(WindowSemanticCapacityExceeded):
            validate_window_transport_granularity(
                overflow_signal_transport(owned=window.owned_src_refs)
            )

    def test_overlimit_is_not_ready(self):
        from app.source_analysis.window_granularity import (
            validate_window_transport_granularity,
        )
        from app.source_analysis.window_granularity_fixtures import default_window

        transcript, window = default_window()
        with pytest.raises(WindowGranularityLimitExceeded):
            validate_window_transport_granularity(
                idea_hard_limit_transport(owned=window.owned_src_refs)
            )


@pytest.mark.skipif(not REAL_CLEAN.exists(), reason="corpus réel absent")
class TestRealProjectOffline:
    def test_historical_dry_run_remains_1_0(self):
        historical = dry_run_win001(PROJECT_NAME)
        assert historical["prompt_version"] == WINDOW_ANALYSIS_PROMPT_VERSION_V10
        assert historical["actual_real_provider_calls"] == 0

    def test_bounded_dry_run_uses_1_1(self):
        result = run_win001_canary(
            PROJECT_NAME,
            window_id="WIN001",
            dry_run=True,
            execute_real=False,
            authorization_scope=AUTHORIZATION_SCOPE,
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
        )
        dry = result.dry_run
        assert result.accepted is True
        assert result.provider_calls == 0
        assert dry["prompt_version"] == WINDOW_ANALYSIS_PROMPT_VERSION
        assert dry["granularity_policy_version"] == POLICY_VERSION
        assert dry["cache_state"] == "MISS"
        assert dry["max_output_tokens"] == 32000
        assert dry["max_attempts"] == 1
        assert dry["connect_timeout_seconds"] == 30.0
        assert dry["read_timeout_seconds"] == 1800.0
        assert dry["estimated_input_tokens"] == 50299
        assert dry["estimated_input_tokens"] <= 60000
        assert dry["execution"] is False
        assert dry["provider"] == "anthropic"
        assert dry["model"] == "claude-sonnet-5"

    def test_cli_dry_run_bounded(self):
        assert (
            canary_cli(
                [
                    PROJECT_NAME,
                    "--window",
                    "WIN001",
                    "--authorization-scope",
                    "BOUNDED_WIN001_ONLY",
                    "--prompt-version",
                    "window-analysis-1.1",
                    "--dry-run",
                ]
            )
            == 0
        )

    def test_artifacts_deterministic_and_protected(self):
        first = run_bounded_win001_retry_readiness(PROJECT_NAME)
        assert first["real_provider_calls"] == 0
        assert first["readiness"] in {
            "READY_FOR_BOUNDED_WIN001_CANARY",
            "BLOCKED",
        }
        readiness = json.loads(
            (REAL_AUDIT / "source_analysis_bounded_win001_retry_readiness.json").read_text(
                encoding="utf-8"
            )
        )
        cost = json.loads(
            (REAL_AUDIT / "source_analysis_bounded_win001_cost_risk.json").read_text(
                encoding="utf-8"
            )
        )
        contract = json.loads(
            (
                REAL_AUDIT / "source_analysis_bounded_win001_execution_contract.json"
            ).read_text(encoding="utf-8")
        )
        dry = json.loads(
            (REAL_AUDIT / "source_analysis_bounded_win001_dry_run.json").read_text(
                encoding="utf-8"
            )
        )
        report = (
            REAL_AUDIT
            / "PHASE_3B77A3_BOUNDED_WIN001_RETRY_READINESS_COST_RISK_REPORT.md"
        ).read_text(encoding="utf-8")
        assert readiness["schema_version"] == SCHEMA_VERSION
        assert readiness["phase"] == PHASE
        assert readiness["request"]["prompt_version"] == WINDOW_ANALYSIS_PROMPT_VERSION
        assert readiness["request"]["signatures_differ"] is True
        assert readiness["cache"]["WIN001_1_1"]["cache_state"] == "MISS"
        assert cost["not_prediction"] is True
        assert cost["historical_spend_separated"] is True
        assert cost["hard_max_is_not_provider_billing_ceiling"] is True
        assert contract["max_new_calls"] == 1
        assert contract["future_real_command_executed"] is False
        assert dry["prompt_version"] == WINDOW_ANALYSIS_PROMPT_VERSION
        assert dry["provider_calls"] == 0
        assert "READINESS =" in report
        assert "WIN001 RETRIED =" in report
        after = protected_hashes(PROJECT_NAME)
        assert after == PROTECTED_BEFORE
        win001 = Path(
            r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
            r"\analysis\windows\WIN001"
        )
        assert not (win001 / "transport.json").exists()
        assert not (win001 / "result.json").exists()
        assert not source_map_path(PROJECT_NAME).exists()
