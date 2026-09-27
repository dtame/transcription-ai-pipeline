"""Audit 3B.7.7A.10 — artefacts déterministes, 0 réseau, 0 source_map."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.source_analysis.writer import source_map_path
from app.source_analysis_output_ceiling_review.constants import (
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALL_AUTHORIZED_NEXT,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
)
from app.source_analysis_output_ceiling_review.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_output_ceiling_review.runner import run_output_ceiling_review
from app.source_analysis_output_ceiling_review.writer import (
    contract_path,
    decision_path,
    forensics_path,
    isolation_path,
    options_path,
    report_path,
)

REAL_AUDIT = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation\audit"
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


@pytest.fixture(scope="module")
def facts():
    assert_offline_package()
    assert_analyzer_not_wired()
    return run_output_ceiling_review()


def test_zero_provider_and_unwired(facts):
    assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
    assert REAL_PROVIDER_CALL_AUTHORIZED_NEXT is False
    assert facts["real_provider_calls"] == 0
    assert facts["phase"] == PHASE
    assert not source_map_path(PROJECT_NAME).exists()


def test_audit_artifacts_exist(facts):
    for path in (
        forensics_path(PROJECT_NAME),
        contract_path(PROJECT_NAME),
        options_path(PROJECT_NAME),
        decision_path(PROJECT_NAME),
        isolation_path(PROJECT_NAME),
        report_path(PROJECT_NAME),
    ):
        assert path.is_file(), path
        leftover = path.with_name(path.name + ".partial")
        assert not leftover.exists()


def test_forensics_payload(facts):
    payload = json.loads(
        (REAL_AUDIT / "source_analysis_small_win001_output_ceiling_forensics.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["phase"] == PHASE
    assert payload["real_provider_calls_this_phase"] == 0
    assert payload["repairs_json"] is False
    assert payload["treated_as_transport"] is False
    assert payload["structured_prefix"]["complete_record_count"] == 108
    assert payload["output_composition"]["provider_thinking_tokens"] == 21911
    blocks = payload["http_envelope"].get("content_blocks") or []
    assert all("thinking_text" not in block for block in blocks)
    assert all(int(block.get("thinking_chars") or 0) == 0 for block in blocks)


def test_decision_and_isolation(facts):
    decision = json.loads(
        (REAL_AUDIT / "source_analysis_output_bounding_architecture_decision.json").read_text(
            encoding="utf-8"
        )
    )
    isolation = json.loads(
        (REAL_AUDIT / "source_analysis_forensic_vs_publication_isolation.json").read_text(
            encoding="utf-8"
        )
    )
    report = (REAL_AUDIT / Path(report_path(PROJECT_NAME).name)).read_text(
        encoding="utf-8"
    )
    assert decision["selected_architecture"] == SELECTED_ARCHITECTURE
    assert decision["real_provider_call_authorized_next"] is False
    assert isolation["sortie"]["ok"] is True
    assert "REAL PROVIDER CALL AUTHORIZED NEXT =" in report
    assert "NO" in report
    assert "max_tokens" in report
    assert facts["result"] in {"PASS", "PARTIAL"}
    assert facts["determinism"]["identical"] is True
