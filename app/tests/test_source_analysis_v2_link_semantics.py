"""Phase 3B.7.7A.14 — FakeAI / offline. 0 réseau. 0 WIN001 réel."""

from __future__ import annotations

import json

import pytest

from app.ai.structured import parse_structured_output
from app.source_analysis.errors import WindowTransportValidationError
from app.source_analysis.ultra_compact_schema import SEMANTIC_TRANSPORT_VERSION
from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    build_window_system_prompt,
    window_prompt_sha256,
)
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.decoder import decode_v2_transport
from app.source_analysis_local_v2.links import (
    ALLOWED_TARGET_KINDS,
    INDEX_BASE,
    LINK_CARDINALITY,
    SELF_LINKS,
    link_contract,
)
from app.source_analysis_local_v2.prompt import (
    build_window_system_prompt_v12,
    build_window_system_prompt_v121,
    window_prompt_v12_sha256,
    window_prompt_v121_sha256,
)
from app.source_analysis_local_v2.schema import (
    build_semantic_transport_v2_schema,
    compare_v1_v2_schemas,
)
from app.source_analysis_local_v2.synthetic import measure_v2_worst_case
from app.source_analysis_local_v2.validator import validate_v2_links
from app.source_analysis_output_ceiling_review.constants import PROMPT_10_SHA, PROMPT_11_SHA
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis.canonical_vocabulary import (
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
)
from app.source_analysis_v2_grammar_canary.constants import (
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
)
from app.source_analysis_v2_grammar_canary.fixture import build_synthetic_fixture
from app.source_analysis_v2_link_semantics.constants import (
    A13_CLASSIFICATION,
    A13_RAW_SHA256,
    A13_REQUEST_IDENTITY,
    PHASE,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SEMANTIC_WIN001_AUTHORIZED,
    TARGET_JSON_LOCAL_TOKENS,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
    WINDOW_ANALYSIS_PROMPT_VERSION_V121,
)
from app.source_analysis_v2_link_semantics.evidence import read_a13_raw_bytes
from app.source_analysis_v2_link_semantics.fixtures import (
    corrected_a13_transport,
    duplicate_link_transport,
    empty_link_by_kind_transports,
    forward_link_transport,
    out_of_range_transport,
    self_link_transport,
    valid_multi_link_transport,
    wrong_kind_target_transport,
)
from app.source_analysis_v2_link_semantics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v2_link_semantics.prompt_audit import (
    audit_prompt_1_2,
    audit_prompt_1_2_1,
    prompt_hardening_facts,
)
from app.source_analysis_v2_link_semantics.replay import replay_a13_offline
from app.source_analysis_thinking_contract.canary import (
    GrammarCanaryAuthorizationError,
    run_grammar_canary,
    run_semantic_win001_canary,
)
from app.source_analysis_thinking_contract.v2_config import V2_THINKING_CONTRACT


def _allowed():
    return set(build_synthetic_fixture().window.owned_src_refs)


def _decode(payload):
    return decode_v2_transport(payload, allowed_source_refs=_allowed())


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOfflineGuards:
    def test_package_offline_and_unwired(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_WINDOW_CALLS == 0
        assert SEMANTIC_WIN001_AUTHORIZED is False
        assert PHASE == "3B.7.7A.14"

    def test_a12_still_blocks_real_canaries(self):
        with pytest.raises(GrammarCanaryAuthorizationError):
            run_grammar_canary(execute_real=True)
        with pytest.raises(GrammarCanaryAuthorizationError):
            run_semantic_win001_canary()


class TestHistoricalFreeze:
    def test_prompt_1_0_and_1_1_byte_identical(self):
        sha11 = window_prompt_sha256(
            build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION)
        )
        sha10 = window_prompt_sha256(
            build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION_V10)
        )
        assert sha11 == PROMPT_11_SHA
        assert sha10 == PROMPT_10_SHA

    def test_prompt_1_2_not_mutated(self):
        first = build_window_system_prompt_v12("en")
        second = build_window_system_prompt_v12("en")
        assert first == second
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V12 == "window-analysis-1.2"
        assert "l=TOPIC" in first

    def test_transport_v2_bytes_unchanged(self):
        comparison = compare_v1_v2_schemas()
        assert comparison["v2_generic"]["raw_bytes"] == EXPECTED_RAW_SCHEMA_BYTES == 559
        assert comparison["v2_generic"]["adapted_bytes"] == EXPECTED_ADAPTED_SCHEMA_BYTES == 621
        assert SEMANTIC_TRANSPORT_VERSION == "semantic-transport-v1"
        assert build_semantic_transport_v2_schema()["properties"]["records"]["items"][
            "properties"
        ]["l"] == {"type": "array", "items": {"type": "integer"}}

    def test_generation_c_and_planner(self):
        hashes = generation_c_hashes()
        assert hashes["raw_sha256"] == GENERATION_C_RAW_SHA256_3B43
        assert hashes["anthropic_sha256"] == GENERATION_C_ANTHROPIC_SHA256_3B43
        assert POLICY_VERSION == "window-granularity-1.0"
        assert PLANNER_VERSION == "window-planner-v2.0"
        assert V2_THINKING_CONTRACT == "THINKING_DISABLED"


