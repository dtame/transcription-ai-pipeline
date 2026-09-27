"""Phase 3B.7.7A.25 — post-A.24 metadata architecture. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.source_analysis.models import IDEA_KINDS
from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v3.constants import WINDOW_ANALYSIS_PROMPT_VERSION_V132
from app.source_analysis_local_v3.e2e import run_direct_e2e, run_hierarchical_e2e
from app.source_analysis_local_v3.prompt import build_window_system_prompt_v132
from app.source_analysis_v3_a25_forensics.constants import (
    A19_STATUS,
    A21_STATUS,
    A22_STATUS,
    A23_STATUS,
    A24_STATUS_UNCHANGED,
    FUTURE_REAL_CALL_AUTHORIZED,
    I44_CLASSIFICATION,
    IMPLEMENTATION_SCOPE,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_CHANGED,
    SELECTED_ARCHITECTURE,
    SEMANTIC_COUNTERFACTUAL,
    SEMANTIC_REVIEW_STATUS,
    WIN004_RETRY_AUTHORIZED,
)
from app.source_analysis_v3_a25_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v3_a25_forensics.replay import replay_a24_offline
from app.source_analysis_v3_a25_forensics.runner import build_bundle


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOffline:
    def test_package_offline_and_unwired(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_WINDOW_CALLS == 0
        assert WIN004_RETRY_AUTHORIZED is False
        assert FUTURE_REAL_CALL_AUTHORIZED is False
        assert A19_STATUS == "FAIL"
        assert A21_STATUS == "PASS"
        assert A22_STATUS == "FAIL"
        assert A23_STATUS == "PASS"
        assert A24_STATUS_UNCHANGED == "FAIL"
        assert SCHEMA_CHANGED is False
        assert SELECTED_ARCHITECTURE == "GLOBALIZE_IDEA_SUBTYPE"
        assert IMPLEMENTATION_SCOPE == "DESIGN_ONLY"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert PRODUCTION_PLANNER_VERSION == PLANNER_VERSION == "window-planner-v2.0"
        assert not source_map_path(PROJECT_NAME).is_file()
        assert "example" not in IDEA_KINDS


class TestReplayAndDecision:
    def test_a24_remains_invalid_and_architecture_is_selected(self):
        replay = replay_a24_offline(PROJECT_NAME)
        assert replay["structured_parse"] == "PASS"
        assert replay["v3_decoder"] == "FAIL"
        assert replay["evidence_modified"] is False
        assert replay["normalized"] is False
        assert any("example" in err for err in replay["replay_errors"])
        bundle = build_bundle(tests="unit")
        header = bundle["header"]
        assert header["a24_status"] == "FAIL"
        assert header["real_provider_calls"] == 0
        assert header["real_window_calls"] == 0
        assert header["result"] == "PARTIAL"
        inventory = bundle["inventory"]
        assert inventory["total_latent_root_violations"] == 1
        assert inventory["total_cascade_violations"] == 0
        assert inventory["replaces_production_fail_fast"] is False
        assert inventory["mutated_transport"] is False
        codes = {row["code"] for row in inventory["root_violations"]}
        assert codes == {"metadata_or_kind_payload"}
        assert bundle["src_audit"]["malformed_lexical_refs"] == []
        assert bundle["handle_gate"]["handle_gate_pass"] is True
        assert header["numeric_link_regression"] == 0
        i44 = bundle["i44"]
        assert i44["raw"]["h"] == "I44"
        assert i44["raw"]["m"] == ["example", "supporting"]
        assert i44["classification"] == I44_CLASSIFICATION
        assert i44["duplicate_example_check"]["valid_example_for_same_material"] is True
        assert i44["mutated_payload"] is False
        meta = bundle["metadata"]
        assert meta["m_overloaded"] is True
        assert meta["idea_subtype_necessity"]["required_locally"] is False
        assert bundle["semantic"]["status"] == SEMANTIC_REVIEW_STATUS
        assert bundle["semantic"]["unsupported_content"] == 0
        assert bundle["semantic"]["semantic_counterfactual"] == SEMANTIC_COUNTERFACTUAL
        assert bundle["coverage"]["verified_semantic_src_coverage_pct"] == 23.05
        assert bundle["coverage"]["beginning"] is True
        assert bundle["coverage"]["middle"] is True
        assert bundle["coverage"]["end"] is True
        assert bundle["coverage"]["major_ideas_missing"] == 1
        assert bundle["coverage"]["major_ideas_partial"] == 1
        delta = bundle["delta"]
        assert (
            delta["major_idea_delta"]["missing_idea_automated"]["completely_absent"]
            is False
        )
        assert delta["prompt_1_3_2_effectiveness"]["reliably_enforced"] is False
        assert bundle["architecture"]["selected"] == "GLOBALIZE_IDEA_SUBTYPE"
        assert bundle["architecture"]["v4_design_written"] is False
        assert bundle["policy"]["status"] == "DEFINED"
        assert bundle["policy"]["do_not_use_raw_coverage_threshold"] is True
        future = bundle["future"]
        assert future["future_real_call_authorized"] is False
        assert future["future_real_call_ready"] is False
        assert future["win004_retry_authorized"] is False
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V132 == "window-analysis-1.3.2"
        prompt = build_window_system_prompt_v132("en")
        assert 'Never use "example" as an IDEA kind' in prompt


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
    assert REAL_PROJECT.joinpath("analysis", "windows", "WIN004").exists() is False
    assert REAL_PROJECT.joinpath("analysis", "windows", "WIN001").exists() is False
