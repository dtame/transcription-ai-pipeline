"""Phase 3B.7.7A.35 — FakeAI / offline. 0 réseau. 0 consolidation réelle."""

from __future__ import annotations

import copy
import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.models import format_idea_id, format_topic_id
from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_v31_global_grammar_canary.constants import (
    A34_SCHEMA_ADAPTED_BYTES,
    A34_SCHEMA_HASH,
    A34_SCHEMA_RAW_BYTES,
    AUTHORIZATION_SCOPE,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    FORBIDDEN_WINDOW_IDS,
    FROZEN_GRANULARITY,
    FROZEN_PLANNER,
    FROZEN_PROMPT,
    FROZEN_SRC_POLICY,
    FROZEN_TRANSPORT,
    GLOBAL_PROMPT_VERSION,
    GLOBAL_TRANSPORT_VERSION,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    SYNTHETIC_SRC_IDS,
    THINKING_MODE,
)
from app.source_analysis_v31_global_grammar_canary.decoder import decode_global_transport
from app.source_analysis_v31_global_grammar_canary.dispositions import audit_dispositions
from app.source_analysis_v31_global_grammar_canary.fixture import (
    build_synthetic_fixture,
    expected_valid_transport,
)
from app.source_analysis_v31_global_grammar_canary.guard import (
    GlobalGrammarCanaryError,
    OneShotCallGuard,
    assert_synthetic_identity,
    reject_real_project_input,
    validate_authorization_scope,
)
from app.source_analysis_v31_global_grammar_canary.handles import inspect_global_handles
from app.source_analysis_v31_global_grammar_canary.identity import (
    recompute_schema_identity,
    verify_schema_identity,
)
from app.source_analysis_v31_global_grammar_canary.payload import build_audited_request
from app.source_analysis_v31_global_grammar_canary.reconstruct import (
    reconstruct_source_map,
    replay_reconstruction,
)
from app.source_analysis_v31_global_grammar_canary.runner import (
    dry_run_canary,
    run_global_grammar_canary,
)
from app.source_analysis_v31_global_grammar_canary.validate import interpret_canary_response
from app.source_analysis_v31_global_preflight.constants import (
    CONSOLIDATION_AUTHORIZED,
    GRAMMAR_CANARY_AUTHORIZED,
    REAL_CONSOLIDATION_CALLS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
)
from app.source_analysis_v31_global_preflight.normalize import build_normalized_input
from app.source_analysis_v31_global_preflight.transport import measure_global_schema
from app.source_analysis_v31_global_preflight.validator import validate_global_transport


def _fake_engine(payload=None):
    transport = payload or expected_valid_transport()
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


class TestFreezeAndSchemaIdentity:
    def test_local_extraction_remains_frozen(self):
        assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"
        assert FROZEN_PLANNER == "window-planner-v2.1-small"
        assert FROZEN_PROMPT == "window-analysis-1.4.0"
        assert FROZEN_TRANSPORT == "semantic-transport-v3.1-local-lite"
        assert FROZEN_GRANULARITY == "window-granularity-1.2-kind-specific"
        assert FROZEN_SRC_POLICY == "src-reference-policy-1.1-narrow-canonicalization"
        assert PLANNER_VERSION == "window-planner-v2.0"
        assert PRODUCTION_MAX_OUTPUT_TOKENS == 32000
        assert CANARY_MAX_OUTPUT_TOKENS == 2048
        assert CANARY_MAX_OUTPUT_TOKENS != PRODUCTION_MAX_OUTPUT_TOKENS
        assert GLOBAL_PROMPT_VERSION == "global-consolidation-1.0"
        assert GLOBAL_TRANSPORT_VERSION == "global-consolidation-transport-1.0"
        assert THINKING_MODE == "disabled"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert GRAMMAR_CANARY_AUTHORIZED is False
        assert CONSOLIDATION_AUTHORIZED is False
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_CONSOLIDATION_CALLS == 0
        assert not source_map_path(PROJECT_NAME).is_file()

    def test_schema_identity_matches_a34(self):
        measured = measure_global_schema()
        recomputed = recompute_schema_identity()
        assert measured["raw_bytes"] == A34_SCHEMA_RAW_BYTES == 1040
        assert measured["adapted_bytes"] == A34_SCHEMA_ADAPTED_BYTES == 1195
        assert measured["hash"] == A34_SCHEMA_HASH
        assert A34_SCHEMA_HASH.startswith("7a8ce905")
        assert A34_SCHEMA_HASH.endswith("61633")
        assert recomputed["matches_a34_constants"] is True
        verified = verify_schema_identity(PROJECT_NAME)
        assert verified["schema_identity"] == "MATCH"


