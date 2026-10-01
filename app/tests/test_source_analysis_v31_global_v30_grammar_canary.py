"""Phase 3B.7.7A.44 — FakeAI / offline. 0 réseau. 0 consolidation réelle."""

from __future__ import annotations

import copy
import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_drop_domain.gate import publication_eligibility
from app.source_analysis_v31_global_reuse_output.prompt_v30 import prompt_v30_bundle
from app.source_analysis_v31_global_reuse_output.transport_v30 import (
    measure_global_schema_v30,
)
from app.source_analysis_v31_global_reuse_output.validate import (
    derived_src_union,
    validate_global_transport_v30,
)
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    AUTHORIZATION_SCOPE as A37_SCOPE,
)
from app.source_analysis_v31_global_v201_contract_canary.constants import (
    AUTHORIZATION_SCOPE as A42_SCOPE,
)
from app.source_analysis_v31_global_v20_grammar_canary.constants import (
    AUTHORIZATION_SCOPE as A40_SCOPE,
)
from app.source_analysis_v31_global_v30_grammar_canary.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    A39_STATUS_PRESERVED,
    A40_STATUS_PRESERVED,
    A41_STATUS_PRESERVED,
    A42_STATUS_PRESERVED,
    A43_STATUS_PRESERVED,
    AUTHORIZATION_SCOPE,
    CANARY_MAX_OUTPUT_TOKENS,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_ABSOLUTE_HEADROOM,
    PRODUCTION_CONSERVATIVE_OUTPUT_TOKENS,
    PRODUCTION_EXPECTED_OUTPUT_TOKENS,
    PRODUCTION_HARD_PLANNING_TOKENS,
    PRODUCTION_HARD_UTILIZATION,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PRODUCTION_OUTPUT_RISK,
    PROJECT_NAME,
    PROMPT_VERSION,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_PREFLIGHT,
    READY_WINDOWS,
    RELATION_HINT_ID,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    SELECTED_ARCHITECTURE,
    SYNTHESIZED_IDEA_MAX_CHARS,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v30_grammar_canary.fixture import (
    build_synthetic_fixture,
    equivalent_v20_style_transport,
    expected_dispositions,
    expected_valid_transport_v30,
    with_forbidden_single_member_rewrite,
    with_missing_synthesis,
    with_oversized_merge_v,
)
from app.source_analysis_v31_global_v30_grammar_canary.guard import (
    GlobalGrammarCanaryError,
    OneShotCallGuard,
    reject_real_project_input,
    reject_thinking_enabled,
    reject_wrong_architecture,
    validate_authorization_scope,
)
from app.source_analysis_v31_global_v30_grammar_canary.identity import (
    recompute_schema_identity,
    verify_schema_identity,
)
from app.source_analysis_v31_global_v30_grammar_canary.payload import (
    build_audited_request,
    estimate_canary_output,
)
from app.source_analysis_v31_global_v30_grammar_canary.runner import (
    dry_run_canary,
    run_global_v30_grammar_canary,
)
from app.source_analysis_v31_global_v30_grammar_canary.validate import (
    interpret_canary_response_v30,
)


