"""Phase 4B.2.7.3 — one real Terra P3 negative canary. Network forbidden."""

from __future__ import annotations

import json

import pytest

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.thinking import UNKNOWN_TOKEN_COUNT, extract_openai_usage_telemetry
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs
from app.book_semantic_gate_4b24.leak import audit_label_leak
from app.book_semantic_gate_4b262.telemetry import run_telemetry_cases
from app.book_semantic_gate_4b271.coverage import validate_compact_payload_111
from app.book_semantic_gate_4b272.fakeai import simulated_p3_compact
from app.book_semantic_gate_4b272.request import freeze_p3_request
from app.book_semantic_gate_4b273.accounting import CallAccounting
from app.book_semantic_gate_4b273.constants import (
    AUTHORIZED_REMOTE_TERRA_INVOCATIONS,
    AUTHORIZED_SONNET_CALLS,
    DISPUTED_CAUSAL_CLAUSE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_CLAUSE_END,
    EXPECTED_CLAUSE_START,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_SOURCE_MAP,
    H01_REQUEST_SHA256,
    HISTORICAL_4B271_STATUS,
    HISTORICAL_4B272_STATUS,
    HISTORICAL_4B27_STATUS,
    MODEL,
    P3_EVIDENCE_HANDLES,
    PHASE,
    PROJECT_NAME,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    SDK_MAX_RETRIES,
)
from app.book_semantic_gate_4b273.engine import (
    NoRetryAccountingOpenAIEngine,
    inspect_sdk_retry_policy,
)
from app.book_semantic_gate_4b273.guard import BookSemanticGate273Error, consume_remote_lock
from app.book_semantic_gate_4b273.replay import replay_saved_response
from app.book_semantic_gate_4b273.request import evidence_matches_manifest, freeze_and_identify
from app.book_semantic_gate_4b273.review import review_p3_semantic_response
from app.book_semantic_gate_4b273.runner import _classify
from app.book_semantic_gate_4b273.writer import write_canary_artifacts


