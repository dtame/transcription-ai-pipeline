"""Phase 3B.7.7A.45 — FakeAI / offline. 0 réseau. 0 consolidation réelle."""

from __future__ import annotations

import json

import pytest

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_reuse_output.prompt_v30 import prompt_v30_bundle
from app.source_analysis_v31_global_reuse_output.transport_v30 import (
    measure_global_schema_v30,
)
from app.source_analysis_v31_global_v30_exact_preflight.audit import (
    audit_prompt_consistency,
    audit_request_redundancy,
)
from app.source_analysis_v31_global_v30_exact_preflight.consistency import (
    decoder_schema_consistency,
    publication_gate_plan,
    reconstructor_consistency,
    validator_consistency,
)
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_PRODUCTION_INPUT_TOKENS,
    A38_STATUS_PRESERVED,
    A39_STATUS_PRESERVED,
    A40_STATUS_PRESERVED,
    A41_STATUS_PRESERVED,
    A42_STATUS_PRESERVED,
    A43_ESTIMATED_PRODUCTION_INPUT,
    A43_HARD_OUTPUT,
    A43_STATUS_PRESERVED,
    A44_CHARS_PER_TOKEN,
    A44_REQUEST_ID,
    A44_STATUS_PRESERVED,
    CONNECT_TIMEOUT_SECONDS,
    EXPECTED_IDEA,
    FUTURE_AUTHORIZATION_SCOPE,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MODEL,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    READ_TIMEOUT_SECONDS,
    READY_WINDOWS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SAFETY_70,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v30_exact_preflight.estimator import (
    calibrated_output_budget,
)
from app.source_analysis_v31_global_v30_exact_preflight.evidence import verify_a44_identity
from app.source_analysis_v31_global_v30_exact_preflight.fakeai import (
    drop_stress_transport,
    expected_mix_transport,
    merge_stress_transport,
    production_inventory,
)
from app.source_analysis_v31_global_v30_exact_preflight.guard import (
    authorize_future_call,
    future_call_guard_spec,
)
from app.source_analysis_v31_global_v30_exact_preflight.identity import (
    verify_schema_identity,
)
from app.source_analysis_v31_global_v30_exact_preflight.inventory import (
    idea_handle_identity,
    load_exact_windows,
)
from app.source_analysis_v31_global_v30_exact_preflight.offline import (
    GlobalExactPreflightError,
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_v30_exact_preflight.payload import (
    build_audited_request,
    dry_run_identity_tuple,
    secrets_present,
)
from app.source_analysis_v31_global_v30_exact_preflight.runner import build_bundle
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_v31_global_reuse_output.fixture import all_distinct_reuse_transport


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestHistoricalFreeze:
    def test_a34_through_a44_remain_immutable(self):
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
        assert A44_STATUS_PRESERVED == "PASS"
        assert PHASE == "3B.7.7A.45"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN == "YES"
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert not source_map_path(PROJECT_NAME).is_file()
        assert A44_REQUEST_ID == "req_011CfY6EGQtoB2iSvDaHNCwx"
        assert A38_PRODUCTION_INPUT_TOKENS == 68138
        assert A43_ESTIMATED_PRODUCTION_INPUT == 68405

    def test_schema_prompt_transport_identity(self):
        schema = measure_global_schema_v30()
        prompt = prompt_v30_bundle()
        identity = verify_schema_identity()
        assert schema["raw_bytes"] == SCHEMA_RAW_BYTES == 1583
        assert schema["adapted_bytes"] == SCHEMA_ADAPTED_BYTES == 1831
        assert schema["hash"] == SCHEMA_HASH
        assert identity["schema_identity"] == "MATCH"
        assert prompt["prompt_version"] == PROMPT_VERSION == "global-consolidation-3.0"
        assert prompt["previous_prompt_mutated"] is False
        assert TRANSPORT_VERSION == "global-consolidation-transport-3.0"
        assert MODEL == "claude-sonnet-5"
        assert THINKING_MODE == "disabled"
        assert PRODUCTION_MAX_OUTPUT_TOKENS == 48000


class TestExactWindows:
    def test_seven_window_inventory_and_idea_handles(self):
        bundle = load_exact_windows()
        normalized = bundle["normalized"]
        observed = bundle["inventory_check"]["observed"]
        assert observed["total_records"] == 623
        assert observed["TOPIC"] == 67
        assert observed["IDEA"] == 286
        assert observed["RELATION"] == 127
        assert observed["EXAMPLE"] == 49
        assert observed["REFERENCE"] == 59
        assert observed["UNCERTAINTY"] == 35
        ideas = idea_handle_identity(normalized)
        assert ideas["count"] == EXPECTED_IDEA == 286
        assert len(ideas["ordered_handles"]) == 286
        first = idea_handle_identity(normalized)
        assert first["handle_set_sha256"] == ideas["handle_set_sha256"]
        assert list(READY_WINDOWS) == [
            "WIN001",
            "WIN002",
            "WIN003",
            "WIN004",
            "WIN005",
            "WIN006",
            "WIN007",
        ]

    def test_normalized_input_and_request_determinism(self):
        windows = load_exact_windows()
        built_a = build_audited_request(
            windows["normalized"],
            window_set_sha256="abc",
        )
        built_b = build_audited_request(
            windows["normalized"],
            window_set_sha256="abc",
        )
        assert dry_run_identity_tuple(built_a["audit"]) == dry_run_identity_tuple(
            built_b["audit"]
        )
        assert (
            built_a["audit"]["provider_visible_hash"]
            == built_b["audit"]["provider_visible_hash"]
        )
        assert built_a["audit"]["normalized_input_hash"]
        assert built_a["audit"]["request_identity"]
        assert secrets_present(built_a["payload"]) == []
        assert built_a["audit"]["model"] == MODEL
        assert built_a["audit"]["thinking_type"] == "disabled"
        assert built_a["audit"]["max_tokens"] == 48000
        assert "api_key" not in json.dumps(built_a["payload"])


class TestBudgetsAndEstimator:
    def test_single_member_reuse_and_merge_estimator(self):
        budget = calibrated_output_budget()
        assert budget["calibration"]["old_2_0_estimator_used"] is False
        assert budget["single_member_v_absent_in_all_scenarios"] is True
        distinct = budget["scenarios"]["all_distinct_286_reuse"]
        assert distinct["reused"] == 286
        assert distinct["synthesized"] == 0
        assert distinct["single_member_v_absent"] is True
        merge = budget["scenarios"]["pair_synthesis_worst_text"]
        assert merge["synthesized"] >= 1
        assert merge["single_member_v_absent"] is True
        assert budget["hard_planning"] <= SAFETY_70 or budget["hard_planning"] <= 36000
        assert budget["max_output"] == 48000
        assert budget["calibration"]["a44_chars_per_token"] == A44_CHARS_PER_TOKEN
        assert budget["calibration"]["generic_4_chars_per_token_used"] is False
        assert budget["a43_reference"]["hard"] == A43_HARD_OUTPUT

    def test_all_distinct_expected_merge_drop_stress_payloads(self):
        windows = load_exact_windows()
        transcript = load_clean_transcript(PROJECT_NAME)
        inventory = production_inventory(windows["normalized"], transcript)
        distinct = all_distinct_reuse_transport(inventory)
        expected = expected_mix_transport(inventory)
        merges = merge_stress_transport(inventory)
        drops = drop_stress_transport(inventory)
        assert len(distinct["i"]) == 286
        assert all("v" not in idea for idea in distinct["i"])
        assert any(len(idea.get("m") or []) >= 2 for idea in expected["i"])
        assert any(len(idea.get("m") or []) >= 2 for idea in merges["i"])
        assert len(drops["drop"]) >= 1
        assert all(row["w"] in {"transport_artifact", "non_substantive_fragment"} for row in drops["drop"])


class TestConsistencyAndGuard:
    def test_prompt_schema_decoder_validator_reconstructor_publication(self):
        assert audit_prompt_consistency()["ok"] is True
        assert decoder_schema_consistency()["status"] == "PASS"
        assert validator_consistency()["status"] == "PASS"
        assert reconstructor_consistency()["status"] == "PASS"
        gate = publication_gate_plan()
        assert gate["status"] == "PASS"
        assert gate["publication_eligible_now"] is False
        assert gate["future_failure_policy"]["automatic_retry"] is False

    def test_future_authorization_and_hash_mismatch(self):
        approved = future_call_guard_spec(
            normalized_input_hash="n1",
            request_hash="r1",
            provider_visible_hash="p1",
            window_set_sha256="w1",
            prompt_hash="h1",
            schema_hash=SCHEMA_HASH,
            hard_planning=20000,
            estimated_input=68000,
        )
        observed = {
            "normalized_input_hash": "n1",
            "request_hash": "r1",
            "provider_visible_hash": "p1",
            "window_set_sha256": "w1",
            "prompt_version": PROMPT_VERSION,
            "prompt_hash": "h1",
            "transport_version": TRANSPORT_VERSION,
            "schema_hash": SCHEMA_HASH,
            "model": MODEL,
            "thinking_mode": THINKING_MODE,
            "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
            "authorization_scope": FUTURE_AUTHORIZATION_SCOPE,
            "retries": 0,
            "max_engine_generate": 1,
            "hard_planning": 20000,
        }
        assert authorize_future_call(observed, approved)["ok"] is True
        bad = dict(observed)
        bad["request_hash"] = "changed"
        with pytest.raises(GlobalExactPreflightError, match="BLOCKED_PRECALL"):
            authorize_future_call(bad, approved)

    def test_timeout_selection(self):
        assert CONNECT_TIMEOUT_SECONDS == 30.0
        assert READ_TIMEOUT_SECONDS == 600.0
        assert READ_TIMEOUT_SECONDS < 1800.0


class TestOfflineBundle:
    def test_build_bundle_zero_provider_and_fakeai(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        a44 = verify_a44_identity()
        assert a44["ok"] is True
        bundle = build_bundle(tests="offline A.45 unit")
        header = bundle["header"]
        assert header["real_provider_calls"] == 0
        assert header["schema_identity"] == "MATCH"
        assert header["local_ideas"] == 286
        assert header["request_determinism"] == "PASS"
        assert header["all_distinct_286_reuse_stress"] == "PASS"
        assert header["expected_mix_stress"] == "PASS"
        assert header["merge_stress"] == "PASS"
        assert header["drop_stress"] == "PASS"
        assert header["fakeai_canonical_reconstruction"] == "PASS"
        assert header["fakeai_canonical_validation"] == "PASS"
        assert "ESTIMATED" in str(header["estimated_expected_cost"])
        assert bundle["guards"]["engine_generate"] is False
        assert not source_map_path(PROJECT_NAME).is_file()
        redundancy = bundle["contract"]["redundancy"]
        compact = load_exact_windows()["normalized"]["compact"]
        request = bundle["exact_request"]["provider_visible"]
        user = ((request.get("messages") or [{}])[0].get("content")) or ""
        system = request.get("system") or ""
        audited = audit_request_redundancy(
            compact=compact, user_text=user, system_text=system
        )
        assert audited["readiness"] == "CLEAN"
        assert secrets_present(request) == []
