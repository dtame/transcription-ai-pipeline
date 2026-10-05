"""Phase 4B.2.4.1 — OpenAI runtime preflight. Network forbidden. 0 provider calls."""

from __future__ import annotations

import json

import pytest

from app.ai.contracts import AIRequest
from app.ai.provider_preflight import (
    REASON_PROVIDER_CREDENTIAL_NOT_READY,
    REASON_PROVIDER_RUNTIME_NOT_READY,
    assert_provider_ready_for_authorization,
    check_provider_runtime_readiness,
    future_call_accounting_contract,
    redact_secrets,
    wrap_remote_openai_methods,
)
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.openai_engine import OpenAIEngine
from app.ai.registry import get_ai_engine, get_engine_for_stage
from app.book_semantic_gate_4b23.fakeai import fixture_supported, run_fakeai_catalog
from app.book_semantic_gate_4b23.guard import assert_offline_package
from app.book_semantic_gate_4b241.constants import (
    AUTHORIZED_TERRA_CALLS,
    EXPECTED_REQUEST_SHA256_FROZEN,
    HISTORICAL_4B24_STATUS,
    MODEL,
    OPENAI_SDK_CONSTRAINT,
    OUTPUT_MODE,
    PROVIDER,
    TERRA_EXECUTION_AUTHORIZED,
)
from app.book_semantic_gate_4b241.guard import assert_offline_only
from app.book_semantic_gate_4b241.lock import lock_forensics
from app.book_semantic_gate_4b24.constants import EXPECTED_BENCHMARK_FILE_SHA256
from app.book_semantic_gate_4b24.identity import benchmark_identity
from app.book_semantic_gate_4b24.precall import build_precall


LEAK_KEY = "sk-SECRET-4B241-LEAK-TEST-VALUE-DO-NOT-PERSIST"


