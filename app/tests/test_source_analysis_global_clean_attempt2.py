"""
Phase 3B Final essai #2 — portes pré-appel, timeouts 30/7200, publication gardée.

Aucun test de ce fichier n'ouvre de connexion : `no_ai_network` interdit
tout POST. Le moteur réel n'est jamais construit.
"""

from __future__ import annotations

import ast
import inspect
import json

import pytest

from app.ai.contracts import AIRequest
from app.ai.errors import AIRequestError, AITimeoutError, AITransientError
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis.guard import RealCallGuard
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.real_run import GuardedEngine
from app.source_analysis.writer import source_map_path
from app.source_analysis_global_clean.constants import (
    CANARY_SIGNATURE_MARKS,
    EXPECTED_MODEL,
    EXPECTED_MODEL_MAX_OUTPUT,
    EXPECTED_PROMPT_VERSION,
    MAX_ATTEMPTS,
    MAX_REAL_CALLS,
    TRANSPORT_VERSION,
)
from app.source_analysis_global_clean.writer import (
    dry_run_path as attempt1_dry_run_path,
)
from app.source_analysis_global_clean_attempt2.constants import (
    ATTEMPT_NUMBER,
    DRY_RUN_ARTIFACT_NAME,
    EXPECTED_CONNECT_TIMEOUT_SECONDS,
    EXPECTED_READ_TIMEOUT_SECONDS,
    FORBIDDEN_THIRD_TIMEOUTS,
    REPORT_NAME,
    RESULT_ARTIFACT_NAME,
    SOURCE_ANALYSIS_CONNECT_ENV,
    SOURCE_ANALYSIS_READ_ENV,
    TRANSPORT_ARTIFACT_NAME,
)
from app.source_analysis_global_clean_attempt2.runner import run_global_clean_attempt2
from app.source_analysis_global_clean_attempt2.timeouts import (
    refuse_third_timeout_value,
    third_timeout_escalation_prohibited,
)
from app.source_analysis_global_clean_attempt2.writer import (
    dry_run_path,
    production_source_map_path,
    transport_path,
)
from app.source_analysis_long_run_policy.constants import (
    THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED,
)
from app.source_analysis.vocabulary_fixtures import build_observed_3b43_invalid_transport
from app.tests.source_analysis_fixtures import (  # noqa: F401
    analysis_env,
    drop_segments,
    fake_engine,
    fake_ultra_analysis_payload,
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


def _remap_ultra(src_ids: list[str]) -> dict:
    payload = fake_ultra_analysis_payload()
    chosen = list(src_ids[:3]) or list(src_ids)
    for record in payload.get("records") or []:
        if record.get("s"):
            record["s"] = list(chosen)
    return payload


def _routed_fake(src_ids: list[str], **kwargs):
    engine = fake_engine(payload=_remap_ultra(src_ids), model="claude-sonnet-5", **kwargs)
    engine.provider_name = "anthropic"
    return engine


def _run_attempt2(env, **kwargs):
    defaults = dict(
        dry_run=True,
        sortie_dir=env.sortie,
        require_protected=False,
        require_credential=False,
        inject_timeout_env=True,
    )
    defaults.update(kwargs)
    return run_global_clean_attempt2(env.project_name, **defaults)


class TestAttemptNumberAndInput:
    def test_attempt_number_is_two(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = _run_attempt2(analysis_env)
        assert result.attempt_number == ATTEMPT_NUMBER == 2
        assert result.outcome == "PASS"
        path = dry_run_path(analysis_env.project_name, sortie_dir=analysis_env.sortie)
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["attempt_number"] == 2
        assert payload["would_call_ai"] is True
        assert payload["actual_real_calls"] == 0
        assert not attempt1_dry_run_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()

    def test_clean_derived_and_provenance(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = _run_attempt2(analysis_env)
        assert result.mode == "DERIVED"
        assert result.original_not_selected is True
        assert result.provenance_verified is True
        assert result.sparse_src_preserved is True
        assert result.present_src_count == 5
        assert result.prompt_version == EXPECTED_PROMPT_VERSION == "1.3"
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"
        assert result.vocabulary_parity == "PASS"
        assert result.missing_from_prompt == []
        assert result.extra_in_prompt == []
        assert result.uses_production_generation_c is True
        assert result.generation_c_unchanged is True
        assert result.generation_a_absent_from_payload is True
        assert result.generation_b_absent_from_payload is True
        assert result.decoder_integrity["fail_closed"] is True
        assert result.strategy == "global"
        assert result.resolved_max_output == EXPECTED_MODEL_MAX_OUTPUT
        assert result.max_output_coherent is True


class TestTimeoutPolicy:
    def test_connect_30_read_7200_stage_env(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = _run_attempt2(analysis_env)
        assert result.effective_connect_timeout_seconds == EXPECTED_CONNECT_TIMEOUT_SECONDS
        assert result.effective_read_timeout_seconds == EXPECTED_READ_TIMEOUT_SECONDS
        assert result.connect_source == "stage_env"
        assert result.read_source == "stage_env"
        assert result.requests_timeout_tuple == [30.0, 7200.0]
        assert result.timeout_env_injected is True
        assert result.other_stages_isolated is True
        assert result.policy_match == "PASS"
        assert result.third_global_timeout_escalation_allowed is False
        payload = json.loads(
            dry_run_path(
                analysis_env.project_name, sortie_dir=analysis_env.sortie
            ).read_text(encoding="utf-8")
        )
        assert payload["effective_connect_timeout_seconds"] == 30.0
        assert payload["effective_read_timeout_seconds"] == 7200.0
        assert payload["connect_source"] == "stage_env"
        assert payload["read_source"] == "stage_env"
        assert payload["third_global_timeout_escalation_allowed"] is False

    def test_timeout_mismatch_stops_without_call(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        _sparse_env(analysis_env)
        monkeypatch.setenv(SOURCE_ANALYSIS_CONNECT_ENV, "30")
        monkeypatch.setenv(SOURCE_ANALYSIS_READ_ENV, "3600")
        engine = _routed_fake(list(SPARSE_KEEP))
        result = _run_attempt2(
            analysis_env,
            dry_run=False,
            engine=engine,
            inject_timeout_env=False,
        )
        assert result.classification == "PRE_CALL_TIMEOUT_MISMATCH"
        assert result.actual_real_calls == 0
        assert engine.call_count == 0
        assert result.source_map_published is False

    def test_requests_tuple_not_scalar(self, no_ai_network):
        inspector = AnthropicEngine(model=EXPECTED_MODEL, api_key="t")
        request = AIRequest(
            prompt="x",
            model=EXPECTED_MODEL,
            metadata={"stage": "source_analysis"},
        )
        import os

        os.environ[SOURCE_ANALYSIS_CONNECT_ENV] = "30"
        os.environ[SOURCE_ANALYSIS_READ_ENV] = "7200"
        try:
            timeouts = inspector.resolve_timeouts(request)
            assert timeouts.as_requests_timeout() == (30.0, 7200.0)
            assert not isinstance(timeouts.as_requests_timeout(), float)
        finally:
            os.environ.pop(SOURCE_ANALYSIS_CONNECT_ENV, None)
            os.environ.pop(SOURCE_ANALYSIS_READ_ENV, None)

    def test_stage_isolation_defaults(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = _run_attempt2(analysis_env)
        from app.source_analysis_global_clean_attempt2.timeouts import (
            diagnose_other_stages,
        )

        blocks = diagnose_other_stages()
        assert blocks["editorial_planning"]["read_seconds"] == 300.0
        assert blocks["book_generation"]["read_seconds"] == 300.0
        assert blocks["book_validation"]["read_seconds"] == 300.0
        assert blocks["source_analysis"]["read_seconds"] == 7200.0
        assert result.other_stages_isolated is True

    def test_third_timeout_escalation_prohibited(self):
        assert THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED is False
        assert third_timeout_escalation_prohibited() is True
        for value in FORBIDDEN_THIRD_TIMEOUTS:
            with pytest.raises(Exception):
                refuse_third_timeout_value(value)


class TestCallGuard:
    def test_one_call_max_attempts_retry_false(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        engine = fake_engine(
            script=[AITransientError("timeout")],
            model="claude-sonnet-5",
        )
        engine.provider_name = "anthropic"
        result = _run_attempt2(
            analysis_env,
            dry_run=False,
            engine=engine,
        )
        assert result.max_real_calls == MAX_REAL_CALLS == 1
        assert result.max_attempts == MAX_ATTEMPTS == 1
        assert result.retry is False
        assert result.fallback is None
        assert result.actual_real_calls == 1
        assert engine.call_count == 1
        assert result.source_map_published is False

    def test_http_error_counts_as_one_call(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        engine = fake_engine(
            script=[AIRequestError("Anthropic a répondu 429.")],
            model="claude-sonnet-5",
        )
        engine.provider_name = "anthropic"
        result = _run_attempt2(
            analysis_env, dry_run=False, engine=engine
        )
        assert result.actual_real_calls == 1
        assert result.network["anthropic"] == 1
        assert result.network["openai"] == 0
        assert engine.call_count == 1

    def test_timeout_kind_captured(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        engine = fake_engine(
            script=[
                AITimeoutError(
                    "read timeout",
                    timeout_kind="read",
                    connect_timeout_seconds=30.0,
                    read_timeout_seconds=7200.0,
                    elapsed_ms=7200000,
                )
            ],
            model="claude-sonnet-5",
        )
        engine.provider_name = "anthropic"
        result = _run_attempt2(
            analysis_env, dry_run=False, engine=engine
        )
        assert result.actual_real_calls == 1
        assert result.timeout_kind == "read"
        assert result.elapsed_ms == 7200000
        assert result.next_action == (
            "3B.6_GLOBAL_ANALYSIS_EXECUTION_STRATEGY_REVIEW"
        )
        assert result.source_map_published is False

    def test_guarded_engine_refuses_second_generate(self, no_ai_network):
        inner = fake_engine(payload=fake_ultra_analysis_payload())
        guarded = GuardedEngine(inner, RealCallGuard(max_calls=MAX_REAL_CALLS))
        guarded.generate(AIRequest(prompt="x"))
        with pytest.raises(MaxRealCallsExceededError):
            guarded.generate(AIRequest(prompt="x"))
        assert guarded.generate_calls == 1


class TestPublicationGating:
    def test_invalid_vocab_preserves_attempt2_transport(
        self, analysis_env, no_ai_network
    ):
        _sparse_env(analysis_env)
        payload = build_observed_3b43_invalid_transport("SRC000001")
        engine = fake_engine(payload=payload, model="claude-sonnet-5")
        engine.provider_name = "anthropic"
        result = _run_attempt2(
            analysis_env, dry_run=False, engine=engine
        )
        assert result.actual_real_calls == 1
        assert result.vocabulary_compliance == "FAIL"
        assert result.source_map_published is False
        assert result.transport_preserved == "PASS"
        assert transport_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).is_file()
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        assert TRANSPORT_ARTIFACT_NAME in result.files_created

    def test_state_success_only_after_publication(
        self, analysis_env, no_ai_network
    ):
        _sparse_env(analysis_env)
        engine = _routed_fake(list(SPARSE_KEEP))
        result = _run_attempt2(
            analysis_env, dry_run=False, engine=engine
        )
        assert result.outcome == "PASS"
        assert result.pipeline_result == "PASS"
        assert result.source_map_published is True
        assert result.project_state_status == "completed"
        assert result.determinism == "PASS"
        assert result.invalid_tokens == []
        assert result.phase4_invoked is False
        assert analysis_env.source_map_path.exists()
        leftover = analysis_env.partial_path
        assert leftover.exists() is False

    def test_existing_source_map_stops(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        map_path = source_map_path(analysis_env.project_name)
        map_path.parent.mkdir(parents=True, exist_ok=True)
        before = b'{"keep": true}\n'
        map_path.write_bytes(before)
        engine = _routed_fake(list(SPARSE_KEEP))
        result = _run_attempt2(
            analysis_env, dry_run=False, engine=engine
        )
        assert result.stop_reason == "EXISTING_SOURCE_MAP"
        assert result.actual_real_calls == 0
        assert engine.call_count == 0
        assert map_path.read_bytes() == before

    def test_dry_run_deterministic_and_no_phase4(
        self, analysis_env, no_ai_network
    ):
        _sparse_env(analysis_env)
        result = _run_attempt2(analysis_env)
        assert result.dry_run_deterministic is True
        assert result.dry_run_sha256_run1 == result.dry_run_sha256_run2
        assert result.signature not in CANARY_SIGNATURE_MARKS
        assert result.phase4_invoked is False
        assert DRY_RUN_ARTIFACT_NAME in result.files_created
        assert RESULT_ARTIFACT_NAME not in result.files_created
        assert REPORT_NAME not in result.files_created


class TestOptionalProtected:
    def test_optional_ultra_canary_source_map_may_be_absent(
        self, analysis_env, no_ai_network
    ):
        _sparse_env(analysis_env)
        result = _run_attempt2(analysis_env, require_protected=False)
        assert result.outcome == "PASS"
        assert result.actual_real_calls == 0


class TestPhase4Forbidden:
    def test_attempt2_package_does_not_import_phase4(self):
        import app.source_analysis_global_clean_attempt2.runner as runner_module
        import app.source_analysis_global_clean_attempt2.cli as cli_module

        for module in (runner_module, cli_module):
            source = inspect.getsource(module)
            tree = ast.parse(source)
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
            forbidden = {
                "app.editorial",
                "app.editorial_planning",
                "app.book_generation",
                "app.book_validation",
                "app.visual_design",
            }
            assert imported.isdisjoint(forbidden)
            for marker in (
                "create_editorial_plan",
                "run_editorial",
                "editorial_plan.json",
            ):
                assert marker not in source
