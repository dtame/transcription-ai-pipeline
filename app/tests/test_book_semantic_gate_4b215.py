"""Phase 4B.2.15 — one real Terra Semantic Gate 2.0.2 h11 canary. Network forbidden."""

from __future__ import annotations

import json

import pytest

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.thinking import UNKNOWN_TOKEN_COUNT, extract_openai_usage_telemetry
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b215.accounting import CallAccounting
from app.book_semantic_gate_4b215.budget import reserve_budget
from app.book_semantic_gate_4b215.constants import (
    AUTHORIZED_REMOTE_TERRA_INVOCATIONS,
    AUTHORIZED_SONNET_CALLS,
    BUDGET_CAP_USD,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    H11_EVIDENCE,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    MIN_USABLE_OUTPUT_TOKENS,
    MODEL,
    PHASE,
    PROJECT_NAME,
    REQUIRED_UNIT_IDS,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    SDK_MAX_RETRIES,
    TARGET_CLAUSE,
    TARGET_UNIT_ID,
)
from app.book_semantic_gate_4b215.engine import (
    NoRetryAccountingOpenAIEngine,
    inspect_sdk_retry_policy,
)
from app.book_semantic_gate_4b215.guard import BookSemanticGate215Error, consume_remote_lock
from app.book_semantic_gate_4b215.precall import build_precall
from app.book_semantic_gate_4b215.replay import replay_saved_response
from app.book_semantic_gate_4b215.request import freeze_and_identify, prepare_h11_units
from app.book_semantic_gate_4b215.review import review_h11_semantic_response
from app.book_semantic_gate_4b215.runner import _classify
from app.book_semantic_gate_4b215.validation import validate_contract
from app.book_semantic_gate_4b215.writer import write_canary_artifacts
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs


LEAK_KEY = "sk-SECRET-4B215-LEAK-TEST-VALUE-DO-NOT-PERSIST"


