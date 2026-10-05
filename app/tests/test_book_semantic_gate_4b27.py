"""Phase 4B.2.7 — compact single-case Terra canary. Network forbidden."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.thinking import UNKNOWN_TOKEN_COUNT, extract_openai_usage_telemetry
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs
from app.book_semantic_gate_4b24.leak import audit_label_leak
from app.book_semantic_gate_4b262.contract import validate_compact_payload
from app.book_semantic_gate_4b262.fakeai import simulated_compact_single_case
from app.book_semantic_gate_4b262.request import freeze_single_case_request
from app.book_semantic_gate_4b262.selection import evidence_manifest
from app.book_semantic_gate_4b262.telemetry import run_telemetry_cases
from app.book_semantic_gate_4b27.accounting import CallAccounting
from app.book_semantic_gate_4b27.constants import (
    AUTHORIZED_REMOTE_TERRA_INVOCATIONS,
    AUTHORIZED_SONNET_CALLS,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_EVIDENCE_HANDLES,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_REQUEST_SHA256_4B26,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B241_STATUS,
    HISTORICAL_4B24_STATUS,
    HISTORICAL_4B251_STATUS,
    HISTORICAL_4B25_STATUS,
    HISTORICAL_4B261_STATUS,
    HISTORICAL_4B262_STATUS,
    HISTORICAL_4B26_STATUS,
    MODEL,
    PHASE,
    PROJECT_NAME,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
    SDK_MAX_RETRIES,
)
from app.book_semantic_gate_4b27.engine import (
    NoRetryAccountingOpenAIEngine,
    inspect_sdk_retry_policy,
)
from app.book_semantic_gate_4b27.guard import BookSemanticGate27Error, consume_remote_lock
from app.book_semantic_gate_4b27.precall import build_precall
from app.book_semantic_gate_4b27.replay import replay_saved_response
from app.book_semantic_gate_4b27.request import evidence_matches_manifest, freeze_and_identify
from app.book_semantic_gate_4b27.review import review_semantic_response
from app.book_semantic_gate_4b27.runner import _classify
from app.book_semantic_gate_4b27.writer import write_canary_artifacts


LEAK_KEY = "sk-SECRET-4B27-LEAK-TEST-VALUE-DO-NOT-PERSIST"


@pytest.fixture(autouse=True)
def _no_network(no_ai_network, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("PROVIDER NETWORK FORBIDDEN")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.Client.send", forbidden)
    return None


class TestHistoricalStatus:
    def test_history_and_authorization_are_frozen(self):
        assert PHASE == "4B.2.7"
        assert AUTHORIZED_REMOTE_TERRA_INVOCATIONS == 1
        assert AUTHORIZED_SONNET_CALLS == 0
        assert SDK_MAX_RETRIES == 0
        assert HISTORICAL_4B24_STATUS == "FAIL"
        assert HISTORICAL_4B241_STATUS == "PASS"
        assert HISTORICAL_4B25_STATUS == "FAIL"
        assert HISTORICAL_4B251_STATUS == "PASS"
        assert HISTORICAL_4B26_STATUS == "FAIL"
        assert HISTORICAL_4B261_STATUS == "PASS"
        assert HISTORICAL_4B262_STATUS == "PASS"
        assert EXPECTED_REQUEST_SHA256 == (
            "9520a4f3e5ff36ec2957b74e82d492019ff630f764e1413853b19d9b96dec6af"
        )
        assert EXPECTED_REQUEST_SHA256 != EXPECTED_REQUEST_SHA256_4B26
        assert EXPECTED_SOURCE_MAP == (
            "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855"
        )
        assert EXPECTED_EDITORIAL_PLAN == (
            "01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440"
        )
        assert EXPECTED_CLEAN_TRANSCRIPT == (
            "1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958"
        )


class TestRequestIdentity:
    def test_frozen_sha_matches_4b262_and_is_deterministic(self):
        identified = freeze_and_identify()
        assert identified["sha256"] == EXPECTED_REQUEST_SHA256
        assert identified["first_sha256"] == identified["second_sha256"]
        assert identified["identity_match"] is True
        assert identified["determinism"] is True
        assert identified["exactly_one_case"] is True
        assert identified["handles_in_request"] == [SELECTED_CASE_HANDLE]
        assert identified["label_leakage"] == 0
        assert identified["payload"]["model"] == MODEL
        assert identified["payload"]["max_completion_tokens"] == 8192
        assert "max_tokens" not in identified["payload"]
        assert "temperature" not in identified["payload"]
        assert "thinking" not in identified["payload"]
        assert identified["payload"]["response_format"] == {"type": "json_object"}

    def test_sdk_serialization_is_offline(self):
        identified = freeze_and_identify()
        sdk = identified["sdk"]
        assert sdk["network_calls"] == 0
        assert sdk["http_requests"] == 0
        assert sdk["serialization_pass"] is True
        assert sdk["checks"]["exactly_one_case"] is True
        assert sdk["checks"]["max_tokens_absent"] is True
        assert sdk["secrets_included"] is False


class TestEvidenceAndLabels:
    def test_evidence_manifest_matches_frozen_handles(self):
        evidence = evidence_manifest()
        assert evidence_matches_manifest(evidence) is True
        assert tuple(evidence["present_ids"]) == EXPECTED_EVIDENCE_HANDLES
        assert SELECTED_CASE_ID == "4b22_p2_supported"

    def test_human_label_is_absent_from_request(self):
        payload = freeze_single_case_request()["payload"]
        leak = audit_label_leak(payload)
        blob = json.dumps(payload, ensure_ascii=False)
        assert leak["pass"] is True
        assert SELECTED_CASE_ID not in blob
        assert "4b22_p2_supported" not in blob
        assert "human_label" not in blob.lower()
        assert LEAK_KEY not in blob


class TestNoRetryAndAccounting:
    def test_sdk_retry_probe_is_zero(self):
        inspect = inspect_sdk_retry_policy()
        assert inspect["pass"] is True
        assert inspect["probe_max_retries"] == 0
        assert inspect["enforced_max_retries"] == 0

    def test_second_generate_is_refused(self):
        engine = NoRetryAccountingOpenAIEngine(
            api_key="offline-4b27-unused",
            client=object(),
        )
        request = AIRequest(
            prompt="offline",
            model=MODEL,
            metadata={"frozen_payload": {"model": MODEL, "messages": []}},
        )

        def boom(_request):
            raise AssertionError("network must not be reached")

        engine._invoke = boom  # type: ignore[method-assign]
        with pytest.raises(Exception):
            engine.generate(request)
        engine.accounting.execution_attempts = 1
        with pytest.raises(BookSemanticGate27Error, match="Second engine.generate"):
            engine.generate(request)

    def test_second_lock_is_refused(self, tmp_path):
        lock = tmp_path / "lock.txt"
        consume_remote_lock(path=lock, phase=PHASE, scope="scope")
        with pytest.raises(BookSemanticGate27Error, match="NO RETRY"):
            consume_remote_lock(path=lock, phase=PHASE, scope="scope")
        assert lock.exists() is True

    def test_accounting_separates_counters(self):
        counts = CallAccounting()
        payload = counts.to_dict()
        assert payload["authorized_remote_invocations"] == 1
        assert payload["execution_attempts"] == 0
        assert payload["remote_invocations"] == 0
        assert payload["http_requests"] == 0
        assert payload["retries"] == 0
        assert payload["fallbacks"] == 0
        assert payload["historical_4b26_unchanged"] is True


class TestTelemetryAndReplay:
    def test_reasoning_tokens_absent_are_unknown(self):
        telemetry = extract_openai_usage_telemetry(
            {"prompt_tokens": 10, "completion_tokens": 8}
        )
        assert telemetry["reasoning_tokens"] == UNKNOWN_TOKEN_COUNT
        assert telemetry["absent_is_unknown"] is True
        cases = run_telemetry_cases()
        assert cases["passed"] is True

    def test_compact_json_replays_identically(self):
        frozen = freeze_single_case_request()
        compact = simulated_compact_single_case(frozen["payload"])
        from app.book_semantic_gate_4b27.request import paragraph_context

        context = paragraph_context()
        raw = json.dumps(compact, ensure_ascii=False)
        replay = replay_saved_response(
            raw,
            paragraph_texts=context["paragraph_texts"],
            required_handles=[SELECTED_CASE_HANDLE],
            paragraph_kinds=context["paragraph_kinds"],
        )
        assert replay["pass"] is True
        assert replay["identical"] is True
        assert replay["provider_calls"] == 0
        validation = validate_compact_payload(
            compact,
            paragraph_texts=context["paragraph_texts"],
            required_handles=[SELECTED_CASE_HANDLE],
            paragraph_kinds=context["paragraph_kinds"],
        )
        assert validation["status"] == "PASS"


class TestSemanticReview:
    def test_supported_requires_justification(self):
        review = review_semantic_response(
            {
                "ch": "CH016",
                "v": "PASS",
                "pr": [
                    {
                        "h": "h01",
                        "v": "SUPPORTED",
                        "c": [
                            {
                                "i": 0,
                                "s": 0,
                                "e": 3,
                                "k": "SUPPORTED",
                                "ev": ["SRC006149"],
                                "r": [],
                            }
                        ],
                        "ev": ["SRC006149"],
                        "r": [],
                    }
                ],
                "sc": {},
                "uh": [],
                "rr": False,
            },
            paragraph_text="abc",
            allowed_handles=EXPECTED_EVIDENCE_HANDLES,
            contract_status="PASS",
            coverage_ok=True,
            spans_ok=True,
        )
        assert review["terra_verdict"] == "SUPPORTED"
        assert review["human_verdict_audit_only"] == "SUPPORTED"
        assert review["human_verdict_not_transmitted"] is True
        assert review["semantic_status"] == "PASS"

    def test_questionable_is_potential_false_rejection(self):
        review = review_semantic_response(
            {
                "ch": "CH016",
                "v": "REVIEW",
                "pr": [
                    {
                        "h": "h01",
                        "v": "QUESTIONABLE",
                        "c": [
                            {
                                "i": 0,
                                "s": 0,
                                "e": 3,
                                "k": "QUESTIONABLE",
                                "ev": ["SRC006149"],
                                "r": ["WEAK_SUPPORT"],
                                "n": "incertitude",
                            }
                        ],
                        "ev": ["SRC006149"],
                        "r": ["WEAK_SUPPORT"],
                    }
                ],
                "sc": {},
                "uh": [],
                "rr": False,
            },
            paragraph_text="abc",
            allowed_handles=EXPECTED_EVIDENCE_HANDLES,
            contract_status="PASS",
            coverage_ok=True,
            spans_ok=True,
        )
        assert review["semantic_status"] == "POTENTIAL_FALSE_REJECTION"
        assert review["review_status"] == "PARTIAL"

    def test_usable_json_with_coverage_or_false_rejection_is_partial(self):
        assert (
            _classify(
                remote=1,
                error_text=None,
                http_success=True,
                finish="stop",
                raw_text='{"ch":"CH016"}',
                json_parse="PASS",
                contract_status="FAIL",
                coverage_ok=False,
                spans_ok=True,
                invalid_refs=[],
                semantic_status="POTENTIAL_FALSE_REJECTION",
                replay_pass=True,
                test_failures=0,
            )
            == "PARTIAL"
        )
        assert (
            _classify(
                remote=1,
                error_text=None,
                http_success=True,
                finish="length",
                raw_text="",
                json_parse="FAIL",
                contract_status="FAIL",
                coverage_ok=False,
                spans_ok=False,
                invalid_refs=[],
                semantic_status="MISSING_VERDICT",
                replay_pass=False,
                test_failures=0,
            )
            == "FAIL"
        )


class TestGuardsAndHygiene:
    def test_wrong_scope_is_rejected(self):
        from app.book_semantic_gate_4b27.__main__ import main

        assert main(["--authorization-scope", "WRONG", "--dry-run"]) == 2

    def test_canonical_inputs_and_book_absent(self):
        identities = verify_canonical_inputs()
        assert identities["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert identities["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert identities["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
        assert production_book_absent(PROJECT_NAME) is True

    def test_writer_does_not_touch_historical_dirs(self, tmp_path):
        from app.book_semantic_gate_4b27.paths import historical_audit_dirs

        bundle = {
            "header": {"result": "DRY_RUN", "remote_invocations": 0},
            "precall": {"phase": PHASE, "secrets_included": False},
            "report_text": "PHASE 4B.2.7\n",
        }
        written = write_canary_artifacts(bundle, root=tmp_path)
        historical = historical_audit_dirs(root=tmp_path)
        for path in historical.values():
            assert path.exists() is False
        assert "precall" in written
        assert LEAK_KEY not in json.dumps(bundle)

    def test_anthropic_engine_is_not_used(self):
        assert AnthropicEngine.provider_name == "anthropic"
        identity = build_precall()
        blob = json.dumps(_jsonable(identity), ensure_ascii=False)
        assert "anthropic" not in blob.lower() or identity["remote_invocations"] == 0
        assert identity["http_sent"] is False
        assert identity["request"]["sha256"] == EXPECTED_REQUEST_SHA256

    def test_secrets_are_redacted_from_precall(self):
        identity = build_precall()
        blob = json.dumps(_jsonable(identity), ensure_ascii=False)
        assert "sk-" not in blob
        assert LEAK_KEY not in blob
        assert identity["secrets_included"] is False


def _jsonable(value):
    if isinstance(value, AIRequest):
        return {"prompt_chars": len(value.prompt)}
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