class TestA13Replay:
    def test_evidence_hash_unchanged(self):
        raw = read_a13_raw_bytes()
        assert raw  # byte read only
        from hashlib import sha256

        assert sha256(raw).hexdigest() == A13_RAW_SHA256

    def test_replay_reproduces_link_failure(self):
        result = replay_a13_offline()
        assert result["structured_parse"] == "PASS"
        assert result["v2_decoder"] == "FAIL"
        assert result["v2_validator"] == "FAIL"
        assert result["reproduced"] is True
        assert result["classification"] == A13_CLASSIFICATION
        assert result["request_identity"] == A13_REQUEST_IDENTITY
        failures = {item["record_index"]: item for item in result["link_failures"]}
        assert failures[1]["record_kind"] == "IDEA"
        assert failures[1]["l"] == [1]
        assert failures[1]["targets"][0]["kind"] == "IDEA"
        assert any("self-link" in reason for reason in failures[1]["reasons"])
        assert failures[2]["record_kind"] == "EXAMPLE"
        assert failures[2]["l"] == [2]
        assert failures[2]["targets"][0]["kind"] == "EXAMPLE"

    def test_structured_parse_still_passes_invalid_links(self):
        result = replay_a13_offline()
        schema = build_semantic_transport_v2_schema()
        parsed = parse_structured_output(result["structured_text"], schema)
        assert parsed["records"][1]["l"] == [1]


class TestLinkContract:
    def test_index_base_zero(self):
        assert INDEX_BASE == 0
        assert link_contract()["index_base"] == 0

    def test_self_links_forbidden(self):
        assert SELF_LINKS == "FORBIDDEN"

    def test_allowed_target_kinds(self):
        assert ALLOWED_TARGET_KINDS["IDEA"] == frozenset({"TOPIC"})
        assert ALLOWED_TARGET_KINDS["RELATION"] == frozenset({"IDEA"})
        assert ALLOWED_TARGET_KINDS["EXAMPLE"] == frozenset({"IDEA"})
        assert ALLOWED_TARGET_KINDS["TOPIC"] == frozenset()
        assert ALLOWED_TARGET_KINDS["REFERENCE"] == frozenset()
        assert ALLOWED_TARGET_KINDS["UNCERTAINTY"] == frozenset()

    def test_idea_l_retained_for_topic_refs(self):
        contract = link_contract()
        assert contract["idea_l_retained"] is True
        assert contract["canonical_mapping"]["IDEA.l"] == "topic_refs"
        assert contract["canonical_mapping"]["EXAMPLE.l"] == "supports_idea_refs"
        assert contract["canonical_mapping"]["RELATION.l"]

    def test_cardinality(self):
        assert LINK_CARDINALITY["RELATION"] == {"min": 2, "max": 2, "empty": "forbidden"}
        assert LINK_CARDINALITY["IDEA"]["empty"] == "allowed"
        assert LINK_CARDINALITY["TOPIC"]["max"] == 0


class TestFixtures:
    def test_corrected_fixture_pass(self):
        decoded = _decode(corrected_a13_transport())
        validate_v2_links(decoded)
        assert decoded["records"][1]["l"] == [0]
        assert decoded["records"][2]["l"] == [1]

    def test_self_link_rejected(self):
        with pytest.raises(WindowTransportValidationError) as excinfo:
            _decode(self_link_transport())
        text = str(excinfo.value)
        assert "auto-lien" in text
        assert "IDEA" in text
        assert "EXAMPLE" in text

    def test_out_of_range_rejected(self):
        with pytest.raises(WindowTransportValidationError) as excinfo:
            _decode(out_of_range_transport())
        assert "hors plage" in str(excinfo.value)

    def test_wrong_kind_target_rejected(self):
        with pytest.raises(WindowTransportValidationError) as excinfo:
            _decode(wrong_kind_target_transport())
        assert "EXAMPLE ne peut lier que IDEA" in str(excinfo.value)

    def test_duplicate_links_rejected(self):
        with pytest.raises(WindowTransportValidationError) as excinfo:
            _decode(duplicate_link_transport())
        assert "dupliqué" in str(excinfo.value)

    def test_valid_multi_link_pass(self):
        decoded = _decode(valid_multi_link_transport())
        assert decoded["records"][1]["l"] == [0, 3]

    def test_forward_link_pass(self):
        decoded = _decode(forward_link_transport())
        assert decoded["records"][0]["l"] == [2]
        assert decoded["records"][0]["k"] == "IDEA"

    def test_empty_link_semantics(self):
        by_kind = empty_link_by_kind_transports()
        _decode(by_kind["idea_empty_allowed"])
        _decode(by_kind["example_empty_allowed"])
        _decode(by_kind["relation_valid"])
        with pytest.raises(WindowTransportValidationError):
            _decode(by_kind["topic_must_be_empty"])
        with pytest.raises(WindowTransportValidationError):
            _decode(by_kind["reference_must_be_empty"])
        with pytest.raises(WindowTransportValidationError):
            _decode(by_kind["uncertainty_must_be_empty"])
        with pytest.raises(WindowTransportValidationError):
            _decode(by_kind["relation_required"])


