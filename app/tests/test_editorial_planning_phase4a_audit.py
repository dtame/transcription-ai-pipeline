"""Écrit les artefacts Phase 4A. 0 publication editorial_plan.json. 0 provider réel."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.editorial_planning.audit_writer import write_audit_bundle
from app.editorial_planning.constants import (
    AUDIT_CONTRACT,
    AUDIT_COVERAGE_POLICY,
    AUDIT_FAKEAI,
    AUDIT_INPUT_BUDGET,
    AUDIT_OUTPUT_BUDGET,
    AUDIT_PREFLIGHT,
    AUDIT_READINESS,
    AUDIT_REPORT,
    AUDIT_SCHEMA_IDENTITY,
    AUDIT_VALIDATOR,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SOURCE_MAP_SHA256,
    PUBLICATION_AUTHORIZED,
    VALIDATION_PROJECT_NAME,
)
from app.editorial_planning.guard import (
    assert_analyzer_untouched,
    assert_no_book_generator,
    assert_offline_package,
)
from app.editorial_planning.runner import build_bundle
from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_phase4a_audit_artifacts_without_publishing_plan():
    assert_offline_package()
    assert_analyzer_untouched()
    assert_no_book_generator()
    assert PUBLICATION_AUTHORIZED is False

    published = source_map_path(VALIDATION_PROJECT_NAME)
    assert published.is_file()

    bundle = build_bundle(
        tests="offline Phase 4A unit",
        test_delta={"new_failure_count": 0, "failed": 0},
    )
    written = write_audit_bundle(
        VALIDATION_PROJECT_NAME,
        bundle,
        tests="offline Phase 4A unit",
    )

    header = bundle["header"]
    assert header["source_map_sha256"] == EXPECTED_SOURCE_MAP_SHA256
    assert header["real_provider_calls"] == 0
    assert header["editorial_plan_json"] == "NOT PUBLISHED"
    assert header["ready_for_real_editorial_planner_call"] == "NO"
    assert bundle["preflight"]["hash_match"] is True
    assert bundle["full_scale"]["assigned"] == EXPECTED_IDEA_COUNT
    assert bundle["full_scale"]["validation"]["status"] != "FAIL"
    assert bundle["input_budget"]["one_global_call_feasible"] is True
    assert bundle["publication"]["path_absent"] is True
    assert not (published.parent / "editorial_plan.json").is_file()

    audit = audit_dir(VALIDATION_PROJECT_NAME)
    for name in (
        AUDIT_INPUT_BUDGET,
        AUDIT_OUTPUT_BUDGET,
        AUDIT_CONTRACT,
        AUDIT_SCHEMA_IDENTITY,
        AUDIT_COVERAGE_POLICY,
        AUDIT_VALIDATOR,
        AUDIT_FAKEAI,
        AUDIT_PREFLIGHT,
        AUDIT_READINESS,
        AUDIT_REPORT,
    ):
        path = audit / name
        assert path.is_file(), path
        assert written[list(written)[0]].parent == audit

    report = (audit / AUDIT_REPORT).read_text(encoding="utf-8")
    assert report.startswith(
        "# PHASE 4A — EDITORIAL PLANNER ARCHITECTURE AND OFFLINE FOUNDATION"
    )
    assert "REAL PROVIDER CALLS = 0" in report
    assert "editorial_plan.json = NOT PUBLISHED" in report
    assert "READY_FOR_REAL_EDITORIAL_PLANNER_CALL = NO" in report
    assert EXPECTED_SOURCE_MAP_SHA256 in report

    preflight = json.loads((audit / AUDIT_PREFLIGHT).read_text(encoding="utf-8"))
    assert preflight["sha256"] == EXPECTED_SOURCE_MAP_SHA256

    readiness = json.loads((audit / AUDIT_READINESS).read_text(encoding="utf-8"))
    assert readiness["READY_FOR_REAL_EDITORIAL_PLANNER_CALL"] is False
    assert header["result"] == "PASS"
    assert Path(bundle["preflight"]["path"]).name == "source_map.json"
