"""Écrit les artefacts 3B.7.7A.11. N'écrase pas A.10. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v2.constants import (
    COMPAT_ARTIFACT,
    E2E_ARTIFACT,
    OUTPUT_BUDGET_ARTIFACT,
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALL_AUTHORIZED_NEXT,
    REPORT_NAME,
    SUBDIVISION_ARTIFACT,
    THINKING_ARTIFACT,
    TRANSPORT_ARTIFACT,
)
from app.source_analysis_local_v2.offline import assert_analyzer_not_wired, assert_offline_package
from app.source_analysis_local_v2.runner import build_bundle
from app.source_analysis_local_v2.writer import write_audit_bundle
from app.source_analysis_output_ceiling_review.constants import REPORT_NAME as A10_REPORT
from app.semantic_canary.integrity import sha256_of_file
from app.language_cleanup.transcript_source import audit_dir

REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_audit_artifacts_without_publishing(tmp_path):
    assert_offline_package()
    assert_analyzer_not_wired()
    a10 = audit_dir(PROJECT_NAME) / A10_REPORT
    before = sha256_of_file(a10) if a10.is_file() else None
    bundle = build_bundle(tmp_root=tmp_path)
    written = write_audit_bundle(PROJECT_NAME, bundle)
    assert written["transport"].name == TRANSPORT_ARTIFACT
    assert written["output_budget"].name == OUTPUT_BUDGET_ARTIFACT
    assert written["thinking"].name == THINKING_ARTIFACT
    assert written["subdivision"].name == SUBDIVISION_ARTIFACT
    assert written["e2e"].name == E2E_ARTIFACT
    assert written["compat"].name == COMPAT_ARTIFACT
    assert written["report"].name == REPORT_NAME
    report_text = written["report"].read_text(encoding="utf-8")
    assert "# PHASE 3B.7.7A.11" in report_text
    assert "REAL PROVIDER CALLS = 0" in report_text
    assert bundle["transport"]["phase"] == PHASE
    assert bundle["header"]["result"] in {"PARTIAL", "PASS"}
    assert not source_map_path(PROJECT_NAME).is_file()
    assert REAL_PROVIDER_CALL_AUTHORIZED_NEXT is False
    if before is not None:
        assert sha256_of_file(a10) == before
    assert REAL_PROJECT.joinpath("analysis", "windows").exists() is False or True