class TestAuthorizationAndGuard:
    def test_missing_scope_fails_before_network(self):
        with pytest.raises(GlobalGrammarCanaryError):
            validate_authorization_scope(None)
        result = run_global_grammar_canary(
            "fixture",
            dry_run=True,
            authorization_scope="WRONG",
        )
        assert result.accepted is False
        assert result.blocked_precall is True
        assert result.engine_generate_attempts == 0

    def test_real_consolidation_and_window_scopes_rejected(self):
        for scope in (
            "REAL_GLOBAL_CONSOLIDATION_CANARY",
            "WIN001_ONLY",
            "V3_SYMBOLIC_HANDLE_GRAMMAR_CANARY_ONLY",
            "FINAL_V31_LOCAL_LITE_WIN005_WIN006_WIN007_ONLY",
        ):
            result = run_global_grammar_canary(
                "fixture",
                dry_run=True,
                authorization_scope=scope,
            )
            assert result.accepted is False
            assert result.engine_generate_attempts == 0

    def test_forbidden_identities(self):
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
        with pytest.raises(GlobalGrammarCanaryError):
            assert_synthetic_identity(
                window_id=CANARY_WINDOW_ID,
                transcript_id=CANARY_TRANSCRIPT_ID,
                src_ids=("SRC000001", "SRC000002"),
            )

    def test_real_project_normalized_input_rejected(self):
        normalized = build_normalized_input(PROJECT_NAME)
        with pytest.raises(GlobalGrammarCanaryError):
            reject_real_project_input(normalized)
        compact = (normalized.get("compact") or {}).get("windows") or []
        assert compact
        assert compact[0]["id"].startswith("WIN")

    def test_second_generate_rejected(self):
        engine = _fake_engine()
        guard = OneShotCallGuard(max_calls=1)
        fixture = build_synthetic_fixture()
        request = build_audited_request(fixture)["request"]
        guard.guarded_generate(engine, request)
        with pytest.raises(Exception):
            guard.guarded_generate(engine, request)


class TestSyntheticFixtureAndPayload:
    def test_fixture_is_synthetic_only(self):
        fixture = build_synthetic_fixture()
        assert fixture.transcript.transcript_id == CANARY_TRANSCRIPT_ID
        assert fixture.transcript.src_ids() == SYNTHETIC_SRC_IDS
        blob = json.dumps(fixture.to_safe_dict())
        for window_id in FORBIDDEN_WINDOW_IDS:
            assert window_id not in blob
        assert "pastoral_retreat" not in blob.lower()
        assert fixture.to_safe_dict()["pastoral"] is False
        assert "SYN001:I1" in fixture.idea_input_ids
        assert len(fixture.idea_input_ids) == 5
        assert fixture.expected_dispositions["SYN001:I1"] == "KEEP"
        assert fixture.expected_dispositions["SYN001:I2"] == "MERGE_EQUIVALENT"
        assert fixture.expected_dispositions["SYN002:I2"] == "LINK_RELATED"
        assert fixture.expected_dispositions["SYN001:I3"] == "DROP"

    def test_payload_thinking_disabled_and_schema_identity(self):
        fixture = build_synthetic_fixture()
        built = build_audited_request(fixture, project_name=PROJECT_NAME)
        audit = built["audit"]
        assert audit["model"] == "claude-sonnet-5"
        assert audit["thinking_type"] == "disabled"
        assert audit["effort_present"] is False
        assert audit["temperature_present"] is False
        assert audit["max_tokens"] == CANARY_MAX_OUTPUT_TOKENS
        assert audit["schema_hash"] == A34_SCHEMA_HASH
        assert audit["raw_bytes"] == 1040
        assert audit["adapted_bytes"] == 1195
        assert "WIN001" not in built["request"].prompt
        assert "SRC000001" not in built["request"].prompt


