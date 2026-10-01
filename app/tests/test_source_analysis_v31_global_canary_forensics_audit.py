"""Écrit les artefacts A.36. N'écrase pas A.19–A.35. 0 provider."""

from __future__ import annotations

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_canary_forensics.constants import (
    COUNTERFACTUAL_ARTIFACT,
    DISPOSITION_ARTIFACT,
    DROP_CONTRACT_ARTIFACT,
    FIXTURE_REVIEW_ARTIFACT,
    FORENSICS_ARTIFACT,
    NEXT_FIXTURE_ARTIFACT,
    NEXT_SCHEMA_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    READINESS_ARTIFACT,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    REAL_CONSOLIDATION_CALLS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REDESIGN_ARTIFACT,
    REPETITION_ARTIFACT,
    REPORT_NAME,
)
from app.source_analysis_v31_global_canary_forensics.evidence import (
    a35_report_path,
    protected_a36_historical_hashes,
)
from app.source_analysis_v31_global_canary_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_canary_forensics.runner import build_bundle
from app.source_analysis_v31_global_canary_forensics.writer import write_audit_bundle
from app.source_analysis_v31_global_grammar_canary.constants import REPORT_NAME as A35_REPORT
from app.source_analysis_v31_global_preflight.constants import REPORT_NAME as A34_REPORT


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_history():
    assert_offline_package()
    assert_analyzer_not_wired()
    a34 = audit_dir(PROJECT_NAME) / A34_REPORT
    a35 = a35_report_path()
    before_a34 = sha256_of_file(a34) if a34.is_file() else None
    before_a35 = sha256_of_file(a35) if a35.is_file() else None
    before_protected = protected_a36_historical_hashes()

    bundle = build_bundle(tests="offline A.36 unit")
    written = write_audit_bundle(PROJECT_NAME, bundle, tests="offline A.36 unit")

    expected = {
        "forensics": FORENSICS_ARTIFACT,
        "dispositions": DISPOSITION_ARTIFACT,
        "drop_contract": DROP_CONTRACT_ARTIFACT,
        "repetition": REPETITION_ARTIFACT,
        "fixture_review": FIXTURE_REVIEW_ARTIFACT,
        "redesign": REDESIGN_ARTIFACT,
        "schema": NEXT_SCHEMA_ARTIFACT,
        "next_fixture": NEXT_FIXTURE_ARTIFACT,
        "counterfactual": COUNTERFACTUAL_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
        "report": REPORT_NAME,
    }
    for key, name in expected.items():
        assert written[key].name == name
        assert written[key].is_file()

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.36 — GLOBAL CONSOLIDATION CANARY FORENSICS"
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert "A.35 STATUS =" in report_text
    assert "FAIL unchanged" in report_text
    assert "req_011CfW2QDYYiMNWoMSoeucx1" in report_text
    assert "CANONICAL DROP TOKEN =" in report_text
    assert "non_substantive_fragment" in report_text
    assert "OLD TRANSPORT =" in report_text
    assert "global-consolidation-transport-1.0" in report_text
    assert "NEXT TRANSPORT =" in report_text
    assert "global-consolidation-transport-1.1" in report_text
    assert "OLD SCHEMA RAW / ADAPTED =" in report_text
    assert "1040 / 1195" in report_text
    assert "claude-sonnet-5" in report_text
    assert "THINKING =" in report_text
    assert "disabled" in report_text
    assert "PRODUCTION MAX OUTPUT =" in report_text
    assert "32000" in report_text
    assert "ONE GLOBAL CALL ARCHITECTURE =" in report_text
    assert "PRESERVED" in report_text
    assert "RELATION_QUALITY_TECHNICAL_DEBT =" in report_text
    assert "SOURCE MAP =" in report_text
    assert "NOT PUBLISHED" in report_text
    assert "PHASE 3B =" in report_text
    assert "INCOMPLETE" in report_text
    assert "NEXT ACTION =" in report_text
    assert "HUMAN REVIEW" in report_text
    assert "READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY" not in report_text.split(
        "READINESS ="
    )[0] or READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO"
    assert PHASE == "3B.7.7A.36"
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert REAL_CONSOLIDATION_CALLS == 0
    assert not source_map_path(PROJECT_NAME).is_file()
    assert bundle["header"]["a35_status"] == "FAIL"
    assert bundle["fakeai"]["ok"] is True
    assert bundle["readiness"]["READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY"] == "NO"

    if before_a34 is not None:
        assert sha256_of_file(a34) == before_a34
    if before_a35 is not None:
        assert sha256_of_file(a35) == before_a35
        assert a35.name == A35_REPORT
    after_protected = protected_a36_historical_hashes()
    for key, digest in before_protected.items():
        assert after_protected.get(key) == digest