@pytest.fixture(autouse=True)
def _no_network(no_ai_network, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("PROVIDER NETWORK FORBIDDEN")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.Client.send", forbidden)
    return None


class TestPhaseGuards:
    def test_offline_and_historical_4b24_remains_fail(self):
        assert_offline_only()
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert HISTORICAL_4B24_STATUS == "FAIL"
        assert EXPECTED_REQUEST_SHA256_FROZEN == (
            "09d6472e544bc60231c77908e6608ff7ee7b6fd4746317f206301082e21eab53"
        )
        assert OPENAI_SDK_CONSTRAINT == "openai>=1.0.0,<3"

    def test_execute_real_rejected_by_cli(self):
        from app.book_semantic_gate_4b241.__main__ import main

        assert main(["--execute-real"]) == 2


class TestMissingSdk:
    def test_missing_sdk_is_runtime_not_ready(self, monkeypatch):
        def missing(name: str):
            if name == "openai":
                raise ImportError("simulated missing openai SDK")
            raise AssertionError(f"unexpected import {name}")

        monkeypatch.setattr(
            "app.ai.provider_preflight.import_provider_sdk", missing
        )
        engine = OpenAIEngine(api_key=LEAK_KEY)
        result = check_provider_runtime_readiness(
            "openai",
            model=MODEL,
            engine=engine,
            output_mode=OUTPUT_MODE,
        )
        assert result.ready is False
        assert result.primary_reason == REASON_PROVIDER_RUNTIME_NOT_READY
        assert result.remote_invocations == 0
        assert result.network_calls == 0
        with pytest.raises(Exception, match=REASON_PROVIDER_RUNTIME_NOT_READY):
            assert_provider_ready_for_authorization(result)


class TestMissingKey:
    def test_missing_key_is_credential_not_ready(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        import app.config as config

        monkeypatch.setattr(config, "OPENAI_API_KEY", "")
        engine = OpenAIEngine()
        result = check_provider_runtime_readiness(
            "openai",
            model=MODEL,
            engine=engine,
            output_mode=OUTPUT_MODE,
        )
        assert result.ready is False
        assert result.primary_reason == REASON_PROVIDER_CREDENTIAL_NOT_READY
        assert result.credential_available == "NO"
        assert result.network_calls == 0
        assert result.remote_invocations == 0


class TestClientConstructionFailure:
    def test_local_client_init_failure_is_runtime_not_ready(self, monkeypatch):
        class Boom:
            def __init__(self, **_kwargs):
                raise RuntimeError("local client initialization failed")

        import openai

        monkeypatch.setattr(openai, "OpenAI", Boom)
        engine = OpenAIEngine(api_key=LEAK_KEY)
        result = check_provider_runtime_readiness(
            "openai",
            model=MODEL,
            engine=engine,
            output_mode=OUTPUT_MODE,
        )
        assert result.ready is False
        assert result.primary_reason == REASON_PROVIDER_RUNTIME_NOT_READY
        assert result.client_construction == "FAIL"
        assert result.network_calls == 0
        assert result.remote_invocations == 0


class TestReadyProvider:
    def test_ready_with_sdk_and_credential(self):
        engine = OpenAIEngine(api_key=LEAK_KEY)
        result = check_provider_runtime_readiness(
            "openai",
            model=MODEL,
            engine=engine,
            output_mode=OUTPUT_MODE,
            request=AIRequest(
                prompt="offline readiness probe",
                model=MODEL,
                response_schema={"type": "object"},
            ),
        )
        assert result.ready is True
        assert result.sdk_import == "PASS"
        assert result.credential_available == "YES"
        assert result.client_construction == "PASS"
        assert result.provider_initialization == "PASS"
        assert result.model_resolution == "PASS"
        assert result.output_mode_supported == "PASS"
        assert result.network_calls == 0
        assert result.remote_invocations == 0
        assert_provider_ready_for_authorization(result)


class TestSecretLeakage:
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


class TestNetworkForbidden:
    def test_remote_create_is_blocked(self):
        engine = OpenAIEngine(api_key=LEAK_KEY)
        client = engine.client()
        wrap_remote_openai_methods(client)
        with pytest.raises(AssertionError, match="PROVIDER NETWORK FORBIDDEN"):
            client.chat.completions.create(model=MODEL, messages=[])

    def test_readiness_does_not_call_httpx(self, monkeypatch):
        hits = []

        def boom(*_args, **_kwargs):
            hits.append("httpx")
            raise AssertionError("PROVIDER NETWORK FORBIDDEN")

        monkeypatch.setattr("httpx.Client.request", boom)
        monkeypatch.setattr("httpx.Client.send", boom)
        engine = OpenAIEngine(api_key=LEAK_KEY)
        result = check_provider_runtime_readiness(
            "openai", model=MODEL, engine=engine, output_mode=OUTPUT_MODE
        )
        assert hits == []
        assert result.network_calls == 0


class TestInstalledOpenAISDK:
    def test_import_version_and_client_construction(self):
        import openai
        from openai import OpenAI

        assert openai.__version__
        client = OpenAI(api_key=LEAK_KEY)
        assert client is not None
        assert type(client).__name__ == "OpenAI"


class TestProductionInitialization:
    def test_registry_and_stage_path(self):
        engine = get_ai_engine("openai")
        assert isinstance(engine, OpenAIEngine)
        staged, settings = get_engine_for_stage("book_validation")
        assert isinstance(staged, OpenAIEngine)
        assert settings.provider == "openai"
        assert settings.model == MODEL


class TestAnthropicRegression:
    def test_anthropic_readiness_does_not_require_anthropic_sdk(self):
        engine = AnthropicEngine(api_key="offline-anthropic-unused", model="claude-sonnet-5")
        result = check_provider_runtime_readiness(
            "anthropic",
            model="claude-sonnet-5",
            engine=engine,
            output_mode=None,
        )
        assert result.network_calls == 0
        assert result.remote_invocations == 0
        assert result.sdk_import == "PASS"
        assert result.details.get("sdk", {}).get("module") == "requests"
        assert result.details.get("sdk", {}).get("uses_official_sdk") is False
        payload = engine.build_payload(
            AIRequest(prompt="offline anthropic regression", model="claude-sonnet-5"),
            "claude-sonnet-5",
        )
        assert payload["model"] == "claude-sonnet-5"
        assert "messages" in payload


class TestFrozenRequestAndBenchmark:
    def test_frozen_terra_request_and_benchmark(self):
        from pathlib import Path

        historical = Path(
            "audit/real/book_semantic_gate_4b24/"
            "book_semantic_gate_4b24_request_identity.json"
        )
        if historical.is_file():
            recorded = json.loads(historical.read_text(encoding="utf-8"))
            assert recorded["request_sha256"] == EXPECTED_REQUEST_SHA256_FROZEN
        identity = build_precall()
        assert identity["request"]["deterministic"] is True
        assert identity["request"]["sha256"] == identity["request"]["sha256_repeat"]
        assert identity["request"]["response_format"] == {"type": "json_object"}
        meta = benchmark_identity()
        assert meta["identity_match"] is True
        assert meta["sha256"] == EXPECTED_BENCHMARK_FILE_SHA256


class TestSemanticGateRegression:
    def test_4b23_offline_fakeai_still_passes(self):
        assert_offline_package()
        catalog = run_fakeai_catalog()
        assert catalog
        fixture = fixture_supported()
        assert fixture["parsed"]


class TestLockSemantics:
    def test_future_accounting_does_not_rewrite_history(self):
        contract = future_call_accounting_contract()
        assert contract["do_not_redefine_historical_4b24_metrics"] is True
        historical = contract["historical_4b24_attempt_2"]
        assert historical["recorded_actual_terra_calls"] == 1
        assert historical["remote_invocations"] == 0
        assert historical["http_requests"] == 0
        lock = lock_forensics()
        assert lock["historical_result"] == "FAIL"
        assert lock["remote_invocations"] == 0
        assert "late import" in lock["why_attempt_2_consumed_slot_before_http"]
        assert "HTTP to OpenAI remained 0" in lock["why_attempt_2_consumed_slot_before_http"]

    def test_missing_runtime_does_not_consume_authorization(self, monkeypatch):
        monkeypatch.setattr(
            "app.ai.provider_preflight.import_provider_sdk",
            lambda name: (_ for _ in ()).throw(ImportError("missing")),
        )
        consumed = []
        readiness = check_provider_runtime_readiness(
            "openai",
            model=MODEL,
            engine=OpenAIEngine(api_key=LEAK_KEY),
        )
        with pytest.raises(Exception):
            assert_provider_ready_for_authorization(readiness)
            consumed.append("lock")
        assert consumed == []
        assert readiness.primary_reason == REASON_PROVIDER_RUNTIME_NOT_READY
