"""
Phase 3B.7.7A.5 — frontière HTTP / AIResponseError.

Aucun réseau réel. Les POST sont mockés. 0 appel provider.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

from app.ai.contracts import AIRequest
from app.ai.cost import CALL_STATUS_FAILED, CostTracker
from app.ai.errors import (
    AIConnectionError,
    AIRequestError,
    AIResponseError,
    AIStructuredOutputError,
    AITimeoutError,
)
from app.ai.pricing import COST_STATUS_UNKNOWN, PricingCatalog
from app.ai.provider_forensics import (
    CLASS_HTTP_ERROR,
    CLASS_HTTP_TRANSPORT_FAILURE,
    CLASS_INVALID_CONTENT_TYPE,
    CLASS_INVALID_RESPONSE_JSON,
    CLASS_INVALID_RESPONSE_TOP_LEVEL,
    CLASS_INVALID_TEXT_BLOCK,
    CLASS_MISSING_CONTENT,
    CLASS_NO_TEXT_BLOCK,
    CLASS_STRUCTURED_JSON_DECODE,
    ENVELOPE_JSON_NAME,
    RAW_BODY_NAME,
    ProviderForensicCollisionError,
    persist_provider_forensics,
    provider_forensic_scope,
    replay_provider_http,
)
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.retry import no_delay_policy
from app.source_analysis.window_analyzer import analyze_window
from app.source_analysis.window_fixtures import make_transcript, window_for
from app.source_analysis.window_writer import result_path, transport_path
from app.tests.ai_fakes import FakeHttpResponse, RecordingPost, anthropic_response
from app.tests.test_ai_cost_tracker import TARIF_FICTIF

SIGNATURE = "a" * 64


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _engine() -> AnthropicEngine:
    return AnthropicEngine(
        model="claude-sonnet-5",
        api_key="cle-de-test",
        retry_policy=no_delay_policy(max_attempts=1),
    )


def _install(monkeypatch, *responses):
    import app.ai.providers._http as http_module

    recorder = RecordingPost(responses)
    monkeypatch.setattr(http_module.requests, "post", recorder)
    return recorder


def _persist_from_error(error, tmp_path: Path) -> dict:
    envelope = getattr(error, "http_envelope", None)
    assert envelope is not None
    return persist_provider_forensics(
        envelope,
        windows_root=tmp_path / "windows",
        window_id="WIN001",
        analysis_signature=SIGNATURE,
        classification=error.classification,
    )


class TestInvalidJsonBody:
    def test_invalid_json_preserved(self, monkeypatch, tmp_path):
        raw = b"{this is not json"
        _install(
            monkeypatch,
            FakeHttpResponse(
                text=raw.decode("utf-8"),
                json_error=True,
                content=raw,
                headers={"request-id": "req_invalid_json"},
            ),
        )
        with provider_forensic_scope(
            windows_root=tmp_path / "windows",
            window_id="WIN001",
            analysis_signature=SIGNATURE,
        ):
            with pytest.raises(AIResponseError) as excinfo:
                _engine().generate(AIRequest(prompt="x"))
        error = excinfo.value
        assert error.classification == CLASS_INVALID_RESPONSE_JSON
        assert error.response_received is True
        assert error.http_status == 200
        assert error.request_id == "req_invalid_json"
        assert error.response is None
        dumped = json.dumps(error.diagnostics())
        assert raw.decode("utf-8") not in dumped
        payload = _persist_from_error(error, tmp_path)
        raw_path = Path(payload["artifact_paths"]["raw_body"])
        assert raw_path.read_bytes() == raw
        assert payload["http_status"] == 200
        assert payload["usage"] is None
        assert "sk-ant-" not in json.dumps(payload)


class TestNonObjectJson:
    def test_json_array_fail_closed(self, monkeypatch, tmp_path):
        _install(monkeypatch, FakeHttpResponse(["not", "an", "object"]))
        with provider_forensic_scope(
            windows_root=tmp_path / "windows",
            window_id="WIN001",
            analysis_signature=SIGNATURE,
        ):
            with pytest.raises(AIResponseError) as excinfo:
                _engine().generate(AIRequest(prompt="x"))
        assert excinfo.value.classification == CLASS_INVALID_RESPONSE_TOP_LEVEL
        payload = _persist_from_error(excinfo.value, tmp_path)
        assert payload["json_top_level_type"] == "list"
        assert payload["raw_content"]["persisted"] is True


class TestMissingContent:
    def test_usage_and_stop_reason_retained(self, monkeypatch, tmp_path):
        _install(
            monkeypatch,
            FakeHttpResponse(
                {
                    "id": "msg_missing",
                    "usage": {"input_tokens": 111, "output_tokens": 22},
                    "stop_reason": "end_turn",
                }
            ),
        )
        with provider_forensic_scope(
            windows_root=tmp_path / "windows",
            window_id="WIN001",
            analysis_signature=SIGNATURE,
        ):
            with pytest.raises(AIResponseError) as excinfo:
                _engine().generate(AIRequest(prompt="x"))
        error = excinfo.value
        assert error.classification == CLASS_MISSING_CONTENT
        assert error.input_tokens == 111
        assert error.output_tokens == 22
        assert error.finish_reason == "end_turn"
        assert error.request_id == "msg_missing"
        assert error.response is None
        payload = _persist_from_error(error, tmp_path)
        assert payload["input_tokens"] == 111
        assert payload["finish_reason"] == "end_turn"
        assert payload["raw_content"]["persisted"] is True


class TestContentWrongType:
    def test_content_object_fail_closed(self, monkeypatch, tmp_path):
        _install(
            monkeypatch,
            FakeHttpResponse(
                {
                    "content": {"type": "text", "text": "nope"},
                    "usage": {"input_tokens": 3, "output_tokens": 1},
                    "stop_reason": "end_turn",
                }
            ),
        )
        with pytest.raises(AIResponseError) as excinfo:
            _engine().generate(AIRequest(prompt="x"))
        assert excinfo.value.classification == CLASS_INVALID_CONTENT_TYPE
        _persist_from_error(excinfo.value, tmp_path)


class TestNoTextBlock:
    def test_no_text_raw_retained(self, monkeypatch, tmp_path):
        _install(
            monkeypatch,
            FakeHttpResponse(
                {"content": [{"type": "tool_use"}], "stop_reason": "tool_use"}
            ),
        )
        with pytest.raises(AIResponseError) as excinfo:
            _engine().generate(AIRequest(prompt="x"))
        assert excinfo.value.classification == CLASS_NO_TEXT_BLOCK
        payload = _persist_from_error(excinfo.value, tmp_path)
        assert payload["raw_content"]["persisted"] is True
        assert payload["content_metadata"]["text_block_count"] == 0


class TestMalformedTextBlock:
    def test_missing_text_field(self, monkeypatch, tmp_path):
        _install(
            monkeypatch,
            FakeHttpResponse({"content": [{"type": "text"}], "stop_reason": "end_turn"}),
        )
        with pytest.raises(AIResponseError) as excinfo:
            _engine().generate(AIRequest(prompt="x"))
        assert excinfo.value.classification == CLASS_INVALID_TEXT_BLOCK
        _persist_from_error(excinfo.value, tmp_path)

    def test_wrong_text_type(self, monkeypatch, tmp_path):
        _install(
            monkeypatch,
            FakeHttpResponse(
                {"content": [{"type": "text", "text": 123}], "stop_reason": "end_turn"}
            ),
        )
        with pytest.raises(AIResponseError) as excinfo:
            _engine().generate(AIRequest(prompt="x"))
        assert excinfo.value.classification == CLASS_INVALID_TEXT_BLOCK


class TestValidTextInvalidStructured:
    def test_structured_forensics_and_http_envelope(self, monkeypatch, tmp_path):
        _install(
            monkeypatch,
            anthropic_response(
                text="{not-json",
                input_tokens=50,
                output_tokens=9,
                stop_reason="end_turn",
                response_id="msg_struct",
            ),
        )
        with provider_forensic_scope(
            windows_root=tmp_path / "windows",
            window_id="WIN001",
            analysis_signature=SIGNATURE,
        ):
            with pytest.raises(AIStructuredOutputError) as excinfo:
                _engine().generate(
                    AIRequest(prompt="x", response_schema={"type": "object"})
                )
        error = excinfo.value
        assert error.classification == CLASS_STRUCTURED_JSON_DECODE
        assert error.response is not None
        assert error.response.text == "{not-json"
        assert error.input_tokens == 50
        assert error.finish_reason == "end_turn"
        envelope = error.http_envelope
        assert envelope is not None
        payload = persist_provider_forensics(
            envelope,
            windows_root=tmp_path / "windows",
            window_id="WIN001",
            analysis_signature=SIGNATURE,
        )
        assert payload["raw_content"]["persisted"] is True
        assert payload["input_tokens"] == 50


class TestValidFullResponse:
    def test_success_unchanged(self, monkeypatch, tmp_path):
        recorder = _install(monkeypatch, anthropic_response(text='{"ok": true}'))
        response = _engine().generate(
            AIRequest(prompt="x", response_schema={"type": "object"})
        )
        assert response.parsed == {"ok": True}
        assert response.provider == "anthropic"
        assert recorder.call_count == 1
        forensic = tmp_path / "analysis" / "provider_forensics"
        assert not forensic.exists()


class TestNon2xx:
    def test_http_error_not_semantic(self, monkeypatch, tmp_path):
        body = {"error": {"type": "invalid_request_error", "message": "bad"}}
        _install(
            monkeypatch,
            FakeHttpResponse(body, status_code=400, headers={"request-id": "req_400"}),
        )
        with provider_forensic_scope(
            windows_root=tmp_path / "windows",
            window_id="WIN001",
            analysis_signature=SIGNATURE,
        ):
            with pytest.raises(AIRequestError) as excinfo:
                _engine().generate(AIRequest(prompt="x"))
        error = excinfo.value
        assert error.classification == CLASS_HTTP_ERROR
        assert error.http_status == 400
        assert error.request_id == "req_400"
        assert "invalid_request_error" not in str(error)
        payload = _persist_from_error(error, tmp_path)
        assert payload["classification"] == CLASS_HTTP_ERROR
        assert json.loads(Path(payload["artifact_paths"]["raw_body"]).read_text(encoding="utf-8")) == body


class TestTimeoutAndConnection:
    def test_timeout_response_not_received(self, monkeypatch):
        _install(monkeypatch, requests.exceptions.ReadTimeout("read timed out"))
        with pytest.raises(AITimeoutError) as excinfo:
            _engine().generate(AIRequest(prompt="x"))
        error = excinfo.value
        assert error.response_received is False
        assert error.classification == CLASS_HTTP_TRANSPORT_FAILURE
        assert error.http_envelope is None
        assert error.raw_sha256 is None

    def test_connection_response_not_received(self, monkeypatch):
        _install(monkeypatch, requests.exceptions.ConnectionError("refused"))
        with pytest.raises(AIConnectionError) as excinfo:
            _engine().generate(AIRequest(prompt="x"))
        assert excinfo.value.response_received is False
        assert excinfo.value.classification == CLASS_HTTP_TRANSPORT_FAILURE


class TestRequestIdAndSecrets:
    def test_request_id_whitelisted(self, monkeypatch, tmp_path):
        _install(
            monkeypatch,
            FakeHttpResponse(
                {"id": "msg_body"},
                headers={"request-id": "req_header_1", "content-type": "application/json"},
            ),
        )
        with pytest.raises(AIResponseError) as excinfo:
            _engine().generate(AIRequest(prompt="x"))
        assert excinfo.value.request_id == "req_header_1"
        payload = _persist_from_error(excinfo.value, tmp_path)
        assert payload["request_id"] == "req_header_1"
        assert payload["headers_subset"]["request-id"] == "req_header_1"

    def test_secret_headers_excluded(self, monkeypatch, tmp_path):
        _install(
            monkeypatch,
            FakeHttpResponse(
                {"id": "msg_secret"},
                headers={
                    "request-id": "req_safe",
                    "Authorization": "Bearer test-secret-token",
                    "x-api-key": "test-secret-key",
                    "Cookie": "session=abc",
                    "Set-Cookie": "session=abc",
                },
            ),
        )
        with pytest.raises(AIResponseError) as excinfo:
            _engine().generate(AIRequest(prompt="x"))
        payload = _persist_from_error(excinfo.value, tmp_path)
        dumped = json.dumps(payload)
        assert "test-secret-token" not in dumped
        assert "test-secret-key" not in dumped
        assert "Authorization" not in dumped
        assert "authorization" not in dumped
        assert "Cookie" not in dumped
        assert "session=abc" not in dumped
        assert payload["secrets_included"] is False
        assert payload["request_id"] == "req_safe"


class TestUsageAndCost:
    def test_usage_before_airesponse(self, monkeypatch):
        _install(
            monkeypatch,
            FakeHttpResponse(
                {
                    "usage": {"input_tokens": 77, "output_tokens": 8},
                    "stop_reason": "max_tokens",
                    "content": None,
                }
            ),
        )
        with pytest.raises(AIResponseError) as excinfo:
            _engine().generate(AIRequest(prompt="x"))
        assert excinfo.value.input_tokens == 77
        assert excinfo.value.output_tokens == 8
        assert excinfo.value.response is None

    def test_cost_from_malformed_envelope(self, monkeypatch):
        _install(
            monkeypatch,
            FakeHttpResponse(
                {
                    "usage": {"input_tokens": 1000, "output_tokens": 200},
                    "stop_reason": "end_turn",
                }
            ),
        )
        with pytest.raises(AIResponseError) as excinfo:
            _engine().generate(AIRequest(prompt="x"))
        tracker = CostTracker(PricingCatalog([TARIF_FICTIF]))
        record = tracker.record_failure(
            provider="fake",
            model="fake-editor",
            error=excinfo.value,
        )
        assert record.status == CALL_STATUS_FAILED
        assert record.input_tokens == 1000
        assert record.output_tokens == 200
        assert record.cost.total_cost is not None

    def test_cost_unknown_without_usage(self, monkeypatch):
        _install(monkeypatch, FakeHttpResponse(text="{broken", json_error=True))
        with pytest.raises(AIResponseError) as excinfo:
            _engine().generate(AIRequest(prompt="x"))
        tracker = CostTracker(PricingCatalog([TARIF_FICTIF]))
        record = tracker.record_failure(
            provider="fake",
            model="fake-editor",
            error=excinfo.value,
        )
        assert record.cost.total_cost is None
        assert record.cost.status == COST_STATUS_UNKNOWN
        assert record.input_tokens is None


class TestCollisionAndAtomicity:
    def test_collision_does_not_overwrite(self, monkeypatch, tmp_path):
        _install(monkeypatch, FakeHttpResponse(text="{aaa", json_error=True, content=b"{aaa"))
        with pytest.raises(AIResponseError) as first:
            _engine().generate(AIRequest(prompt="x"))
        first_payload = _persist_from_error(first.value, tmp_path)
        first_sha = first_payload["raw_content"]["sha256"]
        raw_path = Path(first_payload["artifact_paths"]["raw_body"])
        original = raw_path.read_bytes()

        _install(monkeypatch, FakeHttpResponse(text="{bbb", json_error=True, content=b"{bbb"))
        with pytest.raises(AIResponseError) as second:
            _engine().generate(AIRequest(prompt="x"))
        with pytest.raises(ProviderForensicCollisionError):
            persist_provider_forensics(
                second.value.http_envelope,
                windows_root=tmp_path / "windows",
                window_id="WIN001",
                analysis_signature=SIGNATURE,
            )
        assert raw_path.read_bytes() == original
        assert first_sha != second.value.raw_sha256

    def test_atomicity_leaves_no_valid_partial(self, tmp_path, monkeypatch):
        target = tmp_path / "provider_http_envelope.json"

        def _fail(path, payload):
            partial = Path(path).with_name(Path(path).name + ".partial")
            partial.write_bytes(b"{truncated")
            raise OSError("simulated interrupt")

        monkeypatch.setattr(
            "app.ai.provider_forensics.write_bytes_atomic",
            _fail,
        )
        from app.ai.provider_forensics import ProviderHttpEnvelope

        envelope = ProviderHttpEnvelope(
            response_received=True,
            raw_body=b"{}",
            raw_sha256="a" * 64,
            raw_size=2,
        )
        with pytest.raises(OSError):
            persist_provider_forensics(
                envelope,
                windows_root=tmp_path / "windows",
                window_id="WIN001",
                analysis_signature=SIGNATURE,
            )
        assert not target.exists()
        directory = tmp_path / "provider_forensics" / "WIN001" / SIGNATURE
        if directory.exists():
            finals = [p for p in directory.iterdir() if not p.name.endswith(".partial")]
            for path in finals:
                if path.suffix == ".json":
                    with pytest.raises((json.JSONDecodeError, ValueError)):
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        assert payload.get("schema_version") != "1.0" or False


class TestReplay:
    def test_replay_invalid_json(self):
        result = replay_provider_http(b"{broken")
        assert result.classification == CLASS_INVALID_RESPONSE_JSON
        assert result.airesponse_created is False
        assert result.transport_written is False

    def test_replay_missing_content(self):
        body = json.dumps(
            {"usage": {"input_tokens": 1, "output_tokens": 2}, "stop_reason": "end_turn"}
        ).encode("utf-8")
        result = replay_provider_http(body)
        assert result.classification == CLASS_MISSING_CONTENT
        assert result.usage["input_tokens"] == 1
        assert result.finish_reason == "end_turn"

    def test_replay_no_text(self):
        body = json.dumps({"content": [{"type": "tool_use"}]}).encode("utf-8")
        result = replay_provider_http(body)
        assert result.classification == CLASS_NO_TEXT_BLOCK

    def test_replay_invalid_structured(self):
        body = json.dumps(
            {
                "content": [{"type": "text", "text": "{broken"}],
                "usage": {"input_tokens": 4, "output_tokens": 1},
                "stop_reason": "end_turn",
            }
        ).encode("utf-8")
        result = replay_provider_http(body, response_schema={"type": "object"})
        assert result.error_type == "AIStructuredOutputError"
        assert result.airesponse_created is True
        assert result.structured_parse_passed is False
        assert result.transport_written is False
        assert result.result_written is False

    def test_replay_valid_structured(self):
        body = json.dumps(
            {
                "content": [{"type": "text", "text": '{"ok": true}'}],
                "usage": {"input_tokens": 4, "output_tokens": 1},
                "stop_reason": "end_turn",
                "id": "msg_ok",
            }
        ).encode("utf-8")
        result = replay_provider_http(body, response_schema={"type": "object"})
        assert result.structured_parse_passed is True
        assert result.airesponse_created is True
        assert result.transport_written is False
        assert result.result_written is False


class TestWindowAnalyzerPersistence:
    def test_airesponseerror_persists_forensics(self, monkeypatch, tmp_path):
        _install(monkeypatch, FakeHttpResponse(text="{broken", json_error=True, content=b"{broken"))
        transcript = make_transcript(("one word here",))
        window = window_for(transcript)
        root = tmp_path / "windows"
        with pytest.raises(AIResponseError):
            analyze_window(window, transcript, _engine(), windows_root=root)
        assert not transport_path("fixture", window.window_id, root=root).exists()
        assert not result_path("fixture", window.window_id, root=root).exists()
        forensic_root = tmp_path / "provider_forensics" / window.window_id
        envelopes = list(forensic_root.glob(f"*/{ENVELOPE_JSON_NAME}"))
        assert len(envelopes) == 1
        payload = json.loads(envelopes[0].read_text(encoding="utf-8"))
        assert payload["classification"] == CLASS_INVALID_RESPONSE_JSON
        assert (envelopes[0].parent / RAW_BODY_NAME).read_bytes() == b"{broken"


class TestCallAccounting:
    def test_post_counted_without_airesponse(self, monkeypatch):
        recorder = _install(monkeypatch, FakeHttpResponse(text="{x", json_error=True, content=b"{x"))
        with pytest.raises(AIResponseError):
            _engine().generate(AIRequest(prompt="x"))
        assert recorder.call_count == 1
