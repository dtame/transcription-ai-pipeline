"""Écrit les artefacts A.18 dans un sortie isolé. N'écrase pas A.17."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    EXECUTION_ARTIFACT,
    HANDLES_ARTIFACT,
    PAYLOAD_ARTIFACT,
    PROJECT_NAME,
    REPORT_NAME,
)
from app.source_analysis_v3_symbolic_grammar_canary.runner import (
    run_symbolic_handle_grammar_canary,
)
from app.source_analysis_v3_symbolic_grammar_canary.writer import write_canary_artifacts
from app.source_analysis_v3_symbolic_handles.constants import REPORT_NAME as A17_REPORT

REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_artifacts_to_tmp_without_touching_a17(tmp_path):
    a17 = audit_dir(PROJECT_NAME) / A17_REPORT
    before = sha256_of_file(a17) if a17.is_file() else None
    result = run_symbolic_handle_grammar_canary(
        "fixture",
        authorization_scope=AUTHORIZATION_SCOPE,
        sortie_dir=tmp_path,
    )
    written = write_canary_artifacts("fixture", result, sortie_dir=tmp_path)
    assert written["execution"].name == EXECUTION_ARTIFACT
    assert written["payload"].name == PAYLOAD_ARTIFACT
    assert written["handles"].name == HANDLES_ARTIFACT
    assert written["report"].name == REPORT_NAME
    report = written["report"].read_text(encoding="utf-8")
    assert "# PHASE 3B.7.7A.18" in report
    assert "V3_SYMBOLIC_HANDLE_GRAMMAR_CANARY_ONLY" in report
    assert "REAL WINDOW CALLS = 0" in report
    assert "SOURCE MAP = NOT PUBLISHED" in report
    assert not source_map_path("fixture", sortie_dir=tmp_path).is_file()
    if before is not None:
        assert sha256_of_file(a17) == before
    assert not Path(tmp_path / "fixture" / "analysis" / "source_map.json").exists()
    assert REAL_PROJECT.joinpath("analysis", "source_map.json").exists() is False
