"""Écrit les artefacts A.35. N'écrase pas A.19–A.34. 0 provider."""

from __future__ import annotations

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANONICAL_ARTIFACT,
    CONTRACT_ARTIFACT,
    DISPOSITION_ARTIFACT,
    FIXTURE_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    READINESS_ARTIFACT,
    REPORT_NAME,
    REQUEST_ARTIFACT,
    USAGE_ARTIFACT,
)
from app.source_analysis_v31_global_grammar_canary.runner import run_global_grammar_canary
from app.source_analysis_v31_global_grammar_canary.writer import write_canary_artifacts
from app.source_analysis_v31_global_preflight.constants import REPORT_NAME as A34_REPORT
from app.source_analysis_v31_global_preflight.evidence import (
    protected_a34_historical_hashes,
)
from app.source_analysis_v31_global_preflight.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_touching_history(tmp_path):
    assert_offline_package()
    assert_analyzer_not_wired()
    a34 = audit_dir(PROJECT_NAME) / A34_REPORT
    before_a34 = sha256_of_file(a34) if a34.is_file() else None
    before_protected = protected_a34_historical_hashes()

    result = run_global_grammar_canary(
        "fixture",
        dry_run=True,
        authorization_scope=AUTHORIZATION_SCOPE,
        sortie_dir=tmp_path,
    )
    written = write_canary_artifacts(
        "fixture", result, sortie_dir=tmp_path, tests="offline A.35 unit"
    )

    expected = {
        "fixture": FIXTURE_ARTIFACT,
        "request": REQUEST_ARTIFACT,
        "contract": CONTRACT_ARTIFACT,
        "dispositions": DISPOSITION_ARTIFACT,
        "canonical": CANONICAL_ARTIFACT,
        "usage": USAGE_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
        "report": REPORT_NAME,
    }
    for key, name in expected.items():
        assert written[key].name == name
        assert written[key].is_file()

    report_text = written["report"].read_text(encoding="utf-8")
    assert report_text.startswith(
        "# PHASE 3B.7.7A.35 — GLOBAL CONSOLIDATION TINY GRAMMAR CANARY"
    )
    assert "AUTHORIZED PROVIDER CALLS =" in report_text
    assert "REAL PASTORAL DATA SENT =" in report_text
    assert "NO" in report_text
    assert "REAL CONSOLIDATION EXECUTED =" in report_text
    assert "MODEL =" in report_text
    assert "claude-sonnet-5" in report_text
    assert "PROMPT =" in report_text
    assert "global-consolidation-1.0" in report_text
    assert "TRANSPORT =" in report_text
    assert "global-consolidation-transport-1.0" in report_text
    assert "LOCAL EXTRACTION FUNCTIONALLY FROZEN =" in report_text
    assert "YES" in report_text
    assert "RELATION_QUALITY_TECHNICAL_DEBT =" in report_text
    assert "SOURCE MAP =" in report_text
    assert "NOT PUBLISHED" in report_text
    assert "PHASE 3B =" in report_text
    assert "INCOMPLETE" in report_text
    assert "NEXT ACTION =" in report_text
    assert "HUMAN REVIEW" in report_text
    assert "READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY =" in report_text

    assert PHASE == "3B.7.7A.35"
    assert not source_map_path("fixture", sortie_dir=tmp_path).is_file()
    assert result.engine_generate_attempts == 0

    if before_a34 is not None:
        assert sha256_of_file(a34) == before_a34
    after_protected = protected_a34_historical_hashes()
    for key, digest in before_protected.items():
        assert after_protected.get(key) == digest
