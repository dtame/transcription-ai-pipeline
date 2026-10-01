"""Écrit les artefacts A.46. N'écrase pas A.34–A.45. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_v30_exact_preflight.evidence import (
    protected_a45_historical_hashes,
)
from app.source_analysis_v31_global_v30_real_canary.constants import (
    ACCOUNTABILITY_ARTIFACT,
    DROP_ARTIFACT,
    MERGE_ARTIFACT,
    METADATA_ARTIFACT,
    PHASE,
    PRECALL_ARTIFACT,
    PROJECT_NAME,
    PUBLICATION_ARTIFACT,
    READINESS_ARTIFACT,
    REPORT_NAME,
    REUSE_ARTIFACT,
    TOPIC_ARTIFACT,
    TRANSPORT_ARTIFACT,
    USAGE_ARTIFACT,
)
from app.source_analysis_v31_global_v30_real_canary.isolation import assert_analyzer_not_wired
from app.source_analysis_v31_global_v30_real_canary.paths import canary_root
from app.source_analysis_v31_global_v30_real_canary.runner import CanaryRunResult
from app.source_analysis_v31_global_v30_real_canary.writer import (
    write_canary_artifacts,
    write_precall_manifest,
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def test_write_artifacts_isolated_and_does_not_publish(tmp_path: Path):
    assert_analyzer_not_wired()
    before = protected_a45_historical_hashes(PROJECT_NAME)
    result = CanaryRunResult(
        mode="DRY_RUN",
        project_name=PROJECT_NAME,
        authorization_scope="GLOBAL_CONSOLIDATION_3_0_REAL_CANARY_EXACT_REQUEST_ONLY",
        accepted=True,
    )
    result.dry_run = {
        "preflight": {
            "authorization_scope": result.authorization_scope,
            "human_authorization": {
                "A45_READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY": "YES"
            },
            "ready_windows": ["WIN001"],
            "windows": {"window_set_sha256": "abc", "windows": []},
            "inventory": {"observed": {"IDEA": 286}},
            "normalized_input_hash": "n",
            "request_hash": "r",
            "payload_audit": {"schema_hash": "s"},
            "model": "claude-sonnet-5",
            "prompt_version": "global-consolidation-3.0",
            "transport_version": "global-consolidation-transport-3.0",
            "thinking_mode": "disabled",
            "max_output": 48000,
            "estimated_input": 67146,
            "expected_output": 13112,
            "conservative_output": 18013,
            "hard_output": 29435,
            "cost": {"expected": {"display": "ESTIMATED"}},
        }
    }
    result.execution = {
        "result": "BLOCKED_PRECALL",
        "source_map": "NOT PUBLISHED",
        "publication_eligible": "NO",
        "ready_for_source_map_publication_review": "NO",
        "idea_accountability": "n/a",
    }
    written = write_canary_artifacts(
        PROJECT_NAME,
        result,
        sortie_dir=tmp_path,
        tests="offline A.46 unit",
    )
    root = canary_root(PROJECT_NAME, sortie_dir=tmp_path)
    assert (root / PRECALL_ARTIFACT).is_file()
    assert (root / TRANSPORT_ARTIFACT).is_file()
    assert (root / ACCOUNTABILITY_ARTIFACT).is_file()
    assert (root / REUSE_ARTIFACT).is_file()
    assert (root / MERGE_ARTIFACT).is_file()
    assert (root / DROP_ARTIFACT).is_file()
    assert (root / METADATA_ARTIFACT).is_file()
    assert (root / TOPIC_ARTIFACT).is_file()
    assert (root / USAGE_ARTIFACT).is_file()
    assert (root / PUBLICATION_ARTIFACT).is_file()
    assert (root / READINESS_ARTIFACT).is_file()
    report = written["report"]
    assert report.name == REPORT_NAME
    text = report.read_text(encoding="utf-8")
    assert text.startswith("# PHASE 3B.7.7A.46 — GLOBAL CONSOLIDATION V3.0 ONE REAL CANARY")
    assert "SOURCE MAP =" in text
    assert "NOT PUBLISHED" in text
    assert "NEXT ACTION =" in text
    assert "HUMAN REVIEW" in text
    assert PHASE == "3B.7.7A.46"
    assert not source_map_path(PROJECT_NAME, sortie_dir=tmp_path).is_file()
    after = protected_a45_historical_hashes(PROJECT_NAME)
    assert after == before
    write_precall_manifest(
        PROJECT_NAME, result.dry_run["preflight"], sortie_dir=tmp_path
    )
    live_report = audit_dir(PROJECT_NAME) / REPORT_NAME
    if live_report.is_file():
        sha256_of_file(live_report)
