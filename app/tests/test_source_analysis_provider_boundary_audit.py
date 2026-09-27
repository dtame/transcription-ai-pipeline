"""Phase 3B.7.7A.5 — artefacts d'audit offline. 0 réseau. 0 WIN001."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_provider_boundary.constants import (
    PHASE,
    PROJECT_NAME,
    PROTECTED_EVIDENCE,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    RESULT,
    SCHEMA_VERSION,
    THIRD_WIN001_CALL_AUTHORIZED,
    WINDOW_ANALYSIS_11_REAL_STATUS,
)
from app.source_analysis_provider_boundary.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
    package_imports_network_clients,
    package_invokes_provider,
)
from app.source_analysis_provider_boundary.runner import run_provider_boundary_review
def _protected_hashes() -> dict[str, str]:
    audit = audit_dir(PROJECT_NAME)
    hashes: dict[str, str] = {}
    for rel in PROTECTED_EVIDENCE:
        path = audit / Path(rel).name
        if path.is_file():
            hashes[rel] = sha256_of_file(path)
    return hashes


REAL_AUDIT = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation\audit"
)
PROTECTED_BEFORE = _protected_hashes()


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOfflineGuards:
    def test_package_has_no_network_imports(self):
        assert package_imports_network_clients() == []
        assert package_invokes_provider() == []
        assert_offline_package()
        assert_analyzer_not_wired()

    def test_phase_authorizes_zero_calls(self):
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert THIRD_WIN001_CALL_AUTHORIZED is False


class TestAuditArtifacts:
    def test_real_project_offline_artifacts_deterministic(self):
        first = run_provider_boundary_review(PROJECT_NAME)
        assert first["real_provider_calls"] == 0
        diagnosis = json.loads(
            (REAL_AUDIT / "source_analysis_airesponseerror_provider_boundary_diagnosis.json").read_text(
                encoding="utf-8"
            )
        )
        matrix = json.loads(
            (REAL_AUDIT / "source_analysis_provider_failure_forensic_matrix.json").read_text(
                encoding="utf-8"
            )
        )
        architecture = json.loads(
            (REAL_AUDIT / "source_analysis_provider_response_boundary_architecture.json").read_text(
                encoding="utf-8"
            )
        )
        two = json.loads(
            (REAL_AUDIT / "source_analysis_win001_two_call_evidence_review.json").read_text(
                encoding="utf-8"
            )
        )
        report = (REAL_AUDIT / "PHASE_3B77A5_AIRESPONSEERROR_PROVIDER_BOUNDARY_FORENSICS_ARCHITECTURE_REVIEW_REPORT.md").read_text(
            encoding="utf-8"
        )
        assert diagnosis["schema_version"] == SCHEMA_VERSION
        assert diagnosis["phase"] == PHASE
        assert diagnosis["result"] == RESULT
        assert diagnosis["real_provider_calls_this_phase"] == 0
        assert diagnosis["third_win001_call_authorized"] is False
        assert diagnosis["call_2_exact_sub_condition"] == "UNKNOWN"
        assert diagnosis["window_analysis_1_1_real_status"] == WINDOW_ANALYSIS_11_REAL_STATUS
        assert diagnosis["source_map_present"] is False
        assert diagnosis["project_state"]["not_success"] is True
        assert diagnosis["integrity"]["prompt_1_0_unchanged"] is True
        assert diagnosis["integrity"]["prompt_1_1_unchanged"] is True
        assert diagnosis["integrity"]["max_output_unchanged"] is True
        assert diagnosis["integrity"]["clean_unchanged"] is True
        assert diagnosis["secrets_included"] is False
        assert matrix["real_provider_calls_this_phase"] == 0
        assert len(matrix["rows"]) >= 8
        assert architecture["principle"]["adopted"] is True
        assert architecture["offline_replay"]["repairs_json"] is False
        assert two["third_win001_call_authorized"] is False
        assert two["invented_missing_values"] is False
        assert two["window_analysis_1_1_real_status"] == "UNVALIDATED_REAL"
        assert "THIRD WIN001 CALL AUTHORIZED =" not in report or "NO" in report
        assert "THIRD WIN001 CALL =" in report
        assert "NOT AUTHORIZED" in report
        assert "UNVALIDATED" in report
        assert "0" in report
        after = _protected_hashes()
        assert after == PROTECTED_BEFORE
        win001 = Path(
            r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
            r"\analysis\windows\WIN001"
        )
        assert not (win001 / "transport.json").exists()
        assert not (win001 / "result.json").exists()
        source_map = Path(
            r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
            r"\analysis\source_map.json"
        )
        assert not source_map.exists()
