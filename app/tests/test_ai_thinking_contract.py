"""3B.7.7A.12 — contrat thinking AIRequest / Anthropic. 0 réseau."""

from __future__ import annotations

import pytest

from app.ai.contracts import AIRequest
from app.ai.errors import AIConfigurationError
from app.ai.providers.anthropic_engine import AnthropicEngine, extract_anthropic_text, _extract_text
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.ai.thinking import (
    SONNET5_THINKING_CAPABILITIES,
    resolve_thinking_capabilities,
    thinking_fingerprint,
)
from app.source_analysis_local_v2.schema import build_semantic_transport_v2_schema
from app.source_analysis_thinking_contract.payload import (
    build_named_payload,
    build_v2_payload_request,
)
from app.tests.ai_fakes import FakeHttpResponse, RecordingPost


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _engine(model: str = "claude-sonnet-5") -> AnthropicEngine:
    return AnthropicEngine(model=model, api_key="cle-de-test")


class TestSonnet5Capabilities:
    def test_sonnet5_flags(self):
        caps = resolve_thinking_capabilities("anthropic", "claude-sonnet-5")
        assert caps.known is True
        assert caps.adaptive_thinking_supported is True
        assert caps.thinking_disabled_supported is True
        assert caps.manual_budget_tokens_supported is False
        assert caps.effort_supported is True
        assert caps.adaptive_thinking_default is True
        assert caps.default_effort == "high"
        assert caps.task_budget_supported is False
        assert caps.max_tokens_shared_output is True
        assert "low" in caps.effort_values
        assert caps.to_dict()["model"] == SONNET5_THINKING_CAPABILITIES.model

    def test_unverified_model_not_generalized(self):
        caps = resolve_thinking_capabilities("anthropic", "claude-opus-5")
        assert caps.known is False
        assert caps.thinking_disabled_supported is False
        assert caps.effort_supported is False


class TestProviderDefaultCompatibility:
    def test_historical_request_omits_thinking_and_effort(self):
        payload = _engine().build_payload(
            AIRequest(
                prompt="x",
                response_schema=build_semantic_transport_v2_schema(),
            ),
            "claude-sonnet-5",
        )
        assert "thinking" not in payload
        assert "effort" not in (payload.get("output_config") or {})
        assert payload["output_config"]["format"]["type"] == "json_schema"


class TestPayloadContracts:
    def test_thinking_disabled_payload(self):
        built = build_named_payload("THINKING_DISABLED")
        assert built["thinking"] == {"type": "disabled"}
        assert built["effort"] is None
        assert built["format_present"] is True
        assert built["temperature_present"] is False

    def test_adaptive_low_payload(self):
        built = build_named_payload("ADAPTIVE_LOW")
        assert built["thinking"] == {"type": "adaptive"}
        assert built["effort"] == "low"
        assert built["format_present"] is True

    def test_adaptive_medium_payload(self):
        built = build_named_payload("ADAPTIVE_MEDIUM")
        assert built["thinking"] == {"type": "adaptive"}
        assert built["effort"] == "medium"
        assert built["format_present"] is True

    def test_adaptive_high_explicit_sends_fields(self):
        built = build_named_payload("ADAPTIVE_HIGH")
        assert built["thinking"] == {"type": "adaptive"}
        assert built["effort"] == "high"
        assert built["format_present"] is True

    def test_provider_default_omits_thinking_effort(self):
        built = build_named_payload("provider_default")
        assert built["thinking"] is None
        assert built["effort"] is None
        assert built["format_present"] is True


class TestOutputConfigMerge:
    def test_format_survives_effort(self):
        request = build_v2_payload_request(
            thinking_mode="adaptive", effort="low"
        )
        payload = _engine().build_payload(request, "claude-sonnet-5")
        assert payload["output_config"]["format"]["type"] == "json_schema"
        assert payload["output_config"]["effort"] == "low"
        assert set(payload["output_config"]) >= {"format", "effort"}


class TestFailClosed:
    def test_budget_tokens_rejected_locally(self):
        request = build_v2_payload_request(thinking_budget_tokens=8000)
        with pytest.raises(AIConfigurationError, match="thinking_budget_tokens"):
            _engine().build_payload(request, "claude-sonnet-5")

    def test_invalid_effort_rejected_locally(self):
        with pytest.raises(ValueError, match="effort"):
            AIRequest(prompt="x", effort="turbo")

    def test_unverified_model_explicit_thinking_rejected(self):
        request = AIRequest(prompt="x", thinking_mode="disabled")
        with pytest.raises(AIConfigurationError, match="disabled"):
            _engine(model="un-modele-de-test").build_payload(
                request, "un-modele-de-test"
            )

    def test_thinking_disabled_plus_effort_not_invented_restriction(self):
        request = build_v2_payload_request(
            thinking_mode="disabled", effort="low"
        )
        payload = _engine().build_payload(request, "claude-sonnet-5")
        assert payload["thinking"]["type"] == "disabled"
        assert payload["output_config"]["effort"] == "low"
        assert "format" in payload["output_config"]


