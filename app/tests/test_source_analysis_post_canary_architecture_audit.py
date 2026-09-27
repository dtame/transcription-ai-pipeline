"""Phase 3B.7.7A.6 — artefacts d'audit offline. 0 réseau. 0 WIN001."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_hybrid.constants import HARD_MAX_INPUT_TOKENS, TARGET_INPUT_TOKENS
from app.source_analysis_post_canary_architecture.constants import (
    PHASE,
    PROJECT_NAME,
    PROTECTED_EVIDENCE,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    THIRD_WIN001_CALL_AUTHORIZED,
    WINDOW_ANALYSIS_11_REAL_STATUS,
)
from app.source_analysis_post_canary_architecture.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_post_canary_architecture.runner import (
    run_post_canary_architecture_decision,
)
from app.source_analysis_post_canary_architecture.facts import protected_hashes


def _protected_hashes() -> dict[str, str]:
    return protected_hashes(PROJECT_NAME)


REAL_AUDIT = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation\audit"
)
PROTECTED_BEFORE = _protected_hashes()


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOfflineGuards:
    def test_package_has_no_network_imports(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert THIRD_WIN001_CALL_AUTHORIZED is False


class TestAuditArtifacts:
    def test_real_project_offline_artifacts_deterministic(self):
        first = run_post_canary_architecture_decision(PROJECT_NAME)
        assert first["real_provider_calls"] == 0
        assert first["third_win001_call_authorized"] is False
        assert first["window_analysis_1_1_real_status"] == WINDOW_ANALYSIS_11_REAL_STATUS
        assert first["determinism"]["identical"] is True
        simulations = json.loads(
            (REAL_AUDIT / "source_analysis_post_canary_window_size_simulations.json").read_text(
                encoding="utf-8"
            )
        )
        costs = json.loads(
            (REAL_AUDIT / "source_analysis_post_canary_architecture_cost_scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        consolidation = json.loads(
            (REAL_AUDIT / "source_analysis_post_canary_consolidation_scaling.json").read_text(
                encoding="utf-8"
            )
        )
        options = json.loads(
            (REAL_AUDIT / "source_analysis_post_canary_architecture_options.json").read_text(
                encoding="utf-8"
            )
        )
        decision = json.loads(
            (REAL_AUDIT / "source_analysis_post_canary_architecture_decision.json").read_text(
                encoding="utf-8"
            )
        )
        report = (
            REAL_AUDIT / "PHASE_3B77A6_POST_CANARY_ARCHITECTURE_DECISION_REPORT.md"
        ).read_text(encoding="utf-8")
        assert simulations["schema_version"] == SCHEMA_VERSION
        assert simulations["phase"] == PHASE
        assert simulations["real_provider_calls"] == 0
        assert simulations["production_planner_unchanged"] is True
        assert simulations["production_target"] == TARGET_INPUT_TOKENS
        assert simulations["production_hard_max"] == HARD_MAX_INPUT_TOKENS
        current = simulations["current_three_window"]
        assert current["window_count"] == 3
        assert current["coverage"]["every_present_src_owned_once"] is True
        assert current["coverage"]["duplicate_owned_src"] == []
        assert current["coverage"]["missing_src"] == []
        assert current["coverage"]["source_order_preserved"] is True
        assert len(simulations["candidates"]) >= 7
        for row in simulations["candidates"]:
            if not row.get("feasible"):
                continue
            assert row["coverage"]["every_present_src_owned_once"] is True
            assert row["coverage"]["duplicate_owned_src"] == []
            assert row["prompt_version"] == "window-analysis-1.1"
            assert row["context_src_refs_empty"] is True
        assert costs["historical_spend"]["call_2_usd"] == "UNKNOWN"
        assert costs["historical_spend"]["call_2_counted_as_zero"] is False
        assert costs["historical_spend"]["unknown_is_not_zero"] is True
        assert consolidation["guard"] == 80000
        assert consolidation["capacity_signaling"]["exists"] is True
        assert any(option["name"] == SELECTED_ARCHITECTURE for option in options["options"])
        assert decision["selected_architecture"] == SELECTED_ARCHITECTURE
        assert decision["third_win001_call_authorized"] is False
        assert decision["real_call_authorization"] is False
        assert decision["parameters"]["max_output"] == 32000
        assert decision["parameters"]["production_planner_unchanged"] is True
        assert decision["parameters"]["window_prompt"] == "window-analysis-1.1"
        assert decision["canonical_sourcemap"] == "UNCHANGED"
        assert decision["source_map"] == "NOT PUBLISHED"
        assert "REAL PROVIDER CALLS =" in report
        assert "THIRD WIN001 CALL =" in report
        assert "NOT AUTHORIZED" in report
        assert "UNVALIDATED" in report
        assert SELECTED_ARCHITECTURE in report
        assert first["result"] in {"PASS", "PARTIAL"}
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
        for rel in PROTECTED_EVIDENCE:
            path = audit_dir(PROJECT_NAME) / Path(rel).name
            if path.is_file():
                assert sha256_of_file(path) == PROTECTED_BEFORE[rel]
