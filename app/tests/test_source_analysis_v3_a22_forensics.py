"""Phase 3B.7.7A.23 — forensics A.22 offline. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.source_analysis.models import IDEA_KINDS
from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v3.constants import (
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
    WINDOW_ANALYSIS_PROMPT_VERSION_V132,
)
from app.source_analysis_local_v3.decoder import decode_v3_transport
from app.source_analysis_local_v3.e2e import run_direct_e2e, run_hierarchical_e2e
from app.source_analysis_local_v3.fixtures import v3_success_transport
from app.source_analysis_local_v3.prompt import (
    build_window_system_prompt_v131,
    build_window_system_prompt_v132,
)
from app.source_analysis.errors import WindowTransportValidationError
from app.source_analysis_v3_a22_forensics.constants import (
    A22_STATUS_UNCHANGED,
    FUTURE_REAL_CALL_AUTHORIZED,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_CHANGED,
    SEMANTIC_COUNTERFACTUAL,
    SEMANTIC_INADEQUACY_ROOT_CAUSE,
    SEMANTIC_REVIEW_STATUS,
    WIN004_RETRY_AUTHORIZED,
)
from app.source_analysis_v3_a22_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v3_a22_forensics.replay import replay_a22_offline
from app.source_analysis_v3_a22_forensics.runner import build_bundle


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
        assert A22_STATUS_UNCHANGED == "FAIL"
        assert SCHEMA_CHANGED is False
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert PRODUCTION_PLANNER_VERSION == PLANNER_VERSION == "window-planner-v2.0"
        assert not source_map_path(PROJECT_NAME).is_file()


class TestReplayAndInventory:
    def test_a22_remains_invalid_and_inventory_is_exhaustive(self):
        replay = replay_a22_offline(PROJECT_NAME)
        assert replay["structured_parse"] == "PASS"
        assert replay["v3_decoder"] == "FAIL"
        assert replay["evidence_modified"] is False
        assert replay["normalized"] is False
        assert any("example" in err for err in replay["replay_errors"])
        bundle = build_bundle(tests="unit")
        header = bundle["header"]
        assert header["a22_status"] == "FAIL"
        assert header["a22_target"] == "WIN004"
        assert header["real_provider_calls"] == 0
        inventory = bundle["inventory"]
        assert inventory["total_latent_root_violations"] == 4
        assert inventory["total_cascade_violations"] == 0
        assert inventory["replaces_production_fail_fast"] is False
        assert inventory["mutated_transport"] is False
        codes = {row["code"] for row in inventory["root_violations"]}
        assert codes == {"metadata_or_kind_payload"}
        assert bundle["src_audit"]["valid_canonical_owned_occurrences"] == 480
        assert bundle["src_audit"]["malformed_lexical_refs"] == []
        assert bundle["handle_gate"]["handle_gate_pass"] is True
        assert header["numeric_link_regression"] == 0
        meta = bundle["metadata"]
        assert meta["invalid_idea_example_count"] == 4
        assert meta["other_metadata_violation_count"] == 0
        assert meta["idea_kind_counts"]["example"] == 4
        assert meta["idea_kind_counts"]["claim"] == 32
        four = bundle["four"]
        assert four["duplication_summary"]["all_four_have_a_matching_example"] is True
        assert four["mutated_payload"] is False
        handles = {row["h"] for row in four["records"]}
        assert handles == {"I19", "I27", "I51", "I53"}
        contract = bundle["contract"]
        assert contract["root_cause"] == "PROMPT_VOCABULARY_AMBIGUITY"
        assert contract["difference_idea_vs_example"][
            "exact_conceptual_distinction_already_exists"
        ] is False
        assert contract["schema_enforcement"]["can_currently_enforce_idea_specific_vocabulary"] is False
        assert contract["schema_changed"] is False
        assert contract["prompt_1_3_2"]["created"] is True
        assert contract["prompt_1_3_2"]["mutates_1_3_1"] is False
        assert bundle["semantic"]["status"] == SEMANTIC_REVIEW_STATUS
        assert bundle["semantic"]["unsupported_content"] == 0
        assert bundle["semantic"]["semantic_counterfactual"] == SEMANTIC_COUNTERFACTUAL
        assert bundle["semantic"]["semantic_inadequacy_root_cause"] == (
            SEMANTIC_INADEQUACY_ROOT_CAUSE
        )
        assert bundle["coverage"]["verified_semantic_src_coverage_pct"] == 32.97
        assert bundle["coverage"]["beginning"] is True
        assert bundle["coverage"]["middle"] is True
        assert bundle["coverage"]["end"] is True
        future = bundle["future"]
        assert future["future_real_call_authorized"] is False
        assert future["future_cache"] == "MISS"
        assert future["identity"]["differs_from_a22_signature"] is True
        assert future["identity"]["prompt_version"] == WINDOW_ANALYSIS_PROMPT_VERSION_V132
        assert future["within_35000"] is True
        assert header["prompt_1_3_1_untouched"] is True
        assert header["prompt_1_3_2_contains_hardening"] is True
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V131 == "window-analysis-1.3.1"


class TestPrompt132AndTypeContract:
    def test_1_3_1_untouched_and_1_3_2_hardens(self):
        old = build_window_system_prompt_v131("en")
        new = build_window_system_prompt_v132("en")
        assert 'Never use "example" as an IDEA kind' not in old
        assert 'Never use "example" as an IDEA kind' in new
        assert "l[] on EXAMPLE remains optional" in new
        assert old != new

    def test_decoder_rejects_idea_example_and_accepts_all_valid_kinds(self):
        payload = v3_success_transport()
        allowed = {"SRC000001"}
        decode_v3_transport(payload, allowed_source_refs=allowed)
        idea = next(item for item in payload["records"] if item["k"] == "IDEA")
        for kind in IDEA_KINDS:
            idea["m"] = [kind, "central"]
            decode_v3_transport(payload, allowed_source_refs=allowed)
        idea["m"] = ["example", "supporting"]
        with pytest.raises(WindowTransportValidationError) as exc:
            decode_v3_transport(payload, allowed_source_refs=allowed)
        assert "example" in str(exc.value)
        example = next(item for item in payload["records"] if item["k"] == "EXAMPLE")
        assert example["k"] == "EXAMPLE"
        assert example["m"] != idea["m"]


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
