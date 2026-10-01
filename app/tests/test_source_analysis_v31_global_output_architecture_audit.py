"""Écrit les artefacts A.39. N'écrase pas A.34–A.38. 0 provider."""

from __future__ import annotations

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_output_architecture.constants import (
    BREAKDOWN_ARTIFACT,
    BUDGET_ARTIFACT,
    FORENSICS_ARTIFACT,
    MEMBERSHIP_ARTIFACT,
    NEXT_SCHEMA_ARTIFACT,
    OPTIONS_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    READINESS_ARTIFACT,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    RELATION_DECISION_ARTIFACT,
    REPORT_NAME,
    SELECTED_ARTIFACT,
    STRESS_ARTIFACT,
)
from app.source_analysis_v31_global_output_architecture.evidence import (
    protected_a39_historical_hashes,
)
from app.source_analysis_v31_global_output_architecture.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_output_architecture.paths import a38_report_path
from app.source_analysis_v31_global_output_architecture.runner import build_bundle
from app.source_analysis_v31_global_output_architecture.writer import write_audit_bundle
from app.source_analysis_v31_global_real_consolidation.constants import (
    REPORT_NAME as A38_REPORT,
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_history():
    assert_offline_package()
    assert_analyzer_not_wired()
    a38 = a38_report_path()
    before_a38 = sha256_of_file(a38) if a38.is_file() else None
    before_protected = protected_a39_historical_hashes()

    bundle = build_bundle(tests="offline A.39 unit")
    written = write_audit_bundle(PROJECT_NAME, bundle, tests="offline A.39 unit")

    expected = {
        "forensics": FORENSICS_ARTIFACT,
        "breakdown": BREAKDOWN_ARTIFACT,
        "options": OPTIONS_ARTIFACT,
        "selected": SELECTED_ARTIFACT,
        "membership": MEMBERSHIP_ARTIFACT,
        "relation": RELATION_DECISION_ARTIFACT,
        "budget": BUDGET_ARTIFACT,
        "stress": STRESS_ARTIFACT,
        "schema": NEXT_SCHEMA_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
        "report": REPORT_NAME,
    }
    for key, name in expected.items():
        assert written[key].name == name
        assert written[key].is_file()

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.39 — GLOBAL CONSOLIDATION OUTPUT ARCHITECTURE REDESIGN"
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert "A.38 STATUS =" in report_text
    assert "FAIL unchanged" in report_text
    assert "req_011CfWwT6tCwU9aX9cZwvGAW" in report_text
    assert "OUTPUT_TOKEN_BUDGET_EXHAUSTED" in report_text
    assert "INVERSE IDEA MEMBERSHIP =" in report_text
    assert "global-consolidation-transport-2.0" in report_text
    assert "global-consolidation-2.0" in report_text
    assert "RELATIONS" in report_text or "DEFERRED" in report_text
    assert "claude-sonnet-5" in report_text
    assert "THINKING =" in report_text
    assert "disabled" in report_text
    assert "SOURCE MAP =" in report_text
    assert "NOT PUBLISHED" in report_text
    assert "PHASE 3B =" in report_text
    assert "INCOMPLETE" in report_text
    assert bundle["header"]["result"] == "PASS"
    assert bundle["readiness"]["READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY"] == "NO"
    assert READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO"
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert PHASE == "3B.7.7A.39"
    assert not source_map_path(PROJECT_NAME).is_file()

    if before_a38 is not None:
        assert sha256_of_file(a38) == before_a38
    after_protected = protected_a39_historical_hashes()
    for rel, digest in before_protected.items():
        assert after_protected.get(rel) == digest
    assert A38_REPORT in str(a38)
    assert audit_dir(PROJECT_NAME).is_dir()
