"""Phase 3B.7.7A.36 — FakeAI / offline forensics. 0 réseau. 0 consolidation réelle."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_canary_forensics.analysis import (
    classify_a35_failures,
    disposition_semantics,
    drop_contract_analysis,
    fixture_expectation_review,
    redesign_decision,
    repetition_policy,
    root_causes,
)
from app.source_analysis_v31_global_canary_forensics.constants import (
    A34_SCHEMA_ADAPTED,
    A34_SCHEMA_HASH,
    A34_SCHEMA_RAW,
    A34_STATUS_PRESERVED,
    A35_DROP_PROSE,
    A35_RAW_SHA256,
    A35_RAW_SIZE,
    A35_REQUEST_ID,
    A35_STATUS_PRESERVED,
    CANONICAL_DROP_TOKEN,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MODEL,
    NEW_GRAMMAR_CANARY_REQUIRED,
    NEXT_PROMPT_VERSION,
    NEXT_SCHEMA_ADAPTED_BYTES,
    NEXT_SCHEMA_HASH,
    NEXT_SCHEMA_RAW_BYTES,
    NEXT_TRANSPORT_VERSION,
    OLD_PROMPT_VERSION,
    OLD_TRANSPORT_VERSION,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    REAL_CONSOLIDATION_CALLS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_CHANGED,
    THINKING_MODE,
)
from app.source_analysis_v31_global_canary_forensics.evidence import (
    read_a35_raw_bytes,
    verify_a35_identity,
)
from app.source_analysis_v31_global_canary_forensics.fixture import (
    expected_valid_transport_v11,
    fakeai_catalog,
    fakeai_invalid_drop_prose,
    interpret_transport_v11,
    next_expected_dispositions,
    pipeline_pass,
)
from app.source_analysis_v31_global_canary_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_canary_forensics.prompt_v101 import (
    prompt_v101_bundle,
    prompt_v10_bundle_frozen,
)
from app.source_analysis_v31_global_canary_forensics.replay import (
    parse_a35_transport,
    replay_a35_under_v10_contract,
    replay_drop_only_counterfactual,
)
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    DROP_REASON_CODES,
    REASON_CODES,
    measure_global_schema_v11,
    schema_contains_unsupported_constructs,
)
from app.source_analysis_v31_global_canary_forensics.validator_v11 import (
    validate_global_transport_v11,
)
from app.source_analysis_v31_global_grammar_canary.fixture import (
    build_synthetic_fixture,
    expected_valid_transport,
)
from app.source_analysis_v31_global_preflight.prompt import prompt_bundle as prompt_v10
from app.source_analysis_v31_global_preflight.transport import measure_global_schema
from app.source_analysis_v31_global_preflight.validator import validate_global_transport


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _fixture_ids():
    fixture = build_synthetic_fixture()
    local_src: dict[str, list[str]] = {}
    for window in fixture.compact.get("windows") or []:
        for item in window.get("records") or []:
            local_src[str(item.get("id") or "")] = list(item.get("s") or [])
    return fixture, local_src


class TestOfflineFreeze:
    def test_package_offline_and_unwired(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_WINDOW_CALLS == 0
        assert REAL_CONSOLIDATION_CALLS == 0
        assert A34_STATUS_PRESERVED == "PASS"
        assert A35_STATUS_PRESERVED == "FAIL"
        assert PHASE == "3B.7.7A.36"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"
        assert RELATION_QUALITY_TECHNICAL_DEBT == "YES"
        assert MODEL == "claude-sonnet-5"
        assert THINKING_MODE == "disabled"
        assert PRODUCTION_MAX_OUTPUT_TOKENS == 32000
        assert READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO"
        assert not source_map_path(PROJECT_NAME).is_file()

    def test_historical_prompt_and_schema_unmutated(self):
        measured = measure_global_schema()
        assert measured["raw_bytes"] == A34_SCHEMA_RAW == 1040
        assert measured["adapted_bytes"] == A34_SCHEMA_ADAPTED == 1195
        assert measured["hash"] == A34_SCHEMA_HASH
        prompt = prompt_v10()
        frozen = prompt_v10_bundle_frozen()
        assert prompt["prompt_version"] == OLD_PROMPT_VERSION == "global-consolidation-1.0"
        assert frozen["combined_sha256"] == prompt["combined_sha256"]
        assert frozen["combined_sha256"] == (
            "e21e472186ef3789eaef2a8bb0deca5cf906e5b917efefb15d3da17eaa120e4d"
        )
        assert OLD_TRANSPORT_VERSION == "global-consolidation-transport-1.0"


class TestA35IdentityAndReplay:
    def test_request_identity_and_raw_immutability(self):
        identity = verify_a35_identity()
        assert identity["ok"] is True
        assert identity["request_id"] == A35_REQUEST_ID == "req_011CfW2QDYYiMNWoMSoeucx1"
        raw = read_a35_raw_bytes()
        assert hashlib.sha256(raw).hexdigest() == A35_RAW_SHA256
        assert len(raw) == A35_RAW_SIZE
        parsed = parse_a35_transport()
        drop = next(
            row
            for row in parsed["transport"]["d"]
            if row["i"] == "SYN001:I3"
        )
        assert drop["w"] == A35_DROP_PROSE
        raw_again = read_a35_raw_bytes()
        assert hashlib.sha256(raw_again).hexdigest() == A35_RAW_SHA256

    def test_exact_a35_replay_still_fails_v10_contract(self):
        replay = replay_a35_under_v10_contract()
        assert replay["structured_parse"] == "PASS"
        assert replay["decoder"] == "PASS"
        assert replay["handle_validation"] == "PASS"
        assert replay["idea_disposition_coverage"] == 100.0
        assert replay["silent_drops"] == 0
        assert replay["traceability"] == "PASS"
        assert replay["global_validator"] == "FAIL"
        assert replay["canonical_reconstruction"] == "PASS"
        assert replay["semantic_review"] == "FAIL"
        assert replay["reproduced_a35_failure"] is True
        assert replay["historical_status_unchanged"] == "FAIL"
        assert replay["repaired"] is False
        assert replay["root_validator_violations"]
        assert not replay["cascade_validator_violations"]
        assert replay["drop_row"]["w"] == A35_DROP_PROSE
        v11 = interpret_transport_v11(replay["transport"], signature="a35-on-v11")
        assert pipeline_pass(v11) is False
        assert v11["global_validator"] == "FAIL"

    def test_a35_valid_fakeai_still_passes_historical_validator(self):
        fixture = build_synthetic_fixture()
        transport = expected_valid_transport()
        result = validate_global_transport(
            transport,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            allowed_source_refs=set(fixture.allowed_source_refs),
        )
        assert result["ok"] is True


class TestDropContract:
    def test_drop_prose_fails_and_is_not_normalized(self):
        interpreted = interpret_transport_v11(fakeai_invalid_drop_prose())
        assert pipeline_pass(interpreted) is False
        drop = next(
            row
            for row in (interpreted.get("transport") or {}).get("d") or []
            if row.get("i") == "SYN001:I3"
        )
        assert drop["w"] == A35_DROP_PROSE
        assert interpreted["global_validator"] == "FAIL"
        blob = json.dumps(interpreted.get("errors") or [])
        assert "exact allowed token" in blob or interpreted["structured_parse"] == "FAIL"

    def test_all_allowed_drop_tokens_and_invalid_token(self):
        fixture, local_src = _fixture_ids()
        for token in DROP_REASON_CODES:
            transport = copy.deepcopy(expected_valid_transport_v11())
            for row in transport["d"]:
                if row["i"] == "SYN001:I3":
                    row["w"] = token
            result = validate_global_transport_v11(
                transport,
                idea_input_ids=list(fixture.idea_input_ids),
                allowed_input_ids=set(fixture.allowed_input_ids),
                allowed_source_refs=set(fixture.allowed_source_refs),
                local_src_by_input=local_src,
            )
            assert result["ok"] is True, token
        transport = copy.deepcopy(expected_valid_transport_v11())
        for row in transport["d"]:
            if row["i"] == "SYN001:I3":
                row["w"] = "not_important"
        result = validate_global_transport_v11(
            transport,
            idea_input_ids=list(fixture.idea_input_ids),
            allowed_input_ids=set(fixture.allowed_input_ids),
            allowed_source_refs=set(fixture.allowed_source_refs),
            local_src_by_input=local_src,
        )
        assert result["ok"] is False

    def test_non_drop_reason_must_be_none(self):
        catalog = fakeai_catalog()
        interpreted = interpret_transport_v11(catalog["NON_DROP_REASON_NOT_NONE"])
        assert interpreted["global_validator"] == "FAIL"

    def test_drop_analysis_machine_enum(self):
        analysis = drop_contract_analysis()
        assert analysis["schema_constrains_reason_to_enum"] is False
        assert analysis["validator_imposes_exact_token"] is True
        assert analysis["field_class"] == "MACHINE_CONTROLLED_ENUM"
        assert analysis["vocabulary_expanded_to_accept_a35_prose"] is False
        assert CANONICAL_DROP_TOKEN in analysis["canonical_vocabulary"]
        assert set(REASON_CODES) >= set(DROP_REASON_CODES) | {"none"}


class TestDispositionSemantics:
    def test_keep_merge_other_and_retired_link_related(self):
        semantics = disposition_semantics()
        assert semantics["KEEP"]["a35_companion_planting"]["semantically_invalid"] is False
        assert semantics["LINK_RELATED"]["keep_and_relation_independent"] is True
        assert semantics["LINK_RELATED"]["contract"] == "RETIRED_FROM_REPRESENTATION_ENUM"
        assert "LINK_RELATED" not in semantics["representation_ops_v11"]
        catalog = fakeai_catalog()
        linked = interpret_transport_v11(catalog["LINK_RELATED_REJECTED"])
        assert pipeline_pass(linked) is False
        keep = interpret_transport_v11(expected_valid_transport_v11())
        assert keep["semantic_review"]["status"] == "PASS"
        assert next_expected_dispositions()["SYN002:I2"] == "KEEP"

    def test_silent_drop_and_coverage(self):
        catalog = fakeai_catalog()
        silent = interpret_transport_v11(catalog["SILENT_DROP"])
        assert silent["silent_drops"] == 1
        assert silent["global_validator"] == "FAIL"
        valid = interpret_transport_v11(expected_valid_transport_v11())
        assert valid["idea_disposition_coverage"] == 100.0
        assert valid["silent_drops"] == 0

    def test_merge_source_union(self):
        catalog = fakeai_catalog()
        bad = interpret_transport_v11(catalog["INVALID_MERGE"])
        assert pipeline_pass(bad) is False
        good = interpret_transport_v11(expected_valid_transport_v11())
        merged = next(node for node in good["transport"]["n"] if node["h"] == "I2")
        assert set(merged["s"]) >= {"SRC998003", "SRC998006"}


class TestRepetitionAndFixture:
    def test_repetition_is_optional(self):
        policy = repetition_policy()
        assert policy["fail_canary_for_missing_repetition"] is False
        assert policy["requirement"] == "OPTIONAL_SEMANTIC_ENRICHMENT"
        valid = expected_valid_transport_v11()
        assert not any(node.get("k") == "REPETITION" for node in valid["n"])
        interpreted = interpret_transport_v11(valid)
        assert pipeline_pass(interpreted) is True

    def test_fixture_expectation_classification(self):
        review = fixture_expectation_review()
        assert review["overconstrained"] is True
        by_id = {item["id"]: item for item in review["cases"]}
        assert by_id["SYN002:I2"]["classification"] == "OVERCONSTRAINED_EXPECTATION"
        assert by_id["REPETITION_NODE"]["classification"] == "OVERCONSTRAINED_EXPECTATION"
        assert by_id["SYN001:I3"]["classification"] == "REQUIRED_BY_CONTRACT"
        assert review["a35_remains_fail"] is True


class TestCounterfactual:
    def test_drop_only_counterfactual_and_original_immutable(self):
        original = replay_a35_under_v10_contract()
        counterfactual = replay_drop_only_counterfactual()
        assert original["drop_row"]["w"] == A35_DROP_PROSE
        assert original["global_validator"] == "FAIL"
        assert counterfactual["result"] == "PASS"
        assert counterfactual["global_validator"] == "PASS"
        assert counterfactual["drop_was_sole_technical_validator_root"] is True
        assert counterfactual["keep_not_rewritten_to_link_related"] is True
        assert counterfactual["repetition_not_invented"] is True
        assert counterfactual["counterfactual_is_production_evidence"] is False
        again = replay_a35_under_v10_contract()
        assert again["drop_row"]["w"] == A35_DROP_PROSE
        assert again["global_validator"] == "FAIL"


class TestSchemaAndPromptV11:
    def test_next_schema_size_hash_and_enums(self):
        measured = measure_global_schema_v11()
        assert measured["raw_bytes"] == NEXT_SCHEMA_RAW_BYTES == 1182
        assert measured["adapted_bytes"] == NEXT_SCHEMA_ADAPTED_BYTES == 1337
        assert measured["hash"] == NEXT_SCHEMA_HASH
        assert SCHEMA_CHANGED is True
        assert NEW_GRAMMAR_CANARY_REQUIRED is True
        assert measured["conditional_schema_used"] is False
        assert measured["unsupported_constructs"] == []
        assert schema_contains_unsupported_constructs(measured["schema"]) == []
        reason_enum = (
            measured["schema"]["properties"]["d"]["items"]["properties"]["w"]["enum"]
        )
        op_enum = measured["schema"]["properties"]["d"]["items"]["properties"]["o"]["enum"]
        assert set(reason_enum) == set(REASON_CODES)
        assert "LINK_RELATED" not in op_enum
        prompt = prompt_v101_bundle()
        assert prompt["prompt_version"] == NEXT_PROMPT_VERSION == "global-consolidation-1.0.1"
        assert "emit the exact token only" in prompt["system"].lower() or (
            "exact token only" in prompt["system"]
        )
        assert "LINK_RELATED is not a valid d.o token" in prompt["system"]
        assert prompt["previous_prompt_mutated"] is False

    def test_unknown_input_handle_and_traceability(self):
        catalog = fakeai_catalog()
        assert pipeline_pass(interpret_transport_v11(catalog["UNKNOWN_INPUT"])) is False
        assert pipeline_pass(interpret_transport_v11(catalog["UNKNOWN_HANDLE"])) is False
        traced = interpret_transport_v11(catalog["TRACEABILITY_FAILURE"])
        assert traced["traceability"] == "FAIL" or traced["global_validator"] == "FAIL"

    def test_valid_fakeai_full_pipeline(self):
        interpreted = interpret_transport_v11(expected_valid_transport_v11())
        assert pipeline_pass(interpreted) is True
        assert interpreted["canonical_reconstruction"] == "PASS"
        assert interpreted["canonical_validation"] == "PASS"
        assert not source_map_path(PROJECT_NAME).is_file()

    def test_root_causes_and_redesign(self):
        causes = root_causes()
        assert "PROMPT_MACHINE_ENUM_AMBIGUITY" in causes
        assert "SCHEMA_UNDERCONSTRAINED" in causes
        assert "DISPOSITION_MODEL_OVERLOADED" in causes
        assert "FIXTURE_EXPECTATION_OVERCONSTRAINED" in causes
        redesign = redesign_decision()
        assert redesign["new_grammar_canary_required"] is True
        assert redesign["heuristic_normalization"] is False
        inventory = classify_a35_failures(replay_a35_under_v10_contract())
        assert inventory["root_contract_violations"][0]["id"] == "DROP_REASON_PROSE_NOT_TOKEN"
        assert inventory["cascade_failures"][0]["id"] == "SEMANTIC_FIXTURE_REVIEW_FAIL"

    def test_no_provider_calls_constants(self):
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        catalog = fakeai_catalog()
        assert set(catalog) >= {
            "VALID",
            "INVALID_DROP_PROSE",
            "SILENT_DROP",
            "INVALID_MERGE",
            "UNKNOWN_INPUT",
            "UNKNOWN_HANDLE",
            "TRACEABILITY_FAILURE",
        }
        for name, payload in catalog.items():
            passed = pipeline_pass(interpret_transport_v11(payload, signature=name))
            if name == "VALID":
                assert passed is True
            else:
                assert passed is False, name
