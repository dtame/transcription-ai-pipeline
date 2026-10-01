"""Phase 4B.2.4 — Terra semantic-gate canary. Network blocked."""

from __future__ import annotations

import json

import pytest

from app.book_semantic_gate_4b23.accept import apply_acceptance
from app.book_semantic_gate_4b23.fakeai import fixture_supported
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b23.schema import schema_identity
from app.book_semantic_gate_4b23.transport import decode_transport
from app.book_semantic_gate_4b24.constants import (
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    EXPECTED_BENCHMARK_DATASET_SHA256,
    EXPECTED_BENCHMARK_FILE_SHA256,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_SHA256,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_SCHEMA_SHA256,
    EXPECTED_SCORED_CASES,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B21_STATUS,
    HISTORICAL_4B22_STATUS,
    HISTORICAL_4B2_STATUS,
    MODEL,
    NEGATIVE_CASE_IDS,
    POSITIVE_CASE_IDS,
    PROMPT_VERSION,
    PROVIDER,
    RETRIES,
    SCORED_CASE_ORDER,
    TRANSPORT_VERSION,
)
from app.book_semantic_gate_4b24.engine import CountingOpenAIEngine
from app.book_semantic_gate_4b24.identity import benchmark_identity, contract_identities
from app.book_semantic_gate_4b24.leak import audit_label_leak
from app.book_semantic_gate_4b24.score import classify_canary, score_benchmark
from app.book_semantic_gate_4b24.validate import deterministic_replay, validate_semantic_response


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestIdentities:
    def test_frozen_history_and_limits(self):
        assert AUTHORIZED_TERRA_CALLS == 1
        assert AUTHORIZED_SONNET_CALLS == 0
        assert RETRIES == 0
        assert HISTORICAL_4B2_STATUS == "FAIL"
        assert HISTORICAL_4B21_STATUS == "PASS"
        assert HISTORICAL_4B22_STATUS == "PARTIAL"
        assert EXPECTED_SOURCE_MAP == (
            "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855"
        )
        assert EXPECTED_EDITORIAL_PLAN == (
            "01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440"
        )
        assert EXPECTED_CLEAN_TRANSCRIPT == (
            "1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958"
        )
        assert PROVIDER == "openai"
        assert MODEL == "gpt-5.6-terra"
        assert PROMPT_VERSION == "book-semantic-validator-1.0"
        assert TRANSPORT_VERSION == "book-semantic-validation-transport-1.0"

    def test_benchmark_identity_matches_4b23(self):
        meta = benchmark_identity()
        assert meta["identity_match"] is True
        assert meta["sha256"] == EXPECTED_BENCHMARK_FILE_SHA256
        assert meta["dataset_sha256"] == EXPECTED_BENCHMARK_DATASET_SHA256
        assert meta["scored_case_count"] == EXPECTED_SCORED_CASES
        assert meta["positive_case_ids"] == list(POSITIVE_CASE_IDS)
        assert meta["negative_case_ids"] == list(NEGATIVE_CASE_IDS)
        assert meta["p9b"]["semantic_benchmark_case"] is False

    def test_contract_identities_match_4b23(self):
        contracts = contract_identities()
        assert contracts["contract_match"] is True
        assert contracts["prompt"]["prompt_sha256"] == EXPECTED_PROMPT_SHA256
        assert contracts["schema"]["raw_schema_sha256"] == EXPECTED_SCHEMA_SHA256
        assert schema_identity()["engine_mode"] == "json_object"
        assert schema_identity()["native_json_schema_response_format"] is False


