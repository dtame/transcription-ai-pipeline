"""Écrit les artefacts A.23. N'écrase pas A.19–A.22. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v3_a22_forensics.constants import (
    CONTRACT_ARTIFACT,
    COVERAGE_ARTIFACT,
    FOUR_RECORDS_ARTIFACT,
    FUTURE_RETRY_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REASONING_ARTIFACT,
    REPORT_NAME,
    SEMANTIC_ARTIFACT,
    VIOLATION_ARTIFACT,
    WIN004_RETRY_AUTHORIZED,
)
from app.source_analysis_v3_a22_forensics.evidence import protected_a22_phase_hashes
from app.source_analysis_v3_a22_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v3_a22_forensics.runner import build_bundle
from app.source_analysis_v3_a22_forensics.writer import write_audit_bundle
from app.source_analysis_v3_second_window.constants import REPORT_NAME as A22_REPORT
from app.source_analysis_v3_second_window.paths import candidate_cache_dir
from app.source_analysis_v3_a22_forensics.constants import A22_SIGNATURE

REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_a22():
    assert_offline_package()
    assert_analyzer_not_wired()
    a22 = audit_dir(PROJECT_NAME) / A22_REPORT
    before_report = sha256_of_file(a22) if a22.is_file() else None
    before_protected = protected_a22_phase_hashes()
    bundle = build_bundle(
        tests="offline A.23",
    )
    written = write_audit_bundle(PROJECT_NAME, bundle)
    assert written["violations"].name == VIOLATION_ARTIFACT
    assert written["contract"].name == CONTRACT_ARTIFACT
    assert written["four"].name == FOUR_RECORDS_ARTIFACT
    assert written["semantic"].name == SEMANTIC_ARTIFACT
    assert written["coverage"].name == COVERAGE_ARTIFACT
    assert written["reasoning"].name == REASONING_ARTIFACT
    assert written["future"].name == FUTURE_RETRY_ARTIFACT
    assert written["report"].name == REPORT_NAME
    report_text = written["report"].read_text(encoding="utf-8")
    assert (
        "# PHASE 3B.7.7A.23 — A.22 IDEA/EXAMPLE TYPE-CONTRACT FORENSICS"
        in report_text
    )
    assert "REAL PROVIDER CALLS = 0" in report_text
    assert "REAL WINDOW CALLS = 0" in report_text
    assert "A.22 STATUS = FAIL unchanged" in report_text
    assert "A.22 TARGET = WIN004" in report_text
    assert "FUTURE REAL CALL AUTHORIZED = NO" in report_text
    assert "SOURCE MAP = NOT PUBLISHED" in report_text
    assert "FORENSIC_SEMANTIC_REVIEW_OF_INVALID_V3_WIN004_TRANSPORT" in report_text
    assert "PROMPT = window-analysis-1.3.2" in report_text
    assert "TRANSPORT = semantic-transport-v3" in report_text
    assert "SCHEMA CHANGED = NO" in report_text
    assert "SEMANTICALLY_ACCEPTABLE_BUT_FOR_TRANSPORT_METADATA" in report_text
    assert bundle["header"]["phase"] == PHASE
    assert bundle["header"]["result"] in {"PASS", "PARTIAL"}
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert WIN004_RETRY_AUTHORIZED is False
    assert not source_map_path(PROJECT_NAME).is_file()
    assert not candidate_cache_dir(PROJECT_NAME, A22_SIGNATURE, "WIN004").exists()
    if before_report is not None:
        assert sha256_of_file(a22) == before_report
    assert protected_a22_phase_hashes() == before_protected
    assert REAL_PROJECT.joinpath("analysis", "source_map.json").exists() is False
    assert not REAL_PROJECT.joinpath("analysis", "windows", "WIN004").exists()


def test_network_isolation():
    analyzer = Path(r"C:\TranscriptionAI\app\source_analysis\analyzer.py")
    text = analyzer.read_text(encoding="utf-8")
    assert "source_analysis_v3_a22_forensics" not in text
    main = Path(r"C:\TranscriptionAI\main.py")
    if main.is_file():
        assert "source_analysis_v3_a22_forensics" not in main.read_text(encoding="utf-8")
