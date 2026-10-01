"""Phase 3B.7.7A.37 — FakeAI / offline. 0 réseau. 0 consolidation réelle."""

from __future__ import annotations

import copy
import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.models import format_idea_id, format_topic_id
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_canary_forensics.constants import (
    A34_STATUS_PRESERVED,
    A35_DROP_PROSE,
    A35_STATUS_PRESERVED,
    NEXT_PROMPT_VERSION,
    NEXT_SCHEMA_ADAPTED_BYTES,
    NEXT_SCHEMA_HASH,
    NEXT_SCHEMA_RAW_BYTES,
    NEXT_TRANSPORT_VERSION,
    OLD_PROMPT_VERSION,
    OLD_TRANSPORT_VERSION,
    REAL_PROVIDER_CALLS_THIS_PHASE as A36_REAL_PROVIDER_CALLS,
)
from app.source_analysis_v31_global_canary_forensics.fixture import (
    expected_valid_transport_v11,
    fakeai_catalog,
    fakeai_invalid_drop_prose,
    fakeai_link_related_rejected,
    next_expected_dispositions,
    pipeline_pass,
)
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    DROP_REASON_CODES,
    REASON_CODES,
    REPRESENTATION_OPS,
    measure_global_schema_v11,
)
from app.source_analysis_v31_global_canary_forensics.validator_v11 import (
    validate_global_transport_v11,
)
from app.source_analysis_v31_global_grammar_canary.constants import (
    AUTHORIZATION_SCOPE as A35_SCOPE,
    PHASE as A35_PHASE,
)
from app.source_analysis_v31_global_grammar_canary.fixture import (
    build_synthetic_fixture,
    expected_dispositions as a35_expected_dispositions,
    expected_valid_transport as a35_expected_valid_transport,
)
from app.source_analysis_v31_global_preflight.normalize import build_normalized_input
from app.source_analysis_v31_global_preflight.transport import measure_global_schema
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    FORBIDDEN_WINDOW_IDS,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    SYNTHETIC_SRC_IDS,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v11_grammar_canary.enums import audit_raw_enums
from app.source_analysis_v31_global_v11_grammar_canary.guard import (
    GlobalGrammarCanaryError,
    OneShotCallGuard,
    assert_synthetic_identity,
    reject_real_project_input,
    validate_authorization_scope,
)
from app.source_analysis_v31_global_v11_grammar_canary.identity import (
    recompute_schema_identity,
    verify_schema_identity,
)
from app.source_analysis_v31_global_v11_grammar_canary.payload import build_audited_request
from app.source_analysis_v31_global_v11_grammar_canary.runner import (
    dry_run_canary,
    run_global_v11_grammar_canary,
)
from app.source_analysis_v31_global_v11_grammar_canary.validate import (
    interpret_canary_response_v11,
)


def _fixture_ids():
    fixture = build_synthetic_fixture()
    local_src: dict[str, list[str]] = {}
    for window in fixture.compact.get("windows") or []:
        for item in window.get("records") or []:
            local_src[str(item.get("id") or "")] = list(item.get("s") or [])
    return fixture, local_src