@pytest.fixture(autouse=True)
def _no_network(no_ai_network, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("PROVIDER NETWORK FORBIDDEN")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.Client.send", forbidden)
    return None


def _supported_prefix_and_blocked_guarantee() -> dict:
    units = [
        {"id": "u00", "k": "SUPPORTED", "ev": ["SRC006192"], "r": []},
        {"id": "u01", "k": "SUPPORTED", "ev": ["SRC006192"], "r": []},
        {"id": "u02", "k": "SUPPORTED", "ev": ["IDEA226"], "r": []},
        {"id": "u03", "k": "SUPPORTED", "ev": ["SRC006193"], "r": []},
        {
            "id": "u04",
            "k": "UNSUPPORTED",
            "ev": ["IDEA226"],
            "r": ["NEW_IMPLICATION"],
            "n": "Universal guarantee is not in the supplied evidence.",
        },
    ]
    return {"ch": "CH016", "pr": [{"h": "h11", "u": units}]}


def _guarantee_accepted_payload() -> dict:
    payload = _supported_prefix_and_blocked_guarantee()
    payload["pr"][0]["u"][4] = {"id": "u04", "k": "SUPPORTED", "ev": ["IDEA226"], "r": []}
    return payload


def _prefix_rejected_payload() -> dict:
    payload = _supported_prefix_and_blocked_guarantee()
    payload["pr"][0]["u"][0] = {
        "id": "u00",
        "k": "QUESTIONABLE",
        "ev": ["IDEA226"],
        "r": ["EVIDENCE_MISMATCH"],
        "n": "Mental technique is not attested.",
    }
    return payload


class TestHistoricalStatus:
    def test_history_and_authorization_are_frozen(self):
        assert PHASE == "4B.2.15"
        assert AUTHORIZED_REMOTE_TERRA_INVOCATIONS == 1
        assert AUTHORIZED_SONNET_CALLS == 0
        assert SDK_MAX_RETRIES == 0
        assert HISTORICAL_H01_STATUS == "PARTIAL"
        assert HISTORICAL_H02_STATUS == "PARTIAL"
        assert HISTORICAL_H11_STATUS == "PARTIAL"
        assert HISTORICAL_4B211_STATUS == "PARTIAL"
        assert SELECTED_CASE_HANDLE == "h11"
        assert SELECTED_CASE_ID == "4b276_p4_new_implication"
        assert SELECTED_CASE_HUMAN_LABEL == "UNSUPPORTED"
        assert TARGET_UNIT_ID == "u04"
        assert TARGET_CLAUSE == (
            "which means that every believer is guaranteed a fearless death"
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


class TestH11Preparation:
    def test_guarantee_is_an_independent_unit(self):
        prepared = prepare_h11_units()
        assert prepared["coverage_ok"] is True
        assert tuple(prepared["unit_ids"]) == REQUIRED_UNIT_IDS
        assert prepared["clause_in_target_unit"] is True
        assert prepared["guarantee_independently_evaluable"] is True
        assert prepared["merged_with_other_unit"] is False
        assert TARGET_CLAUSE in str((prepared["target_unit"] or {}).get("text") or "")
        assert prepared["evidence_handles"] == list(H11_EVIDENCE)


class TestRequestAndBudget:
    def test_request_is_deterministic_and_has_no_label_leak(self):
        identified = freeze_and_identify(max_completion_tokens=7500)
        assert identified["first_sha256"] == identified["second_sha256"]
        assert identified["determinism"] is True
        assert identified["exactly_one_case"] is True
        assert identified["handles_in_request"] == [SELECTED_CASE_HANDLE]
        assert identified["label_leakage"] == 0
        assert identified["case_id_in_request"] is False
        blob = json.dumps(identified["payload"], ensure_ascii=False)
        assert SELECTED_CASE_ID not in blob
        assert "human_label" not in blob.lower()
        assert "should be unsupported" not in blob.lower()
        assert TARGET_CLAUSE in blob
        assert identified["payload"]["model"] == MODEL
        assert identified["payload"]["max_completion_tokens"] == 7500
        assert "max_tokens" not in identified["payload"]
        assert "temperature" not in identified["payload"]
        assert identified["payload"]["response_format"] == {"type": "json_object"}

    def test_budget_cap_blocks_8192_and_accepts_usable_cap(self):
        identified = freeze_and_identify(max_completion_tokens=8192)
        reservation = reserve_budget(identified["payload"])
        assert reservation["if_8192_exhausted"]["total_cost_usd"] > float(BUDGET_CAP_USD)
        identified = freeze_and_identify(max_completion_tokens=7500)
        reservation = reserve_budget(identified["payload"])
        assert reservation["within_budget"] is True
        assert reservation["max_completion_tokens"] >= MIN_USABLE_OUTPUT_TOKENS
        assert reservation["theoretical_maximum_usd"] <= float(BUDGET_CAP_USD)
        assert reservation["unknown_is_not_zero"] is True


class TestNoRetryAndAccounting:
    def test_sdk_retry_probe_is_zero(self):
        inspect = inspect_sdk_retry_policy()
        assert inspect["pass"] is True
        assert inspect["probe_max_retries"] == 0
        assert inspect["enforced_max_retries"] == 0

    def test_second_generate_is_refused(self):
        engine = NoRetryAccountingOpenAIEngine(
            api_key="offline-4b215-unused",
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
        with pytest.raises(BookSemanticGate215Error, match="Second engine.generate"):
            engine.generate(request)

    def test_second_lock_is_refused(self, tmp_path):
        lock = tmp_path / "lock.txt"
        consume_remote_lock(path=lock, phase=PHASE, scope="scope")
        with pytest.raises(BookSemanticGate215Error, match="NO RETRY"):
            consume_remote_lock(path=lock, phase=PHASE, scope="scope")
        assert lock.exists() is True

    def test_accounting_separates_counters(self):
        counts = CallAccounting()
        payload = counts.to_dict()
        assert payload["authorized_remote_invocations"] == 1
        assert payload["execution_attempts"] == 0
        assert payload["remote_invocations"] == 0
        assert payload["retries"] == 0
        assert payload["sonnet_calls"] == 0


class TestContractReplayAndReview:
    def test_blocked_guarantee_replays_and_python_blocks(self):
        context = prepare_h11_units()
        compact = _supported_prefix_and_blocked_guarantee()
        raw = json.dumps(compact, ensure_ascii=False)
        contract = validate_contract(
            compact,
            context["prepared"],
            allowed_evidence=context["evidence_handles"],
        )
        assert contract["status"] == "PASS"
        replay = replay_saved_response(
            raw,
            prepared=context["prepared"],
            allowed_handles=context["evidence_handles"],
        )
        assert replay["pass"] is True
        assert replay["provider_calls"] == 0
        review = review_h11_semantic_response(
            compact,
            prepared_units=context["units"],
            allowed_handles=context["evidence_handles"],
            contract_status="PASS",
            coverage_ok=True,
            evidence_ok=True,
            python_decision="BLOCK",
        )
        assert review["universal_guarantee_unsupported"] is True
        assert review["semantic_status"] == "PASS"
        assert review["human_verdict_not_transmitted"] is True

    def test_accepted_guarantee_is_fail(self):
        context = prepare_h11_units()
        compact = _guarantee_accepted_payload()
        review = review_h11_semantic_response(
            compact,
            prepared_units=context["units"],
            allowed_handles=context["evidence_handles"],
            contract_status="PASS",
            coverage_ok=True,
            evidence_ok=True,
            python_decision="PASS",
        )
        assert review["universal_guarantee_accepted"] is True
        assert review["semantic_status"] == "FAIL"

    def test_prefix_rejection_is_partial(self):
        context = prepare_h11_units()
        compact = _prefix_rejected_payload()
        review = review_h11_semantic_response(
            compact,
            prepared_units=context["units"],
            allowed_handles=context["evidence_handles"],
            contract_status="PASS",
            coverage_ok=True,
            evidence_ok=True,
            python_decision="BLOCK",
        )
        assert review["universal_guarantee_unsupported"] is True
        assert review["semantic_status"] == "PARTIAL"
        assert review["supported_claims_review"] == "FALSE_REJECTION"

    def test_reasoning_tokens_absent_are_unknown(self):
        telemetry = extract_openai_usage_telemetry(
            {"prompt_tokens": 10, "completion_tokens": 8}
        )
        assert telemetry["reasoning_tokens"] == UNKNOWN_TOKEN_COUNT
        assert telemetry["absent_is_unknown"] is True

    def test_classify_matrix(self):
        assert (
            _classify(
                remote=0,
                error_text=None,
                http_success=None,
                finish=None,
                raw_text=None,
                json_parse="n/a",
                contract_status="n/a",
                coverage_ok=False,
                evidence_ok=False,
                guarantee_unsupported=False,
                guarantee_accepted=False,
                other_false_rejections=[],
                semantic_status="n/a",
                python_decision=None,
                replay_pass=False,
                test_failures=0,
                inputs_unchanged=True,
            )
            == "BLOCKED_PRECALL"
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
                evidence_ok=True,
                guarantee_unsupported=False,
                guarantee_accepted=True,
                other_false_rejections=[],
                semantic_status="FAIL",
                python_decision="PASS",
                replay_pass=True,
                test_failures=0,
                inputs_unchanged=True,
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
                evidence_ok=True,
                guarantee_unsupported=True,
                guarantee_accepted=False,
                other_false_rejections=["u00"],
                semantic_status="PARTIAL",
                python_decision="BLOCK",
                replay_pass=True,
                test_failures=0,
                inputs_unchanged=True,
            )
            == "PARTIAL"
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
                evidence_ok=True,
                guarantee_unsupported=True,
                guarantee_accepted=False,
                other_false_rejections=[],
                semantic_status="PASS",
                python_decision="BLOCK",
                replay_pass=True,
                test_failures=0,
                inputs_unchanged=True,
            )
            == "PASS"
        )


class TestGuardsAndHygiene:
    def test_wrong_scope_is_rejected(self):
        from app.book_semantic_gate_4b215.__main__ import main

        assert main(["--authorization-scope", "WRONG", "--dry-run"]) == 2

    def test_canonical_inputs_and_book_absent(self):
        identities = verify_canonical_inputs()
        assert identities["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert identities["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert identities["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
        assert production_book_absent(PROJECT_NAME) is True

    def test_writer_does_not_touch_historical_dirs(self, tmp_path):
        from app.book_semantic_gate_4b215.paths import historical_audit_dirs

        bundle = {
            "header": {"result": "DRY_RUN", "remote_invocations": 0},
            "precall": {"phase": PHASE, "secrets_included": False},
            "request_sha256_payload": {"request_sha256": "abc"},
            "report_text": "PHASE 4B.2.15\n",
        }
        written = write_canary_artifacts(bundle, root=tmp_path)
        historical = historical_audit_dirs(root=tmp_path)
        for path in historical.values():
            assert path.exists() is False
        assert "preflight" in written
        assert LEAK_KEY not in json.dumps(bundle)

    def test_anthropic_engine_is_not_used(self):
        assert AnthropicEngine.provider_name == "anthropic"
        identified = freeze_and_identify(max_completion_tokens=7500)
        blob = json.dumps(_jsonable(identified), ensure_ascii=False)
        assert "anthropic" not in blob.lower()

    def test_precall_does_not_send(self):
        identity = build_precall()
        assert identity["http_sent"] is False
        assert identity["remote_invocations"] == 0
        assert identity["secrets_included"] is False


def _jsonable(value):
    if isinstance(value, AIRequest):
        return {"prompt_chars": len(value.prompt)}
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
