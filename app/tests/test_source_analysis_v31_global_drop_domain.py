"""Phase 3B.7.7A.41 — FakeAI / offline. 0 réseau. 0 consolidation réelle."""

from __future__ import annotations

import hashlib
import json

import pytest

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_drop_domain.analysis import (
    inspect_handles_including_drop,
    smallest_hardening_decision,
)
from app.source_analysis_v31_global_drop_domain.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    A39_STATUS_PRESERVED,
    A40_FIXTURE_HASH,
    A40_OUTPUT_TOKENS,
    A40_PREDICTED_OUTPUT,
    A40_PROMPT_HASH,
    A40_RAW_SHA256,
    A40_REQUEST_ID,
    A40_ROOT_VALIDATOR_ERROR,
    A40_STATUS_PRESERVED,
    A40_VIOLATING_ID,
    DROP_DOMAIN,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    NEXT_PROMPT_VERSION,
    OLD_PROMPT_VERSION,
    OLD_TRANSPORT_VERSION,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    READY_FOR_COMPACT_GLOBAL_REAL_CALL_PREFLIGHT,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_CHANGED,
    SECOND_COMPACT_CONTRACT_CANARY_REQUIRED,
    V20_SCHEMA_HASH,
)
from app.source_analysis_v31_global_drop_domain.estimator import (
    a40_estimator_audit,
    revised_production_budget,
)
from app.source_analysis_v31_global_drop_domain.evidence import (
    extract_a40_text_and_json,
    read_a40_raw_bytes,
    verify_a40_identity,
)
from app.source_analysis_v31_global_drop_domain.fakeai import (
    NON_IDEA_DROP_CASES,
    catalog_fakeai_cases,
    interpret_next_contract,
    valid_deferred_relation_transport,
    with_non_idea_drop,
)
from app.source_analysis_v31_global_drop_domain.gate import publication_eligibility
from app.source_analysis_v31_global_drop_domain.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_drop_domain.policy import local_object_kind_policy
from app.source_analysis_v31_global_drop_domain.prompt_v201 import prompt_v201_bundle
from app.source_analysis_v31_global_drop_domain.replay import (
    replay_a40_counterfactual,
    replay_a40_frozen,
)
from app.source_analysis_v31_global_output_architecture.membership import (
    derived_src_union,
    validate_global_transport_v20,
)
from app.source_analysis_v31_global_output_architecture.prompt_v20 import prompt_v20_bundle
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    measure_global_schema_v20,
)
from app.source_analysis_v31_global_v20_grammar_canary.fixture import (
    build_synthetic_fixture,
    expected_valid_transport_v20,
    fixture_hash,
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestHistoricalFreeze:
    def test_a34_through_a40_remain_immutable(self):
        assert A34_STATUS_PRESERVED == "PASS"
        assert A35_STATUS_PRESERVED == "FAIL"
        assert A36_STATUS_PRESERVED == "PASS"
        assert A37_STATUS_PRESERVED == "PASS"
        assert A38_STATUS_PRESERVED == "FAIL"
        assert A39_STATUS_PRESERVED == "PASS"
        assert A40_STATUS_PRESERVED == "FAIL"
        assert PHASE == "3B.7.7A.41"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO"
        assert READY_FOR_COMPACT_GLOBAL_REAL_CALL_PREFLIGHT == "NO"
        assert not source_map_path(PROJECT_NAME).is_file()

    def test_schema_2_0_and_prompt_2_0_byte_identity(self):
        measured = measure_global_schema_v20()
        prompt = prompt_v20_bundle()
        assert measured["raw_bytes"] == 1588
        assert measured["adapted_bytes"] == 1836
        assert measured["hash"] == V20_SCHEMA_HASH
        assert SCHEMA_CHANGED is False
        assert prompt["prompt_version"] == OLD_PROMPT_VERSION
        assert prompt["combined_sha256"] == A40_PROMPT_HASH
        assert fixture_hash() == A40_FIXTURE_HASH
        assert OLD_TRANSPORT_VERSION == "global-consolidation-transport-2.0"
        next_prompt = prompt_v201_bundle()
        assert next_prompt["prompt_version"] == NEXT_PROMPT_VERSION
        assert next_prompt["previous_prompt_mutated"] is False
        assert next_prompt["combined_sha256"] != A40_PROMPT_HASH


class TestA40Replay:
    def test_exact_a40_replay_and_root_failure(self):
        replay = replay_a40_frozen()
        assert replay["identity"]["ok"] is True
        assert replay["raw_immutable"] is True
        assert replay["structured_parse"] == "PASS"
        assert replay["decoder"] == "PASS"
        assert replay["handle_validation"] == "PASS"
        assert replay["idea_accountability_coverage"] == 100.0
        assert replay["derived_src"] == "PASS"
        assert replay["global_validator"] == "FAIL"
        assert replay["canonical_reconstruction"] == "PASS"
        assert replay["canonical_validation"] == "PASS"
        assert replay["deterministic_replay"] == "PASS"
        assert replay["semantic_fixture_review"] == "PASS"
        assert replay["root_error_reproduced"] is True
        assert A40_ROOT_VALIDATOR_ERROR in replay["validator_errors"]
        assert replay["violating_drop"]["id"] == A40_VIOLATING_ID
        assert replay["violating_drop"]["kind"] == "RELATION"
        assert replay["violating_drop"]["reason"] == "transport_artifact"
        vs = replay["provider_success_vs_contract_failure"]
        assert vs["provider_grammar"] == "SUCCESS"
        assert vs["global_contract_validation"] == "FAIL"
        assert replay["a40_status_preserved"] == "FAIL"

    def test_a40_raw_immutability(self):
        raw = read_a40_raw_bytes()
        assert hashlib.sha256(raw).hexdigest() == A40_RAW_SHA256
        text, parsed, raw2 = extract_a40_text_and_json()
        assert raw2 == raw
        assert "SYN:L001" in text
        assert isinstance(parsed, dict)
        identity = verify_a40_identity()
        assert identity["request_id"] == A40_REQUEST_ID
        assert identity["raw_immutable"] is True

    def test_drop_only_counterfactual(self):
        result = replay_a40_counterfactual()
        assert result["original_a40_status"] == "FAIL"
        assert result["a40_remains_fail"] is True
        assert result["repaired_original"] is False
        assert result["removed_only"] == A40_VIOLATING_ID
        assert result["global_validator"] == "PASS"
        assert result["structured_parse"] == "PASS"
        assert result["decoder"] == "PASS"
        assert result["handle_validation"] == "PASS"
        assert result["canonical_reconstruction"] == "PASS"
        assert result["canonical_validation"] == "PASS"
        assert result["sole_technical_root"] is True
        assert result["a40_sole_technical_root"] == "NON_IDEA_IN_IDEA_DROP_DOMAIN"


class TestDropDomain:
    def test_idea_only_drop_domain_and_deferred_relation(self):
        policy = local_object_kind_policy()
        assert policy["drop_domain"] == DROP_DOMAIN
        assert policy["kinds"]["RELATION"]["treatment"] == "DEFERRED"
        assert policy["kinds"]["TOPIC"]["drop"] == "FORBIDDEN"
        payload = valid_deferred_relation_transport()
        fixture = build_synthetic_fixture()
        result = validate_global_transport_v20(
            payload,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            local_kind_by_input=fixture.kind_by_input,
        )
        assert result["ok"] is True
        assert result["exact_set_equality"] is True
        assert "SYN:L001" not in json.dumps(payload)
        interpreted = interpret_next_contract(payload, signature="test-deferred")
        assert interpreted["global_validator"] == "PASS"
        assert interpreted["set_equality"] is True
        assert interpreted["idea_disposition_coverage"] == 100.0

    @pytest.mark.parametrize("name,local_id,kind", NON_IDEA_DROP_CASES)
    def test_non_idea_in_drop_rejected(self, name, local_id, kind):
        payload = with_non_idea_drop(local_id)
        fixture = build_synthetic_fixture()
        result = validate_global_transport_v20(
            payload,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            local_kind_by_input=fixture.kind_by_input,
        )
        assert result["ok"] is False
        assert any("is not a local IDEA" in item for item in result["errors"])
        handles = inspect_handles_including_drop(
            payload,
            allowed_input_ids=set(fixture.allowed_input_ids),
            kind_by_input=fixture.kind_by_input,
        )
        assert handles["handle_validation"] == "FAIL"
        interpreted = interpret_next_contract(payload, signature=f"test-{name}")
        assert interpreted["next_global_validator"] == "FAIL"
        assert interpreted["publication"]["publication_eligible"] is False
        assert interpreted["publication"]["blocked_because_invalid_transport"] is True
        assert kind == fixture.kind_by_input[local_id]

    def test_member_drop_disjoint_and_derived_src(self):
        fixture = build_synthetic_fixture()
        payload = expected_valid_transport_v20()
        result = validate_global_transport_v20(
            payload,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            local_kind_by_input=fixture.kind_by_input,
        )
        members = []
        for idea in payload["i"]:
            members.extend(idea["m"])
        drops = [row["i"] for row in payload["drop"]]
        assert set(members) & set(drops) == set()
        assert set(fixture.idea_input_ids) == set(members) | set(drops)
        assert result["exact_set_equality"] is True
        derived = derived_src_union(["SYN:I002", "SYN:I003"], fixture.src_by_input)
        assert derived == ["SRC998103", "SRC998106"]

    def test_invalid_transport_blocks_publication_even_if_reconstruction_passes(self):
        replay = replay_a40_frozen()
        assert replay["canonical_reconstruction"] == "PASS"
        assert replay["global_validator"] == "FAIL"
        gate = publication_eligibility(
            global_validator_ok=False,
            canonical_reconstruction_ok=True,
        )
        assert gate["publication_eligible"] is False
        assert gate["reconstruction_ok_is_insufficient"] is True
        assert gate["blocked_because_invalid_transport"] is True

    def test_fakeai_catalog(self):
        catalog = catalog_fakeai_cases()
        assert catalog["valid_passes"] is True
        assert catalog["all_negatives_fail"] is True
        assert catalog["valid_deferred_relation"]["relation_absent_from_output"] is True


class TestEstimatorAndHardening:
    def test_output_estimator_calibration_and_286(self):
        audit = a40_estimator_audit()
        assert audit["predicted"] == A40_PREDICTED_OUTPUT
        assert audit["actual"] == A40_OUTPUT_TOKENS
        assert audit["do_not_use_generic_4_chars_per_token_for_provider_json"] is True
        assert audit["do_not_scale_28735_by_1_286"] is True
        budget = revised_production_budget()
        assert budget["naive_scale_rejected"] is True
        assert budget["max_output_unchanged"] == PRODUCTION_MAX_OUTPUT_TOKENS == 48000
        distinct = budget["scenarios"]["all_distinct_286"]
        assert distinct["ideas"] == 286
        assert distinct["chars"] > 0
        assert budget["p50_expected"] > 0
        assert budget["hard_planning"] > 0
        assert "output_risk" in budget
        assert READY_FOR_COMPACT_GLOBAL_REAL_CALL_PREFLIGHT == "NO"

    def test_smallest_hardening_versions_prompt_not_schema(self):
        decision = smallest_hardening_decision()
        assert decision["next_prompt"] == "global-consolidation-2.0.1"
        assert decision["next_transport"] == "global-consolidation-transport-2.0"
        assert decision["schema_changed"] is False
        assert decision["new_grammar_canary_required"] is False
        assert SECOND_COMPACT_CONTRACT_CANARY_REQUIRED is True
        prompt = prompt_v201_bundle()
        assert "LOCAL IDEA HANDLES ONLY" in prompt["system"]
        assert "Local RELATION hints are deferred" in prompt["system"]


class TestOfflineGuards:
    def test_package_offline_and_unwired(self):
        assert_offline_package()
        assert_analyzer_not_wired()

    def test_network_isolation_constants(self):
        from app.source_analysis_v31_global_drop_domain.offline import (
            package_imports_network_clients,
            package_invokes_provider,
        )

        assert package_imports_network_clients() == []
        assert package_invokes_provider() == []
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
