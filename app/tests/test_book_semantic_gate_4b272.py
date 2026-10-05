"""Phase 4B.2.7.2 — P3 negative canary offline freeze. Network forbidden."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.thinking import (
    UNKNOWN_TOKEN_COUNT,
    extract_openai_usage_telemetry,
    extract_thinking_tokens_from_usage,
)
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
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
from app.book_semantic_gate_4b271.coverage import KIND_SIGNIFICANT, classify_uncovered_gaps
from app.book_semantic_gate_4b272.causal import review_causal_claim
from app.book_semantic_gate_4b272.constants import (
    AUTHORIZED_TERRA_CALLS,
    DISPUTED_CAUSAL_CLAUSE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_SOURCE_MAP,
    H01_EVIDENCE_HANDLES,
    H01_REQUEST_SHA256,
    HISTORICAL_4B271_STATUS,
    HISTORICAL_4B27_STATUS,
    MODEL,
    P3_EVIDENCE_HANDLES,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_111,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    SELECTED_CASE_ROLE,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_11,
)
from app.book_semantic_gate_4b272.contract import (
    inspect_contract_111,
    inspect_transport_compatibility,
)
from app.book_semantic_gate_4b272.coverage import analyze_p3_span_coverage, p3_local_propositions
from app.book_semantic_gate_4b272.evidence import build_canonical_evidence_inventory
from app.book_semantic_gate_4b272.fakeai import (
    historical_ten_case_protection,
    interpret_p3_simulation,
)
from app.book_semantic_gate_4b272.guard import assert_offline_only
from app.book_semantic_gate_4b272.identity import p3_benchmark_identity
from app.book_semantic_gate_4b272.request import (
    build_p3_payload,
    freeze_p3_request,
    serialize_p3_sdk,
)
from app.file_utils import content_hash


LEAK_KEY = "sk-SECRET-4B272-LEAK-TEST-VALUE-DO-NOT-PERSIST"


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
        assert PHASE == "4B.2.7.2"
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert HISTORICAL_4B27_STATUS == "PARTIAL"
        assert HISTORICAL_4B271_STATUS == "PASS"
        assert PROMPT_VERSION_111 == "book-semantic-validator-1.1.1-candidate"
        assert TRANSPORT_VERSION_11 == "book-semantic-validation-transport-1.1-candidate"
        assert EXPECTED_SOURCE_MAP == (
            "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855"
        )
        assert EXPECTED_EDITORIAL_PLAN == (
            "01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440"
        )
        assert EXPECTED_CLEAN_TRANSCRIPT == (
            "1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958"
        )
        assert H01_REQUEST_SHA256 == (
            "9520a4f3e5ff36ec2957b74e82d492019ff630f764e1413853b19d9b96dec6af"
        )

    def test_execute_real_rejected_by_cli(self):
        from app.book_semantic_gate_4b272.__main__ import main

        assert main(["--execute-real"]) == 2

    def test_canonical_inputs_unchanged(self):
        identities = verify_canonical_inputs()
        assert identities["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert identities["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert identities["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
        assert production_book_absent(PROJECT_NAME) is True


class TestP3IdentityAndEvidence:
    def test_p3_identity_is_unambiguous(self):
        identity = p3_benchmark_identity()
        assert identity["case_id"] == SELECTED_CASE_ID == P3_CASE_ID == "4b22_p3_new_causal"
        assert identity["opaque_handle"] == SELECTED_CASE_HANDLE == "h02"
        assert identity["role_audit_only"] == SELECTED_CASE_ROLE == "negative"
        assert identity["human_label_audit_only"]["expected_class"] == SELECTED_CASE_HUMAN_LABEL
        assert identity["human_label_audit_only"]["present_in_provider_request"] is False
        assert identity["disputed_causal_clause"] == DISPUTED_CAUSAL_CLAUSE
        assert identity["clause_position"]["exact_match"] is True
        assert identity["clause_position"]["start"] == 406
        assert identity["clause_position"]["end"] == 465
        assert identity["benchmark"]["identity_match"] is True
        assert identity["benchmark_unmodified"] is True
        assert identity["identified"] is True
        assert identity["paragraph_text"].endswith(
            "because it still works wherever it is not resisted by truth."
        )

    def test_benchmark_integrity_and_evidence_complete(self):
        inventory = build_canonical_evidence_inventory()
        assert inventory["complete"] is True
        assert inventory["h01_evidence_not_used"] is True
        assert inventory["h01_handles_injected"] == []
        by_id = {row["id"]: row for row in inventory["src"]}
        assert by_id["SRC006152"]["exact_text"] == "It is an abuse"
        assert by_id["SRC006154"]["exact_text"] == "It is an abuse to your person."
        assert by_id["SRC006155"]["exact_text"] == "And the devil"
        assert by_id["SRC006156"]["exact_text"] == "has used it since."
        assert by_id["SRC006157"]["exact_text"] == "He has not changed his style."
        idea = inventory["ideas"][0]
        assert idea["id"] == "IDEA225"
        assert "old strategy" in idea["exact_text"]
        assert all(row["gate_text_matches_canonical"] for row in inventory["src"])
        assert inventory["external_religious_knowledge_used"] is False
        assert set(inventory["allowed_handles_in_request"]) == set(P3_EVIDENCE_HANDLES)

    def test_causal_clause_is_not_justified_by_authorized_evidence(self):
        review = review_causal_claim()
        assert review["BENCHMARK_EVIDENCE_CONFLICT"] is False
        assert review["sufficient_to_justify_causality"] is False
        assert review["exact_clause_in_authorized_evidence"] is False
        assert review["causal_markers_in_authorized_evidence"] == []
        assert review["clause_content_markers_in_authorized_evidence"] == []
        assert review["core_without_because_attested"] is True
        assert review["lexical_absence_is_not_the_test"] is True
        assert review["negative_canary_still_justified"] is True
        assert review["historical_label_unmodified"] is True
        assert review["external_knowledge_used"] is False


class TestLabelLeakAndIndependence:
    def test_human_labels_and_h01_are_absent_from_request(self):
        payload = build_p3_payload()
        leak = audit_label_leak(payload)
        blob = json.dumps(payload, ensure_ascii=False)
        assert leak["pass"] is True
        assert SELECTED_CASE_ID not in blob
        assert "human_label" not in blob.lower()
        assert "expected_class" not in blob.lower()
        assert "NEW_CAUSAL_LINK" not in blob
        for handle in H01_EVIDENCE_HANDLES:
            assert handle not in blob
        assert '"h01"' not in blob
        assert "IDEA224" not in blob
        frozen = freeze_p3_request()
        assert frozen["independent_of_h01"] is True
        assert frozen["label_leak_pass"] is True
        assert frozen["exactly_one_case"] is True
        assert frozen["handles_in_request"] == [SELECTED_CASE_HANDLE]


class TestContractAndTransport:
    def test_111_protections_and_frozen_fingerprints(self):
        assert content_hash(system_prompt()) == EXPECTED_PROMPT_SYSTEM_SHA256
        assert content_hash(instruction_prompt()) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
        assert candidate_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256
        bundle = candidate_111_prompt_bundle()
        assert bundle["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256
        assert bundle["promoted"] is False
        inspected = inspect_contract_111()
        assert inspected["anomaly"] is None
        assert inspected["blocker"] is None
        protections = inspected["protections"]
        assert protections["accepts_supported_paraphrase"] is True
        assert protections["does_not_require_lexical_match"] is True
        assert protections["blocks_unsupported_causal_relations"] is True
        assert protections["blocks_new_implications"] is True
        assert protections["blocks_invented_examples"] is True
        assert protections["blocks_reference_completion"] is True
        assert protections["requires_reason_code_for_questionable_unsupported"] is True
        assert protections["no_p3_answer_in_prompt"] is True
        transport = inspect_transport_compatibility()
        assert transport["compatible_without_schema_change"] is True
        assert transport["new_transport_created"] is False
        assert transport["schema_change_required"] is False
        assert transport["transport"] == TRANSPORT_VERSION_11


class TestSpansAndCausalConnectors:
    def test_p3_coverage_includes_because_and_rejects_omission(self):
        identity = p3_benchmark_identity()
        text = identity["paragraph_text"]
        audit = analyze_p3_span_coverage(text)
        assert audit["coverage_complete"] is True
        assert audit["causal_clause_covered"] is True
        assert audit["causal_connector_because_covered"] is True
        assert audit["negation_in_causal_clause_covered"] is True
        assert audit["omitting_causal_clause_fails"] is True
        assert audit["non_empty_spans"] is True
        assert audit["valid_offsets"] is True
        assert audit["inconsistent_overlap"] is False
        assert audit["local_111_status"] == "PASS"
        recovered = text[406:465]
        assert recovered == DISPUTED_CAUSAL_CLAUSE
        span = validate_compact_span(text, 406, 465)
        assert span["valid"] is True
        assert span["recovered_text"] == DISPUTED_CAUSAL_CLAUSE
        period = text[465:466]
        assert period == "."
        classified = classify_uncovered_gaps(
            text, [{"s": item["s"], "e": item["e"]} for item in audit["claims"]]
        )
        assert all(item["kind"] != KIND_SIGNIFICANT for item in classified)

    def test_propositions_do_not_skip_the_contested_clause(self):
        identity = p3_benchmark_identity()
        props = p3_local_propositions(identity["paragraph_text"])
        causal = [item for item in props if item.get("contains_causal_clause")]
        assert len(causal) == 1
        assert causal[0]["text"] == DISPUTED_CAUSAL_CLAUSE
        assert causal[0]["contains_because"] is True


class TestRequestFreezeAndSdk:
    def test_request_is_deterministic_and_distinct_from_h01(self):
        frozen = freeze_p3_request()
        assert frozen["determinism"] is True
        assert frozen["first_sha256"] == frozen["second_sha256"]
        assert frozen["sha256"] != H01_REQUEST_SHA256
        assert frozen["differs_from_h01"] is True
        assert frozen["model"] == MODEL
        assert frozen["prompt_version"] == PROMPT_VERSION_111
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

    def test_sdk_serialization_has_zero_network(self):
        captured = serialize_p3_sdk()
        assert captured["network_calls"] == 0
        assert captured["http_requests"] == 0
        assert captured["serialization_pass"] is True
        assert captured["checks"]["max_completion_tokens"] is True
        assert captured["checks"]["max_tokens_absent"] is True
        assert captured["checks"]["temperature_absent"] is True
        assert captured["checks"]["json_object"] is True
        assert captured["checks"]["future_retries_disabled"] is True
        assert captured["secrets_included"] is False


class TestFakeAIAndNegatives:
    def test_ten_historical_cases_and_p3_blocked(self):
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
        payload = build_p3_payload()
        one = interpret_p3_simulation(payload)
        assert one["p3_blocked"] is True
        assert one["causal_claim_flagged"] is True
        assert one["global_verdict_blocks_acceptance"] is True
        assert one["validation"]["status"] == "PASS"
        assert one["no_unnecessary_duplication"] is True


class TestTelemetryAccountingAndPublication:
    def test_reasoning_token_telemetry_unknown_is_not_zero(self):
        present = extract_openai_usage_telemetry(
            {
                "prompt_tokens": 5,
                "completion_tokens": 9,
                "completion_tokens_details": {"reasoning_tokens": 4},
            }
        )
        assert present["reasoning_tokens"] == 4
        absent = extract_openai_usage_telemetry({"prompt_tokens": 1, "completion_tokens": 2})
        assert absent["reasoning_tokens"] == UNKNOWN_TOKEN_COUNT
        assert extract_thinking_tokens_from_usage({"prompt_tokens": 1}) is None
        zero = extract_openai_usage_telemetry(
            {"completion_tokens_details": {"reasoning_tokens": 0}}
        )
        assert zero["reasoning_tokens"] == 0

    def test_anthropic_still_uses_max_tokens_and_book_json_absent(self, tmp_path):
        engine = AnthropicEngine(api_key="offline-anthropic-unused", model="claude-sonnet-5")
        payload = engine.build_payload(
            AIRequest(prompt="offline anthropic regression", model="claude-sonnet-5"),
            "claude-sonnet-5",
        )
        assert payload["max_tokens"] > 0
        assert "max_completion_tokens" not in payload
        from app.book_semantic_gate_4b272.writer import write_phase_artifacts

        write_phase_artifacts(
            {
                "header": {"result": "PASS"},
                "identity": {"phase": PHASE},
                "report_text": "# PHASE 4B.2.7.2\n",
            },
            root=tmp_path,
        )
        assert production_book_absent(PROJECT_NAME) is True
        written = tmp_path / "audit" / "book_semantic_gate_4b272"
        assert (written / "p3_benchmark_identity.json").is_file()
        historical = Path("audit/PHASE_4B27_ONE_REAL_TERRA_COMPACT_SINGLE_CASE_CANARY_REPORT.md")
        assert historical.is_file()
        assert "RESULT = PARTIAL" in historical.read_text(encoding="utf-8")
        blob = json.dumps(build_canonical_evidence_inventory())
        assert LEAK_KEY not in blob
        assert "sk-" not in blob
        request_blob = json.dumps(build_p3_payload())
        assert LEAK_KEY not in request_blob
