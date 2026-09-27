"""Écrit les artefacts A.20. N'écrase pas A.19. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v3_a19_forensics.constants import (
    COVERAGE_ARTIFACT,
    EXAMPLE_POLICY_ARTIFACT,
    FUTURE_RETRY_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REPORT_NAME,
    SEMANTIC_ARTIFACT,
    SRC_CONTRACT_ARTIFACT,
    VIOLATION_ARTIFACT,
    WIN001_RETRY_AUTHORIZED,
)
from app.source_analysis_v3_a19_forensics.evidence import protected_a19_phase_hashes
from app.source_analysis_v3_a19_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v3_a19_forensics.runner import build_bundle
from app.source_analysis_v3_a19_forensics.writer import write_audit_bundle
from app.source_analysis_v3_real_win001.constants import REPORT_NAME as A19_REPORT
from app.source_analysis_v3_real_win001.paths import candidate_cache_dir
from app.source_analysis_v3_a19_forensics.constants import A19_SIGNATURE

REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_a19():
    assert_offline_package()
    assert_analyzer_not_wired()
    a19 = audit_dir(PROJECT_NAME) / A19_REPORT
    before_report = sha256_of_file(a19) if a19.is_file() else None
    before_protected = protected_a19_phase_hashes()
    bundle = build_bundle(
        tests="2692 passed / 0 failed (18 A.20 tests included; 0 provider calls)",
    )
    written = write_audit_bundle(PROJECT_NAME, bundle)
    assert written["violations"].name == VIOLATION_ARTIFACT
    assert written["src_contract"].name == SRC_CONTRACT_ARTIFACT
    assert written["example_policy"].name == EXAMPLE_POLICY_ARTIFACT
    assert written["semantic"].name == SEMANTIC_ARTIFACT
    assert written["coverage"].name == COVERAGE_ARTIFACT
    assert written["future"].name == FUTURE_RETRY_ARTIFACT
    assert written["report"].name == REPORT_NAME
    report_text = written["report"].read_text(encoding="utf-8")
    assert (
        "# PHASE 3B.7.7A.20 — A.19 FULL LATENT-VIOLATION FORENSICS & SRC HARDENING"
        in report_text
    )
    assert "REAL PROVIDER CALLS = 0" in report_text
    assert "REAL WINDOW CALLS = 0" in report_text
    assert "A.19 STATUS = FAIL unchanged" in report_text
    assert "A.19 FIRST DECODER FAILURE = records[50].s[6] = SRc000609" in report_text
    assert "FUTURE REAL CALL AUTHORIZED = NO" in report_text
    assert "SOURCE MAP = NOT PUBLISHED" in report_text
    assert "FORENSIC_SEMANTIC_REVIEW_OF_INVALID_V3_TRANSPORT" in report_text
    assert "PROMPT = window-analysis-1.3.1" in report_text
    assert "TRANSPORT = semantic-transport-v3" in report_text
    assert "SCHEMA CHANGED = NO" in report_text
    assert bundle["header"]["phase"] == PHASE
    assert bundle["header"]["result"] in {"PASS", "PARTIAL"}
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert WIN001_RETRY_AUTHORIZED is False
    assert not source_map_path(PROJECT_NAME).is_file()
    assert not candidate_cache_dir(PROJECT_NAME, A19_SIGNATURE).exists()
    if before_report is not None:
        assert sha256_of_file(a19) == before_report
    assert protected_a19_phase_hashes() == before_protected
    assert REAL_PROJECT.joinpath("analysis", "source_map.json").exists() is False
    assert not REAL_PROJECT.joinpath("analysis", "windows", "WIN001").exists()


def test_network_isolation():
    analyzer = Path(r"C:\TranscriptionAI\app\source_analysis\analyzer.py")
    text = analyzer.read_text(encoding="utf-8")
    assert "source_analysis_v3_a19_forensics" not in text
    main = Path(r"C:\TranscriptionAI\main.py")
    if main.is_file():
        assert "source_analysis_v3_a19_forensics" not in main.read_text(encoding="utf-8")
