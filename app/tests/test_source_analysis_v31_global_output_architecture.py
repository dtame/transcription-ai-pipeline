"""Phase 3B.7.7A.39 — FakeAI / offline. 0 réseau. 0 publication source_map."""

from __future__ import annotations

import hashlib
import json

import pytest

from app.ai.contracts import AIRequest
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_canary_forensics.prompt_v101 import prompt_v101_bundle
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    measure_global_schema_v11,
)
from app.source_analysis_v31_global_output_architecture.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_RAW_TEXT_SHA256,
    A38_REQUEST_ID,
    A38_ROOT_FAILURE,
    A38_STATUS_PRESERVED,
    EXPECTED_IDEA,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MODEL,
    NEXT_PROMPT_VERSION,
    NEXT_SCHEMA_ADAPTED_BYTES,
    NEXT_SCHEMA_HASH,
    NEXT_SCHEMA_RAW_BYTES,
    NEXT_TRANSPORT_VERSION,
    PHASE,
    PHASE_3B_STATUS,
    PROJECT_NAME,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    REAL_CONSOLIDATION_CALLS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    RELATION_QUALITY_TECHNICAL_DEBT,
    THINKING_MODE,
    TRANSPORT_11_32000_FEASIBILITY,
    V11_PROMPT_VERSION,
    V11_TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_output_architecture.estimator import estimate_output
from app.source_analysis_v31_global_output_architecture.evidence import (
    read_a38_raw_bin,
    read_a38_raw_text,
    verify_a38_identity,
)
from app.source_analysis_v31_global_output_architecture.fixture import (
    all_distinct_transport,
    build_full_scale_inventory,
    drop_transport,
    duplicate_member_transport,
    interpret_transport_v20,
    mass_merge_transport,
    missing_member_transport,
    unknown_member_transport,
)
from app.source_analysis_v31_global_output_architecture.forensics import (
    classify_a38_failures,
    inspect_raw_prefix,
    transport_11_complete_output_range,
)
from app.source_analysis_v31_global_output_architecture.gate import pre_call_output_gate
from app.source_analysis_v31_global_output_architecture.membership import (
    derived_src_union,
    validate_global_transport_v20,
)
from app.source_analysis_v31_global_output_architecture.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_output_architecture.prompt_v20 import prompt_v20_bundle
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    measure_global_schema_v20,
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


@pytest.fixture(scope="module")
def inventory():
    return build_full_scale_inventory()


