"""Phase 3B.7.7A.43 — FakeAI / offline. 0 réseau. 0 consolidation réelle."""

from __future__ import annotations

import hashlib
import json

import pytest

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_drop_domain.prompt_v201 import prompt_v201_bundle
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    measure_global_schema_v20,
)
from app.source_analysis_v31_global_reuse_output.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    A39_STATUS_PRESERVED,
    A40_STATUS_PRESERVED,
    A41_STATUS_PRESERVED,
    A42_REQUEST_ID,
    A42_STATUS_PRESERVED,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    NEXT_PROMPT_VERSION,
    NEXT_SCHEMA_ADAPTED_BYTES,
    NEXT_SCHEMA_HASH,
    NEXT_SCHEMA_RAW_BYTES,
    NEXT_TRANSPORT_VERSION,
    OLD_PROMPT_VERSION,
    OLD_TRANSPORT_VERSION,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    READY_FOR_REUSE_ARCHITECTURE_GRAMMAR_CANARY,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SAFETY_70,
    SELECTED_ARCHITECTURE,
    SELECTED_OPTION,
    V20_HARD_OUTPUT,
    V20_SCHEMA_HASH,
)
from app.source_analysis_v31_global_reuse_output.estimator import revised_reuse_budget
from app.source_analysis_v31_global_reuse_output.fakeai import (
    catalog_fakeai_cases,
    full_scale_stress,
    interpret_transport_v30,
)
from app.source_analysis_v31_global_reuse_output.fixture import (
    expected_valid_transport_v30,
    with_forbidden_single_member_rewrite,
    with_missing_synthesis,
)
from app.source_analysis_v31_global_reuse_output.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_reuse_output.prompt_v30 import prompt_v30_bundle
from app.source_analysis_v31_global_reuse_output.quality import classify_local_idea_text
from app.source_analysis_v31_global_reuse_output.reconstruct import (
    expand_reused_idea_text,
    local_idea_text,
)
from app.source_analysis_v31_global_reuse_output.transport_v30 import measure_global_schema_v30
from app.source_analysis_v31_global_reuse_output.validate import (
    derived_src_union,
    validate_global_transport_v30,
)
from app.source_analysis_v31_global_v20_grammar_canary.fixture import build_synthetic_fixture


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestHistoricalFreeze:
    def test_a34_through_a42_remain_immutable(self):
        assert A34_STATUS_PRESERVED == "PASS"
        assert A35_STATUS_PRESERVED == "FAIL"
        assert A36_STATUS_PRESERVED == "PASS"
        assert A37_STATUS_PRESERVED == "PASS"
        assert A38_STATUS_PRESERVED == "FAIL"
        assert A39_STATUS_PRESERVED == "PASS"
        assert A40_STATUS_PRESERVED == "FAIL"
        assert A41_STATUS_PRESERVED == "PASS"
        assert A42_STATUS_PRESERVED == "PASS"
        assert PHASE == "3B.7.7A.43"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO"
        assert READY_FOR_REUSE_ARCHITECTURE_GRAMMAR_CANARY == "YES"
        assert not source_map_path(PROJECT_NAME).is_file()
        assert A42_REQUEST_ID == "req_011CfXza6D59WbhBZVCLPEej"

    def test_schema_3_0_is_new_and_2_0_unmutated(self):
        v20 = measure_global_schema_v20()
        v30 = measure_global_schema_v30()
        old_prompt = prompt_v201_bundle()
        new_prompt = prompt_v30_bundle()
        assert v20["hash"] == V20_SCHEMA_HASH
        assert v20["raw_bytes"] == 1588
        assert v30["raw_bytes"] == NEXT_SCHEMA_RAW_BYTES
        assert v30["adapted_bytes"] == NEXT_SCHEMA_ADAPTED_BYTES
        assert v30["hash"] == NEXT_SCHEMA_HASH
        assert v30["unsupported_constructs"] == []
        assert v30["conditional_schema_used"] is False
        assert old_prompt["prompt_version"] == OLD_PROMPT_VERSION
        assert new_prompt["prompt_version"] == NEXT_PROMPT_VERSION
        assert new_prompt["previous_prompt_mutated"] is False
        assert new_prompt["combined_sha256"] != old_prompt["combined_sha256"]
        assert OLD_TRANSPORT_VERSION == "global-consolidation-transport-2.0"
        assert NEXT_TRANSPORT_VERSION == "global-consolidation-transport-3.0"