class TestOpaqueHandlesAndLeak:
    def test_handles_do_not_encode_labels(self):
        for handle, case_id in SCORED_CASE_ORDER:
            lowered = handle.lower()
            assert "positive" not in lowered
            assert "negative" not in lowered
            assert "invented" not in lowered
            assert "unsupported" not in lowered
            assert case_id not in handle

    def test_label_leak_detects_case_ids(self):
        dirty = {
            "model": "gpt-5.6-terra",
            "messages": [
                {
                    "role": "user",
                    "content": "expected_class SUPPORTED 4b2_p8_invented_funeral",
                }
            ],
        }
        audit = audit_label_leak(dirty)
        assert audit["pass"] is False
        assert audit["label_leakage"] > 0

    def test_clean_payload_has_zero_leak(self):
        payload = {
            "model": "gpt-5.6-terra",
            "messages": [
                {"role": "system", "content": "You are an evidence-bounded semantic auditor."},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "candidate": {
                                "chapter_id": "CH016",
                                "sections": [
                                    {
                                        "sid": "SEC063",
                                        "paras": [{"h": "h01", "t": "Do not ever be afraid of death."}],
                                    }
                                ],
                            }
                        }
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        audit = audit_label_leak(payload)
        assert audit["pass"] is True
        assert audit["label_leakage"] == 0


class TestTransportSpansReasons:
    def test_transport_decode_and_acceptance_policy(self):
        fixture = fixture_supported()
        decoded = decode_transport(fixture["parsed"])
        assert decoded["chapter_handle"] == "CH016"
        result = apply_acceptance(
            fixture["parsed"],
            required_handles=fixture["required"],
            paragraph_texts=fixture["texts"],
            allowed_handles=fixture["allowed"],
        )
        assert result["verdict"] == "PASS"
        assert result["cache_acceptance"] is True

    def test_questionable_and_unsupported_block_cache(self):
        from app.book_semantic_gate_4b23.fakeai import (
            fixture_invented_example,
            fixture_new_causal_link,
            interpret_fixture,
        )

        causal = interpret_fixture(fixture_new_causal_link())
        invented = interpret_fixture(fixture_invented_example())
        assert causal["result"]["cache_acceptance"] is False
        assert invented["result"]["cache_acceptance"] is False
        assert "NEW_CAUSAL_LINK" in REASON_CODES
        assert "INVENTED_EXAMPLE" in REASON_CODES
        assert "REFERENCE_COMPLETION" in REASON_CODES


class TestScorerAndReplay:
    def _rows(self):
        return [
            {
                "case_id": case_id,
                "role": "positive" if case_id in POSITIVE_CASE_IDS else "negative",
                "expected_class": "SUPPORTED" if case_id in POSITIVE_CASE_IDS else "UNSUPPORTED",
                "accepted_classes": (
                    ["SUPPORTED"]
                    if case_id in POSITIVE_CASE_IDS
                    else ["QUESTIONABLE", "UNSUPPORTED"]
                ),
                "expected_reason_codes": (
                    []
                    if case_id in POSITIVE_CASE_IDS
                    else ["INVENTED_EXAMPLE", "NEW_ARGUMENT", "NEW_CAUSAL_LINK", "REFERENCE_COMPLETION"]
                ),
            }
            for _, case_id in SCORED_CASE_ORDER
        ]

    def test_clean_score_and_false_negative_policy(self):
        cases = self._rows()
        results = []
        for handle, case_id in SCORED_CASE_ORDER:
            negative = case_id in NEGATIVE_CASE_IDS
            results.append(
                {
                    "opaque_handle": handle,
                    "case_id": case_id,
                    "paragraph_handle": handle,
                    "verdict": "UNSUPPORTED" if negative else "SUPPORTED",
                    "reason_codes": ["INVENTED_EXAMPLE"] if negative else [],
                    "claim_results": [
                        {
                            "claim_index": 0,
                            "claim_text": "x",
                            "start_offset": 0,
                            "end_offset": 1,
                            "classification": "UNSUPPORTED" if negative else "SUPPORTED",
                            "reason_codes": ["INVENTED_EXAMPLE"] if negative else [],
                            "explanation": "supplied evidence only",
                        }
                    ],
                }
            )
        score = score_benchmark(cases=cases, paragraph_results=results)
        assert score["positive_accepted"] == 6
        assert score["negative_blocked"] == 4
        assert score["negative_false_negatives"] == 0
        assert score["positive_false_rejections"] == 0
        missed = score_benchmark(
            cases=cases,
            paragraph_results=[
                {**row, "verdict": "SUPPORTED", "claim_results": [
                    {**row["claim_results"][0], "classification": "SUPPORTED", "reason_codes": []}
                ]}
                if row["case_id"] == "4b2_p8_invented_funeral"
                else row
                for row in results
            ],
        )
        assert missed["negative_false_negatives"] == 1
        assert (
            classify_canary(
                terra_calls=1,
                sonnet_calls=0,
                retries=0,
                fallbacks=0,
                structural_pass=True,
                label_leakage=0,
                score=missed,
                replay_pass=True,
                inputs_unchanged=True,
                test_failures=0,
                http_success=True,
            )
            == "FAIL"
        )

    def test_deterministic_replay(self):
        fixture = fixture_supported()
        replay = deterministic_replay(
            fixture["parsed"],
            required_handles=fixture["required"],
            paragraph_texts=fixture["texts"],
            allowed_handles=fixture["allowed"],
        )
        assert replay["pass"] is True
        assert replay["identical"] is True
        structural = validate_semantic_response(
            fixture["parsed"],
            required_handles=fixture["required"],
            paragraph_texts=fixture["texts"],
            allowed_handles=fixture["allowed"],
        )
        assert structural["structural_pass"] is True
        assert structural["span_validation"] == "PASS"


class TestEngineGuards:
    def test_temperature_omitted_and_no_retry(self):
        engine = CountingOpenAIEngine(api_key="offline", client=object())
        from app.ai.contracts import AIRequest

        request = AIRequest(
            prompt="audit this chapter candidate",
            system_prompt="auditor",
            model=MODEL,
            temperature=None,
            max_output_tokens=16,
            response_schema={"type": "object"},
        )
        payload = engine.build_payload(request, MODEL)
        assert "temperature" not in payload
        assert payload["response_format"] == {"type": "json_object"}
        assert engine.retry_policy.max_attempts == 1


class TestPrecallDry:
    def test_precall_builds_deterministic_unleaked_request(self):
        from app.book_semantic_gate_4b24.precall import build_precall

        identity = build_precall()
        assert identity["request"]["deterministic"] is True
        assert identity["request"]["sha256"] == EXPECTED_REQUEST_SHA256
        assert identity["request"]["sha256_repeat"] == EXPECTED_REQUEST_SHA256
        assert identity["label_leak"]["pass"] is True
        assert identity["label_leak"]["label_leakage"] == 0
        assert identity["request"]["temperature_present"] is False
        assert identity["request"]["thinking_present"] is False
        assert identity["request"]["response_format"] == {"type": "json_object"}
        assert len(identity["candidate_handles"]) == 10
        if identity["blocked_precall"]:
            assert identity["block_reasons"]
        else:
            assert identity["cost_estimate"]["context_safe"] is True