class TestPromptHardening:
    def test_1_2_was_ambiguous(self):
        audit = audit_prompt_1_2()
        assert audit["could_cause_l_as_current_record_index"] is True
        assert audit["index_base_stated"] is False
        assert audit["json_example_teaches_self_link"] is False

    def test_1_2_1_examples_correct(self):
        audit = audit_prompt_1_2_1()
        system = build_window_system_prompt_v121("en")
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V121 == "window-analysis-1.2.1"
        assert audit["has_link_rules_section"] is True
        assert audit["index_base_stated"] is True
        assert audit["self_link_forbidden_stated"] is True
        assert audit["example_teaches_self_link"] is False
        assert '"l":[0]' in system.replace(" ", "")
        assert "l=[1]" not in system
        assert window_prompt_v121_sha256(system) != window_prompt_v12_sha256(
            build_window_system_prompt_v12("en")
        )

    def test_root_cause_is_contract(self):
        facts = prompt_hardening_facts()
        assert "PROMPT_LINK_SEMANTICS_AMBIGUOUS" in facts["root_cause"]
        assert "MODEL_NONCOMPLIANCE_WITH_CLEAR_RULE" in facts["not_root_cause"]
        assert facts["schema_changed"] is False
        assert facts["second_grammar_canary_needed"] is False


class TestBudgets:
    def test_synthetic_worst_case(self):
        measured = measure_v2_worst_case()
        assert measured["local_tokens"] <= TARGET_JSON_LOCAL_TOKENS
        decoded = decode_v2_transport(
            __import__(
                "app.source_analysis_local_v2.synthetic",
                fromlist=["build_max_policy_v2_transport"],
            ).build_max_policy_v2_transport(),
            allowed_source_refs=None,
        )
        assert decoded["records"]

    def test_thinking_disabled_retained(self):
        assert V2_THINKING_CONTRACT == "THINKING_DISABLED"


class TestFakeAIAndIdentity:
    def test_fakeai_local_and_seven_window_e2e(self, tmp_path):
        from app.source_analysis_v2_link_semantics.preflight import run_fakeai_matrix

        matrix = run_fakeai_matrix(tmp_path)
        assert matrix["local_v2_ready"] is True
        assert matrix["local_prompt_version"] == "window-analysis-1.2.1"
        assert matrix["direct"]["pass"] is True
        assert matrix["direct"]["no_drop"] is True
        assert matrix["hierarchical"]["pass"] is True
        assert matrix["deferred_recovered"]["intent_kinds"]
        assert matrix["deferred_recovered"]["audience_kinds"]
        assert matrix["deferred_recovered"]["voice_tone"]
        assert matrix["src_traceable"] is True

    def test_future_identity_misses_historical(self):
        from app.source_analysis_execution_strategy.windows import load_clean_transcript
        from app.source_analysis_small_window_hierarchy.planner import (
            plan_windows_v21_small,
        )
        from app.source_analysis_v2_link_semantics.identity import future_win001_identity
        from app.source_analysis_v2_link_semantics.constants import PROJECT_NAME

        transcript = load_clean_transcript(PROJECT_NAME)
        plan = plan_windows_v21_small(transcript)
        win001 = next(window for window in plan.windows if window.window_id == "WIN001")
        identity = future_win001_identity(win001, transcript)
        assert identity["cache"] == "MISS"
        assert identity["forensic_collides"] is False
        assert identity["executed"] is False
        assert identity["authorized"] is False
        assert identity["analysis_signature"] != A13_REQUEST_IDENTITY
        assert all(value is False for value in identity["cache_collisions"].values())

    def test_real_preflight_under_hard_max(self):
        from app.source_analysis_v2_link_semantics.preflight import (
            real_seven_window_preflight,
        )

        preflight = real_seven_window_preflight()
        assert preflight["window_count"] == 7
        assert preflight["all_under_35000"] is True
        assert preflight["provider_called"] is False
        assert preflight["max_future_window_input"] <= 35000
