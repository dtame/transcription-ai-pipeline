"""Phase 4B.2.6 — Terra canary. Network blocked. 0 provider calls in tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.contracts import AIRequest
from app.ai.openai_compat import (
    TOKEN_PARAM_MAX_COMPLETION_TOKENS,
    TOKEN_PARAM_MAX_TOKENS,
    capture_openai_sdk_chat_request,
)
from app.ai.provider_preflight import (
    READY_WITH_SERVER_UNVERIFIED_FIELDS,
    REASON_PROVIDER_RUNTIME_NOT_READY,
    assert_provider_ready_for_authorization,
    check_provider_runtime_readiness,
    redact_secrets,
)
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.openai_engine import OpenAIEngine
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.fakeai import fixture_supported, run_fakeai_catalog
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b23.guard import assert_offline_package
from app.book_semantic_gate_4b24.constants import NEGATIVE_CASE_IDS, POSITIVE_CASE_IDS
from app.book_semantic_gate_4b24.score import classify_canary, score_benchmark
from app.book_semantic_gate_4b24.validate import deterministic_replay, validate_semantic_response
from app.book_semantic_gate_4b26.accounting import CallAccounting
from app.book_semantic_gate_4b26.constants import (
    AUTHORIZED_REMOTE_TERRA_INVOCATIONS,
    AUTHORIZED_SONNET_CALLS,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_REQUEST_SHA256_HISTORICAL_4B25,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B21_STATUS,
    HISTORICAL_4B22_STATUS,
    HISTORICAL_4B23_STATUS,
    HISTORICAL_4B241_STATUS,
    HISTORICAL_4B24_STATUS,
    HISTORICAL_4B251_STATUS,
    HISTORICAL_4B25_STATUS,
    HISTORICAL_4B2_STATUS,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PROJECT_NAME,
    SCORED_CASE_ORDER,
    SEMANTIC_TOKEN_BUDGET,
    TOKEN_FIELD,
)
from app.book_semantic_gate_4b26.engine import AccountingOpenAIEngine
from app.book_semantic_gate_4b26.guard import BookSemanticGate26Error, consume_remote_lock
from app.book_semantic_gate_4b26.paths import historical_audit_dirs, venv_python_path
from app.book_semantic_gate_4b26.precall import SERVER_ONLY_UNKNOWNS, build_precall
from app.book_semantic_gate_4b26.runtime import interpreter_match, normalize_executable
from app.book_semantic_gate_4b26.writer import write_canary_artifacts


LEAK_KEY = "sk-SECRET-4B26-LEAK-TEST-VALUE-DO-NOT-PERSIST"


@pytest.fixture(autouse=True)
def _no_network(no_ai_network, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("PROVIDER NETWORK FORBIDDEN")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.Client.send", forbidden)
    return None


class TestHistoricalStatus:
    def test_history_is_frozen(self):
        assert PHASE == "4B.2.6"
        assert AUTHORIZED_REMOTE_TERRA_INVOCATIONS == 1
        assert AUTHORIZED_SONNET_CALLS == 0
        assert HISTORICAL_4B2_STATUS == "FAIL"
        assert HISTORICAL_4B21_STATUS == "PASS"
        assert HISTORICAL_4B22_STATUS == "PARTIAL"
        assert HISTORICAL_4B23_STATUS == "PASS"
        assert HISTORICAL_4B24_STATUS == "FAIL"
        assert HISTORICAL_4B241_STATUS == "PASS"
        assert HISTORICAL_4B25_STATUS == "FAIL"
        assert HISTORICAL_4B251_STATUS == "PASS"
        assert EXPECTED_SOURCE_MAP == (
            "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855"
        )
        assert EXPECTED_EDITORIAL_PLAN == (
            "01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440"
        )
        assert EXPECTED_CLEAN_TRANSCRIPT == (
            "1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958"
        )
        assert EXPECTED_REQUEST_SHA256 == (
            "8a92848e412763f0e67468245f9c007ee9537ffa4f2f5469af9a6934d9ebeb31"
        )
        assert EXPECTED_REQUEST_SHA256_HISTORICAL_4B25 == (
            "09d6472e544bc60231c77908e6608ff7ee7b6fd4746317f206301082e21eab53"
        )
        assert TOKEN_FIELD == "max_completion_tokens"
        assert SEMANTIC_TOKEN_BUDGET == 8192


class TestInterpreterGate:
    def test_wrong_interpreter_is_precall_block(self, monkeypatch):
        monkeypatch.setattr(
            "app.book_semantic_gate_4b26.runtime.sys.executable",
            r"C:\Program Files\Python311\python.exe",
        )
        identity = build_precall()
        assert identity["blocked_precall"] is True
        assert "interpreter" in identity["block_reasons"]
        assert identity["remote_invocations"] == 0

    def test_canonical_venv_normalizes(self):
        expected = venv_python_path()
        if expected.exists():
            assert normalize_executable(expected) == str(expected.resolve())


class TestCorrectedRequestIdentity:
    def test_request_matches_corrected_4b251_sha(self):
        identity = build_precall()
        request = identity["request"]
        payload = identity["payload"]
        assert request["deterministic"] is True
        assert request["sha256"] == request["sha256_repeat"]
        assert request["sha256"] == EXPECTED_REQUEST_SHA256
        assert request["sha256"] != EXPECTED_REQUEST_SHA256_HISTORICAL_4B25
        assert payload["max_completion_tokens"] == SEMANTIC_TOKEN_BUDGET
        assert "max_tokens" not in payload
        assert request["temperature_present"] is False
        assert request["thinking_present"] is False
        assert request["response_format"] == {"type": "json_object"}
        assert identity["label_leak"]["label_leakage"] == 0
        assert len(identity["candidate_handles"]) == 10
        assert identity["case_coverage"]["present"] == 10
        hashes = identity["canonical_hashes"]
        assert hashes["source_map_pre"] == EXPECTED_SOURCE_MAP
        assert hashes["source_map_post"] == EXPECTED_SOURCE_MAP
        assert hashes["editorial_plan_pre"] == EXPECTED_EDITORIAL_PLAN
        assert hashes["editorial_plan_post"] == EXPECTED_EDITORIAL_PLAN
        assert hashes["clean_transcript_pre"] == EXPECTED_CLEAN_TRANSCRIPT
        assert hashes["clean_transcript_post"] == EXPECTED_CLEAN_TRANSCRIPT


class TestApiCompatibility:
    def test_unknown_is_not_pass(self):
        identity = build_precall()
        compat = identity["api_compatibility"]
        assert compat["unknown_is_not_pass"] is True
        assert compat["no_live_probe_authorized"] is True
        assert compat["cannot_claim_server_acceptance"] is True
        fields = set(compat["server_only_unknown_fields"])
        assert "json_object_server_acceptance" in fields
        assert "max_completion_tokens_server_acceptance" in fields
        for item in SERVER_ONLY_UNKNOWNS:
            assert item["status"] == "UNKNOWN"
            assert item["status"] != "PASS"
        local = compat["local_checks"]
        assert local["max_tokens_absent"] is True
        assert local["json_object_local"] is True
        assert local["json_object_server_acceptance"] == "UNKNOWN"
        assert local["max_completion_tokens_server_acceptance"] == "UNKNOWN"

    def test_sdk_serialization_has_corrected_fields(self):
        engine = OpenAIEngine(api_key="offline", client=object())
        payload = engine.build_payload(
            AIRequest(
                prompt="audit this chapter candidate",
                system_prompt="auditor",
                model=MODEL,
                temperature=None,
                max_output_tokens=SEMANTIC_TOKEN_BUDGET,
                response_schema={"type": "object"},
            ),
            MODEL,
        )
        captured = capture_openai_sdk_chat_request(payload, api_key=LEAK_KEY)
        body = captured["body"]
        assert body["max_completion_tokens"] == SEMANTIC_TOKEN_BUDGET
        assert "max_tokens" not in body
        assert "temperature" not in body
        assert "thinking" not in body
        assert body["response_format"] == {"type": "json_object"}
        assert captured["network_calls"] == 0
        assert LEAK_KEY not in json.dumps(captured)


class TestAccountingAndLock:
    def test_missing_sdk_does_not_consume_lock(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "app.ai.provider_preflight.import_provider_sdk",
            lambda name: (_ for _ in ()).throw(ImportError("missing")),
        )
        readiness = check_provider_runtime_readiness(
            "openai",
            model=MODEL,
            engine=OpenAIEngine(api_key=LEAK_KEY),
            output_mode=OUTPUT_MODE,
            request=AIRequest(prompt="offline", model=MODEL, response_schema={"type": "object"}),
        )
        lock = tmp_path / "book_semantic_gate_4b26_real_call.lock"
        with pytest.raises(Exception, match=REASON_PROVIDER_RUNTIME_NOT_READY):
            assert_provider_ready_for_authorization(readiness)
            consume_remote_lock(path=lock, phase=PHASE, scope="x")
        assert lock.exists() is False
        assert readiness.remote_invocations == 0
        assert readiness.network_calls == 0

    def test_second_lock_is_refused(self, tmp_path):
        lock = tmp_path / "lock.txt"
        consume_remote_lock(path=lock, phase=PHASE, scope="scope")
        with pytest.raises(BookSemanticGate26Error, match="NO RETRY"):
            consume_remote_lock(path=lock, phase=PHASE, scope="scope")

    def test_accounting_starts_at_zero(self):
        counts = CallAccounting()
        assert counts.authorized_remote_invocations == 1
        assert counts.execution_attempts == 0
        assert counts.remote_invocations == 0
        assert counts.http_requests == 0
        assert counts.provider_responses == 0
        assert counts.successful_payloads == 0
        assert counts.retries == 0
        assert counts.fallbacks == 0
        payload = counts.to_dict()
        assert payload["historical_4b25_unchanged"] is True


class TestEngineBoundary:
    def test_temperature_omitted_and_create_is_the_boundary(self):
        engine = AccountingOpenAIEngine(api_key="offline", client=object())
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
        assert payload[TOKEN_PARAM_MAX_COMPLETION_TOKENS] == 16
        assert TOKEN_PARAM_MAX_TOKENS not in payload
        assert engine.accounting.remote_invocations == 0
        assert engine.accounting.successful_payloads == 0
        assert engine.retry_policy.max_attempts == 1


class TestTransportSpansReasons:
    def test_transport_schema_spans_and_reason_codes(self):
        fixture = fixture_supported()
        structural = validate_semantic_response(
            fixture["parsed"],
            required_handles=fixture["required"],
            paragraph_texts=fixture["texts"],
            allowed_handles=fixture["allowed"],
        )
        assert structural["structural_pass"] is True
        assert structural["span_validation"] == "PASS"
        replay = deterministic_replay(
            fixture["parsed"],
            required_handles=fixture["required"],
            paragraph_texts=fixture["texts"],
            allowed_handles=fixture["allowed"],
        )
        assert replay["pass"] is True
        assert replay["identical"] is True
        assert "INVENTED_EXAMPLE" in REASON_CODES
        assert "NEW_CAUSAL_LINK" in REASON_CODES
        assert "REFERENCE_COMPLETION" in REASON_CODES
        catalog = run_fakeai_catalog()
        assert catalog
        assert_offline_package()


class TestBenchmarkScoring:
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
                    else [
                        "INVENTED_EXAMPLE",
                        "NEW_ARGUMENT",
                        "NEW_CAUSAL_LINK",
                        "REFERENCE_COMPLETION",
                    ]
                ),
            }
            for _, case_id in SCORED_CASE_ORDER
        ]

    def test_clean_score_and_false_negative_is_fail(self):
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
        missed = score_benchmark(
            cases=cases,
            paragraph_results=[
                {
                    **row,
                    "verdict": "SUPPORTED",
                    "claim_results": [
                        {
                            **row["claim_results"][0],
                            "classification": "SUPPORTED",
                            "reason_codes": [],
                        }
                    ],
                }
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


class TestWriterIsolation:
    def test_artifacts_do_not_enter_historical_dirs(self, tmp_path):
        historical = historical_audit_dirs()
        before = {
            name: {path.name for path in directory.glob("*")} if directory.exists() else set()
            for name, directory in historical.items()
        }
        write_canary_artifacts(
            {
                "header": {"result": "BLOCKED_PRECALL", "remote_invocations": 0},
                "precall": {"phase": PHASE},
                "runtime": {"secrets_included": False},
                "request_identity": {"request_sha256": EXPECTED_REQUEST_SHA256},
                "api_compatibility": {"unknown_is_not_pass": True},
                "call_accounting": CallAccounting().to_dict(),
                "report_text": "# PHASE 4B.2.6\n",
            },
            root=tmp_path,
        )
        after = {
            name: {path.name for path in directory.glob("*")} if directory.exists() else set()
            for name, directory in historical.items()
        }
        assert after == before
        written = tmp_path / "audit" / "real" / "book_semantic_gate_4b26"
        assert (written / "book_semantic_gate_4b26_precall.json").is_file()
        assert (written / "book_semantic_gate_4b26_api_compatibility.json").is_file()
        assert (
            tmp_path / "audit" / "PHASE_4B26_ONE_REAL_TERRA_SEMANTIC_GATE_CANARY_REPORT.md"
        ).is_file()
        assert production_book_absent(PROJECT_NAME) is True


class TestSecretLeak:
    def test_readiness_never_exposes_api_key(self):
        engine = OpenAIEngine(api_key=LEAK_KEY)
        result = check_provider_runtime_readiness(
            "openai",
            model=MODEL,
            engine=engine,
            output_mode=OUTPUT_MODE,
        )
        blob = json.dumps(result.to_dict())
        assert LEAK_KEY not in blob
        assert "REDACTED" in json.dumps(
            redact_secrets({"api_key": LEAK_KEY, "note": LEAK_KEY}, [LEAK_KEY])
        )


class TestAnthropicNonRegression:
    def test_anthropic_still_uses_max_tokens(self):
        engine = AnthropicEngine(api_key="offline-anthropic-unused", model="claude-sonnet-5")
        payload = engine.build_payload(
            AIRequest(prompt="offline anthropic regression", model="claude-sonnet-5"),
            "claude-sonnet-5",
        )
        assert "max_tokens" in payload
        assert "max_completion_tokens" not in payload


class TestReadyClass:
    def test_ready_with_server_unverified_fields(self):
        result = check_provider_runtime_readiness(
            "openai",
            model=MODEL,
            engine=OpenAIEngine(api_key=LEAK_KEY),
            output_mode=OUTPUT_MODE,
            request=AIRequest(
                prompt="offline readiness probe",
                model=MODEL,
                max_output_tokens=SEMANTIC_TOKEN_BUDGET,
                response_schema={"type": "object"},
            ),
        )
        assert result.ready is True
        assert result.readiness_class == READY_WITH_SERVER_UNVERIFIED_FIELDS
        assert result.network_calls == 0
        assert_provider_ready_for_authorization(result)


class TestCli:
    def test_wrong_scope_rejected(self):
        from app.book_semantic_gate_4b26.__main__ import main

        assert main(["--authorization-scope", "WRONG", "--dry-run"]) == 2

    def test_help(self):
        from app.book_semantic_gate_4b26.__main__ import main

        assert main(["--help"]) == 0