def _fake_engine(payload=None):
    transport = payload or expected_valid_transport_v30()
    return FakeAIEngine(
        script=[
            FakeReply(
                text=json.dumps(transport, ensure_ascii=False),
                parsed=transport,
                finish_reason="end_turn",
                input_tokens=120,
                output_tokens=80,
                thinking_tokens=0,
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestHistoricalFreeze:
    def test_a34_through_a43_remain_immutable(self):
        assert A34_STATUS_PRESERVED == "PASS"
        assert A35_STATUS_PRESERVED == "FAIL"
        assert A36_STATUS_PRESERVED == "PASS"
        assert A37_STATUS_PRESERVED == "PASS"
        assert A38_STATUS_PRESERVED == "FAIL"
        assert A39_STATUS_PRESERVED == "PASS"
        assert A40_STATUS_PRESERVED == "FAIL"
        assert A41_STATUS_PRESERVED == "PASS"
        assert A42_STATUS_PRESERVED == "PASS"
        assert A43_STATUS_PRESERVED == "PASS"
        assert PHASE == "3B.7.7A.44"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"
        assert READY_WINDOWS == "7 / 7"
        assert READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO"
        assert READY_FOR_REAL_GLOBAL_CONSOLIDATION_PREFLIGHT == "NO"
        assert SELECTED_ARCHITECTURE == "HARD_SINGLE_MEMBER_REUSE_SYNTHESIZE_MERGES_ONLY"
        assert not source_map_path(PROJECT_NAME).is_file()

    def test_schema_3_0_identity_exact(self):
        measured = measure_global_schema_v30()
        recomputed = recompute_schema_identity()
        prompt = prompt_v30_bundle()
        assert measured["raw_bytes"] == SCHEMA_RAW_BYTES == 1583
        assert measured["adapted_bytes"] == SCHEMA_ADAPTED_BYTES == 1831
        assert measured["hash"] == SCHEMA_HASH
        assert SCHEMA_HASH == (
            "822397b642b0e1724e29686962caab32bff63effe18f05bff26b404bad9b2a90"
        )
        assert prompt["prompt_version"] == PROMPT_VERSION == "global-consolidation-3.0"
        assert prompt["previous_prompt_mutated"] is False
        assert recomputed["matches_a43_constants"] is True
        verified = verify_schema_identity(PROJECT_NAME)
        assert verified["schema_identity"] == "MATCH"
        assert TRANSPORT_VERSION == "global-consolidation-transport-3.0"
        assert THINKING_MODE == "disabled"
        assert PRODUCTION_MAX_OUTPUT_TOKENS == 48000
        assert CANARY_MAX_OUTPUT_TOKENS == 2048
        assert PRODUCTION_EXPECTED_OUTPUT_TOKENS == 12302
        assert PRODUCTION_CONSERVATIVE_OUTPUT_TOKENS == 16822
        assert PRODUCTION_HARD_PLANNING_TOKENS == 25486
        assert PRODUCTION_HARD_UTILIZATION == 0.531
        assert PRODUCTION_ABSOLUTE_HEADROOM == 22514
        assert PRODUCTION_OUTPUT_RISK == "SAFE_FOR_GRAMMAR_CANARY_BUDGET"
        assert SYNTHESIZED_IDEA_MAX_CHARS == 180


class TestAuthorizationAndGuard:
    def test_missing_and_wrong_scope_fail_before_network(self):
        with pytest.raises(GlobalGrammarCanaryError):
            validate_authorization_scope(None)
        result = run_global_v30_grammar_canary(
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
            A42_SCOPE,
            "WIN001_ONLY",
            "GLOBAL_CONSOLIDATION_2_0_1_SECOND_SYNTHETIC_CONTRACT_CANARY_ONLY",
        ):
            result = run_global_v30_grammar_canary(
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
                prompt_version="global-consolidation-2.0.1",
                transport_version=TRANSPORT_VERSION,
                schema_hash=SCHEMA_HASH,
            )
        with pytest.raises(GlobalGrammarCanaryError):
            reject_wrong_architecture(
                model="claude-sonnet-5",
                prompt_version=PROMPT_VERSION,
                transport_version="global-consolidation-transport-2.0",
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
        assert sum(1 for kind in kinds.values() if kind == "IDEA") == 7
        assert sum(1 for kind in kinds.values() if kind == "RELATION") >= 1
        assert sum(1 for kind in kinds.values() if kind == "TOPIC") >= 1
        assert sum(1 for kind in kinds.values() if kind == "EXAMPLE") >= 1
        assert sum(1 for kind in kinds.values() if kind == "REFERENCE") >= 1
        assert sum(1 for kind in kinds.values() if kind == "UNCERTAINTY") >= 1
        assert expected["SYN:I011"] == "KEEP"
        assert expected["SYN:I012"] == "MERGE_EQUIVALENT"
        assert expected["SYN:I013"] == "MERGE_EQUIVALENT"
        assert expected["SYN:I016"] == "DROP"
        assert RELATION_HINT_ID in kinds
        assert kinds[RELATION_HINT_ID] == "RELATION"

    def test_payload_uses_prompt_30_and_transport_30(self):
        fixture = build_synthetic_fixture()
        built = build_audited_request(fixture, project_name=PROJECT_NAME)
        audit = built["audit"]
        assert audit["model"] == "claude-sonnet-5"
        assert audit["thinking_type"] == "disabled"
        assert audit["effort_present"] is False
        assert audit["temperature_present"] is False
        assert audit["max_tokens"] == CANARY_MAX_OUTPUT_TOKENS
        assert audit["schema_hash"] == SCHEMA_HASH
        assert audit["raw_bytes"] == 1583
        assert audit["adapted_bytes"] == 1831
        assert audit["prompt_version"] == "global-consolidation-3.0"
        assert audit["schema_version"] == "global-consolidation-transport-3.0"
        assert "WIN001" not in built["request"].prompt
        assert "SRC000001" not in built["request"].prompt
        assert "omit field v" in (built["request"].system_prompt or "").lower() or (
            "omit field v" in (built["request"].system_prompt or "")
        )
        assert "LOCAL IDEA HANDLES ONLY" in (built["request"].system_prompt or "")


class TestReuseAndSynthesisContract:
    def _validate(self, payload):
        fixture = build_synthetic_fixture()
        return validate_global_transport_v30(
            payload,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            local_kind_by_input=fixture.kind_by_input,
        )

    def test_single_member_v_absent_and_multi_member_v_present(self):
        payload = expected_valid_transport_v30()
        singles = [idea for idea in payload["i"] if len(idea["m"]) == 1]
        merges = [idea for idea in payload["i"] if len(idea["m"]) >= 2]
        assert len(singles) >= 3
        assert len(merges) == 1
        for idea in singles:
            assert "v" not in idea
        for idea in merges:
            assert idea.get("v")
            assert len(idea["v"]) <= 180
        result = self._validate(payload)
        assert result["ok"] is True
        assert result["reuse_count"] == 4
        assert result["synthesize_count"] == 1

    def test_single_member_v_rejection(self):
        payload = with_forbidden_single_member_rewrite()
        result = self._validate(payload)
        assert result["ok"] is False
        assert result["forbidden_rewrites"]
        fixture = build_synthetic_fixture()
        interpreted = interpret_canary_response_v30(
            payload, fixture=fixture, signature="test-a44-rewrite"
        )
        assert interpreted["global_validator"] == "FAIL"
        assert interpreted["SINGLE_MEMBER_WITH_V"] >= 1
        assert interpreted["publication"]["publication_eligible"] is False

    def test_multi_member_missing_v_rejection(self):
        payload = with_missing_synthesis()
        result = self._validate(payload)
        assert result["ok"] is False
        assert result["missing_synthesis"]
        fixture = build_synthetic_fixture()
        interpreted = interpret_canary_response_v30(
            payload, fixture=fixture, signature="test-a44-missing-v"
        )
        assert interpreted["MULTI_MEMBER_WITHOUT_V"] >= 1
        assert interpreted["global_validator"] == "FAIL"

    def test_v_max_180(self):
        payload = with_oversized_merge_v()
        result = self._validate(payload)
        assert result["ok"] is False
        assert any("exceeds 180" in item for item in result["errors"])

    def test_exact_reuse_and_merge_reconstruction(self):
        fixture = build_synthetic_fixture()
        interpreted = interpret_canary_response_v30(
            expected_valid_transport_v30(),
            fixture=fixture,
            signature="test-a44-reuse",
        )
        assert interpreted["reuse_text_exact_equality"] == 100.0
        assert interpreted["merge_text_equality"] == 100.0
        assert interpreted["canonical_reconstruction"] == "PASS"
        assert interpreted["canonical_validation"] == "PASS"
        local = fixture.records["SYN:I011"]["v"]
        reuse_row = next(
            row
            for row in interpreted["reuse_synthesis"]["ideas"]
            if row["members"] == ["SYN:I011"]
        )
        assert reuse_row["canonical_equals_local"] is True
        assert reuse_row["expected_local_text"] == local
        merge_row = next(
            row
            for row in interpreted["reuse_synthesis"]["ideas"]
            if len(row["members"]) >= 2
        )
        assert merge_row["canonical_equals_provider_v"] is True


class TestIdeaOnlyDomain:
    def test_valid_transport_omits_relation_legitimately(self):
        payload = expected_valid_transport_v30()
        fixture = build_synthetic_fixture()
        interpreted = interpret_canary_response_v30(
            payload, fixture=fixture, signature="test-a44"
        )
        assert interpreted["RELATION_HINT_IN_MEMBERS"] == "NO"
        assert interpreted["RELATION_HINT_IN_DROP"] == "NO"
        assert interpreted["NON_IDEA_IN_MEMBERS"] == 0
        assert interpreted["NON_IDEA_IN_DROP"] == 0
        assert interpreted["set_equality"] is True
        assert interpreted["idea_disposition_coverage"] == 100.0
        assert interpreted["keep_count"] == 4
        assert interpreted["merge_equivalent_count"] == 2
        assert interpreted["drop_count"] == 1
        assert "SYN:L011" not in json.dumps(payload)

    def test_one_hundred_percent_accountability_and_derived_src(self):
        payload = expected_valid_transport_v30()
        fixture = build_synthetic_fixture()
        members = []
        for idea in payload["i"]:
            members.extend(idea["m"])
        drops = [row["i"] for row in payload["drop"]]
        assert set(members) & set(drops) == set()
        assert set(fixture.idea_input_ids) == set(members) | set(drops)
        derived = derived_src_union(["SYN:I012", "SYN:I013"], fixture.src_by_input)
        assert derived == ["SRC998203", "SRC998206"]

    def test_invalid_transport_blocks_publication(self):
        gate = publication_eligibility(
            global_validator_ok=False,
            canonical_reconstruction_ok=True,
        )
        assert gate["publication_eligible"] is False
        assert gate["reconstruction_ok_is_insufficient"] is True
        payload = with_forbidden_single_member_rewrite()
        interpreted = interpret_canary_response_v30(
            payload, fixture=build_synthetic_fixture(), signature="test-a44-pub"
        )
        assert interpreted["invalid_transport_publication_gate"] == "PASS"
        assert interpreted["publication"]["publication_eligible"] is False


class TestPipeline:
    def test_valid_transport_full_pipeline(self):
        fixture = build_synthetic_fixture()
        interpreted = interpret_canary_response_v30(
            expected_valid_transport_v30(),
            fixture=fixture,
            signature="test-a44",
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
        assert interpreted["SINGLE_MEMBER_WITH_V"] == 0
        assert interpreted["MULTI_MEMBER_WITHOUT_V"] == 0

    def test_output_estimator_comparison_preflight(self):
        estimate = estimate_canary_output()
        assert estimate["fits_canary_max"] is True
        assert estimate["canary_max_output"] == 2048
        assert estimate["headroom"] > 0
        compact = estimate["compactness_vs_v20_style"]
        assert compact["saved_chars"] > 0
        assert compact["v30_chars"] < compact["v20_style_chars"]
        assert "does not prove production" in estimate["limitation"]
        v20 = equivalent_v20_style_transport()
        assert all("v" in idea for idea in v20["i"])


class TestDryRunAndFakeExecute:
    def test_dry_run_twice_deterministic_and_zero_calls(self):
        first = dry_run_canary(PROJECT_NAME, authorization_scope=AUTHORIZATION_SCOPE)
        second = dry_run_canary(PROJECT_NAME, authorization_scope=AUTHORIZATION_SCOPE)
        assert first["dry_run_identity"] == second["dry_run_identity"]
        assert first["actual_real_provider_calls"] == 0
        assert first["pastoral_content_sent"] is False
        assert first["schema_identity"] == "MATCH"
        assert first["prompt_version"] == "global-consolidation-3.0"
        result = run_global_v30_grammar_canary(
            PROJECT_NAME,
            dry_run=True,
            authorization_scope=AUTHORIZATION_SCOPE,
        )
        assert result.accepted is True
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0

    def test_fake_execute_does_not_publish_source_map(self, tmp_path):
        engine = _fake_engine()
        result = run_global_v30_grammar_canary(
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
        assert exe["RELATION_HINT_IN_DROP"] == "NO"
        assert exe["RELATION_HINT_IN_MEMBERS"] == "NO"
        assert exe["retry"] is False
        assert PHASE == "3B.7.7A.44"
        if exe.get("result") == "PASS":
            assert exe["ready_for_real_global_consolidation_preflight"] == "YES"