class TestTransportDecoderHandlesDispositions:
    def test_expected_transport_decodes_and_validates(self):
        fixture = build_synthetic_fixture()
        transport = expected_valid_transport()
        decoded = decode_global_transport(transport)
        assert decoded["decoder"] == "PASS"
        assert decoded["structured_parse"] == "PASS"
        assert decoded["inventory"]["IDEA"] == 3
        assert decoded["inventory"]["TOPIC"] == 2
        assert decoded["inventory"]["EXAMPLE"] >= 1
        assert decoded["inventory"]["REFERENCE"] == 1
        assert decoded["inventory"]["UNCERTAINTY"] == 1
        assert decoded["inventory"]["REPETITION"] == 1
        result = validate_global_transport(
            transport,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            allowed_source_refs=set(fixture.allowed_source_refs),
        )
        assert result["ok"] is True
        assert result["idea_disposition_coverage"] == 100.0

    def test_unknown_handle_rejected(self):
        transport = expected_valid_transport()
        transport["r"][0]["a"] = "I99"
        handles = inspect_global_handles(transport)
        assert handles["handle_validation"] == "FAIL"
        assert handles["unknown_handles"]

    def test_silent_drop_rejected(self):
        fixture = build_synthetic_fixture()
        transport = expected_valid_transport()
        transport["d"] = [row for row in transport["d"] if row["i"] != "SYN001:I1"]
        audit = audit_dispositions(transport, fixture)
        assert audit["silent_drop_count"] == 1
        assert audit["ok"] is False

    def test_invalid_drop_reason_rejected(self):
        fixture = build_synthetic_fixture()
        transport = expected_valid_transport()
        for row in transport["d"]:
            if row["i"] == "SYN001:I3":
                row["w"] = "not important"
        audit = audit_dispositions(transport, fixture)
        assert audit["forbidden_drop"] or audit["invalid_drop_reason"]
        assert audit["ok"] is False
        result = validate_global_transport(
            transport,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            allowed_source_refs=set(fixture.allowed_source_refs),
        )
        assert result["ok"] is False

    def test_merge_source_union_and_link_related_non_merge(self):
        fixture = build_synthetic_fixture()
        transport = expected_valid_transport()
        audit = audit_dispositions(transport, fixture)
        assert audit["merge_union_ok"] is True
        merged = [item for item in transport["n"] if item["h"] == "I2"][0]
        assert set(merged["s"]) >= {"SRC998003", "SRC998006"}
        assert audit["link_related_non_merge"] is True
        assert audit["link_related"]["SYN002:I2"] == "I3"
        assert audit["link_related"]["SYN002:I2"] != "I2"

    def test_merge_union_missing_src_rejected(self):
        fixture = build_synthetic_fixture()
        transport = expected_valid_transport()
        for node in transport["n"]:
            if node["h"] == "I2":
                node["s"] = ["SRC998003"]
        audit = audit_dispositions(transport, fixture)
        assert audit["merge_union_ok"] is False


class TestCanonicalReconstruction:
    def test_canonical_ids_ordering_and_empty_kind(self):
        fixture = build_synthetic_fixture()
        transport = expected_valid_transport()
        result = reconstruct_source_map(
            transport, fixture.transcript, signature="test-a35"
        )
        assert result["ok"] is True
        assert result["validate_source_map"] == "PASS"
        assert result["all_idea_kinds_empty"] is True
        source_map = result["source_map"]
        assert source_map.topics[0].topic_id == format_topic_id(1)
        assert source_map.ideas[0].idea_id == format_idea_id(1)
        assert all(idea.kind == "" for idea in source_map.ideas)
        assert not result["provider_handles_used_as_final_ids"]
        replay = replay_reconstruction(
            transport, fixture.transcript, signature="test-a35"
        )
        assert replay["status"] == "PASS"
        assert replay["byte_equivalent"] is True

    def test_interpret_pipeline_pass(self):
        fixture = build_synthetic_fixture()
        interpreted = interpret_canary_response(
            expected_valid_transport(),
            fixture=fixture,
            signature="test-a35",
        )
        assert interpreted["structured_parse"] == "PASS"
        assert interpreted["decoder"] == "PASS"
        assert interpreted["handle_validation"] == "PASS"
        assert interpreted["global_validator"] == "PASS"
        assert interpreted["no_drop_validator"] == "PASS"
        assert interpreted["traceability"] == "PASS"
        assert interpreted["relation_validator"] == "PASS"
        assert interpreted["canonical_reconstruction"] == "PASS"
        assert interpreted["canonical_validation"] == "PASS"
        assert interpreted["deterministic_replay"] == "PASS"
        assert interpreted["semantic_review"]["status"] == "PASS"
        assert interpreted["theme_present"] is True
        assert interpreted["intent_present"] is True
        assert interpreted["audience_present"] is True
        assert interpreted["voice_present"] is True


class TestDryRunAndFakeExecute:
    def test_dry_run_zero_provider_calls(self):
        dry = dry_run_canary(PROJECT_NAME, authorization_scope=AUTHORIZATION_SCOPE)
        assert dry["actual_real_provider_calls"] == 0
        assert dry["pastoral_content_sent"] is False
        assert dry["schema_identity"] == "MATCH"
        result = run_global_grammar_canary(
            PROJECT_NAME,
            dry_run=True,
            authorization_scope=AUTHORIZATION_SCOPE,
        )
        assert result.accepted is True
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0

    def test_fake_execute_does_not_publish_source_map(self, tmp_path):
        engine = _fake_engine()
        result = run_global_grammar_canary(
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
        assert exe["retry"] is False
        assert PHASE == "3B.7.7A.35"

    def test_unknown_src_in_response_fails_traceability(self):
        fixture = build_synthetic_fixture()
        transport = copy.deepcopy(expected_valid_transport())
        transport["n"][2]["s"] = ["SRC000001"]
        interpreted = interpret_canary_response(
            transport, fixture=fixture, signature="test-a35"
        )
        assert interpreted["traceability"] == "FAIL" or interpreted["global_validator"] == "FAIL"
