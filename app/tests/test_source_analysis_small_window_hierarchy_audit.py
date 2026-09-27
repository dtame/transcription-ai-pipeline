"""Audit 3B.7.7A.7 — artefacts déterministes, 0 réseau, 0 source_map pastoral."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.source_analysis.writer import source_map_path
from app.source_analysis_small_window_hierarchy.constants import (
    CANDIDATE_PLANNER_VERSION,
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    THIRD_WIN001_CALL_AUTHORIZED,
)
from app.source_analysis_small_window_hierarchy.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_small_window_hierarchy.runner import (
    run_small_window_hierarchy_implementation,
)
from app.source_analysis_small_window_hierarchy.writer import (
    direct_path,
    hierarchical_path,
    plan_path,
    preflight_path,
    report_path,
    router_path,
    traceability_path,
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


@pytest.fixture(scope="module")
def facts():
    assert_offline_package()
    assert_analyzer_not_wired()
    return run_small_window_hierarchy_implementation()


def test_zero_provider_and_unwired(facts):
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert THIRD_WIN001_CALL_AUTHORIZED is False
    assert facts["real_provider_calls"] == 0
    assert facts["phase"] == PHASE
    assert not source_map_path(PROJECT_NAME).exists()
    assert facts["source_map_published"] is False


def test_audit_artifacts_exist(facts):
    for path in (
        plan_path(PROJECT_NAME),
        router_path(PROJECT_NAME),
        direct_path(PROJECT_NAME),
        hierarchical_path(PROJECT_NAME),
        traceability_path(PROJECT_NAME),
        preflight_path(PROJECT_NAME),
        report_path(PROJECT_NAME),
    ):
        assert path.is_file(), path
        leftover = path.with_name(path.name + ".partial")
        assert not leftover.exists()


def test_plan_and_router_payloads(facts):
    plan = facts["plan"]
    assert plan["planner_version"] == CANDIDATE_PLANNER_VERSION
    assert plan["window_count"] == 7
    assert plan["coverage"]["every_present_src_owned_once"] is True
    assert plan["hardcoded_window_count"] is False
    router = facts["router"]
    assert router["guard"] == 80000
    assert router["inspects_actual_built_input"] is True
    assert router["real_clean_route_unknown_until_windows_ready"] is True
    assert router["normal"]["route"] in {"DIRECT_GLOBAL", "REGIONAL_THEN_GLOBAL"}
    assert router["stress"]["route"] in {"DIRECT_GLOBAL", "REGIONAL_THEN_GLOBAL"}


def test_fakeai_and_determinism(facts):
    assert facts["direct"]["real_provider_calls"] == 0
    assert facts["hierarchical"]["real_provider_calls"] == 0
    assert facts["direct"]["e2e"] == "PASS"
    assert facts["determinism"]["plan_identical"] is True
    assert facts["preflight"]["real_provider_calls"] == 0
    assert facts["preflight"]["all_future_cache_miss"] is True
    assert facts["third_win001_call"] == "NO"
    header = report_path(PROJECT_NAME).read_text(encoding="utf-8").split("## 1.")[0]
    assert "REAL PROVIDER CALLS =" in header
    assert "PRODUCTION DEFAULT CHANGED =" in header
