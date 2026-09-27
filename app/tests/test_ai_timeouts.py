"""
Timeouts IA connect/read — Phase 3B.5.1.

Aucun réseau. Les valeurs 30 / 9999 sont TEST-ONLY, pas une
recommandation de production.
"""

from __future__ import annotations

import math

import pytest
import requests

import app.config as config

from app.ai.contracts import AIRequest
from app.ai.errors import AIConfigurationError, AITimeoutError
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.lmstudio import LMStudioEngine
from app.ai.providers.ollama import OllamaEngine
from app.ai.providers.openai_engine import OpenAIEngine
from app.ai.retry import no_delay_policy
from app.ai.settings import resolve_stage_settings
from app.ai.timeouts import (
    AITimeoutConfig,
    SOURCE_DEFAULT,
    SOURCE_ENGINE,
    SOURCE_ENV,
    SOURCE_REQUEST,
    SOURCE_STAGE,
    SOURCE_STAGE_ENV,
    diagnose_stage_timeout,
    parse_timeout_seconds,
    resolve_ai_timeouts,
    validate_timeout_seconds,
)
from app.tests.ai_fakes import (
    FakeCompletion,
    FakeOpenAIClient,
    RecordingPost,
    anthropic_response,
    ollama_response,
    openai_style_response,
)


@pytest.fixture(autouse=True)
def _reseau_interdit(no_ai_network):
    """Tous les tests de ce module partent d'un réseau fermé."""


def _policy():
    return no_delay_policy(max_attempts=1)


class TestAITimeoutConfig:
    def test_tuple_requests(self):
        cfg = AITimeoutConfig(connect_seconds=30, read_seconds=300)
        assert cfg.as_requests_timeout() == (30.0, 300.0)
        assert cfg.connect_source == SOURCE_DEFAULT
        assert cfg.read_source == SOURCE_DEFAULT

    @pytest.mark.parametrize(
        "value",
        [None, 0, -1, math.nan, math.inf, -math.inf, True, False, "30", object()],
    )
    def test_invalid_rejected(self, value):
        with pytest.raises(AIConfigurationError):
            validate_timeout_seconds(value, name="timeout")

    def test_int_and_float_accepted(self):
        assert validate_timeout_seconds(30, name="t") == 30.0
        assert validate_timeout_seconds(12.5, name="t") == 12.5

    def test_parse_numeric_string(self):
        assert parse_timeout_seconds("30", name="env") == 30.0

    def test_parse_empty_string_fails(self):
        with pytest.raises(AIConfigurationError, match="vide"):
            parse_timeout_seconds("   ", name="env")


class TestResolutionPrecedence:
    def test_defaults_without_override(self):
        resolved = resolve_ai_timeouts()
        assert resolved.connect_seconds == config.AI_DEFAULT_CONNECT_TIMEOUT_SECONDS
        assert resolved.read_seconds == config.AI_DEFAULT_TIMEOUT_SECONDS
        assert resolved.connect_source == SOURCE_DEFAULT
        assert resolved.read_source == SOURCE_DEFAULT

    def test_request_overrides_read_only(self):
        resolved = resolve_ai_timeouts(request_timeout_seconds=12)
        assert resolved.read_seconds == 12.0
        assert resolved.read_source == SOURCE_REQUEST
        assert resolved.connect_seconds == config.AI_DEFAULT_CONNECT_TIMEOUT_SECONDS
        assert resolved.connect_source == SOURCE_DEFAULT

    def test_engine_overrides_read_only(self):
        resolved = resolve_ai_timeouts(engine_read_timeout_seconds=3600)
        assert resolved.read_seconds == 3600.0
        assert resolved.read_source == SOURCE_ENGINE
        assert resolved.connect_seconds == config.AI_DEFAULT_CONNECT_TIMEOUT_SECONDS

    def test_stage_env_overrides_stage_and_default(self, monkeypatch):
        monkeypatch.setenv("AI_SOURCE_ANALYSIS_READ_TIMEOUT_SECONDS", "9999")
        monkeypatch.setenv("AI_SOURCE_ANALYSIS_CONNECT_TIMEOUT_SECONDS", "30")
        resolved = resolve_ai_timeouts(
            stage="source_analysis",
            stage_read_timeout_seconds=100,
            stage_connect_timeout_seconds=10,
        )
        assert resolved.connect_seconds == 30.0
        assert resolved.read_seconds == 9999.0
        assert resolved.connect_source == SOURCE_STAGE_ENV
        assert resolved.read_source == SOURCE_STAGE_ENV

    def test_stage_settings_override_default(self):
        resolved = resolve_ai_timeouts(
            stage="source_analysis",
            stage_read_timeout_seconds=900,
            stage_connect_timeout_seconds=15,
        )
        assert resolved.connect_seconds == 15.0
        assert resolved.read_seconds == 900.0
        assert resolved.connect_source == SOURCE_STAGE
        assert resolved.read_source == SOURCE_STAGE

    def test_global_env_read(self, monkeypatch):
        monkeypatch.setenv("AI_DEFAULT_READ_TIMEOUT_SECONDS", "450")
        resolved = resolve_ai_timeouts()
        assert resolved.read_seconds == 450.0
        assert resolved.read_source == SOURCE_ENV

    def test_invalid_env_fails_fast(self, monkeypatch):
        monkeypatch.setenv("AI_SOURCE_ANALYSIS_READ_TIMEOUT_SECONDS", "not-a-number")
        with pytest.raises(AIConfigurationError):
            resolve_ai_timeouts(stage="source_analysis")

    def test_request_wins_over_stage_env(self, monkeypatch):
        monkeypatch.setenv("AI_SOURCE_ANALYSIS_READ_TIMEOUT_SECONDS", "9999")
        resolved = resolve_ai_timeouts(
            stage="source_analysis",
            request_timeout_seconds=12,
        )
        assert resolved.read_seconds == 12.0
        assert resolved.read_source == SOURCE_REQUEST


