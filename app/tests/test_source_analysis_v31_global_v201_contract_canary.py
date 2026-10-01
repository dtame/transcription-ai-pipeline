"""Phase 3B.7.7A.42 — FakeAI / offline. 0 réseau. 0 consolidation réelle."""

from __future__ import annotations

import copy
import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_drop_domain.constants import A40_PROMPT_HASH
from app.source_analysis_v31_global_drop_domain.fakeai import (
    NON_IDEA_DROP_CASES,
    with_non_idea_drop,
)
from app.source_analysis_v31_global_drop_domain.gate import publication_eligibility
from app.source_analysis_v31_global_drop_domain.prompt_v201 import prompt_v201_bundle
from app.source_analysis_v31_global_drop_domain.replay import replay_a40_frozen
from app.source_analysis_v31_global_output_architecture.membership import (
    derived_src_union,
    validate_global_transport_v20,
)
from app.source_analysis_v31_global_output_architecture.prompt_v20 import prompt_v20_bundle
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    measure_global_schema_v20,
)
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    AUTHORIZATION_SCOPE as A37_SCOPE,
)
from app.source_analysis_v31_global_v20_grammar_canary.constants import (
    AUTHORIZATION_SCOPE as A40_SCOPE,
)
from app.source_analysis_v31_global_v20_grammar_canary.fixture import (
    build_synthetic_fixture,
    expected_dispositions,
    expected_valid_transport_v20,
    fixture_hash,
)
from app.source_analysis_v31_global_v201_contract_canary.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    A39_STATUS_PRESERVED,
    A40_FIXTURE_HASH,
    A40_STATUS_PRESERVED,
    A41_STATUS_PRESERVED,
    AUTHORIZATION_SCOPE,
    CANARY_MAX_OUTPUT_TOKENS,
    GLOBAL_TRANSPORT_2_0_GRAMMAR_PROOF,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_CONSERVATIVE_OUTPUT_TOKENS,
    PRODUCTION_EXPECTED_OUTPUT_TOKENS,
    PRODUCTION_HARD_PLANNING_TOKENS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PRODUCTION_OUTPUT_RISK,
    PROJECT_NAME,
    PROMPT_VERSION,
    READY_FOR_COMPACT_GLOBAL_REAL_CALL_PREFLIGHT,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    READY_WINDOWS,
    RELATION_HINT_ID,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v201_contract_canary.guard import (
    GlobalGrammarCanaryError,
    OneShotCallGuard,
    reject_real_project_input,
    reject_thinking_enabled,
    reject_wrong_architecture,
    validate_authorization_scope,
)
from app.source_analysis_v31_global_v201_contract_canary.identity import (
    recompute_schema_identity,
    verify_schema_identity,
)
from app.source_analysis_v31_global_v201_contract_canary.payload import (
    build_audited_request,
    estimate_canary_output,
)
from app.source_analysis_v31_global_v201_contract_canary.runner import (
    dry_run_canary,
    run_global_v201_contract_canary,
)
from app.source_analysis_v31_global_v201_contract_canary.type_boundary import (
    classify_a40_root_defect,
    type_boundary_audit,
)
from app.source_analysis_v31_global_v201_contract_canary.validate import (
    interpret_canary_response_v201,
)


