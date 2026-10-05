"""Phase 4B.2.6.1 — offline forensics. Network forbidden. 0 provider calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.openai_engine import OpenAIEngine
from app.ai.structured import parse_json_payload
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
from app.book_semantic_gate_4b24.validate import validate_semantic_response
from app.book_semantic_gate_4b261.candidates import (
    build_candidate_schema,
    candidate_instruction_prompt,
    candidate_prompt_bundle,
    candidate_system_prompt,
    expand_candidate_to_historical,
)
from app.book_semantic_gate_4b261.complexity import extract_gate_input, extract_gate_paragraphs
from app.book_semantic_gate_4b261.constants import (
    AUTHORIZED_TERRA_CALLS,
    CANDIDATE_PROMPT_VERSION,
    CANDIDATE_TRANSPORT_VERSION,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_REQUEST_SHA256_4B26,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B26_STATUS,
    MODEL,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_HISTORICAL,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_HISTORICAL,
)
from app.book_semantic_gate_4b261.contract import empty_content_is_not_accepted
from app.book_semantic_gate_4b261.evidence import load_4b26_bundle
from app.book_semantic_gate_4b261.fakeai import (
    interpret_compact_simulation,
    interpret_recorded_empty,
    simulated_compact_ten_case,
)
from app.book_semantic_gate_4b261.forensics import (
    parse_recorded_empty_response,
    raw_response_forensics,
    token_usage_analysis,
)
from app.book_semantic_gate_4b261.guard import assert_offline_only
from app.book_semantic_gate_4b261.strategies import build_candidate_payload


LEAK_KEY = "sk-SECRET-4B261-LEAK-TEST-VALUE-DO-NOT-PERSIST"


@pytest.fixture(autouse=True)
def _no_network(no_ai_network, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("PROVIDER NETWORK FORBIDDEN")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.Client.send", forbidden)
    return None


class TestPhaseGuards:
    def test_offline_and_historical_4b26_remains_fail(self):
        assert_offline_only()
        assert PHASE == "4B.2.6.1"
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert HISTORICAL_4B26_STATUS == "FAIL"
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
        from app.book_semantic_gate_4b261.__main__ import main

        assert main(["--execute-real"]) == 2

    def test_canonical_inputs_unchanged(self):
        identities = verify_canonical_inputs()
        assert identities["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert identities["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert identities["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT


class TestRawResponseForensics:
    def test_reads_recorded_empty_response_and_usage(self):
        bundle = load_4b26_bundle()
        assert bundle["request_sha256"] == EXPECTED_REQUEST_SHA256_4B26
        raw = raw_response_forensics(bundle)
        assert raw["message_content"]["visible_bytes"] == 0
        assert raw["finish_reason"]["value"] == "length"
        assert raw["json_usable"] is False
        assert raw["cases_classified"] == 0
        usage = token_usage_analysis(bundle)
        assert usage["reasoning_tokens"] == "UNKNOWN"
        assert usage["do_not_infer_reasoning_from_completion_tokens"] is True
        assert usage["usage_fields_available"]["completion_tokens_or_output_tokens"] == 8192
        assert usage["usage_fields_available"]["prompt_tokens_or_input_tokens"] == 4076
        parsed = parse_recorded_empty_response("")
        assert parsed["empty"] is True
        assert parsed["parse_failure_kind"] == "empty"
        with pytest.raises(Exception):
            parse_json_payload("")


class TestFinishReasonAndMissingCases:
    def test_length_and_empty_do_not_classify_missing_cases(self):
        assert empty_content_is_not_accepted() is True
        empty = interpret_recorded_empty()
        assert empty["json_parse"] == "FAIL"
        assert empty["classifications_issued"] == 0
        assert empty["cache_acceptance"] is False
        assert empty["missing_cases"] == [handle for handle, _ in SCORED_CASE_ORDER]
        validation = validate_semantic_response(
            None,
            required_handles=["h01", "h02"],
            paragraph_texts={"h01": "a", "h02": "b"},
        )
        assert validation["missing_cases"] == ["h01", "h02"]
        assert validation["acceptance"]["cache_acceptance"] is False


class TestCandidateContracts:
    def test_candidate_is_not_historical_and_is_deterministic(self):
        hist_system = system_prompt()
        hist_instr = instruction_prompt()
        first = candidate_prompt_bundle()
        second = candidate_prompt_bundle()
        assert first["prompt_sha256"] == second["prompt_sha256"]
        assert candidate_system_prompt() != hist_system
        assert candidate_instruction_prompt() != hist_instr
        assert first["version"] != PROMPT_VERSION_HISTORICAL
        hist_schema = build_semantic_validation_schema()
        cand_schema = build_candidate_schema()
        assert cand_schema != hist_schema
        assert "t" not in cand_schema["$defs"]["claim"]["required"]
        assert "x" not in cand_schema["$defs"]["claim"]["required"]
        assert "s" in cand_schema["$defs"]["claim"]["required"]
        assert "e" in cand_schema["$defs"]["claim"]["required"]
        assert "k" in cand_schema["$defs"]["claim"]["required"]
        assert "r" in cand_schema["$defs"]["claim"]["required"]

    def test_candidate_request_differs_from_4b26_and_has_no_label_leak(self):
        bundle = load_4b26_bundle()
        payload = build_candidate_payload(extract_gate_input(bundle["payload"]))
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        from app.file_utils import content_hash

        assert content_hash(blob) != EXPECTED_REQUEST_SHA256_4B26
        assert audit_label_leak(payload)["label_leakage"] == 0
        assert [handle for handle, _ in SCORED_CASE_ORDER] == [
            item["handle"] for item in extract_gate_paragraphs(bundle["payload"])
        ]


class TestTenCasesAndInvariants:
    def test_ten_case_ids_and_no_human_label_mutation(self):
        assert len(SCORED_CASE_ORDER) == 10
        assert len(POSITIVE_CASE_IDS) == 6
        assert len(NEGATIVE_CASE_IDS) == 4
        assert FUNERAL_CASE_ID in NEGATIVE_CASE_IDS
        assert CONNECTIVE_CASE_ID in NEGATIVE_CASE_IDS
        assert P3_CASE_ID in NEGATIVE_CASE_IDS
        assert P8_CASE_ID in NEGATIVE_CASE_IDS

    def test_compact_simulation_covers_spans_reasons_and_negatives(self):
        bundle = load_4b26_bundle()
        compact = simulated_compact_ten_case(bundle["payload"])
        assert len(compact["pr"]) == 10
        texts = {
            item["handle"]: item["text"] for item in extract_gate_paragraphs(bundle["payload"])
        }
        expanded = expand_candidate_to_historical(compact, paragraph_texts=texts)
        for para, source in zip(expanded["pr"], extract_gate_paragraphs(bundle["payload"])):
            claim = para["c"][0]
            assert claim["t"] == source["text"]
            assert claim["s"] == 0
            assert claim["e"] == len(source["text"])
            if source["src"] or source["ref"]:
                assert claim["ev"]
        result = interpret_compact_simulation(bundle["payload"])
        assert result["validation"]["case_coverage"] == "PASS"
        assert result["validation"]["span_validation"] == "PASS"
        assert result["score"]["positives_accepted"] == 6
        assert result["score"]["negatives_blocked"] == 4
        assert result["score"]["funeral_blocked"] is True
        assert result["score"]["connective_blocked"] is True
        assert result["score"]["p3_blocked"] is True
        assert result["score"]["p8_blocked"] is True
        assert result["fakeai_not_terra_quality"] is True


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
        from app.book_semantic_gate_4b261.writer import write_phase_artifacts

        write_phase_artifacts(
            {
                "header": {"result": "PASS"},
                "raw": {"phase": PHASE},
                "report_text": "# PHASE 4B.2.6.1\n",
            },
            root=tmp_path,
        )
        assert production_book_absent(PROJECT_NAME) is True
        written = tmp_path / "audit" / "book_semantic_gate_4b261"
        assert (written / "terra_4b26_raw_response_forensics.json").is_file()
        assert not any(Path(tmp_path / "sortie").rglob("book.json")) if (tmp_path / "sortie").exists() else True
        historical = Path("audit/PHASE_4B26_ONE_REAL_TERRA_SEMANTIC_GATE_CANARY_REPORT.md")
        assert historical.is_file()
        text = historical.read_text(encoding="utf-8")
        assert "RESULT = FAIL" in text

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
