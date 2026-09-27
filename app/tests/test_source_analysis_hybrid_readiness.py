"""
Phase 3B.7.6 — hybrid production readiness & WIN001 canary safety.

Aucun réseau. Aucun engine.generate() vers un fournisseur réel.
Aucun source_map de production. Phase 3B reste INCOMPLETE.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ai.contracts import AIRequest
from app.ai.errors import AITimeoutError
from app.ai.providers.fake import FakeReply
from app.ai.settings import resolve_stage_settings
from app.ai.timeouts import diagnose_stage_timeout
from app.source_analysis.canonical_vocabulary import (
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
)
from app.source_analysis.consolidation_models import (
    CONSOLIDATION_MAX_OUTPUT_TOKENS,
    STAGE_CONSOLIDATION,
)
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.window_fixtures import (
    WindowMappedFakeAI,
    mapped_minimal_engine,
    three_window_fixture,
)
from app.source_analysis.window_models import STAGE_WINDOW
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.constants import (
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_TRANSPORT_VERSION,
    HARD_MAX_INPUT_TOKENS,
    PLANNER_VERSION,
)
from app.source_analysis_hybrid_readiness.canary import (
    CanaryAuthorizationError,
    build_canary_anthropic_engine,
    describe_canary_engine,
    dry_run_win001,
    run_win001_canary,
    validate_canary_authorization,
)
from app.source_analysis_hybrid_readiness.canary_cli import main as canary_cli
from app.source_analysis_hybrid_readiness.cli import main as readiness_cli
from app.source_analysis_hybrid_readiness.constants import (
    AUTHORIZATION_SCOPE_WIN001_ONLY,
    CANARY_WINDOW_ID,
    MAX_NEW_CALLS_WIN001,
)
from app.source_analysis_hybrid_readiness.facts import (
    anthropic_credential_available,
    inspect_production_cache,
    rebuild_window_requests,
    verify_clean_transcript,
)
from app.source_analysis_hybrid_readiness.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_hybrid_readiness.retry_audit import build_retry_audit
from app.source_analysis_hybrid_readiness.runner import (
    BASELINE_PASSED,
    TESTS_ADDED,
    run_hybrid_readiness_audit,
)
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis_window_orchestration.offline import (
    assert_analyzer_not_wired as assert_window_orch_not_wired,
)
from app.source_analysis_window_pipeline.offline import (
    assert_analyzer_not_wired as assert_window_not_wired,
)
from app.source_analysis_consolidation.offline import (
    assert_analyzer_not_wired as assert_consolidation_not_wired,
)
from app.source_analysis_hybrid.offline import (
    assert_analyzer_not_wired as assert_hybrid_planner_not_wired,
)
from app.source_analysis_hybrid_reconstruction.offline import (
    assert_analyzer_not_wired as assert_reconstruction_not_wired,
)

REAL_PROJECT = "pastoral_retreat_v2_validation"
REAL_CLEAN = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
    r"\transcripts\clean\transcript_data.json"
)


def test_offline_package_and_analyzer_not_wired():
    assert_offline_package()
    assert_analyzer_not_wired()
    assert_hybrid_planner_not_wired()
    assert_window_not_wired()
    assert_window_orch_not_wired()
    assert_consolidation_not_wired()
    assert_reconstruction_not_wired()


def test_missing_window_rejected_before_provider():
    result = run_win001_canary(
        REAL_PROJECT,
        window_id=None,
        dry_run=True,
        execute_real=False,
    )
    assert result.accepted is False
    assert result.mode == "REJECTED"
    assert result.provider_calls == 0
    assert result.engine_generate_attempted is False


def test_wrong_window_rejected_in_win001_scope():
    with pytest.raises(CanaryAuthorizationError):
        validate_canary_authorization(
            window_id="WIN002",
            authorization_scope=AUTHORIZATION_SCOPE_WIN001_ONLY,
            execute_real=False,
            dry_run=True,
            max_new_calls=MAX_NEW_CALLS_WIN001,
        )


def test_allow_consolidation_rejected():
    result = run_win001_canary(
        REAL_PROJECT,
        window_id=CANARY_WINDOW_ID,
        dry_run=True,
        allow_consolidation=True,
    )
    assert result.accepted is False
    assert result.consolidation_called is False


def test_allow_publication_rejected():
    result = run_win001_canary(
        REAL_PROJECT,
        window_id=CANARY_WINDOW_ID,
        dry_run=True,
        allow_publication=True,
    )
    assert result.accepted is False
    assert result.source_map_published is False


@pytest.mark.skipif(not REAL_CLEAN.exists(), reason="corpus réel absent")
def test_real_dry_run_zero_provider_calls():
    first = dry_run_win001(REAL_PROJECT)
    second = dry_run_win001(REAL_PROJECT)
    assert first["window_id"] == CANARY_WINDOW_ID
    assert first["engine_generate"] is False
    assert first["actual_real_provider_calls"] == 0
    assert first["estimated_input_tokens"] <= HARD_MAX_INPUT_TOKENS
    assert first == second
    assert first["connect_timeout_seconds"] == 30.0
    assert first["read_timeout_seconds"] == 1800.0
    assert first["transcript_text_included"] is False
    assert first["secrets_included"] is False


@pytest.mark.skipif(not REAL_CLEAN.exists(), reason="corpus réel absent")
def test_clean_and_window_plan_facts():
    clean = verify_clean_transcript(REAL_PROJECT)
    assert clean["matches_expected"] is True
    assert clean["segment_count"] == 8298
    assert clean["provenance"]["removed_count"] == 117
    requests = rebuild_window_requests(REAL_PROJECT)
    assert requests["window_count"] == 3
    assert requests["matches_expected_counts"] is True
    assert requests["coverage"]["exact_once"] is True
    assert requests["coverage"]["no_hard_max_violation"] is True
    assert [row["owned_src_count"] for row in requests["windows"]] == [2787, 2771, 2740]


@pytest.mark.skipif(not REAL_CLEAN.exists(), reason="corpus réel absent")
def test_production_cache_all_miss():
    cache = inspect_production_cache(REAL_PROJECT)
    assert cache["all_miss"] is True
    assert cache["unexpected_semantic_artifacts"] is False
    assert cache["fake_ai_in_production_paths"] is False


def test_timeout_resolution_window_and_no_7200_leak():
    window = diagnose_stage_timeout(STAGE_WINDOW)
    assert window["connect_seconds"] == 30.0
    assert window["read_seconds"] == 1800.0
    leaked = diagnose_stage_timeout(
        STAGE_WINDOW,
        environ={"AI_SOURCE_ANALYSIS_READ_TIMEOUT_SECONDS": "7200"},
    )
    assert leaked["read_seconds"] == 1800.0
    engine = build_canary_anthropic_engine()
    request = AIRequest(
        prompt="timeout-probe",
        metadata={"stage": STAGE_WINDOW},
    )
    assert engine.resolve_timeouts(request).as_requests_timeout() == (30.0, 1800.0)


def test_consolidation_timeout_and_max_output():
    consolidation = diagnose_stage_timeout(STAGE_CONSOLIDATION)
    assert consolidation["connect_seconds"] == 30.0
    assert consolidation["read_seconds"] == 1800.0
    settings = resolve_stage_settings(STAGE_CONSOLIDATION)
    assert settings.max_output_tokens == CONSOLIDATION_MAX_OUTPUT_TOKENS
    assert settings.model == "claude-sonnet-5"
    assert settings.provider == "anthropic"


def test_retry_audit_no_hidden_http_retry():
    audit = build_retry_audit()
    assert audit["hidden_http_post_retry"] is False
    assert audit["http"]["uses_requests_session"] is False
    assert audit["canary_retry_safe"] is True
    assert audit["timeouts"]["window_timeout_policy_kept"] is True
    assert audit["timeouts"]["window_with_global_7200_env"]["inherits_7200"] is False
    engine = build_canary_anthropic_engine()
    assert describe_canary_engine(engine)["retry_max_attempts"] == 1
    assert describe_canary_engine(engine)["is_anthropic"] is True
    assert describe_canary_engine(engine)["model"] == "claude-sonnet-5"


def test_canary_engine_does_not_use_default_three_attempts():
    engine = build_canary_anthropic_engine()
    assert engine.retry_policy.max_attempts == 1
    from app.ai.retry import default_retry_policy

    assert default_retry_policy().max_attempts == 3


def test_fake_success_stops_after_win001(tmp_path):
    transcript, plan = three_window_fixture()
    engine = mapped_minimal_engine(plan)
    result = run_win001_canary(
        "fixture",
        window_id="WIN001",
        dry_run=False,
        execute_real=True,
        engine=engine,
        windows_root_override=tmp_path / "windows",
        sortie_dir=tmp_path,
        transcript=transcript,
        plan=plan,
    )
    assert result.accepted is True
    assert result.provider_calls == 1
    assert result.continued_to_next_window is False
    assert result.consolidation_called is False
    assert result.source_map_published is False
    assert result.source_analysis_success is False
    assert result.execution["generated_windows"] == 1
    assert result.execution["total_windows_in_scope"] == 1


def test_fake_failure_stops_after_win001(tmp_path):
    transcript, plan = three_window_fixture()
    engine = WindowMappedFakeAI(
        {
            "WIN001": AITimeoutError("win001 timeout"),
            "WIN002": FakeReply(parsed={"records": []}),
            "WIN003": FakeReply(parsed={"records": []}),
        }
    )
    result = run_win001_canary(
        "fixture",
        window_id="WIN001",
        dry_run=False,
        execute_real=True,
        engine=engine,
        windows_root_override=tmp_path / "windows",
        sortie_dir=tmp_path,
        transcript=transcript,
        plan=plan,
    )
    assert result.accepted is True
    assert result.provider_calls == 1
    assert result.continued_to_next_window is False
    assert result.execution["failed_windows"] == 1
    assert engine.call_count == 1


def test_call_budget_one_even_with_multiple_misses(tmp_path):
    transcript, plan = three_window_fixture()
    engine = mapped_minimal_engine(plan)
    result = run_win001_canary(
        "fixture",
        window_id="WIN001",
        dry_run=False,
        execute_real=True,
        engine=engine,
        max_new_calls=1,
        windows_root_override=tmp_path / "windows",
        sortie_dir=tmp_path,
        transcript=transcript,
        plan=plan,
    )
    assert result.provider_calls <= 1
    assert result.execution["new_calls_consumed"] == 1


def test_execute_without_engine_and_without_allow_real_is_rejected():
    result = run_win001_canary(
        REAL_PROJECT,
        window_id=CANARY_WINDOW_ID,
        dry_run=False,
        execute_real=True,
        allow_real_provider=False,
    )
    assert result.accepted is False
    assert result.provider_calls == 0
    assert "allow_real_provider" in (result.error or "")


def test_canary_cannot_publish_source_map(tmp_path):
    transcript, plan = three_window_fixture()
    engine = mapped_minimal_engine(plan)
    result = run_win001_canary(
        "fixture",
        window_id="WIN001",
        dry_run=False,
        execute_real=True,
        engine=engine,
        windows_root_override=tmp_path / "windows",
        sortie_dir=tmp_path,
        transcript=transcript,
        plan=plan,
    )
    assert result.source_map_published is False
    assert not source_map_path("fixture", sortie_dir=tmp_path).exists()


def test_network_block_on_dry_run(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("requests.post must not run during dry-run")

    monkeypatch.setattr("app.ai.providers._http.requests.post", _boom)
    monkeypatch.setattr("requests.post", _boom)
    first = dry_run_win001(REAL_PROJECT) if REAL_CLEAN.exists() else None
    if first is not None:
        assert first["actual_real_provider_calls"] == 0


@pytest.mark.skipif(not REAL_CLEAN.exists(), reason="corpus réel absent")
def test_credential_boolean_only():
    available = anthropic_credential_available()
    assert available in {True, False}


def test_generation_c_and_prompt_contracts_unchanged():
    generation = generation_c_hashes()
    assert generation["raw_sha256"] == GENERATION_C_RAW_SHA256_3B43
    assert generation["anthropic_sha256"] == GENERATION_C_ANTHROPIC_SHA256_3B43
    assert WINDOW_ANALYSIS_PROMPT_VERSION_V10 == "window-analysis-1.0"
    assert WINDOW_ANALYSIS_PROMPT_VERSION == "window-analysis-1.1"
    assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"
    assert CONSOLIDATION_PROMPT_VERSION == "consolidation-1.0"
    assert CONSOLIDATION_TRANSPORT_VERSION == "consolidation-transport-v1"
    assert PLANNER_VERSION == "window-planner-v2.0"


def test_audit_cli_rejects_real_flags():
    assert readiness_cli(["proj", "--execute-real"]) == 2
    assert readiness_cli(["proj", "--real-call"]) == 2


def test_canary_cli_requires_window():
    assert canary_cli([REAL_PROJECT, "--dry-run"]) == 2


def test_canary_cli_help():
    assert canary_cli(["--help"]) == 0


@pytest.mark.skipif(not REAL_CLEAN.exists(), reason="corpus réel absent")
def test_full_readiness_audit_offline(tmp_path):
    result = run_hybrid_readiness_audit(
        REAL_PROJECT,
        write_artifacts=False,
    )
    assert result.deterministic is True
    assert result.source_map_present is False
    assert result.project_state_status not in {"SUCCESS", "completed"}
    assert result.artifact["real_provider_calls"] == 0
    assert result.artifact["source_map_published"] is False
    assert result.artifact["dry_run"]["identical"] is True
    assert result.artifact["win001"]["estimated_input"] <= HARD_MAX_INPUT_TOKENS
    assert result.readiness_status in {
        "READY_FOR_WIN001_CANARY",
        "BLOCKED",
        "BLOCKED_FOR_HUMAN_REVIEW",
    }
    if result.artifact["prompt_schema"]["credential_available"]:
        assert result.readiness_status == "READY_FOR_WIN001_CANARY"
        assert result.outcome == "PASS"
    assert result.protected_unchanged is True


def test_baseline_constant():
    assert BASELINE_PASSED == 2285
    assert TESTS_ADDED == 25
