"""Écrit les artefacts A.31 isolés. N'écrase pas A.13–A.30. 0 provider réel."""

from __future__ import annotations

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v31_kind_specific_limits.constants import (
    REPORT_NAME as A30_REPORT,
)
from app.source_analysis_v31_final_three.constants import (
    AUTHORIZATION_SCOPE,
    PHASE,
    PREFLIGHT_ARTIFACT,
    PROJECT_NAME,
    REPORT_NAME,
)
from app.source_analysis_v31_final_three.facts import protected_a31_historical_hashes
from app.source_analysis_v31_final_three.report import render_report
from app.source_analysis_v31_final_three.runner import FinalThreeResult, run_final_three


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_preflight_without_touching_historical(tmp_path):
    before = protected_a31_historical_hashes()
    a30 = audit_dir(PROJECT_NAME) / A30_REPORT
    before_a30 = sha256_of_file(a30) if a30.is_file() else None

    dry = run_final_three(
        PROJECT_NAME,
        dry_run=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
        tests="offline A.31",
    )
    assert dry.accepted is True
    assert dry.anthropic_post_attempts == 0
    assert (tmp_path / PROJECT_NAME / "audit" / PREFLIGHT_ARTIFACT).is_file()
    assert not (tmp_path / PROJECT_NAME / "audit" / A30_REPORT).exists()
    assert not (
        tmp_path / PROJECT_NAME / "audit" / "source_analysis_ready_windows_after_a30.json"
    ).exists()

    after = protected_a31_historical_hashes()
    after_a30 = sha256_of_file(a30) if a30.is_file() else None
    assert after == before
    assert after_a30 == before_a30
    assert PHASE == "3B.7.7A.31"


def test_report_header_shape():
    result = FinalThreeResult(
        mode="DRY_RUN",
        project_name=PROJECT_NAME,
        authorization_scope=AUTHORIZATION_SCOPE,
        phase_result="BLOCKED_PRECALL",
        blocked_precall=True,
    )
    report = render_report(result, tests="offline A.31")
    assert report.startswith("# PHASE 3B.7.7A.31 — FINAL THREE REAL LOCAL-LITE WINDOWS")
    assert "TRANSPORT =" in report
    assert "semantic-transport-v3.1-local-lite" in report
    assert "GRANULARITY =" in report
    assert "window-granularity-1.2-kind-specific" in report
    assert "LOCAL_EXTRACTION_FREEZE_CANDIDATE =" in report
    assert "CONSOLIDATION AUTHORIZED =" in report
    assert "PHASE 3B =" in report
    assert REPORT_NAME.endswith(".md")
