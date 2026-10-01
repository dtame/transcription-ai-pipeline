"""Écrit les artefacts A.30. N'écrase pas A.19–A.29. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_kind_specific_limits.constants import (
    PHASE,
    POLICY_ARTIFACT,
    PREFLIGHT_ARTIFACT,
    PROJECT_NAME,
    PROVENANCE_ARTIFACT,
    READY_ARTIFACT,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REPORT_NAME,
    REVALIDATION_ARTIFACT,
    SCHEMA_ARTIFACT,
    WIN003_NEW_PROVIDER_CALL,
    WIN003_PROMOTION_LABEL,
    WIN003_REQUEST_ID,
    WIN003_SIGNATURE,
)
from app.source_analysis_v31_kind_specific_limits.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_kind_specific_limits.runner import build_bundle
from app.source_analysis_v31_kind_specific_limits.writer import write_audit_bundle
from app.source_analysis_v31_length_ceiling.constants import REPORT_NAME as A29_REPORT
from app.source_analysis_v31_length_ceiling.evidence import (
    protected_a29_historical_hashes,
    win003_raw_path,
)
from app.source_analysis_v31_remaining_windows.constants import REPORT_NAME as A28_REPORT
from app.source_analysis_v31_remaining_windows.paths import (
    candidate_cache_dir,
    candidate_window_dir,
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_history():
    assert_offline_package()
    assert_analyzer_not_wired()
    a28 = audit_dir(PROJECT_NAME) / A28_REPORT
    a29 = audit_dir(PROJECT_NAME) / A29_REPORT
    raw = win003_raw_path(PROJECT_NAME)
    before_a28 = sha256_of_file(a28) if a28.is_file() else None
    before_a29 = sha256_of_file(a29) if a29.is_file() else None
    before_raw = sha256_of_file(raw)
    before_protected = protected_a29_historical_hashes()

    bundle = build_bundle(tests="offline A.30")
    written = write_audit_bundle(PROJECT_NAME, bundle, tests="offline A.30")

    assert written["policy"].name == POLICY_ARTIFACT
    assert written["schema"].name == SCHEMA_ARTIFACT
    assert written["revalidation"].name == REVALIDATION_ARTIFACT
    assert written["provenance"].name == PROVENANCE_ARTIFACT
    assert written["ready"].name == READY_ARTIFACT
    assert written["preflight"].name == PREFLIGHT_ARTIFACT
    assert written["report"].name == REPORT_NAME

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.30 — KIND-SPECIFIC LENGTH POLICY + SAVED WIN003 REVALIDATION"
    )
    assert "REAL PROVIDER CALLS =" in report_text
    assert "\n0\n" in report_text
    assert "REAL WINDOW CALLS =" in report_text
    assert "A.28 HISTORICAL STATUS =" in report_text
    assert "FAIL unchanged" in report_text
    assert "A.29 STATUS =" in report_text
    assert "OLD THEME LIMIT =" in report_text
    assert "NEW THEME LIMIT =" in report_text
    assert "OLD EXAMPLE LIMIT =" in report_text
    assert "NEW EXAMPLE LIMIT =" in report_text
    assert "IDEA LIMIT =" in report_text
    assert "280 unchanged" in report_text
    assert "PROMPT =" in report_text
    assert "window-analysis-1.4.0 unchanged" in report_text
    assert "TRANSPORT =" in report_text
    assert "semantic-transport-v3.1-local-lite unchanged" in report_text
    assert "SCHEMA IDENTITY =" in report_text
    assert "UNCHANGED" in report_text
    assert "A.18 GRAMMAR PROOF =" in report_text
    assert "APPLIES" in report_text
    assert "WIN003 RESPONSE SOURCE =" in report_text
    assert "SAVED_A28_RESPONSE" in report_text
    assert "WIN003 NEW PROVIDER CALL =" in report_text
    assert "WIN003 ORIGINAL REQUEST ID =" in report_text
    assert WIN003_REQUEST_ID in report_text
    assert "WIN003 THEME LENGTH =" in report_text
    assert "212" in report_text
    assert "WIN003 EXAMPLE LENGTH =" in report_text
    assert "213" in report_text
    assert "WIN003 IDEA LENGTH =" in report_text
    assert "209" in report_text
    assert "WIN003 PROMOTED =" in report_text
    assert "READY BEFORE =" in report_text
    assert "3 / 7" in report_text
    assert "READY AFTER =" in report_text
    assert "RELATION_QUALITY_TECHNICAL_DEBT =" in report_text
    assert "SOURCE MAP =" in report_text
    assert "NOT PUBLISHED" in report_text
    assert "PHASE 3B =" in report_text
    assert "INCOMPLETE" in report_text
    assert "NEXT ACTION =" in report_text
    assert "HUMAN REVIEW" in report_text

    header = bundle["header"]
    assert header["phase"] == PHASE
    assert header["real_provider_calls"] == REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert WIN003_NEW_PROVIDER_CALL is False
    assert header["result"] == "PASS"
    assert header["win003_promoted"] is True
    assert header["ready_after"] == "4 / 7"
    assert bundle["replay"]["technical_ok"] is True
    assert bundle["replay"]["historical_a28_reproduced"] is True
    assert bundle["schema"]["identity"] == "UNCHANGED"
    assert bundle["ready"]["windows"]["WIN003"] == "READY"
    assert bundle["ready"]["windows"]["WIN005"] == "NOT RUN"
    assert bundle["provenance"]["provider_call_during_a30"] is False
    assert bundle["provenance"]["original_provider_phase"] == "A.28"
    assert bundle["provenance"]["label"] == WIN003_PROMOTION_LABEL
    assert bundle["relations"]["RELATION_QUALITY_TECHNICAL_DEBT"] == "YES"
    assert bundle["preflight"]["executed"] is False
    assert bundle["preflight"]["compatible"] is True
    assert not source_map_path(PROJECT_NAME).is_file()

    isolated = candidate_window_dir(PROJECT_NAME, "WIN003") / "metadata.json"
    cache = (
        candidate_cache_dir(PROJECT_NAME, WIN003_SIGNATURE, "WIN003") / "metadata.json"
    )
    assert isolated.is_file()
    assert cache.is_file()
    meta = isolated.read_text(encoding="utf-8")
    assert "A.28" in meta
    assert "A.30" in meta
    assert "false" in meta.lower() or "provider_call_during_a30" in meta

    after_a28 = sha256_of_file(a28) if a28.is_file() else None
    after_a29 = sha256_of_file(a29) if a29.is_file() else None
    after_raw = sha256_of_file(raw)
    after_protected = protected_a29_historical_hashes()
    assert after_a28 == before_a28
    assert after_a29 == before_a29
    assert after_raw == before_raw
    assert after_protected == before_protected


def test_tmp_write_does_not_create_source_map(tmp_path: Path):
    bundle = build_bundle(PROJECT_NAME, tests="tmp A.30", persist_candidate=False)
    written = write_audit_bundle(
        PROJECT_NAME,
        bundle,
        sortie_dir=tmp_path,
        tests="tmp A.30",
    )
    assert written["report"].is_file()
    assert not (tmp_path / PROJECT_NAME / "source_map.json").exists()
