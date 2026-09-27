"""Écrit les artefacts A.13 dans un sortie isolé. N'écrase pas A.12."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_thinking_contract.constants import (
    PROJECT_NAME,
    REPORT_NAME as A12_REPORT,
    REAL_PROVIDER_CALL_AUTHORIZED,
)
from app.source_analysis_v2_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    EXECUTION_ARTIFACT,
    PAYLOAD_ARTIFACT,
    REPORT_NAME,
)
from app.source_analysis_v2_grammar_canary.runner import run_grammar_thinking_canary
from app.source_analysis_v2_grammar_canary.writer import write_canary_artifacts


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_artifacts_to_tmp_without_touching_a12(tmp_path):
    a12 = audit_dir(PROJECT_NAME) / A12_REPORT
    before = sha256_of_file(a12) if a12.is_file() else None
    result = run_grammar_thinking_canary(
        "fixture",
        authorization_scope=AUTHORIZATION_SCOPE,
        sortie_dir=tmp_path,
    )
    written = write_canary_artifacts("fixture", result, sortie_dir=tmp_path)
    assert written["execution"].name == EXECUTION_ARTIFACT
    assert written["payload"].name == PAYLOAD_ARTIFACT
    assert written["report"].name == REPORT_NAME
    report = written["report"].read_text(encoding="utf-8")
    assert "# PHASE 3B.7.7A.13" in report
    assert "V2_GRAMMAR_CONFIG_CANARY_ONLY" in report
    assert "REAL WINDOW CALLS = 0" in report
    assert not source_map_path("fixture", sortie_dir=tmp_path).is_file()
    assert REAL_PROVIDER_CALL_AUTHORIZED is False
    if before is not None:
        assert sha256_of_file(a12) == before
    assert not Path(tmp_path / "fixture" / "analysis" / "source_map.json").exists()


def test_analyzer_not_wired_to_a13():
    from pathlib import Path as P

    analyzer = P(r"C:\TranscriptionAI\app\source_analysis\analyzer.py")
    main = P(r"C:\TranscriptionAI\main.py")
    text = analyzer.read_text(encoding="utf-8")
    assert "source_analysis_v2_grammar_canary" not in text
    if main.is_file():
        assert "source_analysis_v2_grammar_canary" not in main.read_text(encoding="utf-8")