def _fake_engine(payload=None):
    transport = payload or expected_valid_transport_v11()
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
    def test_a34_a35_a36_remain_immutable(self):
        assert A34_STATUS_PRESERVED == "PASS"
        assert A35_STATUS_PRESERVED == "FAIL"
        assert A35_PHASE == "3B.7.7A.35"
        assert A36_REAL_PROVIDER_CALLS == 0
        assert OLD_PROMPT_VERSION == "global-consolidation-1.0"
        assert OLD_TRANSPORT_VERSION == "global-consolidation-transport-1.0"
        v10 = measure_global_schema()
        assert v10["raw_bytes"] == 1040
        assert v10["adapted_bytes"] == 1195
        assert a35_expected_dispositions()["SYN002:I2"] == "LINK_RELATED"
        a35_drop = [
            row for row in a35_expected_valid_transport()["d"] if row["i"] == "SYN001:I3"
        ][0]
        assert a35_drop["w"] == "transport_artifact"
        assert PHASE == "3B.7.7A.37"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"
        assert not source_map_path(PROJECT_NAME).is_file()

    def test_schema_1_1_identity(self):
        measured = measure_global_schema_v11()
        recomputed = recompute_schema_identity()
        assert measured["raw_bytes"] == SCHEMA_RAW_BYTES == NEXT_SCHEMA_RAW_BYTES == 1182
        assert measured["adapted_bytes"] == SCHEMA_ADAPTED_BYTES == NEXT_SCHEMA_ADAPTED_BYTES == 1337
        assert measured["hash"] == SCHEMA_HASH == NEXT_SCHEMA_HASH
        assert SCHEMA_HASH == (
            "c98e57c3497843abdf294abfb2b691638ed54bdd86e651ab813efca563c6b3e6"
        )
        assert recomputed["matches_a36_constants"] is True
        verified = verify_schema_identity(PROJECT_NAME)
        assert verified["schema_identity"] == "MATCH"
        enums = recomputed["enum_contract"]
        assert enums["d_o_enum"] == list(REPRESENTATION_OPS)
        assert enums["d_w_enum"] == list(REASON_CODES)
        assert enums["link_related_absent"] is True
        assert TRANSPORT_VERSION == NEXT_TRANSPORT_VERSION
        assert PROMPT_VERSION == NEXT_PROMPT_VERSION
        assert THINKING_MODE == "disabled"
        assert PRODUCTION_MAX_OUTPUT_TOKENS == 32000
        assert CANARY_MAX_OUTPUT_TOKENS == 2048


