"""Audit 3B.7.7A.26.1 — artefacts et isolation. 0 provider."""

from __future__ import annotations

import pytest

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_schema_boundary.constants import (
    A19_STATUS,
    A21_STATUS_UNCHANGED,
    A22_STATUS,
    A23_STATUS_UNCHANGED,
    A24_STATUS,
    A25_STATUS,
    A26_STATUS,
    BOUNDARY_ARTIFACT,
    MISMATCH_CLASSIFICATION,
    MIXED_ARTIFACT,
    PROJECT_NAME,
    READY_WINDOWS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    REPORT_NAME,
    ROUNDTRIP_ARTIFACT,
)
from app.source_analysis_v31_schema_boundary.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
    assert_schema_py_untouched,
)
from app.source_analysis_v31_schema_boundary.runner import build_bundle
from app.source_analysis_v31_schema_boundary.writer import write_audit_bundle


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_a261_bundle_and_report(tmp_path):
    assert_offline_package()
    assert_analyzer_not_wired()
    assert_schema_py_untouched()
    bundle = build_bundle(
        project_name=PROJECT_NAME,
        tests="unit A.26.1",
        tmp_root=tmp_path / "fakeai",
        sortie_dir=tmp_path,
    )
    header = bundle["header"]
    report = bundle["report"]
    assert header["result"] == "PASS"
    assert header["real_provider_calls"] == 0
    assert header["real_window_calls"] == 0
    assert header["a26_status"] == "PASS unchanged"
    assert header["schema_py_used_by_local_lite"] == "NO"
    assert header["schema_py_used_by_global_consolidation"] == "NO"
    assert header["schema_py_used_by_publication"] == "NO"
    assert header["importance_to_kind_contamination"] == "NO"
    assert header["local_lite_roundtrip"] == "PASS"
    assert header["mixed_v3_v31"] == "PASS"
    assert header["mismatch_classification"] == MISMATCH_CLASSIFICATION
    assert header["blocks_a27"] == "NO"
    assert header["production_changed"] == "NO"
    assert header["source_map"] == "NOT PUBLISHED"
    assert header["real_windows_ready"] == READY_WINDOWS
    assert header["phase_3b"] == "INCOMPLETE"
    assert header["a19"] == A19_STATUS == "FAIL"
    assert header["a21"] == A21_STATUS_UNCHANGED == "PASS"
    assert header["a22"] == A22_STATUS == "FAIL"
    assert header["a23"] == A23_STATUS_UNCHANGED == "PASS"
    assert header["a24"] == A24_STATUS == "FAIL"
    assert header["a25"] == A25_STATUS == "PARTIAL"
    assert header["a26"] == A26_STATUS == "PASS"
    assert "EXPECTED_STAGE_SPECIFIC_SCHEMA" in report
    assert "schema.py USED BY LOCAL-LITE = NO" in report
    assert "IMPORTANCE→KIND CONTAMINATION = NO" in report
    assert "NEXT ACTION = HUMAN REVIEW" in report
    written = write_audit_bundle(PROJECT_NAME, bundle, sortie_dir=tmp_path)
    assert written["boundary"].name == BOUNDARY_ARTIFACT
    assert written["roundtrip"].name == ROUNDTRIP_ARTIFACT
    assert written["mixed"].name == MIXED_ARTIFACT
    assert written["report"].name == REPORT_NAME
    assert not source_map_path(PROJECT_NAME, sortie_dir=tmp_path).exists()
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert REAL_WINDOW_CALLS == 0
