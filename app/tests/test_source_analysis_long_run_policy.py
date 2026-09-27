"""
Phase 3B.5.2 — politique offline du second essai global.

Aucun réseau. Aucun engine.generate() vers un fournisseur réel.
Aucun .env réel modifié. Aucun source_map de production.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.retry import no_delay_policy
from app.source_analysis.writer import source_map_path
from app.source_analysis_global_clean.writer import production_source_map_path
from app.source_analysis_long_run_policy.audit import (
    assert_offline_package,
    build_deterministic_policy,
    build_policy_audit,
    package_calls_generate_or_post,
)
from app.source_analysis_long_run_policy.cli import main as policy_cli
from app.source_analysis_long_run_policy.cli import run_long_run_policy
from app.source_analysis_long_run_policy.constants import (
    CANDIDATE_READ_TIMEOUTS_SECONDS,
    DECISION_ARCHITECTURE_REVIEW,
    DECISION_PRESERVE_TRANSPORT_OFFLINE_DIAGNOSIS,
    DECISION_RETRY_WITH_LONGER_TIMEOUT,
    FIRST_FAILURE_LOWER_BOUND_SECONDS,
    GLOBAL_ATTEMPT_NUMBER,
    LINEAR_CANARY_EXTRAPOLATION_ALLOWED,
    MAX_ATTEMPTS,
    MAX_REAL_CALLS,
    PHASE,
    SELECTED_OPERATIONAL_CONNECT_TIMEOUT_SECONDS,
    SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS,
    SELECTED_POLICY_STATUS,
    SOURCE_ANALYSIS_CONNECT_ENV,
    SOURCE_ANALYSIS_READ_ENV,
    STATUS_AUTHORIZED_FOR_EXECUTION,
    THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED,
)
from app.source_analysis_long_run_policy.policy import (
    decide_after_attempt_2,
    evaluate_candidates,
    justify_selected_timeout,
    local_failure_requirements,
    other_stages_isolated,
    proposed_environ,
    selected_policy,
    simulate_source_analysis_timeouts,
    simulate_stage_timeouts,
)
from app.source_analysis_long_run_policy.writer import policy_path, report_path
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.tests.ai_fakes import RecordingPost, anthropic_response
from app.tests.source_analysis_fixtures import (  # noqa: F401
    analysis_env,
    drop_segments,
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


class TestCandidateEvaluation:
    def test_all_required_candidates_are_evaluated(self):
        rows = evaluate_candidates()
        assert [row["candidate"] for row in rows] == list(
            CANDIDATE_READ_TIMEOUTS_SECONDS
        )
        assert CANDIDATE_READ_TIMEOUTS_SECONDS == (5400, 7200, 9000, 10800)

    def test_no_candidate_at_or_below_first_failure_is_selected(self):
        for row in evaluate_candidates():
            assert row["exceeds_first_failure_lower_bound"] is True
            if row["selected"]:
                assert row["candidate"] > FIRST_FAILURE_LOWER_BOUND_SECONDS

    def test_exactly_one_candidate_selected(self):
        selected = [row for row in evaluate_candidates() if row["selected"]]
        assert len(selected) == 1
        assert selected[0]["candidate"] == SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS

    def test_7200_selected_after_comparing_all_candidates(self):
        justification = justify_selected_timeout()
        assert justification["value"] == 7200
        assert justification["scientifically_proven"] is False
        assert justification["provider_guarantee"] is False
        assert justification["operational_engineering_policy"] is True
        assert justification["linear_canary_extrapolation_used"] is False
        assert "5400" in justification["reasoning"]
        assert "9000" in justification["reasoning"]
        assert "10800" in justification["reasoning"]

    def test_linear_canary_extrapolation_forbidden(self):
        assert LINEAR_CANARY_EXTRAPOLATION_ALLOWED is False


class TestSelectedTimeoutResolution:
    def test_env_patch_resolves_source_analysis_read(self, no_ai_network):
        resolved = simulate_source_analysis_timeouts(environ=proposed_environ())
        assert resolved["connect_seconds"] == float(
            SELECTED_OPERATIONAL_CONNECT_TIMEOUT_SECONDS
        )
        assert resolved["read_seconds"] == float(
            SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS
        )
        assert resolved["connect_source"] == "stage_env"
        assert resolved["read_source"] == "stage_env"
        assert resolved["requests_timeout"] == [
            float(SELECTED_OPERATIONAL_CONNECT_TIMEOUT_SECONDS),
            float(SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS),
        ]


class TestStageIsolation:
    def test_source_analysis_override_does_not_alter_other_stages(self, no_ai_network):
        simulated = simulate_stage_timeouts(environ=proposed_environ())
        assert other_stages_isolated(simulated) is True
        assert simulated["editorial_planning"]["read_seconds"] == 300.0
        assert simulated["book_generation"]["read_seconds"] == 300.0
        assert simulated["book_validation"]["read_seconds"] == 300.0
        assert simulated["source_analysis"]["read_seconds"] == 7200.0


class TestRequestsTuple:
    def test_future_configuration_sends_selected_tuple(
        self, monkeypatch, no_ai_network
    ):
        import app.ai.providers._http as http_module

        monkeypatch.setenv(
            SOURCE_ANALYSIS_CONNECT_ENV,
            str(SELECTED_OPERATIONAL_CONNECT_TIMEOUT_SECONDS),
        )
        monkeypatch.setenv(
            SOURCE_ANALYSIS_READ_ENV,
            str(SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS),
        )
        recorder = RecordingPost([anthropic_response()])
        monkeypatch.setattr(http_module.requests, "post", recorder)
        AnthropicEngine(
            model="claude-sonnet-5",
            api_key="cle-de-test",
            retry_policy=no_delay_policy(max_attempts=1),
        ).generate(AIRequest(prompt="x", metadata={"stage": "source_analysis"}))
        assert recorder.calls[0]["timeout"] == (
            float(SELECTED_OPERATIONAL_CONNECT_TIMEOUT_SECONDS),
            float(SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS),
        )


class TestOneCall:
    def test_policy_is_single_shot(self):
        policy = selected_policy()
        assert policy.max_real_calls == 1
        assert policy.max_attempts == 1
        assert MAX_REAL_CALLS == 1
        assert MAX_ATTEMPTS == 1
        assert policy.retry is False
        assert policy.fallback is None


class TestNoThirdTimeoutEscalation:
    def test_third_escalation_prohibited(self):
        policy = selected_policy()
        assert policy.third_global_timeout_escalation_allowed is False
        assert THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED is False


class TestSecondTimeoutNextStep:
    def test_second_timeout_is_architecture_review_not_longer_retry(self):
        decision = decide_after_attempt_2("AITimeoutError")
        assert decision == DECISION_ARCHITECTURE_REVIEW
        assert decision != DECISION_RETRY_WITH_LONGER_TIMEOUT


class TestPostProviderLocalFailure:
    def test_preserve_transport_offline_no_retry(self):
        decision = decide_after_attempt_2("POST_PROVIDER_LOCAL_FAILURE")
        assert decision == DECISION_PRESERVE_TRANSPORT_OFFLINE_DIAGNOSIS
        rules = local_failure_requirements()
        assert rules["preserve_transport"] is True
        assert rules["offline_diagnosis_first"] is True
        assert rules["provider_retry_allowed"] is False


class TestFailureClasses:
    def test_provider_error_stops(self):
        assert decide_after_attempt_2("429") == "STOP_HUMAN_REVIEW"
        assert decide_after_attempt_2("500") == "STOP_HUMAN_REVIEW"

    def test_truncation_stops(self):
        assert decide_after_attempt_2("max_tokens") == "STOP_NO_RETRY"


class TestPolicyStatusCeiling:
    def test_status_is_technically_authorizable_not_authorized(self):
        policy = selected_policy()
        assert policy.status == SELECTED_POLICY_STATUS
        assert policy.status != STATUS_AUTHORIZED_FOR_EXECUTION
        assert policy.attempt_number == GLOBAL_ATTEMPT_NUMBER


class TestNoExecution:
    def test_package_has_no_generate_or_post(self):
        assert package_calls_generate_or_post() == []
        assert_offline_package()

    def test_audit_modules_do_not_import_network_clients(self):
        root = Path(__file__).resolve().parents[1] / "source_analysis_long_run_policy"
        forbidden = {"requests", "urllib", "httpx", "openai", "anthropic"}
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {alias.name.split(".")[0] for alias in node.names}
                    assert names.isdisjoint(forbidden), path.name
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module.split(".")[0] not in forbidden, path.name

    def test_payload_network_is_zero(self, no_ai_network):
        payload = build_policy_audit()
        assert payload["network"] == {
            "anthropic": 0,
            "openai": 0,
            "whisper": 0,
            "ollama": 0,
            "lm_studio": 0,
            "other": 0,
        }
        assert payload["engine_generate"] == 0
        assert payload["execution"]["provider_call_performed"] is False
        assert payload["execution"]["execution_authorized"] is False
        assert payload["execution"]["attempt_2_executed"] is False


class TestDeterminism:
    def test_policy_sha_stable(self, no_ai_network):
        payload, sha1, sha2 = build_deterministic_policy()
        assert sha1 == sha2
        assert payload["schema_version"] == "1.0"
        assert payload["phase"] == PHASE
        assert payload["mode"] == "OFFLINE_POLICY"
        assert "timestamp" not in payload
        encoded = json.dumps(payload, ensure_ascii=False)
        assert "uuid" not in encoded.lower()


class TestNoPublication:
    def test_cli_does_not_create_source_map(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = run_long_run_policy(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert result.outcome == "PASS"
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        assert not source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()


class TestStateUnchanged:
    def test_cli_does_not_mark_success(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = run_long_run_policy(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert result.project_state_status != "SUCCESS"
        assert result.project_state_status != "completed"
        state = analysis_env.state()
        source = state.get("source_analysis")
        if source:
            assert source.get("status") != "SUCCESS"
            assert source.get("status") != "completed"


class TestCliAndArtifacts:
    def test_cli_rejects_real_call(self):
        assert policy_cli(["demo", "--real-call"]) == 2

    def test_cli_writes_offline_artifacts(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = run_long_run_policy(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert result.outcome == "PASS"
        assert result.policy_deterministic is True
        assert result.protected_unchanged is True
        diag = policy_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        )
        report = report_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        )
        assert diag.is_file()
        assert report.is_file()
        loaded = json.loads(diag.read_bytes().decode("utf-8"))
        assert loaded["network"]["anthropic"] == 0
        assert loaded["execution"]["provider_call_performed"] is False
        assert loaded["selected_policy"]["read_timeout_seconds"] == 7200
        assert loaded["selected_policy"]["connect_timeout_seconds"] == 30
        again = run_long_run_policy(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert again.policy_sha256 == result.policy_sha256


class TestIntegrityUnchanged:
    def test_generation_c_unchanged(self):
        hashes = generation_c_hashes()
        assert hashes["raw_matches_historical"] is True
        assert hashes["anthropic_matches_historical"] is True

    def test_prompt_version_unchanged(self):
        from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION

        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"


class TestCostHonesty:
    def test_unknown_output_is_not_zero(self, no_ai_network):
        payload = build_policy_audit()
        known = payload["cost"]["known_input_estimate"]
        assert known["output_cost"] is None
        assert known["total_cost"] is None
        assert known["unknown_must_not_become_zero"] is True
        assert known["input_cost"] is not None
        assert known["input_cost"] != "0"
        assert payload["cost"]["canary_linear_output"]["allowed"] is False
        for row in payload["cost"]["illustrative_output_scenarios"]:
            assert row["label"] == "ILLUSTRATIVE ONLY"
            assert row["prediction"] is False