class TestAuthorizationAndGuard:
    def test_missing_and_wrong_scope_fail_before_network(self):
        with pytest.raises(GlobalGrammarCanaryError):
            validate_authorization_scope(None)
        result = run_global_v11_grammar_canary(
            "fixture",
            dry_run=True,
            authorization_scope="WRONG",
        )
        assert result.accepted is False
        assert result.blocked_precall is True
        assert result.engine_generate_attempts == 0

    def test_real_consolidation_and_a35_scopes_rejected(self):
        for scope in (
            "REAL_GLOBAL_CONSOLIDATION_CANARY",
            A35_SCOPE,
            "WIN001_ONLY",
            "GLOBAL_CONSOLIDATION_TINY_SYNTHETIC_GRAMMAR_CANARY_ONLY",
        ):
            result = run_global_v11_grammar_canary(
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
        expected = next_expected_dispositions()
        blob = json.dumps(fixture.to_safe_dict())
        for window_id in FORBIDDEN_WINDOW_IDS:
            assert window_id not in blob
        assert "pastoral_retreat" not in blob.lower()
        assert expected["SYN001:I1"] == "KEEP"
        assert expected["SYN001:I2"] == "MERGE_EQUIVALENT"
        assert expected["SYN001:I3"] == "DROP"
        assert expected["SYN002:I1"] == "MERGE_EQUIVALENT"
        assert expected["SYN002:I2"] == "KEEP"
        assert "LINK_RELATED" not in expected.values()
        assert "and then uh" in json.dumps(fixture.compact)

    def test_payload_uses_prompt_101_and_transport_11(self):
        fixture = build_synthetic_fixture()
        built = build_audited_request(fixture, project_name=PROJECT_NAME)
        audit = built["audit"]
        assert audit["model"] == "claude-sonnet-5"
        assert audit["thinking_type"] == "disabled"
        assert audit["effort_present"] is False
        assert audit["temperature_present"] is False
        assert audit["max_tokens"] == CANARY_MAX_OUTPUT_TOKENS
        assert audit["schema_hash"] == SCHEMA_HASH
        assert audit["raw_bytes"] == 1182
        assert audit["adapted_bytes"] == 1337
        assert audit["prompt_version"] == "global-consolidation-1.0.1"
        assert audit["schema_version"] == "global-consolidation-transport-1.1"
        assert "WIN001" not in built["request"].prompt
        assert "SRC000001" not in built["request"].prompt
        assert "LINK_RELATED is not a valid" in (built["request"].system_prompt or "")


class TestEnumAndMatrix:
    def _validate(self, payload):
        fixture, local_src = _fixture_ids()
        return validate_global_transport_v11(
            payload,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            allowed_source_refs=set(fixture.allowed_source_refs),
            local_src_by_input=local_src,
        )

    def test_valid_drop_token_and_non_drop_none_accepted(self):
        payload = expected_valid_transport_v11()
        result = self._validate(payload)
        assert result["ok"] is True
        enums = audit_raw_enums(payload)
        assert enums["status"] == "PASS"
        assert enums["free_text_dw_count"] == 0
        assert enums["link_related_count"] == 0
        assert enums["matrix_violation_count"] == 0
        assert "non_substantive_fragment" in enums["observed_dw_tokens"]
        assert "none" in enums["observed_dw_tokens"]

    def test_link_related_rejected(self):
        payload = fakeai_link_related_rejected()
        result = self._validate(payload)
        assert result["ok"] is False
        enums = audit_raw_enums(payload)
        assert enums["link_related_count"] == 1
        assert enums["ok"] is False

    def test_drop_prose_rejected_no_repair(self):
        payload = fakeai_invalid_drop_prose()
        result = self._validate(payload)
        assert result["ok"] is False
        enums = audit_raw_enums(payload)
        assert enums["free_text_dw_count"] == 1
        assert enums["free_text_dw"][0]["w"] == A35_DROP_PROSE
        assert payload["d"][2]["w"] == A35_DROP_PROSE

    def test_drop_plus_none_rejected(self):
        payload = copy.deepcopy(expected_valid_transport_v11())
        for row in payload["d"]:
            if row["i"] == "SYN001:I3":
                row["w"] = "none"
        result = self._validate(payload)
        assert result["ok"] is False
        enums = audit_raw_enums(payload)
        assert any("DROP + none" in item for item in enums["matrix_violations"])

    def test_non_drop_plus_drop_reason_rejected(self):
        payload = copy.deepcopy(expected_valid_transport_v11())
        for row in payload["d"]:
            if row["i"] == "SYN001:I1":
                row["w"] = "non_substantive_fragment"
        result = self._validate(payload)
        assert result["ok"] is False
        enums = audit_raw_enums(payload)
        assert any("KEEP + DROP reason" in item for item in enums["matrix_violations"])

    def test_unknown_drop_token_rejected(self):
        payload = copy.deepcopy(expected_valid_transport_v11())
        for row in payload["d"]:
            if row["i"] == "SYN001:I3":
                row["w"] = "filler"
        result = self._validate(payload)
        assert result["ok"] is False
        assert "filler" not in DROP_REASON_CODES


class TestPipeline:
    def test_valid_transport_full_pipeline(self):
        fixture = build_synthetic_fixture()
        interpreted = interpret_canary_response_v11(
            expected_valid_transport_v11(),
            fixture=fixture,
            signature="test-a37",
        )
        assert pipeline_pass(interpreted) is True
        assert interpreted["structured_parse"] == "PASS"
        assert interpreted["decoder"] == "PASS"
        assert interpreted["handle_validation"] == "PASS"
        assert interpreted["global_validator"] == "PASS"
        assert interpreted["idea_disposition_coverage"] == 100.0
        assert interpreted["silent_drops"] == 0
        assert interpreted["traceability"] == "PASS"
        assert interpreted["canonical_reconstruction"] == "PASS"
        assert interpreted["canonical_validation"] == "PASS"
        assert interpreted["deterministic_replay"] == "PASS"
        assert interpreted["semantic_review"]["status"] == "PASS"
        assert interpreted["link_related_count"] == 0
        assert interpreted["free_text_drop_reason"] == 0
        assert interpreted["operation_reason_matrix"] == "PASS"
        assert interpreted["merge_source_union"] == "PASS"
        assert interpreted["drop_token_ok"] is True
        assert interpreted["keep_plus_independent_relation"] is True
        assert interpreted["repetition_required"] is False
        reconstruction = interpreted["reconstruction"]
        assert reconstruction["all_idea_kinds_empty"] is True
        ids = reconstruction["assigned_provider_to_canonical"]
        assert any(value.startswith("TOP") for value in ids.values())
        assert any(value.startswith("IDEA") for value in ids.values())
        source_map_ideas = reconstruction.get("ideas") or []
        assert all(item.get("kind") == "" for item in source_map_ideas)

    def test_silent_drop_rejected(self):
        fixture = build_synthetic_fixture()
        payload = copy.deepcopy(expected_valid_transport_v11())
        payload["d"] = [row for row in payload["d"] if row["i"] != "SYN001:I1"]
        interpreted = interpret_canary_response_v11(
            payload, fixture=fixture, signature="test-a37"
        )
        assert interpreted["silent_drops"] == 1
        assert interpreted["global_validator"] == "FAIL"

    def test_merge_union_missing_src_rejected(self):
        fixture = build_synthetic_fixture()
        payload = copy.deepcopy(expected_valid_transport_v11())
        for node in payload["n"]:
            if node["h"] == "I2":
                node["s"] = ["SRC998003"]
        interpreted = interpret_canary_response_v11(
            payload, fixture=fixture, signature="test-a37"
        )
        assert interpreted["merge_source_union"] == "FAIL"
        assert interpreted["global_validator"] == "FAIL"

    def test_optional_repetition_absence_is_not_failure(self):
        payload = expected_valid_transport_v11()
        assert not any(item.get("k") == "REPETITION" for item in payload["n"])
        fixture = build_synthetic_fixture()
        interpreted = interpret_canary_response_v11(
            payload, fixture=fixture, signature="test-a37"
        )
        assert interpreted["semantic_review"]["status"] == "PASS"
        assert interpreted["repetition_required"] is False

    def test_canonical_ids_and_replay(self):
        fixture = build_synthetic_fixture()
        interpreted = interpret_canary_response_v11(
            expected_valid_transport_v11(),
            fixture=fixture,
            signature="test-a37",
        )
        assigned = interpreted["reconstruction"]["assigned_provider_to_canonical"]
        assert format_topic_id(1) in assigned.values()
        assert format_idea_id(1) in assigned.values()
        assert interpreted["deterministic_replay"] == "PASS"

    def test_fakeai_catalog_valid_only(self):
        fixture = build_synthetic_fixture()
        catalog = fakeai_catalog()
        for name, payload in catalog.items():
            interpreted = interpret_canary_response_v11(
                payload, fixture=fixture, signature=f"fakeai-{name}"
            )
            if name == "VALID":
                assert pipeline_pass(interpreted) is True
            else:
                assert pipeline_pass(interpreted) is False


class TestDryRunAndFakeExecute:
    def test_dry_run_twice_deterministic_and_zero_calls(self):
        first = dry_run_canary(PROJECT_NAME, authorization_scope=AUTHORIZATION_SCOPE)
        second = dry_run_canary(PROJECT_NAME, authorization_scope=AUTHORIZATION_SCOPE)
        assert first["dry_run_identity"] == second["dry_run_identity"]
        assert first["actual_real_provider_calls"] == 0
        assert first["pastoral_content_sent"] is False
        assert first["schema_identity"] == "MATCH"
        result = run_global_v11_grammar_canary(
            PROJECT_NAME,
            dry_run=True,
            authorization_scope=AUTHORIZATION_SCOPE,
        )
        assert result.accepted is True
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0

    def test_fake_execute_does_not_publish_source_map(self, tmp_path):
        engine = _fake_engine()
        result = run_global_v11_grammar_canary(
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
        assert PHASE == "3B.7.7A.37"