class TestOfflineFreeze:
    def test_package_offline_and_unwired(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_WINDOW_CALLS == 0
        assert REAL_CONSOLIDATION_CALLS == 0
        assert A34_STATUS_PRESERVED == "PASS"
        assert A35_STATUS_PRESERVED == "FAIL"
        assert A36_STATUS_PRESERVED == "PASS"
        assert A37_STATUS_PRESERVED == "PASS"
        assert A38_STATUS_PRESERVED == "FAIL"
        assert PHASE == "3B.7.7A.39"
        assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"
        assert RELATION_QUALITY_TECHNICAL_DEBT == "YES"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO"
        assert THINKING_MODE == "disabled"
        assert MODEL == "claude-sonnet-5"
        assert not source_map_path(PROJECT_NAME).is_file()


class TestA38RawImmutability:
    def test_request_identity_and_hash(self):
        identity = verify_a38_identity()
        assert identity["ok"] is True
        assert identity["request_id"] == A38_REQUEST_ID == "req_011CfWwT6tCwU9aX9cZwvGAW"
        assert identity["repaired"] is False
        assert identity["json_loads_attempted_for_success"] is False
        text = read_a38_raw_text()
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == A38_RAW_TEXT_SHA256
        raw_bin = read_a38_raw_bin()
        assert raw_bin
        second = read_a38_raw_text()
        assert second == text

    def test_max_tokens_root_and_cascade(self):
        failures = classify_a38_failures()
        assert failures["root_failure"] == A38_ROOT_FAILURE == "OUTPUT_TOKEN_BUDGET_EXHAUSTED"
        assert "JSON truncation" in failures["cascade_failures"]
        assert "structured parse FAIL" in failures["cascade_failures"]
        assert failures["repaired"] is False
        assert failures["converted_to_candidate"] is False

    def test_raw_prefix_counts(self):
        prefix = inspect_raw_prefix(read_a38_raw_text())
        assert prefix["label"] == "RAW_PREFIX_FORENSIC_ESTIMATE"
        assert prefix["kind_key_counts"]["TOPIC"] == 42
        assert prefix["kind_key_counts"]["IDEA"] == 281
        assert prefix["complete_objects_by_kind"]["TOPIC"] == 42
        assert prefix["complete_objects_by_kind"]["IDEA"] == 280
        assert prefix["root_r_started"] is False
        assert prefix["root_d_started"] is False
        complete = transport_11_complete_output_range(prefix)
        assert complete["feasibility_32000"] == TRANSPORT_11_32000_FEASIBILITY == "NO"
        assert complete["low"] > 32000


class TestEstimatorAndGate:
    def test_output_estimator_all_distinct_fits_declared_bound(self):
        estimate = estimate_output(topics=67, ideas=286, members_per_idea=1)
        assert estimate["fits_safety"] is True
        assert estimate["fits_max"] is True
        assert estimate["provider_planning_tokens"]["hard"] <= estimate["safety_target"]
        gate = pre_call_output_gate(estimate)
        assert gate["allowed"] is True
        assert "predicted_output" in gate["telemetry_required_after_call"]


class TestInverseMembership:
    def test_286_coverage_all_distinct(self, inventory):
        transport = all_distinct_transport(inventory)
        interpreted = interpret_transport_v20(
            transport, inventory, signature="fakeai-all-distinct"
        )
        assert interpreted["pipeline_pass"] is True
        assert interpreted["validator"]["idea_disposition_coverage"] == 100.0
        assert interpreted["validator"]["silent_drops"] == []
        assert len(transport["i"]) == EXPECTED_IDEA
        assert interpreted["canonical_reconstruction"] == "PASS"
        assert interpreted["canonical_validation"] == "PASS"
        assert interpreted["derived_src_ok"] is True

    def test_mass_merge_traceability(self, inventory):
        transport = mass_merge_transport(inventory)
        interpreted = interpret_transport_v20(
            transport, inventory, signature="fakeai-mass-merge"
        )
        assert interpreted["pipeline_pass"] is True
        assert interpreted["validator"]["exact_set_equality"] is True
        first = transport["i"][0]
        derived = derived_src_union(first["m"], inventory["src_by_input"])
        expected: list[str] = []
        seen: set[str] = set()
        for member in first["m"]:
            for ref in inventory["src_by_input"][member]:
                if ref not in seen:
                    seen.add(ref)
                    expected.append(ref)
        assert derived == expected

    def test_drop_coverage(self, inventory):
        transport = drop_transport(inventory)
        validated = validate_global_transport_v20(
            transport,
            idea_input_ids=inventory["idea_input_ids"],
            allowed_input_ids=inventory["allowed_input_ids"],
            local_kind_by_input=inventory["kind_by_input"],
        )
        assert validated["ok"] is True
        assert len(transport["drop"]) == 2
        assert validated["idea_disposition_coverage"] == 100.0

    def test_unknown_member_fails(self, inventory):
        transport = unknown_member_transport(inventory)
        validated = validate_global_transport_v20(
            transport,
            idea_input_ids=inventory["idea_input_ids"],
            allowed_input_ids=inventory["allowed_input_ids"],
            local_kind_by_input=inventory["kind_by_input"],
        )
        assert validated["ok"] is False
        assert any(item.startswith("UNKNOWN_MEMBER:") for item in validated["errors"])

    def test_duplicate_member_fails(self, inventory):
        transport = duplicate_member_transport(inventory)
        validated = validate_global_transport_v20(
            transport,
            idea_input_ids=inventory["idea_input_ids"],
            allowed_input_ids=inventory["allowed_input_ids"],
            local_kind_by_input=inventory["kind_by_input"],
        )
        assert validated["ok"] is False
        assert any("DUPLICATE_MEMBERSHIP:" in item for item in validated["errors"])

    def test_missing_member_fails(self, inventory):
        transport = missing_member_transport(inventory)
        validated = validate_global_transport_v20(
            transport,
            idea_input_ids=inventory["idea_input_ids"],
            allowed_input_ids=inventory["allowed_input_ids"],
            local_kind_by_input=inventory["kind_by_input"],
        )
        assert validated["ok"] is False
        assert any(item.startswith("SILENT_DROP:") for item in validated["errors"])


class TestSchemaAndPrompt:
    def test_new_schema_identity(self):
        measured = measure_global_schema_v20()
        assert measured["raw_bytes"] == NEXT_SCHEMA_RAW_BYTES == 1588
        assert measured["adapted_bytes"] == NEXT_SCHEMA_ADAPTED_BYTES == 1836
        assert measured["hash"] == NEXT_SCHEMA_HASH
        assert measured["transport_version"] == NEXT_TRANSPORT_VERSION
        assert measured["unsupported_constructs"] == []
        assert measured["sent_to_anthropic"] is False
        v11 = measure_global_schema_v11()
        assert v11["raw_bytes"] == 1182
        assert v11["hash"].startswith("c98e57c3")
        old = prompt_v101_bundle()
        new = prompt_v20_bundle()
        assert old["prompt_version"] == V11_PROMPT_VERSION
        assert new["prompt_version"] == NEXT_PROMPT_VERSION
        assert old["combined_sha256"] != new["combined_sha256"]
        assert V11_TRANSPORT_VERSION == "global-consolidation-transport-1.1"


class TestFakeAI:
    def test_fakeai_returns_all_distinct(self, inventory):
        transport = all_distinct_transport(inventory)
        engine = FakeAIEngine(
            script=[
                FakeReply(
                    text=json.dumps(transport, ensure_ascii=False),
                    parsed=transport,
                    finish_reason="end_turn",
                    input_tokens=100,
                    output_tokens=200,
                    thinking_tokens=0,
                )
            ],
            retry_policy=no_delay_policy(max_attempts=1),
        )
        response = engine.generate(AIRequest(prompt="offline compact transport"))
        payload = json.loads(response.text)
        assert engine.provider_name == "fake"
        interpreted = interpret_transport_v20(
            payload, inventory, signature="fakeai-engine"
        )
        assert interpreted["pipeline_pass"] is True
