"""Écrit les artefacts A.34. N'écrase pas A.19–A.33. 0 provider."""

from __future__ import annotations

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_preflight.constants import (
    BOUNDARY_ARTIFACT,
    BUDGET_ARTIFACT,
    CONTRACT_ARTIFACT,
    DUPLICATE_ARTIFACT,
    FREEZE_ARTIFACT,
    INVENTORY_ARTIFACT,
    NORMALIZED_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    READINESS_ARTIFACT,
    REAL_CONSOLIDATION_CALLS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    RELATION_POLICY_ARTIFACT,
    REPORT_NAME,
    REVIEW_PLAN_ARTIFACT,
    TEST_DELTA_ARTIFACT,
    TRANSPORT_SCHEMA_ARTIFACT,
    VALIDATOR_ARTIFACT,
    WIN007_CANONICAL_SRC,
    WIN007_RAW_SRC,
)
from app.source_analysis_v31_global_preflight.evidence import (
    protected_a34_historical_hashes,
)
from app.source_analysis_v31_global_preflight.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_preflight.runner import build_bundle
from app.source_analysis_v31_global_preflight.writer import write_audit_bundle
from app.source_analysis_v31_src_canonicalization.constants import REPORT_NAME as A33_REPORT


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_history():
    assert_offline_package()
    assert_analyzer_not_wired()
    a33 = audit_dir(PROJECT_NAME) / A33_REPORT
    before_a33 = sha256_of_file(a33) if a33.is_file() else None
    before_protected = protected_a34_historical_hashes()

    bundle = build_bundle(tests="offline A.34")
    written = write_audit_bundle(PROJECT_NAME, bundle, tests="offline A.34")

    expected = {
        "normalized": NORMALIZED_ARTIFACT,
        "inventory": INVENTORY_ARTIFACT,
        "boundary": BOUNDARY_ARTIFACT,
        "duplicates": DUPLICATE_ARTIFACT,
        "relation_policy": RELATION_POLICY_ARTIFACT,
        "contract": CONTRACT_ARTIFACT,
        "schema": TRANSPORT_SCHEMA_ARTIFACT,
        "budget": BUDGET_ARTIFACT,
        "validator": VALIDATOR_ARTIFACT,
        "review": REVIEW_PLAN_ARTIFACT,
        "freeze": FREEZE_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
        "test_delta": TEST_DELTA_ARTIFACT,
        "report": REPORT_NAME,
    }
    for key, name in expected.items():
        assert written[key].name == name
        assert written[key].is_file()

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.34 — GLOBAL CONSOLIDATION OFFLINE PREFLIGHT"
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert "\n0\n" in report_text
    assert "REAL WINDOW CALLS =" in report_text
    assert "REAL CONSOLIDATION CALLS =" in report_text
    assert "READY WINDOWS =" in report_text
    assert "7 / 7" in report_text
    assert "LOCAL EXTRACTION FREEZE CANDIDATE =" in report_text
    assert "LOCAL EXTRACTION FUNCTIONALLY FROZEN =" in report_text
    assert "NORMALIZED GLOBAL INPUT =" in report_text
    assert "RELATION_QUALITY_TECHNICAL_DEBT =" in report_text
    assert "GLOBAL GRAMMAR CANARY REQUIRED =" in report_text
    assert "SOURCE MAP =" in report_text
    assert "NOT PUBLISHED" in report_text
    assert "GLOBAL CONSOLIDATION =" in report_text
    assert "NOT EXECUTED" in report_text
    assert "PHASE 3B =" in report_text
    assert "INCOMPLETE" in report_text
    assert "NEXT ACTION =" in report_text
    assert "HUMAN REVIEW" in report_text
    assert WIN007_RAW_SRC in report_text or WIN007_CANONICAL_SRC in report_text
    assert "window-planner-v2.1-small" in report_text
    assert "window-analysis-1.4.0" in report_text
    assert "semantic-transport-v3.1-local-lite" in report_text
    assert "A.28 =" in report_text
    assert "A.33 =" in report_text

    header = bundle["header"]
    assert header["real_provider_calls"] == 0
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert REAL_CONSOLIDATION_CALLS == 0
    assert not source_map_path(PROJECT_NAME).is_file()
    assert PHASE == "3B.7.7A.34"
    assert header["ready_windows"] == "7 / 7"
    assert header["result"] in {"PASS", "FAIL"}
    assert bundle["gates"]["all_ready"] is True
    assert bundle["normalized"] is not None
    assert bundle["inventory"]["totals"]["IDEA"] >= 1
    assert bundle["boundary"]["ownership_pass"] is True
    assert bundle["relation_policy"]["selected_option"] == "C"
    assert bundle["readiness"]["real_consolidation_executed"] is False
    assert bundle["readiness"]["grammar_canary_run"] is False

    if before_a33 is not None:
        assert sha256_of_file(a33) == before_a33
    after_protected = protected_a34_historical_hashes()
    for key, digest in before_protected.items():
        assert after_protected.get(key) == digest
