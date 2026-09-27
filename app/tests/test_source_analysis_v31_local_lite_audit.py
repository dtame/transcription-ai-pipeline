"""Audit 3B.7.7A.26 — artefacts et isolation. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_v31_local_lite.constants import (
    A19_STATUS,
    A21_STATUS_UNCHANGED,
    A22_STATUS,
    A23_STATUS_UNCHANGED,
    A24_STATUS,
    A25_STATUS,
    CANONICAL_ARTIFACT,
    COMPAT_ARTIFACT,
    CONTRACT_ARTIFACT,
    DOWNSTREAM_ARTIFACT,
    FAKEAI_ARTIFACT,
    FUTURE_ARTIFACT,
    FUTURE_REAL_CALL_AUTHORIZED,
    PROJECT_NAME,
    READY_WINDOWS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    REPORT_NAME,
    SCHEMA_ARTIFACT,
)
from app.source_analysis_v31_local_lite.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_local_lite.runner import build_bundle
from app.source_analysis_v31_local_lite.writer import write_audit_bundle


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_a26_bundle_and_report(tmp_path):
    assert_offline_package()
    assert_analyzer_not_wired()
    bundle = build_bundle(
        project_name=PROJECT_NAME,
        tests="unit A.26",
        tmp_root=tmp_path / "fakeai",
    )
    header = bundle["header"]
    report = bundle["report"]
    assert header["result"] == "PASS"
    assert header["real_provider_calls"] == 0
    assert header["real_window_calls"] == 0
    assert header["selected_architecture"] == "GLOBALIZE_IDEA_SUBTYPE"
    assert header["prompt"] == "window-analysis-1.4.0"
    assert header["transport"] == "semantic-transport-v3.1-local-lite"
    assert header["local_idea_subtype"] == "REMOVED"
    assert header["canonical_idea_subtype"] == "OPTIONAL_ABSENT"
    assert header["future_real_call_authorized"] == "NO"
    assert header["real_windows_ready"] == READY_WINDOWS
    assert header["production_default"] == PLANNER_VERSION == "window-planner-v2.0"
    assert header["source_map"] == "NOT PUBLISHED"
    assert header["phase_3b"] == "INCOMPLETE"
    assert header["a19"] == A19_STATUS == "FAIL"
    assert header["a21"] == A21_STATUS_UNCHANGED == "PASS"
    assert header["a22"] == A22_STATUS == "FAIL"
    assert header["a23"] == A23_STATUS_UNCHANGED == "PASS"
    assert header["a24"] == A24_STATUS == "FAIL"
    assert header["a25"] == A25_STATUS == "PARTIAL"
    assert header["fakeai_win001"] == "PASS"
    assert header["fakeai_win004"] == "PASS"
    assert header["fakeai_all_7"] == "PASS"
    assert header["direct_consolidation"] == "PASS"
    assert header["hierarchical_consolidation"] == "PASS"
    assert header["canonical_reconstruction"] == "PASS"
    assert header["no_drop"] == "PASS"
    assert header["src_traceability"] == "PASS"
    assert header["topic_association"] == "PASS"
    assert header["relation_preservation"] == "PASS"
    assert header["historical_v3"] == "PASS"
    assert header["future_cache"] == "MISS"
    assert header["schema_identical_to_a18"] in {"YES", "NO"}
    assert "PROMPT = window-analysis-1.4.0" in report
    assert "TRANSPORT = semantic-transport-v3.1-local-lite" in report
    assert "FUTURE REAL CALL AUTHORIZED = NO" in report
    assert "NEXT ACTION = HUMAN REVIEW" in report
    written = write_audit_bundle(PROJECT_NAME, bundle, sortie_dir=tmp_path)
    assert written["contract"].name == CONTRACT_ARTIFACT
    assert written["canonical"].name == CANONICAL_ARTIFACT
    assert written["downstream"].name == DOWNSTREAM_ARTIFACT
    assert written["schema"].name == SCHEMA_ARTIFACT
    assert written["fakeai"].name == FAKEAI_ARTIFACT
    assert written["compatibility"].name == COMPAT_ARTIFACT
    assert written["future"].name == FUTURE_ARTIFACT
    assert written["report"].name == REPORT_NAME
    assert not source_map_path(PROJECT_NAME, sortie_dir=tmp_path).exists()
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert REAL_WINDOW_CALLS == 0
    assert FUTURE_REAL_CALL_AUTHORIZED is False
