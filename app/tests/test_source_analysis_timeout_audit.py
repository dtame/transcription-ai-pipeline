"""
Phase 3B.5 — audit offline de la cause du timeout global.

Aucun réseau. Aucun engine.generate() vers un fournisseur réel.
Le timeout de production 3600 n'est pas modifié.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest
import requests

import app.config as config

from app.ai.contracts import AIRequest, USAGE_UNAVAILABLE
from app.ai.cost import CostTracker
from app.ai.errors import AITimeoutError
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.base import BaseAIEngine
from app.ai.retry import RetryPolicy, no_delay_policy
from app.ai.settings import StageSettings, default_timeout_seconds, resolve_stage_settings
from app.source_analysis.guard import RealCallGuard
from app.source_analysis.real_run import GuardedEngine
from app.source_analysis_global_clean.constants import (
    EXPECTED_MODEL,
    EXPECTED_MODEL_MAX_OUTPUT,
    MAX_ATTEMPTS,
    REAL_CALL_TIMEOUT_SECONDS,
    STAGE,
)
from app.source_analysis_global_clean.runner import run_global_clean_source_analysis
from app.source_analysis_global_clean.writer import (
    production_source_map_path,
    transport_path,
)
from app.source_analysis_timeout_audit.audit import (
    anthropic_payload_is_non_streaming,
    assert_offline_package,
    build_deterministic_audit,
    build_timeout_root_cause_audit,
    generate_starts_latency_clock_before_invoke,
    package_calls_generate_or_post,
    production_timeout_unchanged,
    resolve_3b_final_timeout_seconds,
    runner_calls_generate_after_preflight,
    runner_has_no_authorization_wait,
    stage_settings_has_timeout_field,
    timeout_layers,
)
from app.source_analysis_timeout_audit.cli import main as timeout_audit_cli
from app.source_analysis_timeout_audit.cli import run_timeout_root_cause_audit
from app.source_analysis_timeout_audit.constants import (
    INCREASE_3600_ONLY_SUFFICIENT,
    LOWER_TIMEOUT_ELSEWHERE,
    NEW_ANTHROPIC_CALL_AUTHORIZED,
    NEXT_TIMEOUT_JUSTIFICATION,
    PRIMARY_CLASSIFICATION,
)
from app.source_analysis_timeout_audit.writer import diagnostic_path, report_path
from app.tests.ai_fakes import RecordingPost
from app.tests.source_analysis_fixtures import (  # noqa: F401
    analysis_env,
    drop_segments,
    fake_engine,
    write_cleanup_provenance,
    write_transcript,
)

SPARSE_KEEP = ("SRC000001", "SRC000002", "SRC000003", "SRC000004", "SRC000005")
SPARSE_DROP = ("SRC000006", "SRC000007", "SRC000008")


def _sparse_env(env):
    original = env.document
    removed = [segment for segment in original.segments if segment.id in SPARSE_DROP]
    clean = drop_segments(original, set(SPARSE_DROP))
    clean_path = write_transcript(env.transcripts_dir / "clean", clean)
    provenance_path = env.sortie / env.project_name / "audit" / "cleanup_application.json"
    write_cleanup_provenance(
        provenance_path,
        original_path=env.transcript_path,
        clean_path=clean_path,
        original=original,
        clean=clean,
        removed=removed,
    )
    return clean_path, provenance_path


def _anthropic_timeout_engine(**kwargs):
    kwargs.setdefault("model", EXPECTED_MODEL)
    kwargs.setdefault("api_key", "cle-de-test")
    kwargs.setdefault("retry_policy", no_delay_policy(max_attempts=1))
    kwargs.setdefault("timeout_seconds", REAL_CALL_TIMEOUT_SECONDS)
    return AnthropicEngine(**kwargs)


class TestProductionTimeoutUnchanged:
    def test_3600_still_hardcoded(self):
        assert REAL_CALL_TIMEOUT_SECONDS == 3600.0
        assert production_timeout_unchanged() is True

    def test_max_attempts_still_one(self):
        assert MAX_ATTEMPTS == 1


class TestTimeoutResolution:
    def test_effective_3b_final_is_3600(self, no_ai_network):
        assert resolve_3b_final_timeout_seconds() == 3600.0
        assert resolve_3b_final_timeout_seconds() != default_timeout_seconds()

    def test_request_without_timeout_uses_engine(self, no_ai_network):
        engine = _anthropic_timeout_engine()
        request = AIRequest(prompt="x", model=EXPECTED_MODEL)
        assert request.timeout_seconds is None
        assert engine.resolve_timeout(request) == 3600.0

    def test_request_timeout_overrides_engine(self, no_ai_network):
        engine = _anthropic_timeout_engine()
        request = AIRequest(prompt="x", timeout_seconds=12)
        assert engine.resolve_timeout(request) == 12.0

    def test_default_used_when_neither_set(self, no_ai_network):
        engine = AnthropicEngine(
            model=EXPECTED_MODEL,
            api_key="cle-de-test",
            retry_policy=no_delay_policy(max_attempts=1),
        )
        assert engine.resolve_timeout(AIRequest(prompt="x")) == default_timeout_seconds()

    def test_stage_settings_have_no_timeout(self):
        settings = resolve_stage_settings(STAGE)
        assert isinstance(settings, StageSettings)
        assert stage_settings_has_timeout_field() is False
        assert not hasattr(settings, "request_timeout_seconds")

    def test_diagnostic_exposes_effective_timeout(self, no_ai_network):
        payload = build_timeout_root_cause_audit()
        assert payload["effective_timeout"]["seconds"] == 3600.0
        assert payload["effective_timeout"]["lowest_active_timeout_seconds"] == 3600.0
        assert payload["effective_timeout"]["ai_default_active"] is False


class TestExceptionTranslation:
    def test_requests_timeout_becomes_aitimeouterror(self, monkeypatch, no_ai_network):
        import app.ai.providers._http as http_module

        recorder = RecordingPost([requests.exceptions.Timeout("read timed out")])
        monkeypatch.setattr(http_module.requests, "post", recorder)
        engine = _anthropic_timeout_engine()
        with pytest.raises(AITimeoutError) as excinfo:
            engine.generate(AIRequest(prompt="x"))
        assert isinstance(excinfo.value.__cause__, requests.exceptions.Timeout)
        assert excinfo.value.response is None
        assert recorder.calls[0]["timeout"] == (
            config.AI_DEFAULT_CONNECT_TIMEOUT_SECONDS,
            3600.0,
        )

    def test_readtimeout_becomes_aitimeouterror(self, monkeypatch, no_ai_network):
        import app.ai.providers._http as http_module

        recorder = RecordingPost([requests.exceptions.ReadTimeout("no bytes")])
        monkeypatch.setattr(http_module.requests, "post", recorder)
        with pytest.raises(AITimeoutError) as excinfo:
            _anthropic_timeout_engine().generate(AIRequest(prompt="x"))
        assert isinstance(excinfo.value.__cause__, requests.exceptions.ReadTimeout)
        assert "3600" in str(excinfo.value)

    def test_connecttimeout_becomes_aitimeouterror(self, monkeypatch, no_ai_network):
        import app.ai.providers._http as http_module

        recorder = RecordingPost([requests.exceptions.ConnectTimeout("connect")])
        monkeypatch.setattr(http_module.requests, "post", recorder)
        with pytest.raises(AITimeoutError) as excinfo:
            _anthropic_timeout_engine().generate(AIRequest(prompt="x"))
        assert isinstance(excinfo.value.__cause__, requests.exceptions.ConnectTimeout)


class TestAuthorizationClock:
    def test_latency_clock_starts_immediately_before_invoke(self):
        assert generate_starts_latency_clock_before_invoke() is True
        source = inspect.getsource(BaseAIEngine.generate)
        assert "started = self._clock()" in source
        assert "time.monotonic" in inspect.getsource(BaseAIEngine.__init__)
        assert "input(" not in source

    def test_runner_generate_is_after_preflight_and_dry_run(self):
        assert runner_calls_generate_after_preflight() is True
        assert runner_has_no_authorization_wait() is True

    def test_http_timeout_starts_at_requests_post(self):
        import app.ai.providers._http as http_module

        source = inspect.getsource(http_module.execute_provider_post)
        assert "timeout=timeout_arg" in source
        assert "requests.post(" in source
        assert source.find("requests.post(") < source.find("except requests.exceptions.Timeout")


class TestNoRetryUnknownUsageNoPublication:
    def test_timeout_no_retry_unknown_cost_no_transport(
        self, analysis_env, no_ai_network
    ):
        _sparse_env(analysis_env)
        engine = fake_engine(
            script=[AITimeoutError("Anthropic n'a pas répondu dans les délais (3600.0 s).")],
            model="claude-sonnet-5",
        )
        engine.provider_name = "anthropic"
        result = run_global_clean_source_analysis(
            analysis_env.project_name,
            dry_run=False,
            engine=engine,
            sortie_dir=analysis_env.sortie,
            require_protected=False,
            require_credential=False,
        )
        assert result.error_type == "AITimeoutError"
        assert result.actual_real_calls == 1
        assert engine.call_count == 1
        assert result.retry is False
        assert result.max_attempts == 1
        assert result.source_map_published is False
        assert result.project_state_status == "failed"
        assert result.provider_generation == "FAIL"
        assert result.pipeline_result == "N/A"
        assert result.input_tokens is None
        assert result.output_tokens is None
        assert result.cost_status in {"unavailable", "unknown"}
        assert result.total_cost is None
        assert not transport_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        state = analysis_env.state()
        assert state["source_analysis"]["status"] == "failed"
        assert state["source_analysis"]["error"] == "AITimeoutError"

    def test_cost_tracker_timeout_is_unknown_not_zero(self):
        tracker = CostTracker()
        record = tracker.record_failure(
            provider="anthropic",
            model="claude-sonnet-5",
            stage="source_analysis",
            error=AITimeoutError("trop lent"),
            response=None,
        )
        assert record.usage_source == USAGE_UNAVAILABLE
        assert record.input_tokens is None
        assert record.cost.status == "unknown"
        assert record.cost.total_cost is None

    def test_guarded_engine_counts_timeout_as_one_call(self, no_ai_network):
        inner = fake_engine(script=[AITimeoutError("trop lent")], model="claude-sonnet-5")
        inner._retry_policy = RetryPolicy(max_attempts=1, base_delay_seconds=0.0)
        guarded = GuardedEngine(inner, RealCallGuard(max_calls=1))
        with pytest.raises(AITimeoutError):
            guarded.generate(AIRequest(prompt="x"))
        assert guarded.generate_calls == 1
        assert inner.call_count == 1


class TestDiagnosticAndNetworkGuard:
    def test_diagnostic_determinism(self, no_ai_network):
        payload, sha1, sha2 = build_deterministic_audit()
        assert sha1 == sha2
        assert payload["schema_version"] == "1.0"
        assert payload["phase"] == "3B.5"
        assert payload["mode"] == "OFFLINE"
        assert payload["decision"]["primary_classification"] == PRIMARY_CLASSIFICATION
        assert payload["decision"]["increase_3600_only_sufficient"] == (
            INCREASE_3600_ONLY_SUFFICIENT
        )
        assert payload["decision"]["lower_timeout_elsewhere"] == LOWER_TIMEOUT_ELSEWHERE
        assert payload["decision"]["next_timeout_justification"] == (
            NEXT_TIMEOUT_JUSTIFICATION
        )
        assert payload["decision"]["next_timeout_candidate_seconds"] is None
        assert payload["decision"]["new_anthropic_call_authorized"] is False
        assert NEW_ANTHROPIC_CALL_AUTHORIZED is False
        assert payload["network"] == {
            "anthropic": 0,
            "openai": 0,
            "whisper": 0,
            "ollama": 0,
            "lm_studio": 0,
            "other": 0,
        }
        assert payload["engine_generate"] == 0
        assert "timestamp" not in payload
        assert payload["http"]["streaming"] is False
        assert payload["authorization_wait"]["counts_toward_timeout"] is False
        assert anthropic_payload_is_non_streaming() is True

    def test_layers_include_http_and_exclude_future(self, no_ai_network):
        names = [layer["layer"] for layer in timeout_layers()]
        assert "http_client" in names
        assert "future_thread_subprocess" in names
        http = next(layer for layer in timeout_layers() if layer["layer"] == "http_client")
        assert http["active_in_failed_run"] is True
        assert http["effective_seconds"] == 3600.0
        future = next(
            layer for layer in timeout_layers() if layer["layer"] == "future_thread_subprocess"
        )
        assert future["active_in_failed_run"] is False

    def test_package_has_no_generate_or_post(self):
        assert package_calls_generate_or_post() == []
        assert_offline_package()

    def test_cli_rejects_real_call(self):
        assert timeout_audit_cli(["demo", "--real-call"]) == 2

    def test_cli_writes_offline_artifacts(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = run_timeout_root_cause_audit(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert result.outcome == "PASS"
        assert result.diagnostic_deterministic is True
        assert result.protected_unchanged is True
        diag = diagnostic_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        )
        report = report_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        )
        assert diag.is_file()
        assert report.is_file()
        loaded = json.loads(diag.read_bytes().decode("utf-8"))
        assert loaded["network"]["anthropic"] == 0
        assert loaded["decision"]["new_anthropic_call_authorized"] is False
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        again = run_timeout_root_cause_audit(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert again.diagnostic_sha256 == result.diagnostic_sha256

    def test_audit_modules_do_not_import_requests(self):
        root = Path(__file__).resolve().parents[1] / "source_analysis_timeout_audit"
        forbidden = {"requests", "urllib", "httpx", "openai", "anthropic"}
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {alias.name.split(".")[0] for alias in node.names}
                    assert names.isdisjoint(forbidden), path.name
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module.split(".")[0] not in forbidden, path.name
