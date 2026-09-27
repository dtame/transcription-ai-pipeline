"""Écrit les artefacts A.14. N'écrase pas A.13. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v2_grammar_canary.constants import REPORT_NAME as A13_REPORT
from app.source_analysis_v2_link_semantics.constants import (
    CONTRACT_ARTIFACT,
    IDENTITY_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    PROMPT_ARTIFACT,
    READINESS_ARTIFACT,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REPLAY_ARTIFACT,
    REPORT_NAME,
    SEMANTIC_WIN001_AUTHORIZED,
)
from app.source_analysis_v2_link_semantics.evidence import protected_a13_hashes
from app.source_analysis_v2_link_semantics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v2_link_semantics.runner import build_bundle
from app.source_analysis_v2_link_semantics.writer import write_audit_bundle

REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_a13(tmp_path):
    assert_offline_package()
    assert_analyzer_not_wired()
    a13 = audit_dir(PROJECT_NAME) / A13_REPORT
    before_report = sha256_of_file(a13) if a13.is_file() else None
    before_protected = protected_a13_hashes()
    bundle = build_bundle(
        tmp_root=tmp_path / "e2e",
        tests="2580 passed / 2 failed (pre-existing openai package missing; 0 A.14 failures)",
    )
    written = write_audit_bundle(PROJECT_NAME, bundle)
    assert written["replay"].name == REPLAY_ARTIFACT
    assert written["contract"].name == CONTRACT_ARTIFACT
    assert written["prompt"].name == PROMPT_ARTIFACT
    assert written["readiness"].name == READINESS_ARTIFACT
    assert written["identity"].name == IDENTITY_ARTIFACT
    assert written["report"].name == REPORT_NAME
    report_text = written["report"].read_text(encoding="utf-8")
    assert "# PHASE 3B.7.7A.14" in report_text
    assert "REAL PROVIDER CALLS = 0" in report_text
    assert "SEMANTIC WIN001 AUTHORIZED = NO" in report_text
    assert "UNVERIFIED_REAL" in report_text
    assert bundle["header"]["phase"] == PHASE
    assert bundle["header"]["result"] in {"PASS", "PARTIAL"}
    assert bundle["readiness"]["authorized"] is False
    assert SEMANTIC_WIN001_AUTHORIZED is False
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert not source_map_path(PROJECT_NAME).is_file()
    if before_report is not None:
        assert sha256_of_file(a13) == before_report
    assert protected_a13_hashes() == before_protected
    isolation = bundle["isolation"]
    assert isolation["forensics_allowed"] is True
    assert isolation["unauthorized_semantic_artifacts_forbidden"] is True
    assert REAL_PROJECT.joinpath("analysis", "source_map.json").exists() is False


def test_analyzer_and_main_untouched():
    analyzer = Path(r"C:\TranscriptionAI\app\source_analysis\analyzer.py")
    main = Path(r"C:\TranscriptionAI\main.py")
    text = analyzer.read_text(encoding="utf-8")
    assert "source_analysis_v2_link_semantics" not in text
    assert "source_analysis_local_v2" not in text
    if main.is_file():
        main_text = main.read_text(encoding="utf-8")
        assert "source_analysis_v2_link_semantics" not in main_text
        assert "source_analysis_local_v2" not in main_text
