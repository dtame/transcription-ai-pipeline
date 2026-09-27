"""Phase 3B.7.7A.20 — forensics A.19 offline. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v3.constants import (
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
)
from app.source_analysis_local_v3.e2e import run_direct_e2e, run_hierarchical_e2e
from app.source_analysis_local_v3.source_refs import SRC_CANONICAL_PATTERN
from app.source_analysis_v3_a19_forensics.constants import (
    A19_FIRST_DECODER_FAILURE,
    A19_MALFORMED_SRC,
    A19_STATUS_UNCHANGED,
    EXAMPLE_POLICY,
    FUTURE_REAL_CALL_AUTHORIZED,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_CHANGED,
    SEMANTIC_REVIEW_STATUS,
    SRC_FAILURE_CLASSIFICATION,
    V3_HANDLE_ARCHITECTURE,
    WIN001_RETRY_AUTHORIZED,
)
from app.source_analysis_v3_a19_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v3_a19_forensics.replay import replay_a19_offline
from app.source_analysis_v3_a19_forensics.runner import build_bundle


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOffline:
    def test_package_offline_and_unwired(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_WINDOW_CALLS == 0
        assert WIN001_RETRY_AUTHORIZED is False
        assert FUTURE_REAL_CALL_AUTHORIZED is False
        assert A19_STATUS_UNCHANGED == "FAIL"
        assert SCHEMA_CHANGED is False
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert PRODUCTION_PLANNER_VERSION == PLANNER_VERSION == "window-planner-v2.0"
        assert not source_map_path(PROJECT_NAME).is_file()


class TestReplayAndInventory:
    def test_a19_remains_invalid_and_inventory_is_exhaustive(self):
        replay = replay_a19_offline(PROJECT_NAME)
        assert replay["structured_parse"] == "PASS"
        assert replay["v3_decoder"] == "FAIL"
        assert replay["evidence_modified"] is False
        assert replay["normalized"] is False
        assert any(A19_MALFORMED_SRC in err for err in replay["replay_errors"])
        bundle = build_bundle(tests="unit")
        header = bundle["header"]
        assert header["a19_status"] == "FAIL"
        assert header["a19_first_decoder_failure"] == A19_FIRST_DECODER_FAILURE
        assert header["real_provider_calls"] == 0
        inventory = bundle["inventory"]
        assert inventory["total_latent_root_violations"] >= 1
        assert inventory["replaces_production_fail_fast"] is False
        assert inventory["mutated_transport"] is False
        codes = {row["code"] for row in inventory["root_violations"]}
        assert "src_wrong_case" in codes or "src_malformed" in codes
        src_audit = bundle["src_audit"]
        assert src_audit["canonical_pattern"] == SRC_CANONICAL_PATTERN
        assert src_audit["src000609_is_only_casing_error"] is True
        assert src_audit["valid_canonical_owned_occurrences"] >= 300
        assert src_audit["unknown_well_formed_refs"] == []
        assert src_audit["out_of_window_refs"] == []
        assert src_audit["duplicate_refs_within_records"] == []
        assert src_audit["normalized"] is False
        assert bundle["src_contract"]["python_must_not_normalize"] is True
        assert bundle["src_contract"]["src_failure_classification"] == (
            SRC_FAILURE_CLASSIFICATION
        )
        assert bundle["examples"]["settled_policy"] == EXAMPLE_POLICY
        assert bundle["examples"]["record_87_violates_settled_contract"] is False
        rec87 = bundle["examples"]["record_87"]
        assert rec87 is not None
        assert rec87["l"] == []
        assert bundle["handle_gate"]["handle_gate_pass"] is True
        assert header["v3_handle_architecture"] == V3_HANDLE_ARCHITECTURE
        assert bundle["semantic"]["status"] == SEMANTIC_REVIEW_STATUS
        assert bundle["semantic"]["validated_candidate"] is False
        assert bundle["semantic"]["a15_target_kind_defect"] == "ELIMINATED"
        assert bundle["coverage"]["verified_semantic_src_coverage_pct"] == 27.11
        assert bundle["coverage"]["verified_distinct_src_refs_raw"] == 325
        future = bundle["future"]
        assert future["future_real_call_authorized"] is False
        assert future["future_cache"] == "MISS"
        assert future["identity"]["differs_from_a19_signature"] is True
        assert future["identity"]["prompt_version"] == WINDOW_ANALYSIS_PROMPT_VERSION_V131
        assert future["within_35000"] is True
        assert header["prompt_1_3_untouched"] is True
        assert header["prompt_1_3_1_contains_hardening"] is True
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V13 == "window-analysis-1.3"


class TestFakeAI:
    def test_direct_hierarchical_and_no_drop(self, tmp_path):
        direct = run_direct_e2e(tmp_path / "d")
        hierarchical = run_hierarchical_e2e(tmp_path / "h")
        assert len(direct.window_results) == 7
        assert len(hierarchical.window_results) == 7
        assert direct.no_drop is True
        assert hierarchical.no_drop is True
        assert direct.source_map is not None
        assert hierarchical.source_map is not None


REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


def test_production_untouched():
    assert REAL_PROJECT.joinpath("analysis", "source_map.json").exists() is False
    assert REAL_PROJECT.joinpath("analysis", "windows", "WIN001").exists() is False
