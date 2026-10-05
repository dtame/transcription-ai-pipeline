"""Phase 4B.2.10 — offline Semantic Gate 2.0 contract hardening. Network forbidden."""

from __future__ import annotations

import json

import pytest

from app.book_generation.pipeline import materialize_chapter
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle
from app.book_semantic_gate_4b275.constants import (
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_112_SHA256,
    EXPECTED_PROMPT_113_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
)
from app.book_semantic_gate_4b29.contract import semantic_contract_20_candidate
from app.book_semantic_gate_4b29.fakeai import SCENARIO_NAMES
from app.book_semantic_gate_4b29.interface import BlockedRemoteTransport
from app.book_semantic_gate_4b29.validator import validate_response_20
from app.file_utils import content_hash
from app.book_semantic_gate_4b210.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    FALLBACKS,
    H01_HUMAN_LABEL,
    H01_REQUEST_SHA256,
    HISTORICAL_4B26_STATUS,
    HISTORICAL_4B29_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    MODEL,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_20_CANDIDATE,
    PROMPT_VERSION_201_ACTIVATED,
    PROMPT_VERSION_201_CANDIDATE,
    REAL_TERRA_CANARY_AUTHORIZED,
    RETRIES,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
    SEMANTIC_GATE_20_ENABLED,
    SEMANTIC_TOKEN_BUDGET,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_20_ACTIVATED,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b210.contract import (
    review_contract_20,
    review_semantic_instructions,
    semantic_contract_201_candidate,
)
from app.book_semantic_gate_4b210.fakeai import run_fakeai_contract_tests
from app.book_semantic_gate_4b210.guard import (
    BookSemanticGate210Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b210.preflight import (
    canary_success_criteria,
    cost_estimate,
    sdk_compatibility,
    strategic_stop_rule,
    transport_20_preflight,
)
from app.book_semantic_gate_4b210.request import (
    build_selected_payload,
    freeze_selected_request,
    label_leakage_audit,
    request_determinism_audit,
    request_sha256,
    serialize_selected_sdk,
)
from app.book_semantic_gate_4b210.runner import run_phase
from app.book_semantic_gate_4b210.safety import provider_safety
from app.book_semantic_gate_4b210.selection import candidate_selection
from app.book_semantic_gate_4b210.units import unit_integrity_review


@pytest.fixture(autouse=True)
def _no_network(no_ai_network, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("PROVIDER NETWORK FORBIDDEN")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.Client.send", forbidden)
    return None


class TestPhaseGuards:
    def test_offline_and_historical_statuses(self):
        assert_offline_only()
        assert PHASE == "4B.2.10"
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert REAL_TERRA_CANARY_AUTHORIZED is False
        assert PROMPT_VERSION_20_ACTIVATED is False
        assert PROMPT_VERSION_201_ACTIVATED is False
        assert TRANSPORT_VERSION_20_ACTIVATED is False
        assert SEMANTIC_GATE_20_ENABLED is False
        assert HISTORICAL_4B26_STATUS == "FAIL"
        assert HISTORICAL_4B29_STATUS == "PASS"
        assert HISTORICAL_H01_STATUS == "PARTIAL"
        assert HISTORICAL_H02_STATUS == "PARTIAL"
        assert HISTORICAL_H11_STATUS == "PARTIAL"
        assert RETRIES == 0
        assert FALLBACKS == 0
        assert PROMPT_VERSION_20_CANDIDATE == "book-semantic-validator-2.0-candidate"
        assert PROMPT_VERSION_201_CANDIDATE == "book-semantic-validator-2.0.1-candidate"
        assert TRANSPORT_VERSION_20_CANDIDATE == (
            "book-semantic-validation-transport-2.0-candidate"
        )

    def test_execute_real_rejected_by_cli(self):
        from app.book_semantic_gate_4b210.__main__ import main

        assert main(["--execute-real"]) == 2

    def test_wrong_scope_rejected(self):
        with pytest.raises(BookSemanticGate210Error):
            validate_authorization_scope("wrong")
        result = run_phase(
            authorization_scope=None,
            write_artifacts=False,
            run_tests=False,
        )
        assert result.mode == "REJECTED"


class TestCanonicalHashes:
    def test_canonical_artifacts_match_expected(self):
        identities = verify_canonical_inputs()
        assert identities["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert identities["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert identities["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
        assert production_book_absent(PROJECT_NAME)

    def test_historical_contracts_unmodified(self):
        assert content_hash(system_prompt()) == EXPECTED_PROMPT_SYSTEM_SHA256
        assert content_hash(instruction_prompt()) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
        assert candidate_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256
        assert candidate_111_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256
        assert candidate_112_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_112_SHA256
        assert candidate_113_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256
        frozen_20 = semantic_contract_20_candidate()
        hardened = semantic_contract_201_candidate()
        assert frozen_20["candidate_version"] == PROMPT_VERSION_20_CANDIDATE
        assert hardened["predecessor_2_0_sha256"] == frozen_20["candidate_sha256"]
        assert hardened["candidate_sha256"] != frozen_20["candidate_sha256"]
        assert hardened["does_not_overwrite_2_0_candidate"] is True


class TestContractHardening:
    def test_contract_20_review_finds_ambiguities_without_mutation(self):
        review = review_contract_20()
        frozen = semantic_contract_20_candidate()
        assert review["reviewed_sha256"] == frozen["candidate_sha256"]
        assert review["reviewed_unmodified"] is True
        assert review["hardening_required"] is True
        assert review["human_labels_absent"] is True
        assert review["json_format_explicit"] is True
        assert review["offsets_not_generated_by_model"] is True

    def test_contract_201_defines_verdicts_and_avoids_overfit(self):
        hardened = semantic_contract_201_candidate()
        instructions = review_semantic_instructions()
        prompt = hardened["system_candidate"] + "\n" + hardened["instructions_candidate"]
        assert hardened["overfit_tokens_absent_from_candidate"] is True
        assert "h01" not in prompt.lower()
        assert "human_label" not in prompt.lower()
        assert "Do not require the same words" in prompt
        assert "QUESTIONABLE" in hardened["system_candidate"]
        assert instructions["contract_201"]["all_hardening_checks"] is True
        assert hardened["candidate_activated"] is False
        assert list(REASON_CODES) == hardened["closed_catalog"]


class TestUnitIntegrity:
    def test_h01_h02_h11_units_cover_paragraphs(self):
        review = unit_integrity_review()
        assert review["ok"] is True
        assert review["words_not_lost"] is True
        assert review["connectors_preserved"] is True
        assert review["h01"]["coverage_ok"] is True
        assert review["h02"]["coverage_ok"] is True
        assert review["h11"]["coverage_ok"] is True
        assert review["h01"]["reconstructed_equals_paragraph"] is True
        assert review["context_preservation"] == "PARAGRAPH_ONCE_PLUS_UNIT_TEXTS"
        assert review["h01"]["does_not_copy_paragraph_onto_each_unit"] is True


class TestCanarySelection:
    def test_exactly_one_canary_is_h01(self):
        selection = candidate_selection()
        assert selection["exactly_one_selected"] is True
        assert selection["selected_handle"] == SELECTED_CASE_HANDLE == "h01"
        assert selection["selected_case_id_audit_only"] == SELECTED_CASE_ID
        assert selection["human_label_audit_only"] == H01_HUMAN_LABEL
        assert sum(1 for item in selection["options"] if item.get("selected")) == 1


class TestRequestFreeze:
    def test_request_construction_hash_and_determinism(self):
        first = build_selected_payload()
        second = build_selected_payload()
        assert request_sha256(first) == request_sha256(second)
        frozen = freeze_selected_request()
        assert frozen["determinism"] is True
        assert frozen["sha256"] == frozen["first_sha256"] == frozen["second_sha256"]
        assert frozen["differs_from_h01_historical"] is True
        assert frozen["sha256"] != H01_REQUEST_SHA256
        assert frozen["payload"]["model"] == MODEL
        assert frozen["payload"]["max_completion_tokens"] == SEMANTIC_TOKEN_BUDGET
        assert "max_tokens" not in frozen["payload"]
        assert "temperature" not in frozen["payload"]
        assert "reasoning_effort" not in frozen["payload"]
        assert frozen["payload"]["response_format"] == {"type": "json_object"}
        det = request_determinism_audit()
        assert det["result"] == "PASS"

    def test_units_and_evidence_preserved_in_request(self):
        payload = build_selected_payload()
        user = ""
        for message in payload["messages"]:
            if message["role"] == "user":
                user = message["content"]
        assert "SEMANTIC_GATE_INPUT_JSON" in user
        assert '"u"' in user
        assert "IDEA224" in user
        assert "SRC006149" in user
        assert SELECTED_CASE_HANDLE in user
        assert PROMPT_VERSION_201_CANDIDATE in user
        assert TRANSPORT_VERSION_20_CANDIDATE in user

    def test_label_leakage_absent(self):
        leak = label_leakage_audit()
        blob = json.dumps(freeze_selected_request()["payload"], ensure_ascii=False)
        assert leak["pass"] is True
        assert leak["label_leakage"] == 0
        assert leak["case_id_in_request"] is False
        assert leak["historical_case_id_in_request"] is False
        assert "4b22_p2_supported" not in blob
        assert "expected_class" not in blob
        assert "human_label" not in blob
        assert "ground_truth" not in blob
        assert SELECTED_CASE_ID not in blob

    def test_sdk_serialization_offline(self):
        serialized = serialize_selected_sdk()
        assert serialized["serialization_pass"] is True
        assert serialized["network_calls"] == 0
        assert serialized["http_requests"] == 0
        assert serialized["checks"]["max_tokens_absent"] is True
        assert serialized["checks"]["temperature_absent"] is True
        assert serialized["checks"]["json_object"] is True
        assert serialized["checks"]["reasoning_params_absent"] is True


class TestTransportAndSdk:
    def test_transport_preflight_omits_incompatible_params(self):
        transport = transport_20_preflight()
        assert transport["transport_version"] == TRANSPORT_VERSION_20_CANDIDATE
        assert transport["real_transport_not_activated"] is True
        assert transport["retries"] == 0
        assert transport["fallbacks"] == 0
        assert transport["max_completion_tokens"] == 8192
        sdk = sdk_compatibility()
        assert sdk["openai_sdk_version"]
        assert sdk["no_real_api_key_used"] is True
        assert sdk["max_tokens_forbidden_for_terra"] is True


class TestFakeAIContract:
    def test_conformant_and_nonconformant_responses(self):
        result = run_fakeai_contract_tests()
        assert result["passed"] is True
        assert result["not_terra"] is True
        by_name = {row["scenario"]: row for row in result["scenarios"]}
        assert set(by_name) == set(SCENARIO_NAMES)
        assert by_name["all_supported"]["decision"] in {"PASS", "REVIEW"}
        assert by_name["missing_unit"]["decision"] == "BLOCK"
        assert by_name["unknown_reason_code"]["decision"] == "BLOCK"
        assert by_name["truncated_response"]["decision"] == "BLOCK"
        assert by_name["invalid_json"]["decision"] == "BLOCK"
        assert by_name["invented_causality"]["decision"] == "BLOCK"
        assert all(item["blocked"] for item in result["extra_invalid"])

    def test_validator_does_not_repair(self):
        prepared = unit_integrity_review()["h01"]
        fake_prepared = {
            "paragraph_id": "h01",
            "units": [
                {"unit_id": item["unit_id"]} for item in prepared["units"]
            ],
            "evidence_handles": ["IDEA224"],
        }
        raw = '{"ch":"CH016","v":"PASS"'
        validation = validate_response_20(raw, fake_prepared, expected_chapter="CH016")
        assert validation["ok"] is False
        assert validation["does_not_complete_missing_units"] is True
        assert validation["does_not_repair_reason_codes"] is True


class TestCriteriaCostSafety:
    def test_future_canary_criteria_and_stop_rule(self):
        criteria = canary_success_criteria()
        stop = strategic_stop_rule()
        assert "PASS" in criteria
        assert "PARTIAL" in criteria
        assert "FAIL" in criteria
        assert "BLOCKED_PRECALL" in criteria
        assert criteria["not_executed"] is True
        assert stop["none_of_these_options_activated"] is True
        assert stop["no_automatic_paid_retry_series"] is True

    def test_cost_estimate_uses_configured_rates(self):
        payload = build_selected_payload()
        cost = cost_estimate(payload)
        assert cost["not_live_provider_prices"] is True
        assert cost["configured_rates"]["input_usd_per_million"] == 2.0
        assert cost["configured_rates"]["output_usd_per_million"] == 12.0
        assert cost["maximum_cost_estimate"] is not None
        assert cost["reasoning_tokens"] == "UNKNOWN"
        assert cost["no_provider_cost_in_this_phase"] is True

    def test_provider_safety_blocks_remote(self):
        safety = provider_safety()
        assert safety["ok"] is True
        assert safety["imports_network"] == []
        assert safety["invokes_provider"] == []
        with pytest.raises(Exception):
            BlockedRemoteTransport(provider="openai", model="gpt-5.6-terra")
        assert materialize_chapter.__module__ == "app.book_generation.pipeline"
        assert "book_semantic_gate_4b210" not in (
            __import__("pathlib").Path("app/book_generation/pipeline.py").read_text(
                encoding="utf-8"
            )
        )


class TestPipelineUnchanged:
    def test_book_json_unpublished(self):
        assert production_book_absent(PROJECT_NAME)
