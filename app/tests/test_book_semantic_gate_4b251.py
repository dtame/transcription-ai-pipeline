"""Phase 4B.2.5.1 — Terra API compatibility. Network forbidden. 0 provider calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.contracts import AIRequest
from app.ai.errors import AIConfigurationError
from app.ai.openai_compat import (
    PRODUCTION_OPENAI_ENDPOINT,
    TOKEN_PARAM_MAX_COMPLETION_TOKENS,
    TOKEN_PARAM_MAX_TOKENS,
    capture_openai_sdk_chat_request,
    conflicting_token_fields,
    openai_endpoint_capability_matrix,
    resolve_chat_completions_token_contract,
)
from app.ai.provider_preflight import (
    READY_WITH_SERVER_UNVERIFIED_FIELDS,
    REASON_PROVIDER_CREDENTIAL_NOT_READY,
    REASON_PROVIDER_REQUEST_INCOMPATIBLE,
    REASON_PROVIDER_RUNTIME_NOT_READY,
    assert_provider_ready_for_authorization,
    check_provider_runtime_readiness,
    redact_secrets,
)
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.openai_engine import OpenAIEngine
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.fakeai import fixture_supported, run_fakeai_catalog
from app.book_semantic_gate_4b23.guard import assert_offline_package
from app.book_semantic_gate_4b24.engine import CountingOpenAIEngine
from app.book_semantic_gate_4b251.constants import (
    AUTHORIZED_TERRA_CALLS,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_REQUEST_SHA256_HISTORICAL,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B25_STATUS,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PROJECT_NAME,
    SEMANTIC_TOKEN_BUDGET,
    TERRA_EXECUTION_AUTHORIZED,
)
from app.book_semantic_gate_4b251.guard import assert_offline_only
from app.book_semantic_gate_4b251.identity import (
    build_corrected_identity,
    load_historical_4b25_request,
)
from app.book_semantic_gate_4b251.paths import historical_4b25_request_path


LEAK_KEY = "sk-SECRET-4B251-LEAK-TEST-VALUE-DO-NOT-PERSIST"


@pytest.fixture(autouse=True)
def _no_network(no_ai_network, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("PROVIDER NETWORK FORBIDDEN")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.Client.send", forbidden)
    return None


class TestPhaseGuards:
    def test_offline_and_historical_4b25_remains_fail(self):
        assert_offline_only()
        assert PHASE == "4B.2.5.1"
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert HISTORICAL_4B25_STATUS == "FAIL"
        assert EXPECTED_REQUEST_SHA256_HISTORICAL == (
            "09d6472e544bc60231c77908e6608ff7ee7b6fd4746317f206301082e21eab53"
        )
        assert EXPECTED_SOURCE_MAP == (
            "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855"
        )
        assert EXPECTED_EDITORIAL_PLAN == (
            "01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440"
        )
        assert EXPECTED_CLEAN_TRANSCRIPT == (
            "1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958"
        )

    def test_execute_real_rejected_by_cli(self):
        from app.book_semantic_gate_4b251.__main__ import main

        assert main(["--execute-real"]) == 2


class TestTerraChatCompletionsMapping:
    def test_terra_uses_max_completion_tokens_and_omits_max_tokens(self):
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
        assert payload["max_completion_tokens"] == SEMANTIC_TOKEN_BUDGET
        assert "max_tokens" not in payload
        assert conflicting_token_fields(payload) == [TOKEN_PARAM_MAX_COMPLETION_TOKENS]
        assert "temperature" not in payload
        assert payload["response_format"] == {"type": "json_object"}

    def test_endpoint_specific_contract(self):
        contract = resolve_chat_completions_token_contract(MODEL)
        assert contract.endpoint == PRODUCTION_OPENAI_ENDPOINT
        assert contract.parameter == TOKEN_PARAM_MAX_COMPLETION_TOKENS
        assert TOKEN_PARAM_MAX_TOKENS in contract.do_not_send
        matrix = openai_endpoint_capability_matrix()
        assert matrix["production_endpoint"] == "chat.completions"
        assert matrix["responses_api_used"] is False

    def test_legacy_openai_model_keeps_max_tokens(self):
        engine = OpenAIEngine(api_key="offline", client=object())
        payload = engine.build_payload(
            AIRequest(
                prompt="legacy",
                model="gpt-4o-mini",
                temperature=0.4,
                max_output_tokens=900,
            ),
            "gpt-4o-mini",
        )
        assert payload["max_tokens"] == 900
        assert "max_completion_tokens" not in payload
        assert payload["temperature"] == 0.4

    def test_no_simultaneous_conflicting_token_fields(self):
        engine = CountingOpenAIEngine(api_key="offline", client=object())
        payload = engine.build_payload(
            AIRequest(
                prompt="audit",
                model=MODEL,
                max_output_tokens=SEMANTIC_TOKEN_BUDGET,
                response_schema={"type": "object"},
            ),
            MODEL,
        )
        assert "max_tokens" not in payload
        assert "max_completion_tokens" in payload
        assert len(conflicting_token_fields(payload)) == 1


class TestUnsupportedSettings:
    def test_explicit_terra_temperature_rejected_before_remote(self):
        engine = OpenAIEngine(api_key=LEAK_KEY, client=object())
        with pytest.raises(AIConfigurationError, match="temperature"):
            engine.build_payload(
                AIRequest(prompt="x", model=MODEL, temperature=0.2),
                MODEL,
            )

    def test_unsupported_thinking_rejected_before_remote(self):
        engine = OpenAIEngine(api_key=LEAK_KEY, client=object())
        with pytest.raises(AIConfigurationError, match="thinking_mode"):
            engine.build_payload(
                AIRequest(prompt="x", model=MODEL, thinking_mode="adaptive"),
                MODEL,
            )


class TestAnthropicUnaffected:
    def test_anthropic_still_uses_max_tokens(self):
        engine = AnthropicEngine(api_key="offline-anthropic-unused", model="claude-sonnet-5")
        payload = engine.build_payload(
            AIRequest(prompt="offline anthropic regression", model="claude-sonnet-5"),
            "claude-sonnet-5",
        )
        assert payload["model"] == "claude-sonnet-5"
        assert payload["max_tokens"] > 0
        assert "max_completion_tokens" not in payload


class TestPreflight:
    def test_missing_sdk_is_runtime_not_ready(self, monkeypatch):
        def missing(name: str):
            if name == "openai":
                raise ImportError("simulated missing openai SDK")
            raise AssertionError(f"unexpected import {name}")

        monkeypatch.setattr("app.ai.provider_preflight.import_provider_sdk", missing)
        result = check_provider_runtime_readiness(
            "openai",
            model=MODEL,
            engine=OpenAIEngine(api_key=LEAK_KEY),
            output_mode=OUTPUT_MODE,
        )
        assert result.ready is False
        assert result.primary_reason == REASON_PROVIDER_RUNTIME_NOT_READY
        assert result.network_calls == 0
        assert result.remote_invocations == 0

    def test_missing_key_is_credential_not_ready(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        import app.config as config

        monkeypatch.setattr(config, "OPENAI_API_KEY", "")
        result = check_provider_runtime_readiness(
            "openai",
            model=MODEL,
            engine=OpenAIEngine(),
            output_mode=OUTPUT_MODE,
        )
        assert result.ready is False
        assert result.primary_reason == REASON_PROVIDER_CREDENTIAL_NOT_READY
        assert result.network_calls == 0

    def test_incompatible_setting_is_request_incompatible(self):
        result = check_provider_runtime_readiness(
            "openai",
            model=MODEL,
            engine=OpenAIEngine(api_key=LEAK_KEY),
            output_mode=OUTPUT_MODE,
            request=AIRequest(prompt="offline", model=MODEL, temperature=0.7),
        )
        assert result.ready is False
        assert result.primary_reason == REASON_PROVIDER_REQUEST_INCOMPATIBLE
        assert result.remote_invocations == 0
        assert result.network_calls == 0

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
        assert result.endpoint_selected == "PASS"
        assert result.token_parameter == TOKEN_PARAM_MAX_COMPLETION_TOKENS
        assert result.request_serializable == "PASS"
        assert result.network_calls == 0
        assert_provider_ready_for_authorization(result)


class TestSdkSerialization:
    def test_mock_transport_captures_request_without_http(self, monkeypatch):
        hits = []

        def boom(*_args, **_kwargs):
            hits.append("httpx")
            raise AssertionError("PROVIDER NETWORK FORBIDDEN")

        monkeypatch.setattr("httpx.Client.request", boom)
        monkeypatch.setattr("httpx.Client.send", boom)
        engine = OpenAIEngine(api_key=LEAK_KEY, client=object())
        payload = engine.build_payload(
            AIRequest(
                prompt="offline capture",
                system_prompt="auditor",
                model=MODEL,
                max_output_tokens=SEMANTIC_TOKEN_BUDGET,
                response_schema={"type": "object"},
            ),
            MODEL,
        )
        captured = capture_openai_sdk_chat_request(payload, api_key=LEAK_KEY)
        assert captured["network_calls"] == 0
        assert captured["http_requests"] == 0
        assert captured["intercepted"] is True
        assert captured["method"] == "POST"
        assert captured["url_path"] in {"/chat/completions", "/v1/chat/completions"}
        body = captured["body"]
        assert body["max_completion_tokens"] == SEMANTIC_TOKEN_BUDGET
        assert "max_tokens" not in body
        assert "temperature" not in body
        assert "thinking" not in body
        assert body["response_format"] == {"type": "json_object"}
        assert LEAK_KEY not in json.dumps(captured)
        assert hits == []


class TestSecretLeak:
    def test_readiness_never_exposes_api_key(self):
        result = check_provider_runtime_readiness(
            "openai",
            model=MODEL,
            engine=OpenAIEngine(api_key=LEAK_KEY),
            output_mode=OUTPUT_MODE,
        )
        blob = json.dumps(result.to_dict())
        assert LEAK_KEY not in blob
        assert "REDACTED" in json.dumps(
            redact_secrets({"api_key": LEAK_KEY, "note": LEAK_KEY}, [LEAK_KEY])
        )


class TestCorrectedRequest:
    def test_determinism_differs_from_historical_and_preserves_semantics(self):
        historical = load_historical_4b25_request()
        assert historical["exists"] is True
        assert historical["request_sha256"] == EXPECTED_REQUEST_SHA256_HISTORICAL
        identity = build_corrected_identity()
        assert identity["historical_request_preserved"] is True
        assert identity["deterministic"] is True
        assert identity["differs_from_historical"] is True
        assert identity["canonical_request_sha256"] != EXPECTED_REQUEST_SHA256_HISTORICAL
        assert (
            identity["canonical_request_sha256"]
            == identity["canonical_request_sha256_repeat"]
        )
        payload = identity["payload"]
        assert payload["max_completion_tokens"] == SEMANTIC_TOKEN_BUDGET
        assert "max_tokens" not in payload
        assert identity["diff"]["only_api_compatibility_fields_changed"] is True
        assert identity["case_count"] == 10
        assert identity["label_leakage"] == 0
        assert identity["inputs_unchanged"] is True
        before = identity["identities_before"]
        after = identity["identities_after"]
        assert before["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert after["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert before["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert after["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert before["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
        assert after["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
        assert historical_4b25_request_path().is_file()


class TestFakeAIAndPublication:
    def test_semantic_gate_fakeai_still_passes(self):
        assert_offline_package()
        catalog = run_fakeai_catalog()
        assert catalog
        fixture = fixture_supported()
        assert fixture["parsed"]

    def test_no_book_json_and_no_production_cache_write(self, tmp_path):
        from app.book_semantic_gate_4b251.writer import write_phase_artifacts

        write_phase_artifacts(
            {
                "header": {"result": "PASS"},
                "forensics": {"phase": PHASE},
                "report_text": "# PHASE 4B.2.5.1\n",
            },
            root=tmp_path,
        )
        assert production_book_absent(PROJECT_NAME) is True
        written = tmp_path / "audit" / "book_semantic_gate_4b251"
        assert (written / "openai_terra_parameter_forensics.json").is_file()
        assert not (tmp_path / "sortie").exists() or not any(
            Path(tmp_path / "sortie").rglob("book.json")
        )
