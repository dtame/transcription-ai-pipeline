"""Phase 4B.2.7.6 — independent discriminating canary offline freeze. Network forbidden."""

from __future__ import annotations

import json

import pytest

from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b24.constants import (
    CONNECTIVE_CASE_ID,
    FUNERAL_CASE_ID,
    NEGATIVE_CASE_IDS,
    P3_CASE_ID,
    P8_CASE_ID,
    POSITIVE_CASE_IDS,
    SCORED_CASE_ORDER,
)
from app.book_semantic_gate_4b24.leak import audit_label_leak
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b261.complexity import extract_gate_input
from app.book_semantic_gate_4b262.contract import validate_compact_span
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle
from app.file_utils import content_hash
from app.book_semantic_gate_4b276.constants import (
    AUTHORIZED_TERRA_CALLS,
    DISPUTED_CLAUSE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_112_SHA256,
    EXPECTED_PROMPT_113_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_SOURCE_MAP,
    H01_EVIDENCE_HANDLES,
    H01_REQUEST_SHA256,
    H02_REQUEST_SHA256,
    HISTORICAL_4B26_STATUS,
    HISTORICAL_4B275_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    MODEL,
    P3_EVIDENCE_HANDLES,
    P4_EVIDENCE_HANDLES,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_113,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    SELECTED_CASE_ORIGIN,
    SOURCE_CASE_HANDLE,
    SOURCE_CASE_ID,
    TARGET_FAILURE_FAMILY,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_11,
)
from app.book_semantic_gate_4b276.contract import (
    inspect_contract_113,
    inspect_reason_code_compatibility,
    inspect_transport_compatibility,
)
from app.book_semantic_gate_4b276.evidence import build_canonical_evidence_inventory
from app.book_semantic_gate_4b276.fakeai import (
    historical_ten_case_protection,
    interpret_selected_simulation,
)
from app.book_semantic_gate_4b276.guard import assert_offline_only
from app.book_semantic_gate_4b276.identity import (
    clause_offsets,
    human_reference_label,
    selected_canary_provenance,
    source_paragraph_text,
    synthetic_paragraph_text,
)
from app.book_semantic_gate_4b276.inventory import candidate_inventory, candidate_selection_matrix
from app.book_semantic_gate_4b276.request import (
    build_selected_payload,
    freeze_selected_request,
    serialize_selected_sdk,
)


