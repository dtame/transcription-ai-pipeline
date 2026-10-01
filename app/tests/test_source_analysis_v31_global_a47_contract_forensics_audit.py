"""Écrit les artefacts A.47. N'écrase pas A.34–A.46. 0 provider."""

from __future__ import annotations

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_a47_contract_forensics.constants import (
    CANDIDATE_SEMANTIC_ARTIFACT,
    CONTRACT_MATRIX_ARTIFACT,
    COUNTERFACTUAL_ARTIFACT,
    EDITORIAL_SCAN_ARTIFACT,
    INTENT_CONTRACT_ARTIFACT,
    INTENT_SEMANTIC_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    READINESS_ARTIFACT,
    READY_FOR_A46_OFFLINE_REVALIDATION,
    REPORT_NAME,
)
from app.source_analysis_v31_global_a47_contract_forensics.evidence import (
    protected_a47_historical_hashes,
)
from app.source_analysis_v31_global_a47_contract_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_a47_contract_forensics.runner import build_bundle
from app.source_analysis_v31_global_a47_contract_forensics.writer import write_audit_bundle


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_history():
    assert_offline_package()
    assert_analyzer_not_wired()
    before = protected_a47_historical_hashes(PROJECT_NAME)

    bundle = build_bundle(tests="offline A.47 unit")
    written = write_audit_bundle(PROJECT_NAME, bundle, tests="offline A.47 unit")

    expected = {
        "intent_contract": INTENT_CONTRACT_ARTIFACT,
        "intent_semantics": INTENT_SEMANTIC_ARTIFACT,
        "matrix": CONTRACT_MATRIX_ARTIFACT,
        "editorial": EDITORIAL_SCAN_ARTIFACT,
        "counterfactual": COUNTERFACTUAL_ARTIFACT,
        "candidate_review": CANDIDATE_SEMANTIC_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
        "report": REPORT_NAME,
    }
    for key, name in expected.items():
        assert written[key].name == name
        assert written[key].is_file()

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.47 — A.46 CONTRACT FAILURE FORENSICS"
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert "A.46 HISTORICAL STATUS =" in report_text
    assert "FAIL unchanged" in report_text
    assert "200 / end_turn / 0" in report_text
    assert "67675 / 13317" in report_text
    assert "0.26852 USD" in report_text
    assert "286 / 286" in report_text
    assert "286 / 0 / 0" in report_text
    assert "MULTI_LAYER_CONTRACT_MISMATCH" in report_text
    assert "SEMANTICALLY_VALID_BUT_OVER_LIMIT" in report_text
    assert "SELECTED INTENT LIMIT =" in report_text
    assert "320" in report_text
    assert "PROMPT CHANGE REQUIRED =" in report_text
    assert "global-consolidation-3.0.1" in report_text
    assert "global-consolidation-transport-3.0" in report_text
    assert "CAN_A46_SAVED_RESPONSE_BE_VALIDATED_UNDER_CORRECTED_CONTRACT_WITHOUT_REPAIR =" in report_text
    assert "FALSE_POSITIVE_LEXICAL_SCAN" in report_text
    assert "27.74%" in report_text
    assert "+0.79%" in report_text
    assert "+1.56%" in report_text
    assert "READY_FOR_A46_OFFLINE_REVALIDATION =" in report_text
    assert "SOURCE MAP =" in report_text
    assert "NOT PUBLISHED" in report_text
    assert "PHASE 3B =" in report_text
    assert "INCOMPLETE" in report_text
    assert "NEXT ACTION =" in report_text
    assert "HUMAN REVIEW" in report_text
    assert PHASE == "3B.7.7A.47"
    assert READY_FOR_A46_OFFLINE_REVALIDATION == "YES"
    assert not source_map_path(PROJECT_NAME).is_file()
    assert bundle["header"]["a46_historical_status"] == "FAIL"
    assert bundle["header"]["result"] in {"PASS", "PARTIAL"}

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
