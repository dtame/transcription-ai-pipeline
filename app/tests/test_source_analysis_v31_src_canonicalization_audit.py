"""Écrit les artefacts A.33. N'écrase pas A.19–A.32. 0 provider."""

from __future__ import annotations

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_src_canonicalization.constants import (
    INVENTORY_ARTIFACT,
    PHASE,
    POLICY_ARTIFACT,
    PROJECT_NAME,
    PROMOTION_ARTIFACT,
    PROVENANCE_ARTIFACT,
    READY_ARTIFACT,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REPLAY_ARTIFACT,
    REPORT_NAME,
    SCHEMA_ARTIFACT,
    SRC_POLICY_NEW,
    SRC_POLICY_OLD,
    TEST_DELTA_ARTIFACT,
    WIN007_NEW_PROVIDER_CALL,
    WIN007_PROMOTION_LABEL,
    WIN007_REQUEST_ID,
)
from app.source_analysis_v31_src_canonicalization.evidence import (
    protected_a33_historical_hashes,
)
from app.source_analysis_v31_src_canonicalization.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_src_canonicalization.runner import build_bundle
from app.source_analysis_v31_src_canonicalization.writer import write_audit_bundle
from app.source_analysis_v31_src_typo_forensics.constants import REPORT_NAME as A32_REPORT
from app.source_analysis_v31_src_typo_forensics.evidence import win007_raw_path
from app.source_analysis_v31_final_three.constants import REPORT_NAME as A31_REPORT


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_history():
    assert_offline_package()
    assert_analyzer_not_wired()
    a31 = audit_dir(PROJECT_NAME) / A31_REPORT
    a32 = audit_dir(PROJECT_NAME) / A32_REPORT
    raw = win007_raw_path(PROJECT_NAME)
    before_a31 = sha256_of_file(a31) if a31.is_file() else None
    before_a32 = sha256_of_file(a32) if a32.is_file() else None
    before_raw = sha256_of_file(raw)
    before_protected = protected_a33_historical_hashes()

    bundle = build_bundle(tests="offline A.33")
    written = write_audit_bundle(PROJECT_NAME, bundle, tests="offline A.33")

    assert written["policy"].name == POLICY_ARTIFACT
    assert written["replay"].name == REPLAY_ARTIFACT
    assert written["provenance"].name == PROVENANCE_ARTIFACT
    assert written["promotion"].name == PROMOTION_ARTIFACT
    assert written["ready"].name == READY_ARTIFACT
    assert written["schema"].name == SCHEMA_ARTIFACT
    assert written["test_delta"].name == TEST_DELTA_ARTIFACT
    assert written["report"].name == REPORT_NAME
    if bundle["header"].get("win007_promoted"):
        assert INVENTORY_ARTIFACT in {path.name for path in written.values()}

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.33 — SRC CANONICALIZATION + SAVED WIN007 REVALIDATION"
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert "\n0\n" in report_text
    assert "REAL WINDOW CALLS =" in report_text
    assert "A.31 HISTORICAL STATUS =" in report_text
    assert "FAIL unchanged" in report_text
    assert "A.32 STATUS =" in report_text
    assert "SRC POLICY OLD =" in report_text
    assert SRC_POLICY_OLD in report_text
    assert "SRC POLICY NEW =" in report_text
    assert SRC_POLICY_NEW in report_text
    assert "RAW WIN007 SRC TOKENS =" in report_text
    assert "290" in report_text
    assert "RAW EXACT SRC =" in report_text
    assert "289" in report_text
    assert "RAW MALFORMED SRC =" in report_text
    assert "SRec007337" in report_text
    assert "SRC007337" in report_text
    assert "RAW RESPONSE MUTATED =" in report_text
    assert "STRICT HISTORICAL REPLAY =" in report_text
    assert "PROMPT =" in report_text
    assert "window-analysis-1.4.0 unchanged" in report_text
    assert "TRANSPORT =" in report_text
    assert "semantic-transport-v3.1-local-lite unchanged" in report_text
    assert "GRANULARITY =" in report_text
    assert "window-granularity-1.2-kind-specific unchanged" in report_text
    assert "SCHEMA IDENTITY =" in report_text
    assert "UNCHANGED" in report_text
    assert "A.18 GRAMMAR PROOF =" in report_text
    assert "APPLIES" in report_text
    assert "READY BEFORE =" in report_text
    assert "6 / 7" in report_text
    assert "READY AFTER =" in report_text
    assert "RELATION_QUALITY_TECHNICAL_DEBT =" in report_text
    assert "SOURCE MAP =" in report_text
    assert "NOT PUBLISHED" in report_text
    assert "GLOBAL CONSOLIDATION =" in report_text
    assert "NOT EXECUTED" in report_text
    assert "PHASE 3B =" in report_text
    assert "INCOMPLETE" in report_text
    assert "NEXT ACTION =" in report_text
    assert "HUMAN REVIEW" in report_text
    assert WIN007_REQUEST_ID in report_text or "req_011CfVDkmr5jkE7chHzsafTc" in (
        bundle["replay"]["identity"].get("request_id") or ""
    )

    header = bundle["header"]
    assert header["real_provider_calls"] == 0
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert WIN007_NEW_PROVIDER_CALL is False
    assert not source_map_path(PROJECT_NAME).is_file()
    assert PHASE == "3B.7.7A.33"
    assert bundle["replay"]["strict_reproduced"] is True
    assert bundle["replay"]["raw_token"] == "SRec007337"
    assert bundle["schema"]["identity"] == "UNCHANGED"
    assert header.get("win007_promoted") is True
    assert header["ready_after"] == "7 / 7"
    assert header["result"] == "PASS"
    assert bundle["promotion"]["label"] == WIN007_PROMOTION_LABEL
    assert bundle["ready"]["windows"]["WIN007"] == "READY"
    assert bundle["inventory"] is not None
    assert INVENTORY_ARTIFACT in {path.name for path in written.values()}

    assert sha256_of_file(raw) == before_raw
    if before_a31 is not None:
        assert sha256_of_file(a31) == before_a31
    if before_a32 is not None:
        assert sha256_of_file(a32) == before_a32
    after_protected = protected_a33_historical_hashes()
    for key, digest in before_protected.items():
        assert after_protected.get(key) == digest
