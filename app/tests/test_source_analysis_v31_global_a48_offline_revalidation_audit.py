"""Écrit les artefacts A.48. N'écrase pas A.34–A.47. 0 provider."""

from __future__ import annotations

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_a47_contract_forensics.evidence import (
    a46_intent_text,
    protected_a47_historical_hashes,
)
from app.source_analysis_v31_global_a48_offline_revalidation.constants import (
    ARCHITECTURE_ARTIFACT,
    CANDIDATE_SOURCE_MAP_NAME,
    CONTRACT_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    PUBLICATION_ARTIFACT,
    RAW_IDENTITY_ARTIFACT,
    READINESS_ARTIFACT,
    REPORT_NAME,
    SEMANTIC_ARTIFACT,
    STRUCTURAL_ARTIFACT,
    TECHNICAL_ARTIFACT,
)
from app.source_analysis_v31_global_a48_offline_revalidation.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_a48_offline_revalidation.paths import candidate_path
from app.source_analysis_v31_global_a48_offline_revalidation.runner import build_bundle
from app.source_analysis_v31_global_a48_offline_revalidation.writer import write_audit_bundle


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_publishing_or_rewriting_history():
    assert_offline_package()
    assert_analyzer_not_wired()
    before = protected_a47_historical_hashes(PROJECT_NAME)
    intent_before = a46_intent_text()

    bundle = build_bundle(tests="offline A.48 unit")
    written = write_audit_bundle(PROJECT_NAME, bundle, tests="offline A.48 unit")

    expected = {
        "contract": CONTRACT_ARTIFACT,
        "raw_identity": RAW_IDENTITY_ARTIFACT,
        "technical": TECHNICAL_ARTIFACT,
        "structural": STRUCTURAL_ARTIFACT,
        "semantic": SEMANTIC_ARTIFACT,
        "publication": PUBLICATION_ARTIFACT,
        "architecture": ARCHITECTURE_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
        "report": REPORT_NAME,
        "candidate": CANDIDATE_SOURCE_MAP_NAME,
    }
    for key, name in expected.items():
        assert written[key].name == name
        assert written[key].is_file()

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.48 — A.46 OFFLINE REVALIDATION UNDER CORRECTED CONTRACT"
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert "A.46 HISTORICAL STATUS =" in report_text
    assert "FAIL unchanged" in report_text
    assert "A.47 STATUS =" in report_text
    assert "PASS" in report_text
    assert "67675 / 13317" in report_text
    assert "0.26852 USD" in report_text
    assert "0.00 USD" in report_text
    assert "global-consolidation-3.0" in report_text
    assert "global-consolidation-3.0.1" in report_text
    assert "global-consolidation-transport-3.0" in report_text
    assert "1583 / 1831" in report_text
    assert "822397b642b0e1724e29686962caab32bff63effe18f05bff26b404bad9b2a90" in report_text
    assert "GLOBAL INTENT LIMIT =" in report_text
    assert "320" in report_text
    assert "A.46 INTENT LENGTH =" in report_text
    assert "290" in report_text
    assert "286 / 286" in report_text
    assert "SOURCE MAP =" in report_text
    assert "NOT PUBLISHED" in report_text
    assert "PHASE 3B =" in report_text
    assert "INCOMPLETE" in report_text
    assert "NEXT ACTION =" in report_text
    assert "HUMAN REVIEW" in report_text
    assert "27.74%" in report_text
    assert "+0.79%" in report_text
    assert "+1.56%" in report_text
    assert PHASE == "3B.7.7A.48"
    assert not source_map_path(PROJECT_NAME).is_file()
    assert bundle["header"]["a46_historical_status"] == "FAIL"
    assert bundle["header"]["publication_eligible"] == "YES"
    assert bundle["header"]["result"] == "PASS"
    assert bundle["header"]["ready_for_controlled_source_map_publication"] == "YES"
    assert bundle["header"]["global_consolidation_core_architecture_functionally_frozen"] == "YES"
    assert written["candidate"] == candidate_path(PROJECT_NAME)
    assert a46_intent_text() == intent_before

    after = protected_a47_historical_hashes(PROJECT_NAME)
    for relative, digest in before.items():
        assert after.get(relative) == digest

    a46_report = audit_dir(PROJECT_NAME) / (
        "PHASE_3B77A46_GLOBAL_CONSOLIDATION_V30_ONE_REAL_CANARY_REPORT.md"
    )
    if a46_report.is_file():
        text = a46_report.read_text(encoding="utf-8")
        assert text.startswith("# PHASE 3B.7.7A.46")
        assert "FAIL" in text.split("## Result", 1)[1][:40]
