"""Écrit les artefacts A.32. N'écrase pas A.19–A.31. 0 provider."""

from __future__ import annotations

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_final_three.constants import REPORT_NAME as A31_REPORT
from app.source_analysis_v31_src_typo_forensics.constants import (
    CANONICAL_ARTIFACT,
    COUNTERFACTUAL_ARTIFACT,
    DECISION_ARTIFACT,
    HISTORY_ARTIFACT,
    OPTIONS_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REPORT_NAME,
    ROOT_FAILURE_ARTIFACT,
    SEMANTIC_ARTIFACT,
    WIN007_PROMOTION_AUTHORIZED,
    WIN007_RETRY_AUTHORIZED,
)
from app.source_analysis_v31_src_typo_forensics.evidence import (
    protected_a32_historical_hashes,
    win007_raw_path,
)
from app.source_analysis_v31_src_typo_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_src_typo_forensics.runner import build_bundle
from app.source_analysis_v31_src_typo_forensics.writer import write_audit_bundle


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_history():
    assert_offline_package()
    assert_analyzer_not_wired()
    a31 = audit_dir(PROJECT_NAME) / A31_REPORT
    raw = win007_raw_path(PROJECT_NAME)
    before_report = sha256_of_file(a31) if a31.is_file() else None
    before_raw = sha256_of_file(raw)
    before_protected = protected_a32_historical_hashes()

    bundle = build_bundle(tests="offline A.32")
    written = write_audit_bundle(PROJECT_NAME, bundle, tests="offline A.32")

    assert written["root"].name == ROOT_FAILURE_ARTIFACT
    assert written["history"].name == HISTORY_ARTIFACT
    assert written["options"].name == OPTIONS_ARTIFACT
    assert written["counterfactual"].name == COUNTERFACTUAL_ARTIFACT
    assert written["decision"].name == DECISION_ARTIFACT
    assert written["report"].name == REPORT_NAME
    assert SEMANTIC_ARTIFACT in {path.name for path in written.values()}
    assert CANONICAL_ARTIFACT in {path.name for path in written.values()}

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.32 — WIN007 STRICT SRC TYPO FORENSICS"
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert "\n0\n" in report_text
    assert "REAL WINDOW CALLS =" in report_text
    assert "A.31 STATUS =" in report_text
    assert "FAIL unchanged" in report_text
    assert "READY =" in report_text
    assert "6 / 7" in report_text
    assert "WIN007 =" in report_text
    assert "NOT READY" in report_text
    assert "SRec007337" in report_text
    assert "SRC007337" in report_text
    assert "SOURCE MAP =" in report_text
    assert "NOT PUBLISHED" in report_text
    assert "NEXT ACTION =" in report_text
    assert "HUMAN REVIEW" in report_text
    assert bundle["header"]["result"] == "PASS"
    assert bundle["replay"]["reproduced"] is True
    assert bundle["counterfactual"]["technical"] == "PASS"
    assert bundle["header"]["win007"] == "NOT READY"
    assert WIN007_PROMOTION_AUTHORIZED is False
    assert WIN007_RETRY_AUTHORIZED is False
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert not source_map_path(PROJECT_NAME).is_file()

    assert sha256_of_file(raw) == before_raw
    if before_report is not None:
        assert sha256_of_file(a31) == before_report
    after_protected = protected_a32_historical_hashes()
    for key, digest in before_protected.items():
        assert after_protected.get(key) == digest

    decision = bundle["decision"]
    assert decision["selected_policy"] in {
        "KEEP_STRICT_AND_RETRY_WIN007",
        "IMPLEMENT_NARROW_SRC_CANONICALIZATION_THEN_REVALIDATE_SAVED_WIN007",
        "REDESIGN_SRC_REFERENCE_TRANSPORT_BEFORE_CONTINUING",
        "HUMAN_SEMANTIC_REVIEW_REQUIRED",
        "OTHER_EXPLICITLY_JUSTIFIED",
    }
    assert decision["implemented"] is False
    assert decision["win007_promoted"] is False
    assert PHASE == "3B.7.7A.32"