def _fake_engine(payload=None):
    transport = payload or expected_valid_transport_v20()
    return FakeAIEngine(
        script=[
            FakeReply(
                text=json.dumps(transport, ensure_ascii=False),
                parsed=transport,
                finish_reason="end_turn",
                input_tokens=120,
                output_tokens=90,
                thinking_tokens=0,
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestHistoricalFreeze:
    def test_a34_through_a41_remain_immutable(self):
        assert A34_STATUS_PRESERVED == "PASS"
        assert A35_STATUS_PRESERVED == "FAIL"
        assert A36_STATUS_PRESERVED == "PASS"
        assert A37_STATUS_PRESERVED == "PASS"
        assert A38_STATUS_PRESERVED == "FAIL"
        assert A39_STATUS_PRESERVED == "PASS"
        assert A40_STATUS_PRESERVED == "FAIL"
        assert A41_STATUS_PRESERVED == "PASS"
        assert PHASE == "3B.7.7A.42"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"
        assert READY_WINDOWS == "7 / 7"
        assert READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO"
        assert READY_FOR_COMPACT_GLOBAL_REAL_CALL_PREFLIGHT == "NO"
        assert GLOBAL_TRANSPORT_2_0_GRAMMAR_PROOF == "PASS"
        assert not source_map_path(PROJECT_NAME).is_file()

    def test_prompt_201_identity_and_schema_unchanged(self):
        measured = measure_global_schema_v20()
        recomputed = recompute_schema_identity()
        prompt_old = prompt_v20_bundle()
        prompt_new = prompt_v201_bundle()
        assert measured["raw_bytes"] == SCHEMA_RAW_BYTES == 1588
        assert measured["adapted_bytes"] == SCHEMA_ADAPTED_BYTES == 1836
        assert measured["hash"] == SCHEMA_HASH
        assert SCHEMA_HASH == (
            "90b99a38ac704d00e1304495da0c757118293e43493ddb7321b3ffb3256d8330"
        )
        assert prompt_old["prompt_version"] == "global-consolidation-2.0"
        assert prompt_old["combined_sha256"] == A40_PROMPT_HASH
        assert prompt_new["prompt_version"] == PROMPT_VERSION == "global-consolidation-2.0.1"
        assert prompt_new["previous_prompt_mutated"] is False
        assert prompt_new["combined_sha256"] != A40_PROMPT_HASH
        assert "LOCAL IDEA HANDLES ONLY" in prompt_new["system"]
        assert "Local RELATION hints are deferred" in prompt_new["system"]
        assert recomputed["matches_a39_constants"] is True
        verified = verify_schema_identity(PROJECT_NAME)
        assert verified["schema_identity"] == "MATCH"
        assert TRANSPORT_VERSION == "global-consolidation-transport-2.0"
        assert THINKING_MODE == "disabled"
        assert PRODUCTION_MAX_OUTPUT_TOKENS == 48000
        assert CANARY_MAX_OUTPUT_TOKENS == 2048
        assert PRODUCTION_EXPECTED_OUTPUT_TOKENS == 34514
        assert PRODUCTION_CONSERVATIVE_OUTPUT_TOKENS == 40362
        assert PRODUCTION_HARD_PLANNING_TOKENS == 41430
        assert PRODUCTION_OUTPUT_RISK == "NEEDS_OUTPUT_REDESIGN"

    def test_a40_historical_replay_unchanged(self):
        replay = replay_a40_frozen()
        assert replay["global_validator"] == "FAIL"
        assert replay["root_error_reproduced"] is True
        assert replay["a40_status_preserved"] == "FAIL"
        assert RELATION_HINT_ID in str(replay.get("validator_errors") or replay)


class TestAuthorizationAndGuard:
    def test_missing_and_wrong_scope_fail_before_network(self):
        with pytest.raises(GlobalGrammarCanaryError):
            validate_authorization_scope(None)
        result = run_global_v201_contract_canary(
            "fixture",
            dry_run=True,
            authorization_scope="WRONG",
        )
        assert result.accepted is False
        assert result.blocked_precall is True
        assert result.engine_generate_attempts == 0

    def test_real_data_and_legacy_scopes_rejected(self):
        for scope in (
            "REAL_GLOBAL_CONSOLIDATION_CANARY",
            A37_SCOPE,
            A40_SCOPE,
            "WIN001_ONLY",
            "GLOBAL_CONSOLIDATION_2_0_TINY_SYNTHETIC_GRAMMAR_CANARY_ONLY",
        ):
            result = run_global_v201_contract_canary(
                "fixture",
                dry_run=True,
                authorization_scope=scope,
            )
            assert result.accepted is False
            assert result.engine_generate_attempts == 0

    def test_pastoral_and_real_normalized_rejected(self):
        with pytest.raises(GlobalGrammarCanaryError):
            reject_real_project_input({"windows": ["WIN001"], "src": "SRC000001"})
        with pytest.raises(GlobalGrammarCanaryError):
            reject_real_project_input({"text": "pastoral_retreat transcript"})

    def test_wrong_architecture_and_thinking_rejected(self):
        with pytest.raises(GlobalGrammarCanaryError):
            reject_thinking_enabled("enabled")
        with pytest.raises(GlobalGrammarCanaryError):
            reject_wrong_architecture(
                model="other",
                prompt_version=PROMPT_VERSION,
                transport_version=TRANSPORT_VERSION,
                schema_hash=SCHEMA_HASH,
            )
        with pytest.raises(GlobalGrammarCanaryError):
            reject_wrong_architecture(
                model="claude-sonnet-5",
                prompt_version="global-consolidation-2.0",
                transport_version=TRANSPORT_VERSION,
                schema_hash=SCHEMA_HASH,
            )
        with pytest.raises(GlobalGrammarCanaryError):
            reject_wrong_architecture(
                model="claude-sonnet-5",
                prompt_version=PROMPT_VERSION,
                transport_version="global-consolidation-transport-1.1",
                schema_hash=SCHEMA_HASH,
            )

    def test_second_generate_rejected(self):
        engine = _fake_engine()
        guard = OneShotCallGuard(max_calls=1)
        fixture = build_synthetic_fixture()
        request = build_audited_request(fixture)["request"]
        guard.guarded_generate(engine, request)
        with pytest.raises(Exception):
            guard.guarded_generate(engine, request)


class TestFixtureAndPayload:
    def test_fixture_is_synthetic_and_has_required_kinds(self):
        fixture = build_synthetic_fixture()
        expected = expected_dispositions()
        kinds = fixture.kind_by_input
        blob = json.dumps(fixture.to_safe_dict())
        assert "WIN001" not in blob
        assert "pastoral_retreat" not in blob.lower()
        assert fixture_hash() == A40_FIXTURE_HASH
        assert sum(1 for kind in kinds.values() if kind == "IDEA") >= 7
        assert sum(1 for kind in kinds.values() if kind == "RELATION") >= 1
        assert sum(1 for kind in kinds.values() if kind == "TOPIC") >= 1
        assert sum(1 for kind in kinds.values() if kind == "EXAMPLE") >= 1
        assert sum(1 for kind in kinds.values() if kind == "REFERENCE") >= 1
        assert sum(1 for kind in kinds.values() if kind == "UNCERTAINTY") >= 1
        assert expected["SYN:I001"] == "KEEP"
        assert expected["SYN:I002"] == "MERGE_EQUIVALENT"
        assert expected["SYN:I003"] == "MERGE_EQUIVALENT"
        assert expected["SYN:I006"] == "DROP"
        assert RELATION_HINT_ID in kinds
        assert kinds[RELATION_HINT_ID] == "RELATION"

    def test_payload_uses_prompt_201_and_transport_20(self):
        fixture = build_synthetic_fixture()
        built = build_audited_request(fixture, project_name=PROJECT_NAME)
        audit = built["audit"]
        assert audit["model"] == "claude-sonnet-5"
        assert audit["thinking_type"] == "disabled"
        assert audit["effort_present"] is False
        assert audit["temperature_present"] is False
        assert audit["max_tokens"] == CANARY_MAX_OUTPUT_TOKENS
        assert audit["schema_hash"] == SCHEMA_HASH
        assert audit["raw_bytes"] == 1588
        assert audit["adapted_bytes"] == 1836
        assert audit["prompt_version"] == "global-consolidation-2.0.1"
        assert audit["schema_version"] == "global-consolidation-transport-2.0"
        assert "WIN001" not in built["request"].prompt
        assert "SRC000001" not in built["request"].prompt
        assert "LOCAL IDEA HANDLES ONLY" in (built["request"].system_prompt or "")
        assert "Local RELATION hints are deferred" in (built["request"].system_prompt or "")


class TestIdeaOnlyDomain:
    def _validate(self, payload):
        fixture = build_synthetic_fixture()
        return validate_global_transport_v20(
            payload,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            local_kind_by_input=fixture.kind_by_input,
        )

    def test_valid_transport_omits_relation_legitimately(self):
        payload = expected_valid_transport_v20()
        fixture = build_synthetic_fixture()
        interpreted = interpret_canary_response_v201(
            payload, fixture=fixture, signature="test-a42"
        )
        assert interpreted["RELATION_HINT_IN_MEMBERS"] == "NO"
        assert interpreted["RELATION_HINT_IN_DROP"] == "NO"
        assert interpreted["NON_IDEA_IN_MEMBERS"] == 0
        assert interpreted["NON_IDEA_IN_DROP"] == 0
        assert interpreted["TOPIC_IDEA_DOMAIN_VIOLATIONS"] == 0
        assert interpreted["EXAMPLE_IDEA_DOMAIN_VIOLATIONS"] == 0
        assert interpreted["REFERENCE_IDEA_DOMAIN_VIOLATIONS"] == 0
        assert interpreted["UNCERTAINTY_IDEA_DOMAIN_VIOLATIONS"] == 0
        assert interpreted["set_equality"] is True
        assert interpreted["idea_disposition_coverage"] == 100.0
        assert interpreted["keep_count"] == 4
        assert interpreted["merge_equivalent_count"] == 2
        assert interpreted["drop_count"] == 1
        assert interpreted["a40_root_defect"] == "ELIMINATED_BY_PROMPT_2_0_1"
        assert "SYN:L001" not in json.dumps(payload)

    def test_topic_example_reference_uncertainty_non_drop(self):
        payload = expected_valid_transport_v20()
        fixture = build_synthetic_fixture()
        boundary = type_boundary_audit(payload, kind_by_input=fixture.kind_by_input)
        assert boundary["TOPIC_IDEA_DOMAIN_VIOLATIONS"] == 0
        assert boundary["EXAMPLE_IDEA_DOMAIN_VIOLATIONS"] == 0
        assert boundary["REFERENCE_IDEA_DOMAIN_VIOLATIONS"] == 0
        assert boundary["UNCERTAINTY_IDEA_DOMAIN_VIOLATIONS"] == 0
        drop_ids = [row["i"] for row in payload["drop"]]
        assert "SYN:T001" not in drop_ids
        assert "SYN:E001" not in drop_ids
        assert "SYN:F001" not in drop_ids
        assert "SYN:U001" not in drop_ids
        assert RELATION_HINT_ID not in drop_ids

    @pytest.mark.parametrize("name,local_id,kind", NON_IDEA_DROP_CASES)
    def test_non_idea_drop_rejected(self, name, local_id, kind):
        payload = with_non_idea_drop(local_id)
        fixture = build_synthetic_fixture()
        result = self._validate(payload)
        assert result["ok"] is False
        interpreted = interpret_canary_response_v201(
            payload, fixture=fixture, signature=f"test-a42-{name}"
        )
        assert interpreted["global_validator"] == "FAIL"
        assert interpreted["NON_IDEA_IN_DROP"] >= 1
        assert interpreted["handle_validation"] == "FAIL"
        assert interpreted["publication"]["publication_eligible"] is False
        assert kind == fixture.kind_by_input[local_id]

    def test_non_idea_member_rejected(self):
        payload = copy.deepcopy(expected_valid_transport_v20())
        payload["i"][0]["m"] = ["SYN:T001"]
        fixture = build_synthetic_fixture()
        result = self._validate(payload)
        assert result["ok"] is False
        interpreted = interpret_canary_response_v201(
            payload, fixture=fixture, signature="test-a42-non-idea-member"
        )
        assert interpreted["NON_IDEA_IN_MEMBERS"] >= 1
        assert interpreted["global_validator"] == "FAIL"

    def test_one_hundred_percent_accountability_and_derived_src(self):
        payload = expected_valid_transport_v20()
        fixture = build_synthetic_fixture()
        result = self._validate(payload)
        members = []
        for idea in payload["i"]:
            members.extend(idea["m"])
        drops = [row["i"] for row in payload["drop"]]
        assert set(members) & set(drops) == set()
        assert set(fixture.idea_input_ids) == set(members) | set(drops)
        assert result["exact_set_equality"] is True
        derived = derived_src_union(["SYN:I002", "SYN:I003"], fixture.src_by_input)
        assert derived == ["SRC998103", "SRC998106"]

    def test_invalid_transport_blocks_publication(self):
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
        payload = with_non_idea_drop(RELATION_HINT_ID)
        interpreted = interpret_canary_response_v201(
            payload, fixture=build_synthetic_fixture(), signature="test-a42-pub"
        )
        assert interpreted["invalid_transport_publication_gate"] == "PASS"
        assert interpreted["publication"]["publication_eligible"] is False
        assert classify_a40_root_defect(interpreted["type_boundary"]) == "PERSISTS"


class TestPipeline:
    def test_valid_transport_full_pipeline(self):
        fixture = build_synthetic_fixture()
        interpreted = interpret_canary_response_v201(
            expected_valid_transport_v20(),
            fixture=fixture,
            signature="test-a42",
        )
        assert interpreted["structured_parse"] == "PASS"
        assert interpreted["decoder"] == "PASS"
        assert interpreted["handle_validation"] == "PASS"
        assert interpreted["global_validator"] == "PASS"
        assert interpreted["idea_disposition_coverage"] == 100.0
        assert interpreted["canonical_reconstruction"] == "PASS"
        assert interpreted["canonical_validation"] == "PASS"
        assert interpreted["empty_relations_valid"] is True
        assert interpreted["deterministic_replay"] == "PASS"
        assert interpreted["semantic_review"]["status"] == "PASS"
        assert interpreted["type_boundary"]["status"] == "PASS"
        assert interpreted["invalid_transport_publication_gate"] == "PASS"

    def test_output_estimator_comparison_preflight(self):
        estimate = estimate_canary_output()
        assert estimate["fits_canary_max"] is True
        assert estimate["canary_max_output"] == 2048
        assert estimate["headroom"] > 0
        assert "does not prove production" in estimate["limitation"]


class TestDryRunAndFakeExecute:
    def test_dry_run_twice_deterministic_and_zero_calls(self):
        first = dry_run_canary(PROJECT_NAME, authorization_scope=AUTHORIZATION_SCOPE)
        second = dry_run_canary(PROJECT_NAME, authorization_scope=AUTHORIZATION_SCOPE)
        assert first["dry_run_identity"] == second["dry_run_identity"]
        assert first["actual_real_provider_calls"] == 0
        assert first["pastoral_content_sent"] is False
        assert first["schema_identity"] == "MATCH"
        assert first["prompt_version"] == "global-consolidation-2.0.1"
        result = run_global_v201_contract_canary(
            PROJECT_NAME,
            dry_run=True,
            authorization_scope=AUTHORIZATION_SCOPE,
        )
        assert result.accepted is True
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0

    def test_fake_execute_does_not_publish_source_map(self, tmp_path):
        engine = _fake_engine()
        result = run_global_v201_contract_canary(
            "fixture",
            dry_run=False,
            execute_real=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            allow_real_provider=True,
            engine=engine,
            sortie_dir=tmp_path,
            write_artifacts=True,
        )
        assert result.engine_generate_attempts == 1
        assert result.anthropic_post_attempts == 0
        assert not source_map_path("fixture", sortie_dir=tmp_path).is_file()
        exe = result.execution
        assert exe["pastoral_content_sent"] is False
        assert exe["real_consolidation_executed"] is False
        assert exe["source_map"] == "NOT PUBLISHED"
        assert exe["ready_for_real_global_consolidation_canary"] == "NO"
        assert exe["ready_for_compact_global_real_call_preflight"] == "NO"
        assert exe["RELATION_HINT_IN_DROP"] == "NO"
        assert exe["RELATION_HINT_IN_MEMBERS"] == "NO"
        assert exe["retry"] is False
        assert PHASE == "3B.7.7A.42"
        if exe.get("result") == "PASS":
            assert exe["ready_for_output_budget_redesign"] == "YES"
