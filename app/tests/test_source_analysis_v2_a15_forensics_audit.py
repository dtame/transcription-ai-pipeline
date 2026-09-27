"""Écrit les artefacts A.16. N'écrase pas A.15. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v2_a15_forensics.constants import (
    COVERAGE_ARTIFACT,
    DECISION_ARTIFACT,
    FORENSICS_ARTIFACT,
    OPTIONS_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REPORT_NAME,
    SEMANTIC_ARTIFACT,
    WIN001_RETRY_AUTHORIZED,
)
from app.source_analysis_v2_a15_forensics.evidence import protected_historical_hashes
from app.source_analysis_v2_a15_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v2_a15_forensics.runner import build_bundle
from app.source_analysis_v2_a15_forensics.writer import write_audit_bundle
from app.source_analysis_v2_real_win001.constants import REPORT_NAME as A15_REPORT
from app.source_analysis_v2_real_win001.paths import candidate_cache_dir
from app.source_analysis_v2_a15_forensics.constants import A15_SIGNATURE

REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_a15():
    assert_offline_package()
    assert_analyzer_not_wired()
    a15 = audit_dir(PROJECT_NAME) / A15_REPORT
    before_report = sha256_of_file(a15) if a15.is_file() else None
    before_protected = protected_historical_hashes()
    bundle = build_bundle(
        tests="2604 passed / 0 failed (13 A.16 tests included; 0 provider calls)",
    )
    written = write_audit_bundle(PROJECT_NAME, bundle)
    assert written["forensics"].name == FORENSICS_ARTIFACT
    assert written["semantic"].name == SEMANTIC_ARTIFACT
    assert written["coverage"].name == COVERAGE_ARTIFACT
    assert written["options"].name == OPTIONS_ARTIFACT
    assert written["decision"].name == DECISION_ARTIFACT
    assert written["report"].name == REPORT_NAME
    report_text = written["report"].read_text(encoding="utf-8")
    assert "# PHASE 3B.7.7A.16 — A.15 INVALID-LINK FORENSICS & OFFLINE SEMANTIC REVIEW" in report_text
    assert "REAL PROVIDER CALLS = 0" in report_text
    assert "REAL WINDOW CALLS = 0" in report_text
    assert "INVALID LINKS = 7" in report_text
    assert "FUTURE REAL CALL AUTHORIZED = NO" in report_text
    assert "SOURCE MAP = NOT PUBLISHED" in report_text
    assert "FORENSIC_SEMANTIC_REVIEW_OF_INVALID_TRANSPORT" in report_text
    assert "LOCAL_SYMBOLIC_HANDLES" in report_text
    assert bundle["header"]["phase"] == PHASE
    assert bundle["header"]["result"] in {"PASS", "PARTIAL"}
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert WIN001_RETRY_AUTHORIZED is False
    assert not source_map_path(PROJECT_NAME).is_file()
    assert not candidate_cache_dir(PROJECT_NAME, A15_SIGNATURE).exists()
    if before_report is not None:
        assert sha256_of_file(a15) == before_report
    assert protected_historical_hashes() == before_protected
    assert REAL_PROJECT.joinpath("analysis", "source_map.json").exists() is False
    assert not REAL_PROJECT.joinpath("analysis", "windows", "WIN001").exists()


def test_analyzer_and_main_untouched():
    analyzer = Path(r"C:\TranscriptionAI\app\source_analysis\analyzer.py")
    main = Path(r"C:\TranscriptionAI\main.py")
    text = analyzer.read_text(encoding="utf-8")
    assert "source_analysis_v2_a15_forensics" not in text
    assert "source_analysis_local_v2" not in text
    if main.is_file():
        main_text = main.read_text(encoding="utf-8")
        assert "source_analysis_v2_a15_forensics" not in main_text
        assert "source_analysis_local_v2" not in main_text
