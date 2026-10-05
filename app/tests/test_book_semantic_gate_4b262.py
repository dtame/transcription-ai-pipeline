"""Phase 4B.2.6.2 — offline compact single-case freeze. Network forbidden."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.openai_engine import OpenAIEngine, _usage_as_dict
from app.ai.thinking import (
    UNKNOWN_TOKEN_COUNT,
    extract_openai_usage_telemetry,
    extract_thinking_tokens_from_usage,
)
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.fakeai import fixture_supported, run_fakeai_catalog
from app.book_semantic_gate_4b23.guard import assert_offline_package
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
from app.book_semantic_gate_4b23.schema import build_semantic_validation_schema
from app.book_semantic_gate_4b24.constants import (
    CONNECTIVE_CASE_ID,
    FUNERAL_CASE_ID,
    NEGATIVE_CASE_IDS,
    P3_CASE_ID,
    P8_CASE_ID,
    POSITIVE_CASE_IDS,
    SCORED_CASE_ORDER,
)
from app.book_semantic_gate_4b24.leak import audit_label_leak
from app.book_semantic_gate_4b261.candidates import build_candidate_schema
from app.book_semantic_gate_4b261.evidence import load_4b26_bundle
from app.book_semantic_gate_4b262.constants import (
    AUTHORIZED_TERRA_CALLS,
    CANDIDATE_PROMPT_VERSION,
    CANDIDATE_TRANSPORT_VERSION,
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_REQUEST_SHA256_4B26,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B261_STATUS,
    HISTORICAL_4B26_STATUS,
    MODEL,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_HISTORICAL,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    SELECTED_CASE_ROLE,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_HISTORICAL,
)
from app.book_semantic_gate_4b262.contract import (
    candidate_instruction_prompt,
    candidate_prompt_bundle,
    candidate_system_prompt,
    compact_contract_specification,
    compact_semantic_invariants,
    unnecessary_duplication_absent,
    validate_compact_payload,
    validate_compact_span,
)
from app.book_semantic_gate_4b262.fakeai import (
    interpret_single_case_simulation,
    interpret_ten_case_compact,
    simulated_compact_single_case,
)
from app.book_semantic_gate_4b262.guard import assert_offline_only
from app.book_semantic_gate_4b262.request import (
    build_single_case_payload,
    freeze_single_case_request,
    serialize_single_case_sdk,
)
from app.book_semantic_gate_4b262.selection import evidence_manifest, review_selected_case
from app.book_semantic_gate_4b262.telemetry import run_telemetry_cases
from app.file_utils import content_hash


LEAK_KEY = "sk-SECRET-4B262-LEAK-TEST-VALUE-DO-NOT-PERSIST"


@pytest.fixture(autouse=True)
def _no_network(no_ai_network, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("PROVIDER NETWORK FORBIDDEN")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.Client.send", forbidden)
    return None


class TestPhaseGuards:
    def test_offline_and_historical_statuses(self):
        assert_offline_only()
        assert PHASE == "4B.2.6.2"
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert HISTORICAL_4B26_STATUS == "FAIL"
        assert HISTORICAL_4B261_STATUS == "PASS"
        assert PROMPT_VERSION_HISTORICAL == "book-semantic-validator-1.0"
        assert TRANSPORT_VERSION_HISTORICAL == "book-semantic-validation-transport-1.0"
        assert CANDIDATE_PROMPT_VERSION == "book-semantic-validator-1.1-candidate"
        assert CANDIDATE_TRANSPORT_VERSION == (
            "book-semantic-validation-transport-1.1-candidate"
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
        assert EXPECTED_REQUEST_SHA256_4B26 == (
            "8a92848e412763f0e67468245f9c007ee9537ffa4f2f5469af9a6934d9ebeb31"
        )

    def test_execute_real_rejected_by_cli(self):
        from app.book_semantic_gate_4b262.__main__ import main

        assert main(["--execute-real"]) == 2

    def test_canonical_inputs_unchanged(self):
        identities = verify_canonical_inputs()
        assert identities["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert identities["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert identities["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT


class TestCompactContract:
    def test_candidate_is_not_historical_and_is_deterministic(self):
        first = candidate_prompt_bundle()
        second = candidate_prompt_bundle()
        assert first["prompt_sha256"] == second["prompt_sha256"]
        assert candidate_system_prompt() != system_prompt()
        assert candidate_instruction_prompt() != instruction_prompt()
        assert first["version"] != PROMPT_VERSION_HISTORICAL
        hist_schema = build_semantic_validation_schema()
        cand_schema = build_candidate_schema()
        assert cand_schema != hist_schema
        assert "t" not in cand_schema["$defs"]["claim"]["required"]
        assert "x" not in cand_schema["$defs"]["claim"]["required"]
        for field in ("i", "s", "e", "k", "ev", "r"):
            assert field in cand_schema["$defs"]["claim"]["required"]

    def test_specification_and_invariants(self):
        spec = compact_contract_specification()
        invariants = compact_semantic_invariants()
        assert spec["prompt_version"] == CANDIDATE_PROMPT_VERSION
        assert spec["identical_to_historical"] is False
        assert spec["promoted"] is False
        assert invariants["proposition_level_control_preserved"] is True
        assert invariants["do_not_drop_claim_coverage_to_save_tokens"] is True
        assert invariants["valid_offset_is_not_semantic_support"] is True


class TestSpans:
    def test_offsets_unicode_empty_and_inconsistent(self):
        text = "café👍"
        ok = validate_compact_span(text, 0, len(text))
        assert ok["valid"] is True
        assert ok["recovered_text"] == text
        assert validate_compact_span(text, 0, 0)["errors"] == ["empty_span"]
        assert "end_before_start" in validate_compact_span(text, 3, 1)["errors"]
        assert "end_out_of_bounds" in validate_compact_span(text, 0, 99)["errors"]
        accent = validate_compact_span("é", 0, 1)
        assert accent["valid"] is True
        assert accent["span_code_points"] == 1
        assert ok["valid_offset_is_not_semantic_support"] is True

    def test_valid_span_is_not_semantic_proof(self):
        payload = {
            "ch": "CH016",
            "v": "PASS",
            "pr": [
                {
                    "h": "h01",
                    "v": CLASS_SUPPORTED,
                    "c": [
                        {
                            "i": 0,
                            "s": 0,
                            "e": 3,
                            "k": CLASS_SUPPORTED,
                            "ev": ["SRC001"],
                            "r": [],
                        }
                    ],
                    "ev": ["SRC001"],
                    "r": [],
                }
            ],
            "sc": {
                "supported": 1,
                "questionable": 0,
                "unsupported": 0,
                "non_substantive": 0,
            },
            "uh": [],
            "rr": False,
        }
        result = validate_compact_payload(
            payload,
            paragraph_texts={"h01": "abc def"},
            required_handles=["h01"],
            paragraph_kinds={"h01": "substantive"},
        )
        assert result["status"] == "FAIL"
        assert any("coverage_gap" in item for item in result["coverage_errors"])


class TestCaseSelectionAndEvidence:
    def test_h01_is_positive_supported_and_justified(self):
        review = review_selected_case()
        assert review["selected_handle"] == SELECTED_CASE_HANDLE == "h01"
        assert review["selected_case_id"] == SELECTED_CASE_ID == "4b22_p2_supported"
        assert review["selected_case_role"] == SELECTED_CASE_ROLE == "positive"
        assert review["human_label_audit_only"]["expected_class"] == SELECTED_CASE_HUMAN_LABEL
        assert review["case_changed"] is False
        assert review["selected"] is True
        assert review["size"]["chars"] > 0
        assert review["if_negative_would_also_show_blocking"] is False

    def test_evidence_complete_and_labels_not_in_request(self):
        evidence = evidence_manifest()
        assert evidence["complete"] is True
        assert evidence["other_cases_excluded"] is True
        payload = build_single_case_payload()
        leak = audit_label_leak(payload)
        assert leak["pass"] is True
        assert SELECTED_CASE_ID not in json.dumps(payload)
        assert "human_label" not in json.dumps(payload).lower()


class TestSingleCaseRequest:
    def test_exactly_one_case_deterministic_and_distinct(self):
        frozen = freeze_single_case_request()
        assert frozen["exactly_one_case"] is True
        assert frozen["handles_in_request"] == [SELECTED_CASE_HANDLE]
        assert frozen["determinism"] is True
        assert frozen["first_sha256"] == frozen["second_sha256"]
        assert frozen["differs_from_4b26"] is True
        assert frozen["sha256"] != EXPECTED_REQUEST_SHA256_4B26
        assert frozen["model"] == MODEL
        assert frozen["payload"]["max_completion_tokens"] == 8192
        assert "max_tokens" not in frozen["payload"]
        assert "temperature" not in frozen["payload"]
        assert frozen["payload"]["response_format"] == {"type": "json_object"}
        assert frozen["label_leak_pass"] is True

    def test_sdk_serialization_has_zero_network(self):
        captured = serialize_single_case_sdk()
        assert captured["network_calls"] == 0
        assert captured["http_requests"] == 0
        assert captured["serialization_pass"] is True
        assert captured["checks"]["max_completion_tokens"] is True
        assert captured["checks"]["max_tokens_absent"] is True
        assert captured["checks"]["temperature_absent"] is True
        assert captured["checks"]["json_object"] is True
        assert captured["secrets_included"] is False


class TestTenCasesAndNegatives:
    def test_ten_case_ids_unmodified(self):
        assert len(SCORED_CASE_ORDER) == 10
        assert len(POSITIVE_CASE_IDS) == 6
        assert len(NEGATIVE_CASE_IDS) == 4
        assert FUNERAL_CASE_ID in NEGATIVE_CASE_IDS
        assert CONNECTIVE_CASE_ID in NEGATIVE_CASE_IDS
        assert P3_CASE_ID in NEGATIVE_CASE_IDS
        assert P8_CASE_ID in NEGATIVE_CASE_IDS

    def test_compact_simulation_covers_all_historical_cases(self):
        bundle = load_4b26_bundle()
        ten = interpret_ten_case_compact(bundle["payload"])
        assert ten["validation"]["status"] == "PASS"
        assert ten["no_unnecessary_duplication"] is True
        assert ten["score"]["positives_accepted"] == 6
        assert ten["score"]["negatives_blocked"] == 4
        assert ten["score"]["funeral_blocked"] is True
        assert ten["score"]["connective_blocked"] is True
        assert ten["score"]["p3_blocked"] is True
        assert ten["score"]["p8_blocked"] is True
        assert unnecessary_duplication_absent(ten["compact"]) is True
        one_payload = build_single_case_payload()
        one = interpret_single_case_simulation(one_payload)
        assert one["validation"]["status"] == "PASS"
        assert one["compact"]["pr"][0]["h"] == SELECTED_CASE_HANDLE
        assert simulated_compact_single_case(one_payload)["pr"][0]["v"] == CLASS_SUPPORTED


class TestReasoningTelemetry:
    def test_reasoning_tokens_present_absent_zero_and_details(self):
        present = extract_openai_usage_telemetry(
            {
                "prompt_tokens": 5,
                "completion_tokens": 9,
                "completion_tokens_details": {"reasoning_tokens": 4},
            }
        )
        assert present["reasoning_tokens"] == 4
        assert present["input_tokens"] == 5
        assert present["completion_tokens"] == 9
        assert present["visible_output_tokens"] == UNKNOWN_TOKEN_COUNT
        assert extract_thinking_tokens_from_usage(
            {"completion_tokens_details": {"reasoning_tokens": 4}}
        ) == 4
        absent = extract_openai_usage_telemetry({"prompt_tokens": 1, "completion_tokens": 2})
        assert absent["reasoning_tokens"] == UNKNOWN_TOKEN_COUNT
        assert extract_thinking_tokens_from_usage({"prompt_tokens": 1}) is None
        zero = extract_openai_usage_telemetry(
            {"completion_tokens_details": {"reasoning_tokens": 0}}
        )
        assert zero["reasoning_tokens"] == 0
        historical = extract_thinking_tokens_from_usage(
            {"output_tokens_details": {"thinking_tokens": 11}}
        )
        assert historical == 11
        persisted = _usage_as_dict(
            type(
                "U",
                (),
                {
                    "prompt_tokens": 3,
                    "completion_tokens": 6,
                    "total_tokens": 9,
                    "completion_tokens_details": type(
                        "D", (), {"reasoning_tokens": 2}
                    )(),
                },
            )()
        )
        assert persisted["completion_tokens_details"]["reasoning_tokens"] == 2
        suite = run_telemetry_cases()
        assert suite["passed"] is True
        assert suite["network_calls"] == 0


class TestAnthropicAndPublication:
    def test_anthropic_still_uses_max_tokens(self):
        engine = AnthropicEngine(api_key="offline-anthropic-unused", model="claude-sonnet-5")
        payload = engine.build_payload(
            AIRequest(prompt="offline anthropic regression", model="claude-sonnet-5"),
            "claude-sonnet-5",
        )
        assert payload["max_tokens"] > 0
        assert "max_completion_tokens" not in payload

    def test_historical_fakeai_and_no_book_json(self, tmp_path):
        assert_offline_package()
        catalog = run_fakeai_catalog()
        assert catalog["passed"] is True
        assert fixture_supported()["parsed"]
        from app.book_semantic_gate_4b262.writer import write_phase_artifacts

        write_phase_artifacts(
            {
                "header": {"result": "PASS"},
                "contract": {"phase": PHASE},
                "report_text": "# PHASE 4B.2.6.2\n",
            },
            root=tmp_path,
        )
        assert production_book_absent(PROJECT_NAME) is True
        written = tmp_path / "audit" / "book_semantic_gate_4b262"
        assert (written / "compact_contract_11_specification.json").is_file()
        assert not any(Path(tmp_path / "sortie").rglob("book.json")) if (
            tmp_path / "sortie"
        ).exists() else True
        historical = Path("audit/PHASE_4B26_ONE_REAL_TERRA_SEMANTIC_GATE_CANARY_REPORT.md")
        assert historical.is_file()
        assert "RESULT = FAIL" in historical.read_text(encoding="utf-8")

    def test_openai_engine_does_not_call_network_when_building_payload(self):
        engine = OpenAIEngine(api_key=LEAK_KEY, client=object())
        payload = engine.build_payload(
            AIRequest(
                prompt="offline",
                system_prompt="auditor",
                model=MODEL,
                max_output_tokens=8192,
                response_schema={"type": "object"},
            ),
            MODEL,
        )
        assert payload["max_completion_tokens"] == 8192
        assert payload["response_format"] == {"type": "json_object"}
        assert LEAK_KEY not in json.dumps(payload)
        assert content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


class TestCompactEscapeHatchAndReasons:
    def test_non_substantive_cannot_skip_substantive_paragraph(self):
        text = "A substantive pastoral claim about death."
        payload = {
            "ch": "CH016",
            "v": "PASS",
            "pr": [
                {
                    "h": "h01",
                    "v": CLASS_NON_SUBSTANTIVE,
                    "c": [
                        {
                            "i": 0,
                            "s": 0,
                            "e": len(text),
                            "k": CLASS_NON_SUBSTANTIVE,
                            "ev": [],
                            "r": [],
                        }
                    ],
                    "ev": [],
                    "r": [],
                }
            ],
            "sc": {
                "supported": 0,
                "questionable": 0,
                "unsupported": 0,
                "non_substantive": 1,
            },
            "uh": [],
            "rr": False,
        }
        result = validate_compact_payload(
            payload,
            paragraph_texts={"h01": text},
            required_handles=["h01"],
            paragraph_kinds={"h01": "substantive"},
        )
        assert result["status"] == "FAIL"
        assert any("escape_hatch" in item for item in result["claim_errors"])

    def test_questionable_requires_reason_and_note(self):
        text = "Because it still works wherever it is not resisted by truth."
        payload = {
            "ch": "CH016",
            "v": "REVIEW",
            "pr": [
                {
                    "h": "h02",
                    "v": CLASS_QUESTIONABLE,
                    "c": [
                        {
                            "i": 0,
                            "s": 0,
                            "e": len(text),
                            "k": CLASS_QUESTIONABLE,
                            "ev": [],
                            "r": [],
                        }
                    ],
                    "ev": [],
                    "r": [],
                }
            ],
            "sc": {
                "supported": 0,
                "questionable": 1,
                "unsupported": 0,
                "non_substantive": 0,
            },
            "uh": [],
            "rr": True,
        }
        result = validate_compact_payload(
            payload,
            paragraph_texts={"h02": text},
            required_handles=["h02"],
            paragraph_kinds={"h02": "substantive"},
        )
        assert result["status"] == "FAIL"
        assert any("reservation_required" in item for item in result["claim_errors"])
