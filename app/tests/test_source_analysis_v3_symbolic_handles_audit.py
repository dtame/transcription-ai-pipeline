"""Écrit les artefacts A.17. N'écrase pas A.15. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v2_a15_forensics.evidence import protected_historical_hashes
from app.source_analysis_v2_real_win001.constants import REPORT_NAME as A15_REPORT
from app.source_analysis_v3_symbolic_handles.constants import (
    CANARY_ARTIFACT,
    DESIGN_ARTIFACT,
    FAKEAI_ARTIFACT,
    PHASE,
    PREFLIGHT_ARTIFACT,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REPORT_NAME,
    RESOLUTION_ARTIFACT,
    SCHEMA_ARTIFACT,
    WIN001_RETRY_AUTHORIZED,
)
from app.source_analysis_v3_symbolic_handles.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v3_symbolic_handles.runner import build_bundle
from app.source_analysis_v3_symbolic_handles.writer import write_audit_bundle

REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_a15(tmp_path):
    assert_offline_package()
    assert_analyzer_not_wired()
    a15 = audit_dir(PROJECT_NAME) / A15_REPORT
    before_report = sha256_of_file(a15) if a15.is_file() else None
    before_protected = protected_historical_hashes()
    bundle = build_bundle(
        tests="2631 passed / 0 failed (27 A.17 tests included; 0 provider calls)",
        tmp_root=tmp_path,
    )
    written = write_audit_bundle(PROJECT_NAME, bundle)
    assert written["design"].name == DESIGN_ARTIFACT
    assert written["schema"].name == SCHEMA_ARTIFACT
    assert written["resolution"].name == RESOLUTION_ARTIFACT
    assert written["fakeai"].name == FAKEAI_ARTIFACT
    assert written["preflight"].name == PREFLIGHT_ARTIFACT
    assert written["canary"].name == CANARY_ARTIFACT
    assert written["report"].name == REPORT_NAME
    report_text = written["report"].read_text(encoding="utf-8")
    assert "# PHASE 3B.7.7A.17 — LOCAL SYMBOLIC HANDLES TRANSPORT REDESIGN" in report_text
    assert "REAL PROVIDER CALLS = 0" in report_text
    assert "REAL WINDOW CALLS = 0" in report_text
    assert "SELECTED ARCHITECTURE = LOCAL_SYMBOLIC_HANDLES" in report_text
    assert "TRANSPORT = semantic-transport-v3" in report_text
    assert "PROMPT = window-analysis-1.3" in report_text
    assert "SERVER GRAMMAR VERIFIED = NO" in report_text
    assert "REAL CALL AUTHORIZED = NO" in report_text
    assert "SOURCE MAP = NOT PUBLISHED" in report_text
    assert "PHASE 3B = INCOMPLETE" in report_text
    assert "A.13 remains proof only for semantic-transport-v2" in report_text
    assert bundle["header"]["phase"] == PHASE
    assert bundle["header"]["result"] in {"PASS", "PARTIAL"}
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert WIN001_RETRY_AUTHORIZED is False
    assert not source_map_path(PROJECT_NAME).is_file()
    if before_report is not None:
        assert sha256_of_file(a15) == before_report
    assert protected_historical_hashes() == before_protected
    assert REAL_PROJECT.joinpath("analysis", "source_map.json").exists() is False


def test_analyzer_and_main_untouched():
    analyzer = Path(r"C:\TranscriptionAI\app\source_analysis\analyzer.py")
    main = Path(r"C:\TranscriptionAI\main.py")
    text = analyzer.read_text(encoding="utf-8")
    assert "source_analysis_local_v3" not in text
    assert "source_analysis_v3_symbolic_handles" not in text
    if main.is_file():
        main_text = main.read_text(encoding="utf-8")
        assert "source_analysis_local_v3" not in main_text
        assert "source_analysis_v3_symbolic_handles" not in main_text