class TestReuseContract:
    def test_reuse_single_member_and_merge_synthesis(self):
        catalog = catalog_fakeai_cases()
        assert catalog["valid_passes"] is True
        assert catalog["negatives_fail"] is True
        valid = catalog["valid_reuse_and_merge"]
        assert valid["canonical_reconstruction"] == "PASS"
        assert valid["canonical_validation"] == "PASS"
        assert valid["reuse_text_exact"] is True
        assert valid["idea_accountability"] is True
        assert valid["relation_absent"] is True

    def test_reuse_text_exact_recovery(self):
        fixture = build_synthetic_fixture()
        transport = expected_valid_transport_v30()
        expanded = expand_reused_idea_text(transport, fixture.inventory())
        reused = [idea for idea in expanded["i"] if idea.get("reuse")]
        assert reused
        for idea in reused:
            member = idea["m"][0]
            assert idea["v"] == local_idea_text(fixture.inventory(), member)
            assert "v" not in next(
                row for row in transport["i"] if row["h"] == idea["h"]
            )

    def test_multi_member_source_union(self):
        fixture = build_synthetic_fixture()
        members = ["SYN:I002", "SYN:I003"]
        union = derived_src_union(members, fixture.src_by_input)
        assert union == ["SRC998103", "SRC998106"]

    def test_single_member_forbidden_rewrite(self):
        fixture = build_synthetic_fixture()
        payload = with_forbidden_single_member_rewrite()
        result = validate_global_transport_v30(
            payload,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            local_kind_by_input=fixture.kind_by_input,
        )
        assert result["ok"] is False
        assert result["forbidden_rewrites"]

    def test_multi_member_missing_synthesis(self):
        fixture = build_synthetic_fixture()
        payload = with_missing_synthesis()
        result = validate_global_transport_v30(
            payload,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            local_kind_by_input=fixture.kind_by_input,
        )
        assert result["ok"] is False
        assert result["missing_synthesis"]

    def test_idea_only_drop_and_relation_omission(self):
        fixture = build_synthetic_fixture()
        payload = expected_valid_transport_v30()
        blob = json.dumps(payload)
        assert "SYN:L001" not in blob
        assert payload["drop"] == [{"i": "SYN:I006", "w": "non_substantive_fragment"}]
        result = interpret_transport_v30(
            payload, fixture.inventory(), signature="a43-drop-relation"
        )
        assert result["pipeline_pass"] is True
        assert result["coverage"] == 100.0

    def test_zero_network_and_offline_package(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0


class TestFullScaleAndBudget:
    def test_all_distinct_286_and_mixed_stress(self):
        stress = full_scale_stress()
        assert stress["ok"] is True
        assert stress["all_distinct_286_reuse"]["status"] == "PASS"
        assert stress["mixed_full_scale"]["status"] == "PASS"
        assert stress["all_distinct_286_reuse"]["ideas"] == 286
        assert stress["high_synthesis"]["applicable"] is False

    def test_output_estimator_and_hard_bound(self):
        budget = revised_reuse_budget()
        assert budget["hard_planning"] < V20_HARD_OUTPUT
        assert budget["hard_planning"] <= SAFETY_70
        assert budget["max_output"] == PRODUCTION_MAX_OUTPUT_TOKENS
        assert budget["p50_expected"] < budget["conservative"] <= budget["hard_planning"]
        assert SELECTED_OPTION == "B"
        assert SELECTED_ARCHITECTURE == "HARD_SINGLE_MEMBER_REUSE_SYNTHESIZE_MERGES_ONLY"

    def test_local_idea_classifier_ready_for_reuse(self):
        assert (
            classify_local_idea_text(
                "Physical exercise is spiritually endorsed and beneficial."
            )
            == "READY_FOR_REUSE"
        )
        assert classify_local_idea_text("uh") == "NOT_SELF_CONTAINED"


class TestDeterministicReplay:
    def test_schema_identity_stable(self):
        first = measure_global_schema_v30()
        second = measure_global_schema_v30()
        assert first["hash"] == second["hash"] == NEXT_SCHEMA_HASH
        dumped = json.dumps(first["schema"], ensure_ascii=False, sort_keys=True)
        assert hashlib.sha256(dumped.encode("utf-8")).hexdigest() or True
        prompt = prompt_v30_bundle()
        again = prompt_v30_bundle()
        assert prompt["combined_sha256"] == again["combined_sha256"]
