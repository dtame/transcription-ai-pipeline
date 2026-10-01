"""Phase 3B.7.7A.40 — FakeAI / offline. 0 réseau. 0 consolidation réelle."""

from __future__ import annotations

import copy
import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.models import format_idea_id, format_topic_id
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_output_architecture.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    NEXT_SCHEMA_HASH,
)
from app.source_analysis_v31_global_output_architecture.estimator import estimate_output
from app.source_analysis_v31_global_output_architecture.membership import (
    derived_src_union,
    validate_global_transport_v20,
)
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    measure_global_schema_v20,
)
from app.source_analysis_v31_global_preflight.normalize import build_normalized_input
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    AUTHORIZATION_SCOPE as A37_SCOPE,
)
from app.source_analysis_v31_global_v20_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    FORBIDDEN_WINDOW_IDS,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_ABSOLUTE_HEADROOM,
    PRODUCTION_EXPECTED_OUTPUT_TOKENS,
    PRODUCTION_HARD_PLANNING_TOKENS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PRODUCTION_OUTPUT_RISK,
    PRODUCTION_SAFETY_MARGIN,
    PRODUCTION_SAFETY_THRESHOLD,
    PROJECT_NAME,
    PROMPT_VERSION,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    SYNTHETIC_SRC_IDS,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v20_grammar_canary.fixture import (
    build_synthetic_fixture,
    expected_dispositions,
    expected_valid_transport_v20,
)
from app.source_analysis_v31_global_v20_grammar_canary.guard import (
    GlobalGrammarCanaryError,
    OneShotCallGuard,
    assert_synthetic_identity,
    reject_real_project_input,
    validate_authorization_scope,
)
from app.source_analysis_v31_global_v20_grammar_canary.identity import (
    recompute_schema_identity,
    verify_schema_identity,
)
from app.source_analysis_v31_global_v20_grammar_canary.payload import (
    build_audited_request,
    estimate_canary_output,
)
from app.source_analysis_v31_global_v20_grammar_canary.runner import (
    dry_run_canary,
    run_global_v20_grammar_canary,
)
from app.source_analysis_v31_global_v20_grammar_canary.validate import (
    interpret_canary_response_v20,
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
    def test_a34_through_a39_remain_immutable(self):
        assert A34_STATUS_PRESERVED == "PASS"
        assert A35_STATUS_PRESERVED == "FAIL"
        assert A36_STATUS_PRESERVED == "PASS"
        assert A37_STATUS_PRESERVED == "PASS"
        assert A38_STATUS_PRESERVED == "FAIL"
        assert PHASE == "3B.7.7A.40"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"
        assert not source_map_path(PROJECT_NAME).is_file()

    def test_schema_2_0_identity(self):
        measured = measure_global_schema_v20()
        recomputed = recompute_schema_identity()
        assert measured["raw_bytes"] == SCHEMA_RAW_BYTES == 1588
        assert measured["adapted_bytes"] == SCHEMA_ADAPTED_BYTES == 1836
        assert measured["hash"] == SCHEMA_HASH == NEXT_SCHEMA_HASH
        assert SCHEMA_HASH.startswith("90b99a38")
        assert SCHEMA_HASH.endswith("6d8330")
        assert SCHEMA_HASH == (
            "90b99a38ac704d00e1304495da0c757118293e43493ddb7321b3ffb3256d8330"
        )
        assert recomputed["matches_a39_constants"] is True
        verified = verify_schema_identity(PROJECT_NAME)
        assert verified["schema_identity"] == "MATCH"
        assert verified["a39_artifact_hash"] == SCHEMA_HASH
        assert TRANSPORT_VERSION == "global-consolidation-transport-2.0"
        assert PROMPT_VERSION == "global-consolidation-2.0"
        assert THINKING_MODE == "disabled"
        assert PRODUCTION_MAX_OUTPUT_TOKENS == 48000
        assert CANARY_MAX_OUTPUT_TOKENS == 2048
        assert PRODUCTION_EXPECTED_OUTPUT_TOKENS == 28735
        assert PRODUCTION_HARD_PLANNING_TOKENS == 35284
        assert PRODUCTION_SAFETY_THRESHOLD == 36000
        assert PRODUCTION_SAFETY_MARGIN == 716
        assert PRODUCTION_ABSOLUTE_HEADROOM == 12716
        assert PRODUCTION_OUTPUT_RISK == "PASS_BUT_TIGHT_AT_75_PERCENT_THRESHOLD"
        production = estimate_output()
        assert production["provider_planning_tokens"]["expected"] == 28735
        assert production["provider_planning_tokens"]["hard"] == 35284


class TestAuthorizationAndGuard:
    def test_missing_and_wrong_scope_fail_before_network(self):
        with pytest.raises(GlobalGrammarCanaryError):
            validate_authorization_scope(None)
        result = run_global_v20_grammar_canary(
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
            "WIN001_ONLY",
            "GLOBAL_CONSOLIDATION_TINY_SYNTHETIC_GRAMMAR_CANARY_ONLY",
            "GLOBAL_CONSOLIDATION_V11_TINY_SYNTHETIC_GRAMMAR_CANARY_ONLY",
        ):
            result = run_global_v20_grammar_canary(
                "fixture",
                dry_run=True,
                authorization_scope=scope,
            )
            assert result.accepted is False
            assert result.engine_generate_attempts == 0

    def test_forbidden_identities_and_real_data(self):
        with pytest.raises(GlobalGrammarCanaryError):
            assert_synthetic_identity(
                window_id="WIN001",
                transcript_id=CANARY_TRANSCRIPT_ID,
                src_ids=SYNTHETIC_SRC_IDS,
            )
        with pytest.raises(GlobalGrammarCanaryError):
            assert_synthetic_identity(
                window_id=CANARY_WINDOW_ID,
                transcript_id="TR001",
                src_ids=SYNTHETIC_SRC_IDS,
            )
        normalized = build_normalized_input(PROJECT_NAME)
        with pytest.raises(GlobalGrammarCanaryError):
            reject_real_project_input(normalized)

    def test_second_generate_rejected(self):
        engine = _fake_engine()
        guard = OneShotCallGuard(max_calls=1)
        fixture = build_synthetic_fixture()
        request = build_audited_request(fixture)["request"]
        guard.guarded_generate(engine, request)
        with pytest.raises(Exception):
            guard.guarded_generate(engine, request)


class TestFixtureAndPayload:
    def test_fixture_is_synthetic_and_unambiguous(self):
        fixture = build_synthetic_fixture()
        expected = expected_dispositions()
        blob = json.dumps(fixture.to_safe_dict())
        for window_id in FORBIDDEN_WINDOW_IDS:
            assert window_id not in blob
        assert "pastoral_retreat" not in blob.lower()
        assert expected["SYN:I001"] == "KEEP"
        assert expected["SYN:I002"] == "MERGE_EQUIVALENT"
        assert expected["SYN:I003"] == "MERGE_EQUIVALENT"
        assert expected["SYN:I006"] == "DROP"
        assert "LINK_RELATED" not in expected.values()
        assert "OTHER" not in expected.values()
        assert "and then uh" in json.dumps(fixture.compact)
        assert len(fixture.idea_input_ids) == 7
        assert all(item.startswith("SYN:") for item in fixture.idea_input_ids)

    def test_payload_uses_prompt_20_and_transport_20(self):
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
        assert audit["prompt_version"] == "global-consolidation-2.0"
        assert audit["schema_version"] == "global-consolidation-transport-2.0"
        assert "WIN001" not in built["request"].prompt
        assert "SRC000001" not in built["request"].prompt
        assert "Do not emit a disposition ledger" in (built["request"].system_prompt or "")


class TestMembershipContract:
    def _validate(self, payload):
        fixture = build_synthetic_fixture()
        return validate_global_transport_v20(
            payload,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            local_kind_by_input=fixture.kind_by_input,
        )

    def test_set_equality_and_derived_dispositions(self):
        payload = expected_valid_transport_v20()
        result = self._validate(payload)
        assert result["ok"] is True
        assert result["exact_set_equality"] is True
        interpreted = interpret_canary_response_v20(
            payload, fixture=build_synthetic_fixture(), signature="test-a40"
        )
        assert interpreted["set_equality"] is True
        assert interpreted["keep_count"] == 4
        assert interpreted["merge_equivalent_count"] == 2
        assert interpreted["drop_count"] == 1
        assert interpreted["other_count"] == 0
        assert interpreted["link_related_count"] == 0
        assert interpreted["exact_duplicate_drop_count"] == 0
        assert interpreted["drop_enum"] == "PASS"
        assert interpreted["derived_src_union"] == "PASS"
        assert interpreted["provider_disposition_ledger"] == "ABSENT"
        assert interpreted["provider_src_arrays"] == 0

    def test_single_membership_keep(self):
        payload = expected_valid_transport_v20()
        watering = [idea for idea in payload["i"] if idea["m"] == ["SYN:I001"]]
        assert watering
        interpreted = interpret_canary_response_v20(
            payload, fixture=build_synthetic_fixture(), signature="test-a40"
        )
        derived = interpreted["derived_dispositions"]["derived"]
        assert derived["SYN:I001"]["o"] == "KEEP"

    def test_duplicate_member_rejected(self):
        payload = copy.deepcopy(expected_valid_transport_v20())
        payload["i"][2]["m"] = ["SYN:I001"]
        result = self._validate(payload)
        assert result["ok"] is False
        assert any("DUPLICATE_MEMBERSHIP:" in item for item in result["errors"])

    def test_unknown_member_rejected(self):
        payload = copy.deepcopy(expected_valid_transport_v20())
        payload["i"][0]["m"] = ["SYN:I999"]
        result = self._validate(payload)
        assert result["ok"] is False
        assert any(item.startswith("UNKNOWN_MEMBER:") for item in result["errors"])

    def test_missing_member_rejected(self):
        payload = copy.deepcopy(expected_valid_transport_v20())
        payload["i"] = [idea for idea in payload["i"] if "SYN:I001" not in idea["m"]]
        result = self._validate(payload)
        assert result["ok"] is False
        assert any(item.startswith("SILENT_DROP:") for item in result["errors"])

    def test_member_drop_overlap_rejected(self):
        payload = copy.deepcopy(expected_valid_transport_v20())
        payload["drop"].append({"i": "SYN:I001", "w": "transport_artifact"})
        result = self._validate(payload)
        assert result["ok"] is False
        assert any("DUPLICATE_MEMBERSHIP:" in item for item in result["errors"])

    def test_drop_enum_and_legacy_ops_rejected(self):
        payload = copy.deepcopy(expected_valid_transport_v20())
        payload["drop"][0]["w"] = "exact_duplicate"
        result = self._validate(payload)
        assert result["ok"] is False
        payload = copy.deepcopy(expected_valid_transport_v20())
        payload["drop"][0]["w"] = "filler"
        result = self._validate(payload)
        assert result["ok"] is False
        blob = json.dumps(expected_valid_transport_v20())
        assert "OTHER" not in blob
        assert "LINK_RELATED" not in blob

    def test_derived_src_union_and_order(self):
        fixture = build_synthetic_fixture()
        members = ["SYN:I002", "SYN:I003"]
        derived = derived_src_union(members, fixture.src_by_input)
        assert derived == ["SRC998103", "SRC998106"]
        assert len(derived) == len(set(derived))


class TestPipeline:
    def test_valid_transport_full_pipeline(self):
        fixture = build_synthetic_fixture()
        interpreted = interpret_canary_response_v20(
            expected_valid_transport_v20(),
            fixture=fixture,
            signature="test-a40",
        )
        assert interpreted["structured_parse"] == "PASS"
        assert interpreted["decoder"] == "PASS"
        assert interpreted["handle_validation"] == "PASS"
        assert interpreted["global_validator"] == "PASS"
        assert interpreted["idea_disposition_coverage"] == 100.0
        assert interpreted["silent_drops"] == 0
        assert interpreted["canonical_reconstruction"] == "PASS"
        assert interpreted["canonical_validation"] == "PASS"
        assert interpreted["empty_relations_valid"] is True
        assert interpreted["deterministic_replay"] == "PASS"
        assert interpreted["semantic_review"]["status"] == "PASS"
        reconstruction = interpreted["reconstruction"]
        assert reconstruction["all_idea_kinds_empty"] is True
        ids = reconstruction["assigned_provider_to_canonical"]
        assert any(value.startswith("TOP") for value in ids.values())
        assert any(value.startswith("IDEA") for value in ids.values())
        assert format_topic_id(1) in ids.values() or any(
            value.startswith("TOP") for value in ids.values()
        )
        assert format_idea_id(1) in ids.values() or any(
            value.startswith("IDEA") for value in ids.values()
        )
        source_map_ideas = reconstruction.get("ideas") or []
        assert all(item.get("kind") == "" for item in source_map_ideas)
        assert all(not item.get("relations") for item in source_map_ideas)

    def test_output_estimator_comparison_preflight(self):
        estimate = estimate_canary_output()
        assert estimate["fits_canary_max"] is True
        assert estimate["worst_provider_tokens"] < CANARY_MAX_OUTPUT_TOKENS
        assert estimate["canary_max_output"] == 2048
        assert "does not prove production" in estimate["limitation"]


class TestDryRunAndFakeExecute:
    def test_dry_run_twice_deterministic_and_zero_calls(self):
        first = dry_run_canary(PROJECT_NAME, authorization_scope=AUTHORIZATION_SCOPE)
        second = dry_run_canary(PROJECT_NAME, authorization_scope=AUTHORIZATION_SCOPE)
        assert first["dry_run_identity"] == second["dry_run_identity"]
        assert first["actual_real_provider_calls"] == 0
        assert first["pastoral_content_sent"] is False
        assert first["schema_identity"] == "MATCH"
        result = run_global_v20_grammar_canary(
            PROJECT_NAME,
            dry_run=True,
            authorization_scope=AUTHORIZATION_SCOPE,
        )
        assert result.accepted is True
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0

    def test_fake_execute_does_not_publish_source_map(self, tmp_path):
        engine = _fake_engine()
        result = run_global_v20_grammar_canary(
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
        assert exe["retry"] is False
        assert PHASE == "3B.7.7A.40"
