"""Phase 4B.2.5 — Terra canary. Network blocked. 0 provider calls in tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.contracts import AIRequest
from app.ai.provider_preflight import (
    REASON_PROVIDER_RUNTIME_NOT_READY,
    assert_provider_ready_for_authorization,
    check_provider_runtime_readiness,
    redact_secrets,
)
from app.ai.providers.openai_engine import OpenAIEngine
from app.book_semantic_gate_4b25.accounting import CallAccounting
from app.book_semantic_gate_4b25.constants import (
    AUTHORIZED_REMOTE_TERRA_INVOCATIONS,
    AUTHORIZED_SONNET_CALLS,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_REQUEST_SHA256_FROZEN,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B21_STATUS,
    HISTORICAL_4B22_STATUS,
    HISTORICAL_4B23_STATUS,
    HISTORICAL_4B241_STATUS,
    HISTORICAL_4B24_STATUS,
    HISTORICAL_4B2_STATUS,
    MODEL,
    OUTPUT_MODE,
    PHASE,
)
from app.book_semantic_gate_4b25.engine import AccountingOpenAIEngine
from app.book_semantic_gate_4b25.guard import BookSemanticGate25Error, consume_remote_lock
from app.book_semantic_gate_4b25.paths import historical_4b24_audit_dir, venv_python_path
from app.book_semantic_gate_4b25.precall import build_precall
from app.book_semantic_gate_4b25.runtime import interpreter_match, normalize_executable
from app.book_semantic_gate_4b25.writer import write_canary_artifacts


LEAK_KEY = "sk-SECRET-4B25-LEAK-TEST-VALUE-DO-NOT-PERSIST"


@pytest.fixture(autouse=True)
def _no_network(no_ai_network, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("PROVIDER NETWORK FORBIDDEN")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.Client.send", forbidden)
    return None


class TestHistoricalStatus:
    def test_history_is_frozen(self):
        assert PHASE == "4B.2.5"
        assert AUTHORIZED_REMOTE_TERRA_INVOCATIONS == 1
        assert AUTHORIZED_SONNET_CALLS == 0
        assert HISTORICAL_4B2_STATUS == "FAIL"
        assert HISTORICAL_4B21_STATUS == "PASS"
        assert HISTORICAL_4B22_STATUS == "PARTIAL"
        assert HISTORICAL_4B23_STATUS == "PASS"
        assert HISTORICAL_4B24_STATUS == "FAIL"
        assert HISTORICAL_4B241_STATUS == "PASS"
        assert EXPECTED_SOURCE_MAP == (
            "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855"
        )
        assert EXPECTED_EDITORIAL_PLAN == (
            "01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440"
        )
        assert EXPECTED_CLEAN_TRANSCRIPT == (
            "1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958"
        )
        assert EXPECTED_REQUEST_SHA256_FROZEN == (
            "09d6472e544bc60231c77908e6608ff7ee7b6fd4746317f206301082e21eab53"
        )


class TestInterpreterGate:
    def test_wrong_interpreter_is_precall_block(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "app.book_semantic_gate_4b25.runtime.sys.executable",
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


class TestFrozenRequest:
    def test_request_identity_matches_4b23_4b24(self):
        from pathlib import Path

        historical = Path(
            "audit/real/book_semantic_gate_4b25/"
            "book_semantic_gate_4b25_request_identity.json"
        )
        if historical.is_file():
            recorded = json.loads(historical.read_text(encoding="utf-8"))
            assert recorded["request_sha256"] == EXPECTED_REQUEST_SHA256_FROZEN
            assert recorded["payload"]["max_tokens"] == 8192
        identity = build_precall()
        assert identity["request"]["deterministic"] is True
        assert identity["request"]["sha256"] == identity["request"]["sha256_repeat"]
        assert identity["label_leak"]["label_leakage"] == 0
        assert identity["request"]["response_format"] == {"type": "json_object"}
        assert identity["request"]["temperature_present"] is False
        assert len(identity["candidate_handles"]) == 10


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
        lock = tmp_path / "book_semantic_gate_4b25_real_call.lock"
        with pytest.raises(Exception, match=REASON_PROVIDER_RUNTIME_NOT_READY):
            assert_provider_ready_for_authorization(readiness)
            consume_remote_lock(path=lock, phase=PHASE, scope="x")
        assert lock.exists() is False
        assert readiness.remote_invocations == 0
        assert readiness.network_calls == 0

    def test_second_lock_is_refused(self, tmp_path):
        lock = tmp_path / "lock.txt"
        consume_remote_lock(path=lock, phase=PHASE, scope="scope")
        with pytest.raises(BookSemanticGate25Error, match="NO RETRY"):
            consume_remote_lock(path=lock, phase=PHASE, scope="scope")

    def test_accounting_starts_at_zero(self):
        counts = CallAccounting()
        assert counts.authorized_remote_invocations == 1
        assert counts.execution_attempts == 0
        assert counts.remote_invocations == 0
        assert counts.http_requests == 0
        assert counts.provider_responses == 0
        assert counts.retries == 0
        assert counts.fallbacks == 0


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
        assert engine.accounting.remote_invocations == 0
        assert engine.retry_policy.max_attempts == 1


class TestWriterIsolation:
    def test_artifacts_do_not_enter_4b24_dir(self, tmp_path):
        historical = historical_4b24_audit_dir()
        before = {path.name for path in historical.glob("*")} if historical.exists() else set()
        write_canary_artifacts(
            {
                "header": {"result": "BLOCKED_PRECALL", "remote_invocations": 0},
                "precall": {"phase": PHASE},
                "runtime": {"secrets_included": False},
                "request_identity": {"request_sha256": EXPECTED_REQUEST_SHA256_FROZEN},
                "call_accounting": CallAccounting().to_dict(),
                "report_text": "# PHASE 4B.2.5\n",
            },
            root=tmp_path,
        )
        after = {path.name for path in historical.glob("*")} if historical.exists() else set()
        assert after == before
        written = tmp_path / "audit" / "real" / "book_semantic_gate_4b25"
        assert (written / "book_semantic_gate_4b25_precall.json").is_file()
        assert (tmp_path / "audit" / "PHASE_4B25_ONE_REAL_TERRA_SEMANTIC_GATE_BENCHMARK_CANARY_REPORT.md").is_file()


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


class TestCli:
    def test_wrong_scope_rejected(self):
        from app.book_semantic_gate_4b25.__main__ import main

        assert main(["--authorization-scope", "WRONG", "--dry-run"]) == 2
