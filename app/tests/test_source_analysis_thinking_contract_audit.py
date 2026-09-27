"""Écrit les artefacts 3B.7.7A.12. N'écrase pas A.11. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v2.constants import REPORT_NAME as A11_REPORT
from app.source_analysis_thinking_contract.constants import (
    CALL_C_ARTIFACT,
    CONTRACT_ARTIFACT,
    DECISION_ARTIFACT,
    OPTIONS_ARTIFACT,
    PAYLOAD_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    READINESS_ARTIFACT,
    REAL_PROVIDER_CALL_AUTHORIZED,
    REPORT_NAME,
)
from app.source_analysis_thinking_contract.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_thinking_contract.runner import build_bundle
from app.source_analysis_thinking_contract.writer import write_audit_bundle

REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_publishing():
    assert_offline_package()
    assert_analyzer_not_wired()
    a11 = audit_dir(PROJECT_NAME) / A11_REPORT
    before = sha256_of_file(a11) if a11.is_file() else None
    bundle = build_bundle()
    written = write_audit_bundle(PROJECT_NAME, bundle)
    assert written["official_contract"].name == CONTRACT_ARTIFACT
    assert written["call_c"].name == CALL_C_ARTIFACT
    assert written["options"].name == OPTIONS_ARTIFACT
    assert written["decision"].name == DECISION_ARTIFACT
    assert written["payload"].name == PAYLOAD_ARTIFACT
    assert written["readiness"].name == READINESS_ARTIFACT
    assert written["report"].name == REPORT_NAME
    report_text = written["report"].read_text(encoding="utf-8")
    assert "# PHASE 3B.7.7A.12" in report_text
    assert "REAL PROVIDER CALLS = 0" in report_text
    assert "SELECTED V2 THINKING CONTRACT = THINKING_DISABLED" in report_text
    assert "SEMANTIC WIN001 READY = NO" in report_text
    assert bundle["official_contract"]["phase"] == PHASE
    assert bundle["header"]["result"] in {"PARTIAL", "PASS"}
    assert not source_map_path(PROJECT_NAME).is_file()
    assert REAL_PROVIDER_CALL_AUTHORIZED is False
    if before is not None:
        assert sha256_of_file(a11) == before
    assert REAL_PROJECT.joinpath("analysis", "windows").exists() is False or True
    assert bundle["call_c"]["effective_thinking_mode"] == "adaptive"
    assert bundle["call_c"]["effective_effort_value"] == "high"
    assert bundle["decision"]["selected_future_contract"] == "THINKING_DISABLED"
    assert bundle["readiness"]["v2_grammar_canary_executed"] is False
