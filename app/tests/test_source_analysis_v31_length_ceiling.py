"""Phase 3B.7.7A.29 — forensics plafond 200. 0 provider. 0 retry."""

from __future__ import annotations

import inspect

import pytest

from app.source_analysis.errors import WindowGranularityLimitExceeded
from app.source_analysis.validator import validate_source_map
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.fixtures import v2_success_transport
from app.source_analysis_local_v2.granularity import (
    TEXT_HARD_LIMITS,
    V11_MINIMAL_TEXT_HARD_LIMITS,
    validate_v11_minimal_transport_granularity,
    validate_v2_transport_granularity,
)
from app.source_analysis_local_v3.schema import (
    measure_v31_local_lite_schema_pair,
    semantic_transport_v3_fingerprint,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis.window_granularity import LOCAL_STRING_TRUNCATION
from app.source_analysis_v31_length_ceiling.constants import (
    A18_PROOF_STILL_APPLIES,
    A28_STATUS_UNCHANGED,
    CURRENT_EXAMPLE_LIMIT,
    CURRENT_IDEA_LIMIT,
    CURRENT_THEME_LIMIT,
    EXAMPLE_CHARS,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    EXPECTED_SCHEMA_HASH,
    IDEA_CHARS,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_IDENTITY_CHANGES,
    SELECTED_POLICY,
    THEME_CHARS,
    WIN003_RETRY_AUTHORIZED,
)
from app.source_analysis_v31_length_ceiling.counterfactual import (
    assert_production_limits_untouched,
    evaluate_ceiling,
)
from app.source_analysis_v31_length_ceiling.lengths import (
    candidate_limits,
    character_definition,
    prompt_length_contract,
)
from app.source_analysis_v31_length_ceiling.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_length_ceiling.replay import replay_win003_offline
from app.source_analysis.writer import source_map_path


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOffline:
    def test_package_offline_and_unwired(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_WINDOW_CALLS == 0
        assert WIN003_RETRY_AUTHORIZED is False
        assert A28_STATUS_UNCHANGED == "FAIL"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert PRODUCTION_PLANNER_VERSION == PLANNER_VERSION == "window-planner-v2.0"
        assert not source_map_path(PROJECT_NAME).is_file()


class TestCharacterAndCurrentContract:
    def test_200_means_python_len_unicode_code_points(self):
        definition = character_definition()
        assert definition["python_len_str"] is True
        assert definition["unicode_code_points"] is True
        assert definition["bytes"] is False
        assert definition["tokens"] is False
        assert definition["trimmed_length"] is False
        assert definition["normalized_length"] is False
        assert definition["proof_sample"]["python_len"] == 1
        assert definition["proof_sample"]["utf8_bytes"] == 2

    def test_limits_are_kind_specific_not_universal_200(self):
        assert CURRENT_THEME_LIMIT == 200
        assert CURRENT_EXAMPLE_LIMIT == 200
        assert CURRENT_IDEA_LIMIT == 280
        assert V11_MINIMAL_TEXT_HARD_LIMITS["TOPIC.v"] == 80
        assert V11_MINIMAL_TEXT_HARD_LIMITS["intent"] == 280
        assert TEXT_HARD_LIMITS["IDEA.v"] == 280
        assert LOCAL_STRING_TRUNCATION is False

    def test_exact_200_boundary_passes(self):
        payload = v2_success_transport()
        payload["theme"] = "t" * 200
        payload["records"][4]["v"] = "e" * 200
        payload["records"][1]["v"] = "i" * 200
        validate_v11_minimal_transport_granularity(payload)

    def test_201_rejects_theme_and_example_not_idea(self):
        theme = v2_success_transport()
        theme["theme"] = "t" * 201
        with pytest.raises(WindowGranularityLimitExceeded, match="theme"):
            validate_v11_minimal_transport_granularity(theme)

        example = v2_success_transport()
        example["records"][4]["v"] = "e" * 201
        with pytest.raises(WindowGranularityLimitExceeded, match="EXAMPLE"):
            validate_v11_minimal_transport_granularity(example)

        idea = v2_success_transport()
        idea["records"][1]["v"] = "i" * 201
        validate_v11_minimal_transport_granularity(idea)
        validate_v2_transport_granularity(idea)

    def test_idea_209_is_legal_under_production_280(self):
        payload = v2_success_transport()
        payload["records"][1]["v"] = "i" * IDEA_CHARS
        validate_v11_minimal_transport_granularity(payload)
        validate_v2_transport_granularity(payload)

    def test_no_truncation_on_reject(self):
        payload = v2_success_transport()
        original = "x" * 213
        payload["records"][4]["v"] = original
        with pytest.raises(WindowGranularityLimitExceeded):
            validate_v11_minimal_transport_granularity(payload)
        assert payload["records"][4]["v"] == original
        assert LOCAL_STRING_TRUNCATION is False


class TestWin003Replay:
    def test_reproduces_exact_failure_and_strings(self):
        replay = replay_win003_offline(PROJECT_NAME)
        assert replay["reproduced"] is True
        assert replay["structured_parse"] == "PASS"
        assert replay["v31_decoder"] == "PASS"
        assert replay["v31_validator"] == "FAIL"
        assert replay["response_repaired"] is False
        assert replay["truncated"] is False
        offenders = replay["offenders"]
        assert offenders["theme"]["chars"] == THEME_CHARS == 212
        assert offenders["idea"]["chars"] == IDEA_CHARS == 209
        assert offenders["example"]["chars"] == EXAMPLE_CHARS == 213
        assert offenders["theme"]["python_len"] == len(offenders["theme"]["value"])
        assert offenders["idea"]["kind"] == "IDEA"
        assert offenders["example"]["kind"] == "EXAMPLE"
        assert offenders["idea"]["exceeds_production"] is False
        assert offenders["theme"]["exceeds_production"] is True
        assert offenders["example"]["exceeds_production"] is True
        assert "theme : 212 caractères > 200" in replay["granularity_error"]
        assert "records[81].v (EXAMPLE) : 213 > 200" in replay["granularity_error"]
        assert "IDEA" not in replay["granularity_error"]


class TestCounterfactualPolicies:
    def test_candidate_ceilings_do_not_mutate_production(self):
        replay = replay_win003_offline(PROJECT_NAME)
        transport = replay["transport"]
        before = dict(V11_MINIMAL_TEXT_HARD_LIMITS)
        live_before = dict(TEXT_HARD_LIMITS)
        for ceiling in (225, 250, 300):
            row = evaluate_ceiling(transport, ceiling, replay=replay)
            assert row["technical"] == "PASS"
            assert V11_MINIMAL_TEXT_HARD_LIMITS == before
            assert TEXT_HARD_LIMITS == live_before
        assert_production_limits_untouched()
        assert candidate_limits(225)["theme"] == 225
        assert V11_MINIMAL_TEXT_HARD_LIMITS["theme"] == 200

    def test_200_counterfactual_still_fails(self):
        replay = replay_win003_offline(PROJECT_NAME)
        row = evaluate_ceiling(replay["transport"], 200, replay=replay)
        assert row["technical"] == "FAIL"


class TestSchemaAndCanonical:
    def test_schema_identity_unchanged_and_no_maxlength(self):
        measured = measure_v31_local_lite_schema_pair()
        assert measured["raw_bytes"] == EXPECTED_RAW_SCHEMA_BYTES == 588
        assert measured["adapted_bytes"] == EXPECTED_ADAPTED_SCHEMA_BYTES == 650
        assert semantic_transport_v31_local_lite_fingerprint() == EXPECTED_SCHEMA_HASH
        assert semantic_transport_v3_fingerprint() == EXPECTED_SCHEMA_HASH
        assert SCHEMA_IDENTITY_CHANGES is False
        assert A18_PROOF_STILL_APPLIES is True
        unsupported = (measured.get("adapted_unsupported") or {}).get("maxLength")
        assert unsupported == []

    def test_canonical_validator_has_no_200_length_cap(self):
        source = inspect.getsource(validate_source_map)
        assert "200" not in source
        assert "max_length" not in source
        assert "maxLength" not in source

    def test_prompt_states_topic_and_idea_only(self):
        contract = prompt_length_contract()
        assert contract["explicit_length_instructions"]["TOPIC.v"] is True
        assert contract["explicit_length_instructions"]["IDEA.v"] is True
        assert contract["explicit_length_instructions"]["theme"] is False
        assert contract["explicit_length_instructions"]["EXAMPLE.v"] is False
        assert contract["stated_limits"]["IDEA.v"] == 280

    def test_selected_policy_is_kind_specific(self):
        assert SELECTED_POLICY == "USE_KIND_SPECIFIC_LIMITS"
