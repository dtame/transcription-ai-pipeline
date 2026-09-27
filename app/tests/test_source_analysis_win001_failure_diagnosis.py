"""
Phase 3B.7.7A.1 — WIN001 structured-output failure & token diagnosis.

Aucun réseau réel. Aucun retry WIN001. Aucun transport/result de production.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.contracts import AIRequest
from app.ai.errors import AIStructuredOutputError
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.ai.structured_forensics import (
    FORENSICS_JSON_NAME,
    FORENSICS_RAW_NAME,
    forensics_dir,
    forensics_window_root,
)
from app.source_analysis.ultra_compact_schema import build_ultra_compact_response_schema
from app.source_analysis.window_analyzer import analyze_window, resolve_window_execution
from app.source_analysis.window_cache import inspect_window_cache
from app.source_analysis.window_fixtures import (
    make_transcript,
    minimal_transport,
    window_for,
)
from app.source_analysis.window_writer import result_path, transport_path
from app.source_analysis_win001_failure_diagnosis.constants import (
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_VERSION,
)
from app.source_analysis_win001_failure_diagnosis.integrity import protected_hashes
from app.source_analysis_win001_failure_diagnosis.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
    package_imports_network_clients,
    package_invokes_provider,
)
from app.source_analysis_win001_failure_diagnosis.runner import (
    run_win001_failure_diagnosis,
)
from app.tests.ai_fakes import RecordingPost, anthropic_response

REAL_AUDIT = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation\audit"
)
PROTECTED_BEFORE = protected_hashes(PROJECT_NAME)


def _anthropic(**kwargs) -> AnthropicEngine:
    return AnthropicEngine(
        model="claude-sonnet-5",
        api_key="cle-de-test",
        retry_policy=no_delay_policy(max_attempts=1),
    )


def _install_post(monkeypatch, *responses):
    import app.ai.providers._http as http_module

    recorder = RecordingPost(responses)
    monkeypatch.setattr(http_module.requests, "post", recorder)
    return recorder


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOfflineGuards:
    def test_package_has_no_network_imports(self):
        assert package_imports_network_clients() == []
        assert package_invokes_provider() == []
        assert_offline_package()
        assert_analyzer_not_wired()

    def test_phase_authorizes_zero_calls(self):
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0


class TestStructuredErrorMetadata:
    def test_usage_max_output_and_malformed_json(self, monkeypatch):
        _install_post(
            monkeypatch,
            anthropic_response(
                text='{"theme": "incomplete"',
                input_tokens=106973,
                output_tokens=32000,
                stop_reason="max_tokens",
                response_id="msg_diag_1",
                model="claude-sonnet-5",
            ),
        )
        with pytest.raises(AIStructuredOutputError) as excinfo:
            _anthropic().generate(
                AIRequest(
                    prompt="window",
                    system_prompt="sys",
                    model="claude-sonnet-5",
                    max_output_tokens=32000,
                    response_schema=build_ultra_compact_response_schema(),
                    metadata={"stage": "source_analysis_window"},
                )
            )
        err = excinfo.value
        assert err.parse_failure_kind == "json_decode"
        assert err.input_tokens == 106973
        assert err.output_tokens == 32000
        assert err.finish_reason == "max_tokens"
        assert err.request_id == "msg_diag_1"
        assert err.raw_text_sha256
        assert err.raw_text_chars > 0
        assert err.response is not None
        assert err.response.parsed is None
        diagnostics = err.diagnostics()
        assert diagnostics["parse_failure_kind"] == "json_decode"
        assert "cle-de-test" not in json.dumps(diagnostics)
        assert '{"theme"' not in diagnostics["message"] or len(diagnostics["message"]) < 400

    def test_empty_content_classified(self):
        with pytest.raises(AIStructuredOutputError) as excinfo:
            from app.ai.structured import parse_structured_output

            parse_structured_output("   ", {"type": "object"})
        assert excinfo.value.parse_failure_kind == "empty"

    def test_schema_failure_classified(self):
        with pytest.raises(AIStructuredOutputError) as excinfo:
            from app.ai.structured import parse_structured_output

            parse_structured_output("{}", {"type": "object", "required": ["theme"]})
        assert excinfo.value.parse_failure_kind == "schema"


class TestRawResponsePreservation:
    def test_structured_failure_persists_forensics_not_transport(self, tmp_path):
        transcript = make_transcript(("Faith changes the crossing.",))
        window = window_for(transcript)
        root = tmp_path / "windows"
        engine = FakeAIEngine(
            script=[
                FakeReply(
                    text='{"theme": "cut mid-stream"',
                    input_tokens=1000,
                    output_tokens=32000,
                    finish_reason="max_tokens",
                    request_id="msg_raw_1",
                )
            ],
            retry_policy=no_delay_policy(max_attempts=1),
        )
        with pytest.raises(AIStructuredOutputError) as excinfo:
            analyze_window(window, transcript, engine, windows_root=root)
        assert engine.call_count == 1
        assert not transport_path("fixture", window.window_id, root=root).exists()
        assert not result_path("fixture", window.window_id, root=root).exists()
        bundle = resolve_window_execution(window, transcript, engine=engine)
        forensic_dir = forensics_dir(root, window.window_id, bundle.signature)
        payload = json.loads((forensic_dir / FORENSICS_JSON_NAME).read_text(encoding="utf-8"))
        assert payload["analysis_signature"] == bundle.signature
        assert forensic_dir != forensics_window_root(root, window.window_id)
        raw = (forensic_dir / FORENSICS_RAW_NAME).read_text(encoding="utf-8")
        assert payload["parse_error"]["parse_failure_kind"] == "json_decode"
        assert payload["usage"]["output_tokens"] == 32000
        assert payload["finish_reason"] == "max_tokens"
        assert payload["request_id"] == "msg_raw_1"
        assert payload["transport_written"] is False
        assert payload["result_written"] is False
        assert payload["retry"] is False
        assert payload["secrets_included"] is False
        assert raw == '{"theme": "cut mid-stream"'
        assert payload["raw_content"]["persisted"] is True
        assert payload["raw_content"]["raw_text_sha256"] == excinfo.value.raw_text_sha256
        cache = inspect_window_cache(
            window,
            transcript,
            windows_root=root,
            project_name="fixture",
            expected_signature="unused-on-miss",
        )
        assert cache.cache_state == "MISS"
        assert cache.transport_present is False

    def test_valid_structured_path_unchanged(self, tmp_path):
        transcript = make_transcript(("Faith changes the crossing of a trial.",))
        window = window_for(transcript)
        root = tmp_path / "windows"
        engine = FakeAIEngine(
            script=[FakeReply(parsed=minimal_transport())],
            retry_policy=no_delay_policy(max_attempts=1),
        )
        result = analyze_window(window, transcript, engine, windows_root=root)
        assert result.window_id == window.window_id
        assert transport_path("fixture", window.window_id, root=root).is_file()
        assert result_path("fixture", window.window_id, root=root).is_file()
        assert not list(
            forensics_window_root(root, window.window_id).glob(
                f"**/{FORENSICS_JSON_NAME}"
            )
        )


class TestSecrets:
    def test_forensic_json_has_no_api_key(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-test-value")
        _install_post(
            monkeypatch,
            anthropic_response(
                text="{broken",
                input_tokens=10,
                output_tokens=32000,
                stop_reason="max_tokens",
                response_id="msg_secret",
            ),
        )
        with pytest.raises(AIStructuredOutputError) as excinfo:
            _anthropic().generate(
                AIRequest(
                    prompt="x",
                    response_schema={"type": "object"},
                    model="claude-sonnet-5",
                )
            )
        from app.ai.structured_forensics import persist_structured_output_forensics

        payload = persist_structured_output_forensics(
            error=excinfo.value,
            windows_root=tmp_path / "windows",
            window_id="WIN001",
            analysis_signature="a" * 64,
        )
        dumped = json.dumps(payload)
        assert "sk-ant-secret-test-value" not in dumped
        assert "cle-de-test" not in dumped
        assert "Authorization" not in dumped
        assert payload["secrets_included"] is False


class TestOfflineDiagnosisArtifacts:
    def test_real_project_offline_artifacts_deterministic(self):
        first = run_win001_failure_diagnosis(PROJECT_NAME)
        assert first["real_provider_calls"] == 0
        failure = json.loads((REAL_AUDIT / "source_analysis_win001_structured_failure_diagnosis.json").read_text(encoding="utf-8"))
        token = json.loads((REAL_AUDIT / "source_analysis_win001_token_accounting_diagnosis.json").read_text(encoding="utf-8"))
        obs = json.loads((REAL_AUDIT / "source_analysis_structured_output_observability_review.json").read_text(encoding="utf-8"))
        assert failure["schema_version"] == SCHEMA_VERSION
        assert failure["phase"] == PHASE
        assert failure["real_provider_calls_this_phase"] == 0
        assert failure["win001_retried"] is False
        assert failure["transport"] == "ABSENT"
        assert token["local_estimate"]["matches_observed_49617"] is True
        assert token["local_estimate"]["includes_response_schema"] is False
        assert token["schema_bytes"]["could_explain_57356_token_gap"] is False
        assert token["duplication_checks"]["payload_duplication_of_src"] is False
        assert token["duplication_checks"]["src_user_counts_all_one"] is True
        assert token["duplication_checks"]["unexpected_duplication"] == []
        assert token["cost_arithmetic"]["arithmetic_correct"] is True
        assert token["context_margin"]["exceeded_usable_context"] is False
        assert token["long_context"]["crossed_protocol_threshold"] is False
        assert obs["implemented_hardening"]["semantic_behavior_changed"] is False
        assert "transcript" not in json.dumps(token).lower() or token["transcript_text_included"] is False
        after = protected_hashes(PROJECT_NAME)
        assert after == PROTECTED_BEFORE
        win001 = Path(
            r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
            r"\analysis\windows\WIN001"
        )
        assert not (win001 / "transport.json").exists()
        assert not (win001 / "result.json").exists()
