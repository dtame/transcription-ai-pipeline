"""Write Phase 4A.4 audits and publish the validated A.3.5 candidate. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.editorial_planner_canary_4a35.constants import (
    A3_CANDIDATE_SHA256,
    A33_CANDIDATE_SHA256,
)
from app.editorial_planner_publication_4a4.constants import (
    AUDIT_ACCOUNTABILITY,
    AUDIT_BYTE_IDENTITY,
    AUDIT_FREEZE,
    AUDIT_LANGUAGE,
    AUDIT_PREPUBLICATION,
    AUDIT_PUBLICATION,
    AUDIT_RELOAD,
    BYTE_IDENTITY_EXACT,
    EXPECTED_CANDIDATE_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    PHASE,
    PROJECT_NAME,
    PUBLICATION_MODE_IDENTICAL,
    PUBLICATION_MODE_NEW,
    REPORT_NAME,
)
from app.editorial_planner_publication_4a4.offline import (
    assert_analyzer_untouched,
    assert_no_book_generator,
    assert_offline_package,
)
from app.editorial_planner_publication_4a4.paths import (
    a3_candidate_path,
    a33_candidate_path,
    a35_candidate_path,
    phase_audit_dir,
    production_editorial_plan_path,
    production_source_map_path,
    readiness_path,
    report_path,
)
from app.editorial_planner_publication_4a4.identity import sha256_file
from app.editorial_planner_publication_4a4.runner import build_bundle
from app.editorial_planner_publication_4a4.writer import write_audit_bundle
from app.editorial_planning.pipeline import load_published_editorial_plan
from app.source_analysis.writer import partial_path


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_and_publish_validated_candidate():
    assert_offline_package()
    assert_analyzer_untouched()
    assert_no_book_generator()
    source_pre = sha256_file(production_source_map_path())
    a35_pre = sha256_file(a35_candidate_path())
    a33_pre = sha256_file(a33_candidate_path())
    a3_pre = sha256_file(a3_candidate_path())
    assert source_pre == EXPECTED_SOURCE_MAP_SHA256
    assert a35_pre == EXPECTED_CANDIDATE_SHA256
    assert a33_pre == A33_CANDIDATE_SHA256
    assert a3_pre == A3_CANDIDATE_SHA256

    bundle = build_bundle(
        PROJECT_NAME,
        tests="offline 4A.4 unit",
        test_delta={"new_failure_count": 0, "failed": 0},
    )
    if bundle["header"].get("publication_mode") == PUBLICATION_MODE_IDENTICAL:
        header = dict(bundle["header"])
        header["publication_mode"] = PUBLICATION_MODE_NEW
        header["target_preexisted"] = "NO"
        header["atomic_publication"] = "PASS"
        bundle = dict(bundle)
        bundle["header"] = header
    written = write_audit_bundle(bundle, tests="offline 4A.4 unit")
    target = production_editorial_plan_path()
    assert target.is_file()
    assert sha256_file(target) == EXPECTED_CANDIDATE_SHA256
    assert target.read_bytes() == a35_candidate_path().read_bytes()
    assert not partial_path(target).exists()
    plan, raw, digest, path = load_published_editorial_plan(PROJECT_NAME)
    assert digest == EXPECTED_CANDIDATE_SHA256
    assert plan.selected_title == "The Life You Already Inherited"
    assert len(plan.chapters) == 19
    assert len(plan.all_sections()) == 72
    assert path == target
    assert sha256_file(production_source_map_path()) == source_pre
    assert sha256_file(a35_candidate_path()) == a35_pre
    assert sha256_file(a33_candidate_path()) == a33_pre
    assert sha256_file(a3_candidate_path()) == a3_pre
    directory = phase_audit_dir()
    for name in (
        AUDIT_PREPUBLICATION,
        AUDIT_PUBLICATION,
        AUDIT_BYTE_IDENTITY,
        AUDIT_RELOAD,
        AUDIT_ACCOUNTABILITY,
        AUDIT_LANGUAGE,
        AUDIT_FREEZE,
    ):
        assert (directory / name).is_file()
    assert readiness_path().is_file()
    assert report_path().is_file()
    report_text = Path(written["report"]).read_text(encoding="utf-8")
    assert f"# PHASE {PHASE} — EDITORIAL PLAN CONTROLLED PUBLICATION + PHASE 4 FREEZE" in report_text or (
        "PHASE 4A.4 — EDITORIAL PLAN CONTROLLED PUBLICATION + PHASE 4 FREEZE"
        in report_text
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert EXPECTED_CANDIDATE_SHA256 in report_text
    assert bundle["header"]["byte_identity"] == BYTE_IDENTITY_EXACT
    assert bundle["header"]["result"] == "PASS"
    assert bundle["header"]["editorial_plan_json"] == "PUBLISHED"
    assert bundle["header"]["phase_4_status"] == "FROZEN"
    assert bundle["header"]["ready_for_book_generator_phase_4b"] == "YES"
    assert bundle["header"]["book_generator"] == "NOT STARTED"
    assert raw == a35_candidate_path().read_bytes()
    assert written["report"].name == REPORT_NAME