class TestTemperatureCompatibility:
    def test_none_omitted(self):
        payload = _engine().build_payload(AIRequest(prompt="x"), "claude-sonnet-5")
        assert "temperature" not in payload

    def test_sonnet5_drops_non_default_temperature(self):
        payload = _engine().build_payload(
            AIRequest(prompt="x", temperature=0.7), "claude-sonnet-5"
        )
        assert "temperature" not in payload

    def test_other_model_keeps_temperature(self):
        payload = _engine(model="un-modele-de-test").build_payload(
            AIRequest(prompt="x", temperature=0.4), "un-modele-de-test"
        )
        assert payload["temperature"] == 0.4


class TestResponseParsing:
    def test_thinking_block_before_text(self):
        data = {
            "stop_reason": "end_turn",
            "content": [
                {"type": "thinking", "thinking": "hidden"},
                {"type": "text", "text": '{"ok": true}'},
            ],
        }
        assert extract_anthropic_text(data) == '{"ok": true}'
        assert _extract_text(data) == '{"ok": true}'

    def test_text_only_no_thinking_block(self):
        data = {
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "plain"}],
        }
        assert extract_anthropic_text(data) == "plain"
        assert _extract_text(data) == "plain"


class TestUsageAndFinishReason:
    def test_thinking_tokens_and_finish_reason_retained(self, monkeypatch):
        import app.ai.providers._http as http_module

        body = {
            "id": "msg_think",
            "model": "claude-sonnet-5",
            "stop_reason": "max_tokens",
            "content": [{"type": "text", "text": '{"k":1}'}],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 32000,
                "output_tokens_details": {"thinking_tokens": 21911},
            },
        }
        monkeypatch.setattr(
            http_module.requests,
            "post",
            RecordingPost([FakeHttpResponse(body)]),
        )
        response = AnthropicEngine(
            model="claude-sonnet-5",
            api_key="cle-de-test",
            retry_policy=no_delay_policy(),
        ).generate(AIRequest(prompt="x"))
        assert response.thinking_tokens == 21911
        assert response.output_tokens == 32000
        assert response.finish_reason == "max_tokens"
        assert response.raw_usage["output_tokens_details"]["thinking_tokens"] == 21911

    def test_unknown_thinking_is_none_not_zero(self, monkeypatch):
        import app.ai.providers._http as http_module

        monkeypatch.setattr(
            http_module.requests,
            "post",
            RecordingPost(
                [
                    FakeHttpResponse(
                        {
                            "id": "msg_plain",
                            "model": "claude-sonnet-5",
                            "stop_reason": "end_turn",
                            "content": [{"type": "text", "text": "ok"}],
                            "usage": {"input_tokens": 3, "output_tokens": 2},
                        }
                    )
                ]
            ),
        )
        response = AnthropicEngine(
            model="claude-sonnet-5",
            api_key="cle-de-test",
            retry_policy=no_delay_policy(),
        ).generate(AIRequest(prompt="x"))
        assert response.thinking_tokens is None
        assert response.thinking_tokens != 0


class TestFingerprint:
    def test_thinking_fingerprints_differ(self):
        disabled = thinking_fingerprint("disabled", None)
        low = thinking_fingerprint("adaptive", "low")
        medium = thinking_fingerprint("adaptive", "medium")
        default = thinking_fingerprint(None, None)
        high = thinking_fingerprint("adaptive", "high")
        assert len({disabled, low, medium, default, high}) == 5
        assert thinking_fingerprint(None, None) == thinking_fingerprint(
            "provider_default", None
        )


class TestWithPromptPreservesThinking:
    def test_with_prompt_copies_thinking_fields(self):
        original = AIRequest(
            prompt="a",
            thinking_mode="adaptive",
            effort="low",
        )
        copied = original.with_prompt("b")
        assert copied.thinking_mode == "adaptive"
        assert copied.effort == "low"


class TestFakeAIInspectsMetadata:
    def test_fakeai_sees_selected_contract(self):
        engine = FakeAIEngine(
            script=[FakeReply(text="ok", finish_reason="stop")],
            retry_policy=no_delay_policy(),
        )
        engine.generate(
            AIRequest(prompt="x", thinking_mode="disabled", metadata={"thinking_contract": "THINKING_DISABLED"})
        )
        assert engine.last_request is not None
        assert engine.last_request.thinking_mode == "disabled"
        assert engine.last_request.metadata["thinking_contract"] == "THINKING_DISABLED"