LEAK_KEY = "sk-SECRET-4B276-LEAK-TEST-VALUE-DO-NOT-PERSIST"


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
        assert PHASE == "4B.2.7.6"
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert HISTORICAL_4B26_STATUS == "FAIL"
        assert HISTORICAL_4B275_STATUS == "PASS"
        assert HISTORICAL_H01_STATUS == "PARTIAL"
        assert HISTORICAL_H02_STATUS == "PARTIAL"
        assert PROMPT_VERSION_113 == "book-semantic-validator-1.1.3-candidate"
        assert TRANSPORT_VERSION_11 == "book-semantic-validation-transport-1.1-candidate"

    def test_execute_real_rejected_by_cli(self):
        from app.book_semantic_gate_4b276.__main__ import main

        assert main(["--execute-real"]) == 2

    def test_canonical_inputs_unchanged(self):
        identities = verify_canonical_inputs()
        assert identities["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert identities["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert identities["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
        assert production_book_absent(PROJECT_NAME) is True


class TestSelectionAndIndependence:
    def test_selected_canary_is_synthetic_p4_variant(self):
        inventory = candidate_inventory()
        matrix = candidate_selection_matrix()
        provenance = selected_canary_provenance()
        assert inventory["selected"] == SELECTED_CASE_ID
        assert matrix["selected"]["handle"] == SELECTED_CASE_HANDLE == "h11"
        assert provenance["origin"] == SELECTED_CASE_ORIGIN
        assert provenance["synthetic"] is True
        assert provenance["presented_as_authentic_citation"] is False
        assert provenance["historical_benchmark_modified"] is False
        assert provenance["source_case_id_audit_only"] == SOURCE_CASE_ID
        assert TARGET_FAILURE_FAMILY == "NEW_IMPLICATION_AND_UNCERTAINTY_STRENGTHENED"
        others = [
            item
            for item in inventory["candidates"]
            if item.get("case_id_audit_only") != SELECTED_CASE_ID
        ]
        assert all(item["score"]["eligible"] is False for item in others)

    def test_source_p4_is_preserved_and_offsets_exact(self):
        source = source_paragraph_text()
        text = synthetic_paragraph_text()
        assert source.endswith(".")
        assert text.startswith(source[:-1])
        assert DISPUTED_CLAUSE in text
        assert "because" not in DISPUTED_CLAUSE
        assert "sting" not in text
        assert "funeral" not in text.lower()
        assert "bargain" not in text
        offsets = clause_offsets(text)
        assert offsets["exact_match"] is True
        assert text[offsets["start"] : offsets["end"]] == DISPUTED_CLAUSE
        human = human_reference_label()
        assert human["present_in_provider_request"] is False
        assert human["paragraph_verdict_expected"] == SELECTED_CASE_HUMAN_LABEL
        assert human["claims"][0]["verdict"] == "SUPPORTED"
        assert human["claims"][1]["supported"] is False


class TestEvidenceAndLeak:
    def test_evidence_is_canonical_p4_only(self):
        inventory = build_canonical_evidence_inventory()
        assert inventory["complete"] is True
        assert inventory["h01_evidence_not_used"] is True
        assert inventory["h02_evidence_not_used"] is True
        assert inventory["fabricated_evidence_added"] is False
        by_id = {row["id"]: row for row in inventory["src"]}
        assert by_id["SRC006192"]["exact_text"] == "It's not mind over matter."
        assert by_id["SRC006193"]["exact_text"] == "It must be your reality."
        assert by_id["SRC006195"]["exact_text"] == "It must be your reality."
        idea = inventory["ideas"][0]
        assert idea["id"] == "IDEA226"
        assert "lived reality" in idea["exact_text"]
        assert all(row["gate_text_matches_canonical"] for row in inventory["src"])
        assert set(inventory["allowed_handles_in_request"]) == set(P4_EVIDENCE_HANDLES)
        assert DISPUTED_CLAUSE.lower() not in idea["exact_text"].lower()

    def test_human_labels_and_history_are_absent_from_request(self):
        payload = build_selected_payload()
        leak = audit_label_leak(payload)
        blob = json.dumps(payload, ensure_ascii=False)
        catalog_noise = {"new_causal", "reference_completion"}
        assert not (set(leak["hits"]) - catalog_noise)
        assert SELECTED_CASE_ID not in blob
        assert SOURCE_CASE_ID not in blob
        assert "human_label" not in blob.lower()
        assert "expected_class" not in blob.lower()
        for handle in H01_EVIDENCE_HANDLES + P3_EVIDENCE_HANDLES:
            assert handle not in blob
        assert '"h01"' not in blob
        assert '"h02"' not in blob
        assert '"h03"' not in blob
        frozen = freeze_selected_request()
        assert frozen["independent_of_h01_h02"] is True
        assert frozen["label_leak_pass"] is True
        assert frozen["exactly_one_case"] is True
        assert frozen["handles_in_request"] == [SELECTED_CASE_HANDLE]
        system = next(
            item["content"] for item in frozen["payload"]["messages"] if item["role"] == "system"
        )
        user = next(
            item["content"] for item in frozen["payload"]["messages"] if item["role"] == "user"
        )
        assert DISPUTED_CLAUSE in user
        assert DISPUTED_CLAUSE not in system


class TestContractAndTransport:
    def test_113_protections_and_frozen_fingerprints(self):
        assert content_hash(system_prompt()) == EXPECTED_PROMPT_SYSTEM_SHA256
        assert content_hash(instruction_prompt()) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
        assert candidate_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256
        assert candidate_111_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256
        assert candidate_112_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_112_SHA256
        bundle = candidate_113_prompt_bundle()
        assert bundle["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256
        assert bundle["promoted"] is False
        inspected = inspect_contract_113()
        assert inspected["anomaly"] is None
        protections = inspected["protections"]
        assert protections["accepts_supported_paraphrase"] is True
        assert protections["blocks_new_implications"] is True
        assert protections["blocks_unsupported_strengthening"] is True
        assert protections["blocks_which_means_extension"] is True
        assert protections["no_case_answer_in_prompt"] is True
        reasons = inspect_reason_code_compatibility()
        assert reasons["codes_in_catalog"] is True
        assert reasons["no_code_invented_for_this_canary"] is True
        for code in reasons["expected_codes_audit_only"]:
            assert code in REASON_CODES
        transport = inspect_transport_compatibility()
        assert transport["compatible_without_schema_change"] is True
        assert transport["new_transport_created"] is False
        assert transport["transport"] == TRANSPORT_VERSION_11


class TestRequestFreezeAndSdk:
    def test_request_is_deterministic_and_distinct(self):
        frozen = freeze_selected_request()
        assert frozen["determinism"] is True
        assert frozen["first_sha256"] == frozen["second_sha256"]
        assert frozen["sha256"] != H01_REQUEST_SHA256
        assert frozen["sha256"] != H02_REQUEST_SHA256
        assert frozen["model"] == MODEL
        assert frozen["prompt_version"] == PROMPT_VERSION_113
        assert frozen["payload"]["max_completion_tokens"] == 8192
        assert "max_tokens" not in frozen["payload"]
        assert "temperature" not in frozen["payload"]
        assert frozen["payload"]["response_format"] == {"type": "json_object"}
        gate = extract_gate_input(frozen["payload"])
        handles = [
            para.get("h")
            for section in (gate.get("candidate") or {}).get("sections") or []
            for para in section.get("paras") or []
        ]
        assert handles == [SELECTED_CASE_HANDLE]
        assert SOURCE_CASE_HANDLE not in handles
        text = gate["candidate"]["sections"][0]["paras"][0]["t"]
        assert text == synthetic_paragraph_text()
        offsets = clause_offsets(text)
        span = validate_compact_span(text, offsets["start"], offsets["end"])
        assert span["valid"] is True
        assert span["recovered_text"] == DISPUTED_CLAUSE

    def test_sdk_serialization_has_zero_network(self):
        captured = serialize_selected_sdk()
        assert captured["network_calls"] == 0
        assert captured["http_requests"] == 0
        assert captured["serialization_pass"] is True
        assert captured["checks"]["max_completion_tokens"] is True
        assert captured["checks"]["max_tokens_absent"] is True
        assert captured["checks"]["temperature_absent"] is True
        assert captured["checks"]["json_object"] is True
        assert captured["checks"]["future_retries_disabled"] is True
        assert captured["checks"]["reasoning_params_absent"] is True
        assert captured["fallbacks"] == 0
        assert captured["secrets_included"] is False


class TestFakeAIAndNegatives:
    def test_ten_historical_cases_remain_protected(self):
        assert len(SCORED_CASE_ORDER) == 10
        assert len(POSITIVE_CASE_IDS) == 6
        assert len(NEGATIVE_CASE_IDS) == 4
        assert FUNERAL_CASE_ID in NEGATIVE_CASE_IDS
        assert CONNECTIVE_CASE_ID in NEGATIVE_CASE_IDS
        assert P3_CASE_ID in NEGATIVE_CASE_IDS
        assert P8_CASE_ID in NEGATIVE_CASE_IDS
        ten = historical_ten_case_protection()
        assert ten["positives_accepted"] == 6
        assert ten["negatives_blocked"] == 4
        assert ten["funeral_blocked"] is True
        assert ten["connective_blocked"] is True
        assert ten["p3_blocked"] is True
        assert ten["p8_blocked"] is True
        assert ten["fakeai_not_terra_quality"] is True
        payload = build_selected_payload()
        one = interpret_selected_simulation(payload)
        assert one["implication_blocked"] is True
        assert one["implication_claim_flagged"] is True
        assert one["flagged_span_is_disputed_clause"] is True
        assert one["supported_prefix_accepted"] is True
        assert one["global_verdict_blocks_acceptance"] is True
        assert one["validation"]["status"] == "PASS"
        assert one["no_unnecessary_duplication"] is True
        assert one["fakeai_not_terra_quality"] is True


class TestSecretsAndPublication:
    def test_no_secret_leak_and_book_unpublished(self):
        blob = json.dumps(freeze_selected_request())
        assert LEAK_KEY not in blob
        assert "sk-" not in blob
        assert production_book_absent(PROJECT_NAME) is True
        assert SELECTED_CASE_HANDLE != SOURCE_CASE_HANDLE
