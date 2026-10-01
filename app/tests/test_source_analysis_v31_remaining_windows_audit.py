"""Écrit les artefacts A.28 isolés. N'écrase pas A.13–A.27. 0 provider réel."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v31_real_win004.constants import REPORT_NAME as A27_REPORT
from app.source_analysis_v31_remaining_windows.constants import (
    AUTHORIZATION_SCOPE,
    PHASE,
    PREFLIGHT_ARTIFACT,
    PROJECT_NAME,
    REPORT_NAME,
)
from app.source_analysis_v31_remaining_windows.facts import (
    protected_a28_historical_hashes,
)
from app.source_analysis_v31_remaining_windows.report import render_report
from app.source_analysis_v31_remaining_windows.runner import (
    RemainingWindowsResult,
    run_remaining_windows,
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_preflight_without_touching_historical(tmp_path):
    before = protected_a28_historical_hashes()
    a27 = audit_dir(PROJECT_NAME) / A27_REPORT
    before_a27 = sha256_of_file(a27) if a27.is_file() else None

    dry = run_remaining_windows(
        PROJECT_NAME,
        dry_run=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        artifact_sortie_dir=tmp_path,
        write_artifacts=True,
        tests="offline A.28",
    )
    assert dry.accepted is True
    assert dry.anthropic_post_attempts == 0
    assert (tmp_path / PROJECT_NAME / "audit" / PREFLIGHT_ARTIFACT).is_file()
    assert not (tmp_path / PROJECT_NAME / "audit" / A27_REPORT).exists()

    after = protected_a28_historical_hashes()
    after_a27 = sha256_of_file(a27) if a27.is_file() else None
    assert after == before
    assert after_a27 == before_a27
    assert PHASE == "3B.7.7A.28"


def test_report_header_shape():
    result = RemainingWindowsResult(
        mode="DRY_RUN",
        project_name=PROJECT_NAME,
        authorization_scope=AUTHORIZATION_SCOPE,
        phase_result="BLOCKED_PRECALL",
        blocked_precall=True,
    )
    report = render_report(result, tests="offline A.28")
    assert report.startswith("# PHASE 3B.7.7A.28 — REMAINING FIVE REAL LOCAL-LITE WINDOWS")
    assert "TRANSPORT =" in report
    assert "semantic-transport-v3.1-local-lite" in report
    assert "CONSOLIDATION AUTHORIZED =" in report
    assert REPORT_NAME.endswith(".md")