LEAK_KEY = "sk-SECRET-4B273-LEAK-TEST-VALUE-DO-NOT-PERSIST"
PARAGRAPH = (
    "Yet we can see fear operating in believers, and this is not normal. "
    "Fear of death is an abuse — an abuse to your very person, a diminishment "
    "of what you were made and remade to be. It is worth naming where this "
    "abuse comes from. The devil has used it since the beginning; he has not "
    "changed his style. The same old strategy that first weaponized death "
    "against humanity is still being run today, unchanged, because it still "
    "works wherever it is not resisted by truth."
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("PROVIDER NETWORK FORBIDDEN")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.Client.send", forbidden)
    return None


class TestHistoricalStatus:
    def test_history_and_authorization_are_frozen(self):
        assert PHASE == "4B.2.7.3"
        assert AUTHORIZED_REMOTE_TERRA_INVOCATIONS == 1
        assert AUTHORIZED_SONNET_CALLS == 0
        assert SDK_MAX_RETRIES == 0
        assert HISTORICAL_4B27_STATUS == "PARTIAL"
        assert HISTORICAL_4B271_STATUS == "PASS"
        assert HISTORICAL_4B272_STATUS == "PASS"
        assert SELECTED_CASE_HANDLE == "h02"
        assert SELECTED_CASE_ID == "4b22_p3_new_causal"
        assert SELECTED_CASE_HUMAN_LABEL == "QUESTIONABLE"
        assert EXPECTED_REQUEST_SHA256 == (
            "5ace261296d808437910f8f9efe247a80daebbb2237bc8af46bda56bf98d7897"
        )
        assert EXPECTED_REQUEST_SHA256 != H01_REQUEST_SHA256
        assert EXPECTED_SOURCE_MAP == (
            "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855"
        )
        assert EXPECTED_EDITORIAL_PLAN == (
            "01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440"
        )
        assert EXPECTED_CLEAN_TRANSCRIPT == (
            "1f33ac732eb82ec1d55f274a152747058c9138cd394dea9c956d28d7e2739958"
        )
        assert PARAGRAPH[EXPECTED_CLAUSE_START:EXPECTED_CLAUSE_END] == DISPUTED_CAUSAL_CLAUSE


class TestRequestIdentity:
    def test_frozen_sha_matches_4b272_and_is_deterministic(self):
        identified = freeze_and_identify()
        assert identified["sha256"] == EXPECTED_REQUEST_SHA256
        assert identified["first_sha256"] == identified["second_sha256"]
        assert identified["identity_match"] is True
        assert identified["determinism"] is True
        assert identified["exactly_one_case"] is True
        assert identified["handles_in_request"] == [SELECTED_CASE_HANDLE]
        assert identified["label_leakage"] == 0
        assert identified["differs_from_h01"] is True
        assert identified["independent_of_h01"] is True
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
        assert sdk["checks"]["prompt_111"] is True
        assert sdk["secrets_included"] is False


class TestEvidenceAndLabels:
    def test_evidence_manifest_matches_p3_handles(self):
        from app.book_semantic_gate_4b272.evidence import build_canonical_evidence_inventory

        inventory = build_canonical_evidence_inventory()
        assert evidence_matches_manifest(inventory) is True
        assert tuple(inventory["present_ids"]) == P3_EVIDENCE_HANDLES
        assert SELECTED_CASE_ID == "4b22_p3_new_causal"

    def test_human_label_is_absent_from_request(self):
        payload = freeze_p3_request()["payload"]
        leak = audit_label_leak(payload)
        blob = json.dumps(payload, ensure_ascii=False)
        assert leak["pass"] is True
        assert SELECTED_CASE_ID not in blob
        assert "4b22_p3_new_causal" not in blob
        assert "human_label" not in blob.lower()
        assert "NEW_CAUSAL_LINK" not in blob
        assert LEAK_KEY not in blob
        assert '"h01"' not in blob


class TestNoRetryAndAccounting:
    def test_sdk_retry_probe_is_zero(self):
        inspect = inspect_sdk_retry_policy()
        assert inspect["pass"] is True
        assert inspect["probe_max_retries"] == 0
        assert inspect["enforced_max_retries"] == 0

    def test_second_generate_is_refused(self):
        engine = NoRetryAccountingOpenAIEngine(
            api_key="offline-4b273-unused",
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
        with pytest.raises(BookSemanticGate273Error, match="Second engine.generate"):
            engine.generate(request)

    def test_second_lock_is_refused(self, tmp_path):
        lock = tmp_path / "lock.txt"
        consume_remote_lock(path=lock, phase=PHASE, scope="scope")
        with pytest.raises(BookSemanticGate273Error, match="NO RETRY"):
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
        assert payload["sonnet_calls"] == 0
        assert payload["historical_4b27_unchanged"] is True


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
        frozen = freeze_p3_request()
        compact = simulated_p3_compact(frozen["payload"])
        from app.book_semantic_gate_4b273.request import paragraph_context

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
        validation = validate_compact_payload_111(
            compact,
            paragraph_texts=context["paragraph_texts"],
            required_handles=[SELECTED_CASE_HANDLE],
            paragraph_kinds=context["paragraph_kinds"],
        )
        assert validation["status"] == "PASS"


class TestSemanticReview:
    def _payload(self, claims, *, global_v="REVIEW", para_v="QUESTIONABLE"):
        return {
            "ch": "CH016",
            "v": global_v,
            "pr": [
                {
                    "h": "h02",
                    "v": para_v,
                    "c": claims,
                    "ev": ["IDEA225"],
                    "r": ["NEW_CAUSAL_LINK"],
                }
            ],
            "sc": {},
            "uh": [],
            "rr": True,
        }

    def test_correct_causal_flag_is_pass(self):
        review = review_p3_semantic_response(
            self._payload(
                [
                    {
                        "i": 0,
                        "s": 0,
                        "e": EXPECTED_CLAUSE_START,
                        "k": "SUPPORTED",
                        "ev": ["IDEA225"],
                        "r": [],
                    },
                    {
                        "i": 1,
                        "s": EXPECTED_CLAUSE_START,
                        "e": EXPECTED_CLAUSE_END,
                        "k": "QUESTIONABLE",
                        "ev": [],
                        "r": ["NEW_CAUSAL_LINK"],
                        "n": "Causal relation is not in evidence.",
                    },
                ]
            ),
            paragraph_text=PARAGRAPH,
            allowed_handles=P3_EVIDENCE_HANDLES,
            contract_status="PASS",
            coverage_ok=True,
            spans_ok=True,
        )
        assert review["disputed_causal_clause_verdict"] == "QUESTIONABLE"
        assert review["disputed_causal_clause_reason_code"] == "NEW_CAUSAL_LINK"
        assert review["semantic_status"] == "PASS"
        assert review["human_verdict_not_transmitted"] is True

    def test_accepting_causal_clause_fails(self):
        review = review_p3_semantic_response(
            self._payload(
                [
                    {
                        "i": 0,
                        "s": 0,
                        "e": len(PARAGRAPH),
                        "k": "SUPPORTED",
                        "ev": ["IDEA225"],
                        "r": [],
                    }
                ],
                global_v="PASS",
                para_v="SUPPORTED",
            ),
            paragraph_text=PARAGRAPH,
            allowed_handles=P3_EVIDENCE_HANDLES,
            contract_status="PASS",
            coverage_ok=True,
            spans_ok=True,
        )
        assert review["clause_accepted_as_supported"] is True
        assert review["semantic_status"] == "FAIL"

    def test_omitting_clause_fails(self):
        review = review_p3_semantic_response(
            self._payload(
                [
                    {
                        "i": 0,
                        "s": 0,
                        "e": 40,
                        "k": "QUESTIONABLE",
                        "ev": [],
                        "r": ["NEW_FACT"],
                    }
                ]
            ),
            paragraph_text=PARAGRAPH,
            allowed_handles=P3_EVIDENCE_HANDLES,
            contract_status="PASS",
            coverage_ok=True,
            spans_ok=True,
        )
        assert review["clause_omitted"] is True
        assert review["wrong_target"] is True
        assert review["semantic_status"] == "FAIL"

    def test_all_questionable_without_discrimination_fails(self):
        review = review_p3_semantic_response(
            self._payload(
                [
                    {
                        "i": 0,
                        "s": 0,
                        "e": len(PARAGRAPH),
                        "k": "QUESTIONABLE",
                        "ev": [],
                        "r": ["OTHER"],
                    }
                ]
            ),
            paragraph_text=PARAGRAPH,
            allowed_handles=P3_EVIDENCE_HANDLES,
            contract_status="PASS",
            coverage_ok=True,
            spans_ok=True,
        )
        assert review["all_claims_questionable"] is True
        assert review["semantic_status"] in {"FAIL", "PARTIAL"}

    def test_usable_json_with_coverage_gap_is_partial(self):
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
                semantic_status="PARTIAL",
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
        assert (
            _classify(
                remote=1,
                error_text=None,
                http_success=True,
                finish="stop",
                raw_text='{"ch":"CH016"}',
                json_parse="PASS",
                contract_status="PASS",
                coverage_ok=True,
                spans_ok=True,
                invalid_refs=[],
                semantic_status="FAIL",
                replay_pass=True,
                test_failures=0,
            )
            == "FAIL"
        )


class TestGuardsAndHygiene:
    def test_wrong_scope_is_rejected(self):
        from app.book_semantic_gate_4b273.__main__ import main

        assert main(["--authorization-scope", "WRONG", "--dry-run"]) == 2

    def test_canonical_inputs_and_book_absent(self):
        identities = verify_canonical_inputs()
        assert identities["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert identities["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert identities["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
        assert production_book_absent(PROJECT_NAME) is True

    def test_writer_does_not_touch_historical_dirs(self, tmp_path):
        from app.book_semantic_gate_4b273.paths import historical_audit_dirs

        bundle = {
            "header": {"result": "DRY_RUN", "remote_invocations": 0},
            "precall": {"phase": PHASE, "secrets_included": False},
            "report_text": "PHASE 4B.2.7.3\n",
        }
        written = write_canary_artifacts(bundle, root=tmp_path)
        historical = historical_audit_dirs(root=tmp_path)
        for path in historical.values():
            assert path.exists() is False
        assert "precall" in written
        assert LEAK_KEY not in json.dumps(bundle)

    def test_anthropic_engine_is_not_used(self):
        assert AnthropicEngine.provider_name == "anthropic"
        identity = freeze_and_identify()
        blob = json.dumps(_jsonable(identity), ensure_ascii=False)
        assert "anthropic" not in blob.lower()
        assert identity["sha256"] == EXPECTED_REQUEST_SHA256

    def test_secrets_are_redacted_from_precall_shape(self):
        identified = freeze_and_identify()
        blob = json.dumps(_jsonable(identified), ensure_ascii=False)
        assert "sk-" not in blob
        assert LEAK_KEY not in blob
        assert identified.get("secrets_included") is False


def _jsonable(value):
    if isinstance(value, AIRequest):
        return {"prompt_chars": len(value.prompt)}
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
