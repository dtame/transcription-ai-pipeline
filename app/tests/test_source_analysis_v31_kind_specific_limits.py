"""Phase 3B.7.7A.30 — limites kind-specific + replay WIN003. 0 provider."""

from __future__ import annotations

import pytest

from app.source_analysis.errors import WindowGranularityLimitExceeded
from app.source_analysis.window_granularity import (
    POLICY_VERSION,
    TEXT_HARD_LIMITS as V10_LIMITS,
    validate_window_transport_granularity,
)
from app.source_analysis.window_signature import WindowSignatureInputs
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.constants import (
    GRANULARITY_POLICY_VERSION,
    GRANULARITY_POLICY_VERSION_12_KIND_SPECIFIC,
)
from app.source_analysis_local_v2.fixtures import v2_success_transport
from app.source_analysis_local_v2.granularity import (
    EXAMPLE_V_TEXT_HARD_LIMIT,
    IDEA_V_TEXT_HARD_LIMIT,
    TEXT_HARD_LIMITS,
    THEME_TEXT_HARD_LIMIT,
    V11_MINIMAL_TEXT_HARD_LIMITS,
    granularity_policy,
    validate_v11_minimal_transport_granularity,
    validate_v2_transport_granularity,
)
from app.source_analysis_local_v3.schema import (
    measure_v31_local_lite_schema_pair,
    semantic_transport_v3_fingerprint,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_kind_specific_limits.constants import (
    A18_PROOF_STILL_APPLIES,
    A28_HISTORICAL_STATUS,
    A28_VALIDATOR_ERROR,
    A29_STATUS,
    EXAMPLE_CHARS,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    EXPECTED_SCHEMA_HASH,
    IDEA_CHARS,
    NEW_EXAMPLE_LIMIT,
    NEW_THEME_LIMIT,
    OLD_EXAMPLE_LIMIT,
    OLD_THEME_LIMIT,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SELECTED_POLICY,
    SIGNATURE_DECISION,
    THEME_CHARS,
    WIN003_NEW_PROVIDER_CALL,
    WIN003_REQUEST_ID,
)
from app.source_analysis_v31_kind_specific_limits.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_kind_specific_limits.replay import replay_saved_win003
from app.source_analysis_v31_length_ceiling.replay import replay_win003_offline


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _set_kind_value(payload: dict, kind: str, text: str) -> dict:
    for item in payload["records"]:
        if item["k"] == kind:
            item["v"] = text
            return payload
    raise AssertionError(f"kind {kind} absent")


class TestOffline:
    def test_package_offline_and_unwired(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_WINDOW_CALLS == 0
        assert WIN003_NEW_PROVIDER_CALL is False
        assert A28_HISTORICAL_STATUS == "FAIL"
        assert A29_STATUS == "PASS"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert PRODUCTION_PLANNER_VERSION == PLANNER_VERSION == "window-planner-v2.0"
        assert not source_map_path(PROJECT_NAME).is_file()


class TestKindSpecificPolicy:
    def test_approved_limits_and_no_universal_ceiling(self):
        assert SELECTED_POLICY == "USE_KIND_SPECIFIC_LIMITS"
        assert OLD_THEME_LIMIT == 200
        assert NEW_THEME_LIMIT == THEME_TEXT_HARD_LIMIT == 225
        assert OLD_EXAMPLE_LIMIT == 200
        assert NEW_EXAMPLE_LIMIT == EXAMPLE_V_TEXT_HARD_LIMIT == 225
        assert IDEA_V_TEXT_HARD_LIMIT == 280
        assert TEXT_HARD_LIMITS["theme"] == 225
        assert TEXT_HARD_LIMITS["EXAMPLE.v"] == 225
        assert TEXT_HARD_LIMITS["IDEA.v"] == 280
        assert TEXT_HARD_LIMITS["TOPIC.v"] == 80
        assert TEXT_HARD_LIMITS["RELATION.v"] == 40
        assert TEXT_HARD_LIMITS["REFERENCE.v"] == 220
        assert TEXT_HARD_LIMITS["UNCERTAINTY.v"] == 280
        assert TEXT_HARD_LIMITS["intent"] == 280
        assert TEXT_HARD_LIMITS["aud"] == 280
        assert len(set(TEXT_HARD_LIMITS.values())) > 1
        assert 225 in TEXT_HARD_LIMITS.values()
        assert not all(value == 225 for value in TEXT_HARD_LIMITS.values())
        policy = granularity_policy()
        assert policy["policy_version"] == GRANULARITY_POLICY_VERSION_12_KIND_SPECIFIC
        assert policy["historical_1_1_minimal"] == GRANULARITY_POLICY_VERSION
        assert policy["universal_ceiling"] is False
        assert policy["local_string_truncation"] is False

    def test_historical_policies_remain_reproducible(self):
        assert POLICY_VERSION == "window-granularity-1.0"
        assert V10_LIMITS["theme"] == 200
        assert V10_LIMITS["EXAMPLE.v"] == 200
        assert V11_MINIMAL_TEXT_HARD_LIMITS["theme"] == 200
        assert V11_MINIMAL_TEXT_HARD_LIMITS["EXAMPLE.v"] == 200
        assert GRANULARITY_POLICY_VERSION == "window-granularity-1.1-minimal"

    def test_theme_boundaries(self):
        for length in (224, 225):
            payload = v2_success_transport()
            payload["theme"] = "t" * length
            validate_v2_transport_granularity(payload)
        fail = v2_success_transport()
        fail["theme"] = "t" * 226
        with pytest.raises(WindowGranularityLimitExceeded, match=r"theme : 226 caractères > 225"):
            validate_v2_transport_granularity(fail)

    def test_example_boundaries(self):
        for length in (224, 225):
            payload = v2_success_transport()
            _set_kind_value(payload, "EXAMPLE", "e" * length)
            validate_v2_transport_granularity(payload)
        fail = v2_success_transport()
        _set_kind_value(fail, "EXAMPLE", "e" * 226)
        with pytest.raises(
            WindowGranularityLimitExceeded,
            match=r"records\[4\]\.v \(EXAMPLE\) : 226 > 225",
        ):
            validate_v2_transport_granularity(fail)

    def test_idea_regression(self):
        for length in (209, 218, 280):
            payload = v2_success_transport()
            _set_kind_value(payload, "IDEA", "i" * length)
            validate_v2_transport_granularity(payload)
        fail = v2_success_transport()
        _set_kind_value(fail, "IDEA", "i" * 281)
        with pytest.raises(
            WindowGranularityLimitExceeded,
            match=r"records\[1\]\.v \(IDEA\) : 281 > 280",
        ):
            validate_v2_transport_granularity(fail)

    def test_other_kind_regressions(self):
        cases = (
            ("TOPIC", 80, 81),
            ("RELATION", 40, 41),
            ("REFERENCE", 220, 221),
            ("UNCERTAINTY", 280, 281),
        )
        for kind, allowed, over in cases:
            ok = v2_success_transport()
            _set_kind_value(ok, kind, "x" * allowed)
            validate_v2_transport_granularity(ok)
            fail = v2_success_transport()
            _set_kind_value(fail, kind, "x" * over)
            with pytest.raises(WindowGranularityLimitExceeded, match=kind) as excinfo:
                validate_v2_transport_granularity(fail)
            assert f"{over} > {allowed}" in str(excinfo.value)

    def test_over_limit_rejected_unchanged(self):
        payload = v2_success_transport()
        original = "z" * 226
        payload["theme"] = original
        _set_kind_value(payload, "EXAMPLE", original)
        with pytest.raises(WindowGranularityLimitExceeded):
            validate_v2_transport_granularity(payload)
        assert payload["theme"] == original
        assert payload["records"][4]["v"] == original

    def test_historical_1_0_still_rejects_201_theme(self):
        payload = v2_success_transport()
        payload["theme"] = "t" * 201
        with pytest.raises(WindowGranularityLimitExceeded, match="theme"):
            validate_window_transport_granularity(payload)


class TestWin003Replay:
    def test_historical_a28_still_fails_same_error(self):
        historical = replay_win003_offline(PROJECT_NAME)
        assert historical["reproduced"] is True
        assert historical["granularity_error"] == A28_VALIDATOR_ERROR
        assert "theme : 212 caractères > 200" in historical["granularity_error"]
        assert "records[81].v (EXAMPLE) : 213 > 200" in historical["granularity_error"]
        assert A28_HISTORICAL_STATUS == "FAIL"

    def test_saved_response_passes_corrected_policy(self):
        replay = replay_saved_win003(PROJECT_NAME)
        assert replay["provider_calls"] == 0
        assert replay["identity"]["same_paid_response"] is True
        assert replay["identity"]["request_id"] == WIN003_REQUEST_ID
        assert replay["theme_length"] == THEME_CHARS == 212
        assert replay["example_length"] == EXAMPLE_CHARS == 213
        assert replay["idea_length"] == IDEA_CHARS == 209
        assert replay["values_unchanged"] is True
        assert replay["historical_a28_reproduced"] is True
        assert replay["structured_parse"] == "PASS"
        assert replay["local_lite_metadata"] == "PASS"
        assert replay["src"] == "PASS"
        assert replay["handles"] == "PASS"
        assert replay["numeric_regression"] == "NO"
        assert replay["decoder"] == "PASS"
        assert replay["local_validator"] == "PASS"
        assert replay["capacity"] == "absent"
        assert replay["technical_ok"] is True
        assert replay["response_repaired"] is False
        assert replay["truncated"] is False
        assert replay["live_granularity_error"] is None
        assert replay["canonical_reconstruction"] == "PASS"
        assert replay["mixed_compatibility"] == "PASS"
        assert replay["all_kinds_empty"] is True
        assert replay["importance_to_kind_contamination"] == 0
        assert replay["semantic_quality"] == "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
        relations = replay["relation_quality_summary"] or {}
        assert relations.get("well-supported") == 0
        assert relations.get("plausible-loose") == 18
        assert relations.get("incorrect") == 0
        assert relations.get("unverifiable") == 0


class TestSchemaAndSignature:
    def test_schema_identity_unchanged(self):
        measured = measure_v31_local_lite_schema_pair()
        assert measured["raw_bytes"] == EXPECTED_RAW_SCHEMA_BYTES == 588
        assert measured["adapted_bytes"] == EXPECTED_ADAPTED_SCHEMA_BYTES == 650
        assert semantic_transport_v31_local_lite_fingerprint() == EXPECTED_SCHEMA_HASH
        assert semantic_transport_v3_fingerprint() == EXPECTED_SCHEMA_HASH
        assert A18_PROOF_STILL_APPLIES is True

    def test_signature_does_not_include_granularity_policy(self):
        assert "granularity" not in WindowSignatureInputs.__dataclass_fields__
        assert "policy_version" not in WindowSignatureInputs.__dataclass_fields__
        assert SIGNATURE_DECISION == "REUSE_EXISTING_SIGNATURE"
