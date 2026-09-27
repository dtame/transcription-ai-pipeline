"""Audit 3B.7.7A.8 — artefacts déterministes, 0 réseau, 0 source_map pastoral."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.source_analysis.writer import source_map_path
from app.source_analysis_small_window_readiness.constants import (
    AUTHORIZATION_SCOPE,
    PHASE,
    PLANNER_VERSION_REQUIRED,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
)
from app.source_analysis_small_window_readiness.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_small_window_readiness.runner import (
    run_small_window_production_readiness,
)
from app.source_analysis_small_window_readiness.writer import (
    boundary_path,
    cache_path,
    contract_path,
    cost_path,
    dry_run_path,
    readiness_path,
    report_path,
)

REAL_AUDIT = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation\audit"
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


@pytest.fixture(scope="module")
def facts():
    assert_offline_package()
    assert_analyzer_not_wired()
    return run_small_window_production_readiness()


def test_zero_provider_and_unwired(facts):
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert facts["real_provider_calls"] == 0
    assert facts["phase"] == PHASE
    assert not source_map_path(PROJECT_NAME).exists()


def test_audit_artifacts_exist(facts):
    for path in (
        readiness_path(PROJECT_NAME),
        cost_path(PROJECT_NAME),
        contract_path(PROJECT_NAME),
        boundary_path(PROJECT_NAME),
        dry_run_path(PROJECT_NAME),
        cache_path(PROJECT_NAME),
        report_path(PROJECT_NAME),
    ):
        assert path.is_file(), path
        leftover = path.with_name(path.name + ".partial")
        assert not leftover.exists()


def test_readiness_payload(facts):
    assert facts["readiness"] in {
        "READY_FOR_SMALL_WIN001_CANARY",
        "BLOCKED",
    }
    assert facts["result"] in {"PASS", "PARTIAL", "FAIL"}
    contract = (REAL_AUDIT / "source_analysis_small_win001_execution_contract.json")
    assert contract.is_file()
    import json

    body = json.loads(contract.read_text(encoding="utf-8"))
    assert body["authorization_scope"] == AUTHORIZATION_SCOPE
    assert body["planner_version"] == PLANNER_VERSION_REQUIRED
    assert body["window"] == "WIN001"
    assert body["prompt"] == "window-analysis-1.1"
    assert body["max_attempts"] == 1
    assert body["continuation"] is False
    assert body["future_real_command_executed"] is False


def test_report_header(facts):
    header = report_path(PROJECT_NAME).read_text(encoding="utf-8").split("## 1.")[0]
    assert "READINESS =" in header
    assert "REAL PROVIDER CALLS =" in header
    assert "CANDIDATE PLANNER =" in header
    assert "PRODUCTION DEFAULT CHANGED =" in header
    assert "window-planner-v2.1-small" in header
    assert "THIS COMMAND WAS NOT EXECUTED." in report_path(PROJECT_NAME).read_text(
        encoding="utf-8"
    )


def test_determinism(facts):
    assert facts["sha256"]
    # write_twice_and_verify already regenerated artifacts; re-read on disk.
    from app.semantic_canary.integrity import sha256_of_file

    on_disk = {
        "readiness": sha256_of_file(readiness_path(PROJECT_NAME)),
        "cost_risk": sha256_of_file(cost_path(PROJECT_NAME)),
        "execution_contract": sha256_of_file(contract_path(PROJECT_NAME)),
        "boundary": sha256_of_file(boundary_path(PROJECT_NAME)),
        "dry_run": sha256_of_file(dry_run_path(PROJECT_NAME)),
        "cache": sha256_of_file(cache_path(PROJECT_NAME)),
        "report": sha256_of_file(report_path(PROJECT_NAME)),
    }
    assert on_disk == facts["sha256"]
