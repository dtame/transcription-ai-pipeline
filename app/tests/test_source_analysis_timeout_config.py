"""
Phase 3B.5.1 — configuration offline des timeouts longs.

Aucun réseau. Aucun engine.generate() vers un fournisseur réel.
Aucune valeur opérationnelle longue n'est autorisée.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from app.ai.contracts import AIRequest, USAGE_UNAVAILABLE
from app.ai.cost import CostTracker
from app.ai.errors import AITimeoutError
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.retry import RetryPolicy
from app.source_analysis.guard import RealCallGuard
from app.source_analysis.real_run import GuardedEngine
from app.source_analysis_global_clean.constants import (
    MAX_ATTEMPTS,
    REAL_CALL_TIMEOUT_SECONDS,
)
from app.source_analysis_global_clean.runner import run_global_clean_source_analysis
from app.source_analysis_global_clean.writer import (
    production_source_map_path,
    transport_path,
)
from app.source_analysis_timeout_config.audit import (
    assert_offline_package,
    build_deterministic_audit,
    build_timeout_config_audit,
    generation_c_hashes,
    package_calls_generate_or_post,
    runner_passes_hardcoded_timeout,
    sibling_real_run_passes_hardcoded_timeout,
)
from app.source_analysis_timeout_config.cli import main as timeout_config_cli
from app.source_analysis_timeout_config.cli import run_timeout_config_audit
from app.source_analysis_timeout_config.constants import (
    EXACT_NEXT_READ_TIMEOUT_AUTHORIZED,
    NEW_ANTHROPIC_CALL_AUTHORIZED,
    PHASE,
)
from app.source_analysis_timeout_config.writer import diagnostic_path, report_path
from app.tests.source_analysis_fixtures import (  # noqa: F401
    analysis_env,
    drop_segments,
    fake_engine,
    write_cleanup_provenance,
    write_transcript,
)

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


class TestRunnerNoLongerHardcodesTimeout:
    def test_historical_constant_still_3600(self):
        assert REAL_CALL_TIMEOUT_SECONDS == 3600.0

    def test_runner_does_not_pass_hardcoded_timeout(self):
        assert runner_passes_hardcoded_timeout() is False

    def test_sibling_real_run_does_not_pass_hardcoded_timeout(self):
        assert sibling_real_run_passes_hardcoded_timeout() is False

    def test_max_attempts_still_one(self):
        assert MAX_ATTEMPTS == 1


class TestTimeoutBeforePublication:
    def test_timeout_no_retry_unknown_cost_no_transport(
        self, analysis_env, no_ai_network
    ):
        _sparse_env(analysis_env)
        engine = fake_engine(
            script=[AITimeoutError("Anthropic n'a pas répondu dans les délais.")],
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
            error=AITimeoutError("trop lent", timeout_kind="read"),
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


class TestOfflinePreflightAndDiagnostic:
    def test_preflight_exposes_sources(self, no_ai_network):
        payload = build_timeout_config_audit()
        stage = payload["stages"]["source_analysis"]
        assert stage["provider"] == "anthropic"
        assert stage["model"] == "claude-sonnet-5"
        assert stage["connect_source"] in {"default", "env", "stage", "stage_env"}
        assert stage["read_source"] in {"default", "env", "stage", "stage_env", "provider"}
        assert stage["long_read_override_supported"] is True
        assert payload["production_decision"]["exact_next_read_timeout_authorized"] is False
        assert EXACT_NEXT_READ_TIMEOUT_AUTHORIZED is False

    def test_diagnostic_determinism(self, no_ai_network):
        payload, sha1, sha2 = build_deterministic_audit()
        assert sha1 == sha2
        assert payload["schema_version"] == "1.0"
        assert payload["phase"] == PHASE
        assert payload["mode"] == "OFFLINE"
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
        assert payload["architecture"]["connect_read_separated"] is True
        assert payload["architecture"]["legacy_constant_controls_runner"] is False
        assert payload["http"]["requests_timeout_shape"] == "tuple"
        assert NEW_ANTHROPIC_CALL_AUTHORIZED is False

    def test_package_has_no_generate_or_post(self):
        assert package_calls_generate_or_post() == []
        assert_offline_package()

    def test_cli_rejects_real_call(self):
        assert timeout_config_cli(["demo", "--real-call"]) == 2

    def test_cli_writes_offline_artifacts(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = run_timeout_config_audit(
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
        assert loaded["engine_generate"] == 0
        assert loaded["production_decision"]["new_anthropic_call_authorized"] is False
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        again = run_timeout_config_audit(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert again.diagnostic_sha256 == result.diagnostic_sha256

    def test_audit_modules_do_not_import_requests(self):
        root = Path(__file__).resolve().parents[1] / "source_analysis_timeout_config"
        forbidden = {"requests", "urllib", "httpx", "openai", "anthropic"}
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {alias.name.split(".")[0] for alias in node.names}
                    assert names.isdisjoint(forbidden), path.name
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module.split(".")[0] not in forbidden, path.name

    def test_generation_c_unchanged(self):
        hashes = generation_c_hashes()
        assert hashes["raw_matches_historical"] is True
        assert hashes["anthropic_matches_historical"] is True

    def test_prompt_version_unchanged(self):
        from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION

        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"


class TestNoHeartbeatOrStreaming:
    def test_generate_source_has_no_percent_progress(self):
        payload_source = inspect.getsource(AnthropicEngine.build_payload)
        assert '"stream"' not in payload_source
        assert "57%" not in payload_source
        invoke_source = inspect.getsource(AnthropicEngine._invoke)
        assert "stream=True" not in invoke_source

    def test_http_uses_monotonic(self):
        import app.ai.providers._http as http_module

        source = inspect.getsource(http_module.execute_provider_post)
        assert "time.monotonic" in source
        assert "datetime.now" not in source
