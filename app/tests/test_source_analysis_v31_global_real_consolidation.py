"""Phase 3B.7.7A.38 — FakeAI / offline. 0 réseau. 0 publication source_map."""

from __future__ import annotations

import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_canary_forensics.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
)
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    measure_global_schema_v11,
)
from app.source_analysis_v31_global_canary_forensics.validator_v11 import (
    validate_global_transport_v11,
)
from app.source_analysis_v31_global_preflight.constants import READY_WINDOWS
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    AUTHORIZATION_SCOPE as A37_SCOPE,
)
from app.source_analysis_v31_global_v11_grammar_canary.enums import audit_raw_enums
from app.source_analysis_v31_global_real_consolidation.constants import (
    A36_STATUS_PRESERVED,
    A37_REQUEST_ID,
    A37_STATUS_PRESERVED,
    AUTHORIZATION_SCOPE,
    EXPECTED_IDEA,
    GLOBAL_TRANSPORT_1_1_GRAMMAR_PROOF,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MAX_OUTPUT_TOKENS,
    MODEL,
    PHASE,
    PHASE_3B_STATUS,
    PROJECT_NAME,
    PROMPT_VERSION,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    SOURCE_MAP_PUBLICATION_AUTHORIZED,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_real_consolidation.fake_transport import (
    mechanical_keep_transport,
)
from app.source_analysis_v31_global_real_consolidation.guard import (
    GlobalRealConsolidationError,
    OneShotCallGuard,
    reject_contract_drift,
    reject_publication_path,
    reject_raw_transcript_payload,
    validate_authorization_scope,
    validate_project_name,
    validate_ready_windows,
)
from app.source_analysis_v31_global_real_consolidation.identity import (
    recompute_schema_identity,
)
from app.source_analysis_v31_global_real_consolidation.input_contract import (
    allowed_input_ids,
    allowed_source_refs,
    assert_frozen_inventory,
    load_normalized_bundle,
    local_src_by_input,
    serialize_twice,
)
from app.source_analysis_v31_global_real_consolidation.payload import build_audited_request
from app.source_analysis_v31_global_real_consolidation.preflight import run_preflight
from app.source_analysis_v31_global_real_consolidation.runner import (
    dry_run_consolidation,
    run_real_global_consolidation,
)


def _fake_engine(payload):
    return FakeAIEngine(
        script=[
            FakeReply(
                text=json.dumps(payload, ensure_ascii=False),
                parsed=payload,
                finish_reason="end_turn",
                input_tokens=200,
                output_tokens=150,
                thinking_tokens=0,
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestHistoricalFreeze:
    def test_history_and_freeze(self):
        assert A34_STATUS_PRESERVED == "PASS"
        assert A35_STATUS_PRESERVED == "FAIL"
        assert A36_STATUS_PRESERVED == "PASS"
        assert A37_STATUS_PRESERVED == "PASS"
        assert GLOBAL_TRANSPORT_1_1_GRAMMAR_PROOF == "PASS"
        assert A37_REQUEST_ID == "req_011CfWW9vr5GRSeGTyAeS2oX"
        assert PHASE == "3B.7.7A.38"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"
        assert RELATION_QUALITY_TECHNICAL_DEBT == "YES"
        assert SOURCE_MAP_PUBLICATION_AUTHORIZED is False
        assert not source_map_path(PROJECT_NAME).is_file()

    def test_schema_identity(self):
        measured = measure_global_schema_v11()
        recomputed = recompute_schema_identity()
        assert measured["raw_bytes"] == SCHEMA_RAW_BYTES == 1182
        assert measured["adapted_bytes"] == SCHEMA_ADAPTED_BYTES == 1337
        assert measured["hash"] == SCHEMA_HASH
        assert recomputed["matches_a38_constants"] is True
        assert PROMPT_VERSION == "global-consolidation-1.0.1"
        assert TRANSPORT_VERSION == "global-consolidation-transport-1.1"


class TestGuards:
    def test_authorization_scope(self):
        assert validate_authorization_scope(AUTHORIZATION_SCOPE) == AUTHORIZATION_SCOPE
        with pytest.raises(GlobalRealConsolidationError):
            validate_authorization_scope(A37_SCOPE)
        with pytest.raises(GlobalRealConsolidationError):
            validate_authorization_scope("REAL_GLOBAL_CONSOLIDATION")

    def test_project_and_windows(self):
        assert validate_project_name(PROJECT_NAME) == PROJECT_NAME
        with pytest.raises(GlobalRealConsolidationError):
            validate_project_name("other_project")
        assert validate_ready_windows(READY_WINDOWS) == tuple(READY_WINDOWS)
        with pytest.raises(GlobalRealConsolidationError):
            validate_ready_windows(READY_WINDOWS[:-1])
        with pytest.raises(GlobalRealConsolidationError):
            validate_ready_windows(READY_WINDOWS + ("WIN008",))

    def test_model_thinking_max_output(self):
        reject_contract_drift(
            prompt_version=PROMPT_VERSION,
            transport_version=TRANSPORT_VERSION,
            schema_hash=SCHEMA_HASH,
            model=MODEL,
            thinking_mode=THINKING_MODE,
            max_output=MAX_OUTPUT_TOKENS,
        )
        with pytest.raises(GlobalRealConsolidationError):
            reject_contract_drift(
                prompt_version=PROMPT_VERSION,
                transport_version=TRANSPORT_VERSION,
                schema_hash=SCHEMA_HASH,
                model="claude-opus-5",
                thinking_mode=THINKING_MODE,
                max_output=MAX_OUTPUT_TOKENS,
            )
        with pytest.raises(GlobalRealConsolidationError):
            reject_contract_drift(
                prompt_version=PROMPT_VERSION,
                transport_version=TRANSPORT_VERSION,
                schema_hash=SCHEMA_HASH,
                model=MODEL,
                thinking_mode="adaptive",
                max_output=MAX_OUTPUT_TOKENS,
            )
        with pytest.raises(GlobalRealConsolidationError):
            reject_contract_drift(
                prompt_version=PROMPT_VERSION,
                transport_version=TRANSPORT_VERSION,
                schema_hash=SCHEMA_HASH,
                model=MODEL,
                thinking_mode=THINKING_MODE,
                max_output=2048,
            )

    def test_raw_transcript_and_publication(self):
        reject_raw_transcript_payload("intro {\"windows\":[]}", compact_text="{\"windows\":[]}")
        with pytest.raises(GlobalRealConsolidationError):
            reject_raw_transcript_payload(
                "CLEAN transcript follows SRC000001",
                compact_text="{\"windows\":[]}",
            )
        with pytest.raises(GlobalRealConsolidationError):
            reject_publication_path("sortie/x/analysis/source_map.json")

    def test_one_shot_guard(self):
        guard = OneShotCallGuard(max_calls=1)
        engine = _fake_engine({"gm": {}, "n": [], "r": [], "d": []})
        from app.ai.contracts import AIRequest

        request = AIRequest(
            prompt="x",
            model=MODEL,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            thinking_mode=THINKING_MODE,
            metadata={"stage": "source_analysis_v31_global_real_consolidation"},
        )
        guard.guarded_generate(engine, request)
        with pytest.raises(Exception):
            guard.guarded_generate(engine, request)


class TestInputContract:
    def test_inventory_and_determinism(self):
        bundle = load_normalized_bundle(PROJECT_NAME)
        check = assert_frozen_inventory(
            bundle["normalized"], bundle["inventory"], bundle["boundary"]
        )
        assert check["ok"] is True
        assert check["observed"]["IDEA"] == EXPECTED_IDEA
        assert check["observed"]["total_records"] == 623
        assert serialize_twice(bundle["normalized"])["equal"] is True
        assert set(bundle["normalized"]["windows"]) == set(READY_WINDOWS)


class TestPayload:
    def test_audited_request_contract(self):
        bundle = load_normalized_bundle(PROJECT_NAME)
        built = build_audited_request(bundle["normalized"], project_name=PROJECT_NAME)
        audit = built["audit"]
        assert audit["model"] == MODEL
        assert audit["thinking_type"] == "disabled"
        assert audit["max_tokens"] == 32000
        assert audit["prompt_version"] == PROMPT_VERSION
        assert audit["schema_version"] == TRANSPORT_VERSION
        assert audit["schema_hash"] == SCHEMA_HASH
        assert audit["raw_transcript_included"] is False
        request = built["request"]
        assert "transcript_data.json" not in request.prompt
        assert bundle["normalized"]["compact_sha256"] == audit["input_hash"]


class TestDispositionsAndMatrix:
    def test_mechanical_transport_covers_286(self):
        bundle = load_normalized_bundle(PROJECT_NAME)
        transport = mechanical_keep_transport(bundle["normalized"])
        idea_ids = list(bundle["normalized"]["idea_input_ids"])
        validator = validate_global_transport_v11(
            transport,
            idea_input_ids=idea_ids,
            allowed_input_ids=allowed_input_ids(bundle["normalized"]),
            allowed_source_refs=allowed_source_refs(bundle["normalized"]),
            local_src_by_input=local_src_by_input(bundle["normalized"]),
        )
        assert validator["ok"] is True
        assert validator["idea_disposition_coverage"] == 100.0
        assert validator["silent_drop_count"] == 0
        enums = audit_raw_enums(transport)
        assert enums["status"] == "PASS"
        assert enums["link_related_count"] == 0
        assert enums["matrix_status"] == "PASS"
        assert enums["keep_count"] + enums["other_count"] == len(transport["d"])

    def test_link_related_rejected(self):
        bundle = load_normalized_bundle(PROJECT_NAME)
        transport = mechanical_keep_transport(bundle["normalized"])
        for row in transport["d"]:
            if row["i"] in bundle["normalized"]["idea_input_ids"]:
                row["o"] = "LINK_RELATED"
                break
        enums = audit_raw_enums(transport)
        assert enums["link_related_count"] == 1
        assert enums["status"] == "FAIL"

    def test_silent_drop_rejected(self):
        bundle = load_normalized_bundle(PROJECT_NAME)
        transport = mechanical_keep_transport(bundle["normalized"])
        idea_id = bundle["normalized"]["idea_input_ids"][0]
        transport["d"] = [row for row in transport["d"] if row["i"] != idea_id]
        validator = validate_global_transport_v11(
            transport,
            idea_input_ids=list(bundle["normalized"]["idea_input_ids"]),
            allowed_input_ids=allowed_input_ids(bundle["normalized"]),
            allowed_source_refs=allowed_source_refs(bundle["normalized"]),
            local_src_by_input=local_src_by_input(bundle["normalized"]),
        )
        assert validator["ok"] is False
        assert validator["silent_drop_count"] == 1

    def test_merge_source_union(self):
        bundle = load_normalized_bundle(PROJECT_NAME)
        transport = mechanical_keep_transport(bundle["normalized"])
        idea_ids = list(bundle["normalized"]["idea_input_ids"])
        first, second = idea_ids[0], idea_ids[1]
        src_map = local_src_by_input(bundle["normalized"])
        handle = None
        for row in transport["d"]:
            if row["i"] == first:
                handle = row["g"]
                row["o"] = "MERGE_EQUIVALENT"
            if row["i"] == second:
                row["o"] = "MERGE_EQUIVALENT"
                row["g"] = handle
        for node in transport["n"]:
            if node["h"] == handle:
                node["s"] = sorted(set(src_map[first] + src_map[second]))
        validator = validate_global_transport_v11(
            transport,
            idea_input_ids=idea_ids,
            allowed_input_ids=allowed_input_ids(bundle["normalized"]),
            allowed_source_refs=allowed_source_refs(bundle["normalized"]),
            local_src_by_input=src_map,
        )
        assert all("missing SRC union" not in str(err) for err in validator["errors"])


class TestRunner:
    def test_wrong_scope_blocked(self):
        result = run_real_global_consolidation(
            PROJECT_NAME,
            dry_run=True,
            authorization_scope="WRONG",
        )
        assert result.blocked_precall is True
        assert result.anthropic_post_attempts == 0

    def test_dry_run_zero_calls(self):
        result = run_real_global_consolidation(
            PROJECT_NAME,
            dry_run=True,
            authorization_scope=AUTHORIZATION_SCOPE,
        )
        assert result.accepted is True
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0
        assert result.dry_run["real_consolidation_executed"] is False

    def test_fake_execute_one_call_no_publication(self):
        bundle = load_normalized_bundle(PROJECT_NAME)
        transport = mechanical_keep_transport(bundle["normalized"])
        result = run_real_global_consolidation(
            PROJECT_NAME,
            dry_run=False,
            execute_real=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            allow_real_provider=False,
            engine=_fake_engine(transport),
        )
        assert result.engine_generate_attempts == 1
        assert result.anthropic_post_attempts <= 1
        assert (result.execution or {}).get("source_map") == "NOT PUBLISHED"
        assert not source_map_path(PROJECT_NAME).is_file()
        assert float((result.execution or {}).get("idea_disposition_coverage") or 0) == 100.0


class TestPreflight:
    def test_preflight_pass(self):
        preflight = run_preflight(
            PROJECT_NAME, authorization_scope=AUTHORIZATION_SCOPE
        )
        assert preflight["ok"] is True
        assert preflight["actual_calls"] == 0
        assert preflight["schema"]["schema_identity"] == "MATCH"
        dry = dry_run_consolidation(
            PROJECT_NAME, authorization_scope=AUTHORIZATION_SCOPE
        )
        assert dry["dry_run_identity"] is not None
