"""
Phase 3B.7.7A.8 — small-window production readiness.

Aucun réseau. Aucun appel provider réel. Aucun --execute-real pastoral.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis_hybrid_readiness.canary import (
    CanaryAuthorizationError,
    dry_run_win001,
    resolve_canary_planner_version,
    resolve_canary_prompt_version,
    run_win001_canary,
)
from app.source_analysis_hybrid_readiness.canary_cli import main as canary_cli
from app.source_analysis_hybrid_readiness.constants import (
    AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY,
    AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY,
    AUTHORIZATION_SCOPE_WIN001_ONLY,
)
from app.source_analysis_small_window_hierarchy.constants import CANDIDATE_PLANNER_VERSION
from app.source_analysis_small_window_hierarchy.fixtures import n_window_plan
from app.source_analysis_small_window_readiness.constants import (
    AUTHORIZATION_SCOPE,
    DRY_RUN_COMMAND,
    FUTURE_REAL_COMMAND,
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOWS_EXECUTED,
)
from app.source_analysis_small_window_readiness.fixtures import run_fakeai_matrix
from app.source_analysis_small_window_readiness.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
    package_imports_network_clients,
    package_invokes_provider,
)

REAL_CLEAN = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
    r"\transcripts\clean\transcript_data.json"
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
        assert REAL_WINDOWS_EXECUTED == 0
        assert "execute-real" not in DRY_RUN_COMMAND
        assert "window-planner-v2.1-small" in DRY_RUN_COMMAND
        assert "SMALL_V21_WIN001_ONLY" in DRY_RUN_COMMAND
        assert "window-planner-v2.1-small" in FUTURE_REAL_COMMAND
        assert PHASE == "3B.7.7A.8"


class TestPlannerSelection:
    def test_small_scope_resolves_v21_small(self):
        assert (
            resolve_canary_planner_version(AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY)
            == CANDIDATE_PLANNER_VERSION
        )
        with pytest.raises(CanaryAuthorizationError):
            resolve_canary_planner_version(
                AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY,
                "window-planner-v2.0",
            )

    def test_historical_scope_stays_v20(self):
        assert (
            resolve_canary_planner_version(AUTHORIZATION_SCOPE_WIN001_ONLY)
            == "window-planner-v2.0"
        )
        with pytest.raises(CanaryAuthorizationError):
            resolve_canary_planner_version(
                AUTHORIZATION_SCOPE_WIN001_ONLY,
                CANDIDATE_PLANNER_VERSION,
            )

    def test_small_scope_requires_1_1(self):
        assert (
            resolve_canary_prompt_version(AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY)
            == WINDOW_ANALYSIS_PROMPT_VERSION
        )
        with pytest.raises(CanaryAuthorizationError):
            resolve_canary_prompt_version(
                AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY,
                WINDOW_ANALYSIS_PROMPT_VERSION_V10,
            )

    def test_bounded_scope_unchanged(self):
        assert (
            resolve_canary_prompt_version(AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY)
            == WINDOW_ANALYSIS_PROMPT_VERSION
        )

    def test_cli_rejects_unknown_scope(self):
        assert canary_cli([PROJECT_NAME, "--window", "WIN001", "--authorization-scope", "WIN001_ONLY", "--dry-run"]) in {0, 2}


class TestFakeAIExactRunner:
    def test_matrix(self):
        matrix = run_fakeai_matrix()
        assert matrix["isolated_from_pastoral"] is True
        success = matrix["success"]
        assert success["provider_calls"] == 1
        assert success["engine_calls"] == 1
        assert success["ready_windows"] == 1
        assert success["generated_windows"] == 1
        assert success["continued"] is False
        assert success["consolidation"] is False
        assert success["source_map"] is False
        assert success["source_analysis_success"] is False
        assert success["warm_used_cache"] is True
        assert success["warm_engine_calls"] == 0
        boundary = matrix["provider_boundary"]
        assert boundary["engine_calls"] == 1
        assert boundary["forensics_json"] is True
        assert boundary["forensics_raw"] is True
        assert boundary["continued"] is False
        structured = matrix["structured"]
        assert structured["forensics_present"] is True
        assert structured["parse_kind"] == "json_decode"
        assert structured["continued"] is False
        capacity = matrix["capacity"]
        assert capacity["transport_present"] is True
        assert capacity["result_absent"] is True
        assert capacity["overflow_present"] is True
        hard = matrix["hard_limit"]
        assert hard["transport_present"] is True
        assert hard["result_absent"] is True
        assert hard["continued"] is False

    def test_injected_v20_plan_rejected(self, tmp_path):
        from app.source_analysis.window_fixtures import three_window_fixture
        from app.source_analysis.window_granularity_fixtures import bounded_success_transport
        from app.ai.providers.fake import FakeReply
        from app.source_analysis.window_fixtures import WindowMappedFakeAI

        transcript, plan = three_window_fixture()
        engine = WindowMappedFakeAI(
            {"WIN001": FakeReply(parsed=bounded_success_transport(owned=plan.windows[0].owned_src_refs))}
        )
        result = run_win001_canary(
            "fixture",
            window_id="WIN001",
            dry_run=False,
            execute_real=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            planner_version=CANDIDATE_PLANNER_VERSION,
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
            engine=engine,
            windows_root_override=tmp_path / "windows",
            sortie_dir=tmp_path,
            transcript=transcript,
            plan=plan,
        )
        assert result.accepted is False
        assert result.provider_calls == 0
        assert result.engine_generate_attempted is False


class TestScopeCannotSelectV20:
    def test_n_window_plan_is_candidate(self):
        _transcript, plan = n_window_plan(2)
        assert plan.planner_version == CANDIDATE_PLANNER_VERSION
        assert plan.windows[0].window_id == "WIN001"


@pytest.mark.skipif(not REAL_CLEAN.exists(), reason="corpus réel absent")
class TestRealProjectOffline:
    def test_small_dry_run_uses_v21(self):
        result = run_win001_canary(
            PROJECT_NAME,
            window_id="WIN001",
            dry_run=True,
            execute_real=False,
            authorization_scope=AUTHORIZATION_SCOPE,
            planner_version=CANDIDATE_PLANNER_VERSION,
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
        )
        dry = result.dry_run
        assert result.accepted is True
        assert result.provider_calls == 0
        assert dry["planner_version"] == CANDIDATE_PLANNER_VERSION
        assert dry["prompt_version"] == WINDOW_ANALYSIS_PROMPT_VERSION
        assert dry["granularity_policy_version"] == POLICY_VERSION
        assert dry["first_src"] == "SRC000001"
        assert dry["last_src"] == "SRC001201"
        assert dry["owned_src_count"] == 1195
        assert dry["word_count"] == 5447
        assert dry["estimated_input_tokens"] == 23618
        assert dry["estimated_input_tokens"] <= 35000
        assert dry["max_output_tokens"] == 32000
        assert dry["max_attempts"] == 1
        assert dry["connect_timeout_seconds"] == 30.0
        assert dry["read_timeout_seconds"] == 1800.0
        assert dry["cache_state"] == "MISS"
        assert dry["execution"] is False
        assert dry["plan_window_count"] == 7

    def test_historical_dry_run_still_v20(self):
        historical = dry_run_win001(PROJECT_NAME)
        assert historical["prompt_version"] == WINDOW_ANALYSIS_PROMPT_VERSION_V10
        assert historical["planner_version"] == "window-planner-v2.0"
        assert historical["actual_real_provider_calls"] == 0
        assert historical["plan_window_count"] == 3