class TestStageIsolation:
    def test_source_analysis_override_does_not_leak(self, monkeypatch):
        monkeypatch.setenv("AI_SOURCE_ANALYSIS_READ_TIMEOUT_SECONDS", "9999")
        monkeypatch.setenv("AI_SOURCE_ANALYSIS_CONNECT_TIMEOUT_SECONDS", "30")
        source = diagnose_stage_timeout("source_analysis")
        planning = diagnose_stage_timeout("editorial_planning")
        generation = diagnose_stage_timeout("book_generation")
        validation = diagnose_stage_timeout("book_validation")
        assert source["read_seconds"] == 9999.0
        assert source["connect_seconds"] == 30.0
        for other in (planning, generation, validation):
            assert other["read_seconds"] == config.AI_DEFAULT_TIMEOUT_SECONDS
            assert other["connect_seconds"] == config.AI_DEFAULT_CONNECT_TIMEOUT_SECONDS
            assert other["read_source"] == SOURCE_DEFAULT


class TestHttpTuple:
    def test_anthropic_sends_connect_read_tuple(self, monkeypatch):
        import app.ai.providers._http as http_module

        recorder = RecordingPost([anthropic_response()])
        monkeypatch.setattr(http_module.requests, "post", recorder)
        AnthropicEngine(
            model="claude-sonnet-5",
            api_key="cle-de-test",
            retry_policy=_policy(),
            connect_timeout_seconds=30,
            timeout_seconds=9999,
        ).generate(AIRequest(prompt="x", metadata={"stage": "source_analysis"}))
        assert recorder.calls[0]["timeout"] == (30.0, 9999.0)

    def test_long_read_does_not_lengthen_connect(self, monkeypatch):
        import app.ai.providers._http as http_module

        recorder = RecordingPost([anthropic_response()])
        monkeypatch.setattr(http_module.requests, "post", recorder)
        AnthropicEngine(
            model="claude-sonnet-5",
            api_key="cle-de-test",
            retry_policy=_policy(),
            timeout_seconds=9999,
        ).generate(AIRequest(prompt="x"))
        connect, read = recorder.calls[0]["timeout"]
        assert read == 9999.0
        assert connect == config.AI_DEFAULT_CONNECT_TIMEOUT_SECONDS
        assert connect != read

    def test_read_timeout_classified(self, monkeypatch):
        import app.ai.providers._http as http_module

        recorder = RecordingPost([requests.exceptions.ReadTimeout("no bytes")])
        monkeypatch.setattr(http_module.requests, "post", recorder)
        with pytest.raises(AITimeoutError) as excinfo:
            AnthropicEngine(
                model="claude-sonnet-5",
                api_key="cle-de-test",
                retry_policy=_policy(),
                timeout_seconds=40,
            ).generate(AIRequest(prompt="x"))
        error = excinfo.value
        assert error.timeout_kind == "read"
        assert error.read_timeout_seconds == 40.0
        assert error.connect_timeout_seconds == config.AI_DEFAULT_CONNECT_TIMEOUT_SECONDS
        assert error.response is None
        assert isinstance(error.__cause__, requests.exceptions.ReadTimeout)

    def test_connect_timeout_classified(self, monkeypatch):
        import app.ai.providers._http as http_module

        recorder = RecordingPost([requests.exceptions.ConnectTimeout("connect")])
        monkeypatch.setattr(http_module.requests, "post", recorder)
        with pytest.raises(AITimeoutError) as excinfo:
            AnthropicEngine(
                model="claude-sonnet-5",
                api_key="cle-de-test",
                retry_policy=_policy(),
            ).generate(AIRequest(prompt="x"))
        assert excinfo.value.timeout_kind == "connect"
        assert isinstance(excinfo.value.__cause__, requests.exceptions.ConnectTimeout)

    def test_generic_timeout_unknown(self, monkeypatch):
        import app.ai.providers._http as http_module

        recorder = RecordingPost([requests.exceptions.Timeout("generic")])
        monkeypatch.setattr(http_module.requests, "post", recorder)
        with pytest.raises(AITimeoutError) as excinfo:
            AnthropicEngine(
                model="claude-sonnet-5",
                api_key="cle-de-test",
                retry_policy=_policy(),
            ).generate(AIRequest(prompt="x"))
        assert excinfo.value.timeout_kind == "unknown"

    def test_elapsed_uses_monotonic(self, monkeypatch):
        import app.ai.providers._http as http_module

        engine = AnthropicEngine(
            model="claude-sonnet-5",
            api_key="cle-de-test",
            retry_policy=_policy(),
        )
        ticks = [100.0]

        def fake_monotonic():
            if ticks:
                return ticks.pop(0)
            return 102.5

        monkeypatch.setattr(http_module.time, "monotonic", fake_monotonic)
        recorder = RecordingPost([requests.exceptions.ReadTimeout("slow")])
        monkeypatch.setattr(http_module.requests, "post", recorder)
        with pytest.raises(AITimeoutError) as excinfo:
            engine.generate(AIRequest(prompt="x"))
        assert excinfo.value.elapsed_ms == 2500

    def test_ollama_keeps_provider_read(self, monkeypatch):
        import app.ai.providers._http as http_module

        recorder = RecordingPost([ollama_response()])
        monkeypatch.setattr(http_module.requests, "post", recorder)
        OllamaEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))
        assert recorder.calls[0]["timeout"] == (
            config.AI_DEFAULT_CONNECT_TIMEOUT_SECONDS,
            config.OLLAMA_TIMEOUT_SECONDS,
        )

    def test_lmstudio_keeps_default_read(self, monkeypatch):
        import app.ai.providers._http as http_module

        recorder = RecordingPost([openai_style_response()])
        monkeypatch.setattr(http_module.requests, "post", recorder)
        LMStudioEngine(retry_policy=_policy()).generate(AIRequest(prompt="x"))
        assert recorder.calls[0]["timeout"] == (
            config.AI_DEFAULT_CONNECT_TIMEOUT_SECONDS,
            config.AI_DEFAULT_TIMEOUT_SECONDS,
        )

    def test_openai_sdk_still_receives_scalar(self):
        client = FakeOpenAIClient(FakeCompletion(content="ok"))
        engine = OpenAIEngine(client=client, retry_policy=_policy())
        engine.generate(AIRequest(prompt="x", timeout_seconds=12))
        assert client.calls[0]["timeout"] == 12
        assert not isinstance(client.calls[0]["timeout"], tuple)


class TestStageSettingsTimeoutFields:
    def test_production_stages_have_no_operational_long_read(self):
        for stage in (
            "source_analysis",
            "editorial_planning",
            "book_generation",
            "book_validation",
        ):
            settings = resolve_stage_settings(stage)
            assert settings.connect_timeout_seconds is None
            assert settings.read_timeout_seconds is None
            assert not hasattr(settings, "request_timeout_seconds")
