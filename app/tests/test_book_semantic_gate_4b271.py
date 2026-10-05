"""Phase 4B.2.7.1 — h01 forensics and 1.1.1 calibration. Network forbidden."""

from __future__ import annotations

import json

import pytest

from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.claims import uncovered_spans
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b27.request import paragraph_context
from app.book_semantic_gate_4b271.analysis import (
    analyze_disputed_clause,
    paraphrase_boundary_matrix,
    review_human_label,
    review_src006180,
    terra_response_forensics,
)
from app.book_semantic_gate_4b271.calibration import (
    calibration_candidate,
    candidate_111_instruction_prompt,
    candidate_111_prompt_bundle,
    candidate_111_system_prompt,
    contract_comparison,
)
from app.book_semantic_gate_4b271.constants import (
    AUTHORIZED_TERRA_CALLS,
    DISPUTED_CLAUSE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B24_STATUS,
    HISTORICAL_4B241_STATUS,
    HISTORICAL_4B25_STATUS,
    HISTORICAL_4B251_STATUS,
    HISTORICAL_4B26_STATUS,
    HISTORICAL_4B261_STATUS,
    HISTORICAL_4B262_STATUS,
    HISTORICAL_4B27_STATUS,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_111,
    SELECTED_CASE_HUMAN_LABEL,
    SEMANTIC_FINDING_CODE,
    TERRA_EXECUTION_AUTHORIZED,
)
from app.book_semantic_gate_4b271.coverage import (
    KIND_SIGNIFICANT,
    KIND_TERMINATOR,
    classify_uncovered_gaps,
    uncovered_significant_spans,
    validate_compact_payload_111,
)
from app.book_semantic_gate_4b271.evidence import (
    build_canonical_evidence_inventory,
    load_saved_terra_payload,
)
from app.book_semantic_gate_4b271.fakeai import (
    historical_ten_case_protection,
    run_calibration_fixtures,
)
from app.book_semantic_gate_4b271.guard import assert_offline_only
from app.file_utils import content_hash


LEAK_KEY = "sk-SECRET-4B271-LEAK-TEST-VALUE-DO-NOT-PERSIST"


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
        assert PHASE == "4B.2.7.1"
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert HISTORICAL_4B24_STATUS == "FAIL"
        assert HISTORICAL_4B241_STATUS == "PASS"
        assert HISTORICAL_4B25_STATUS == "FAIL"
        assert HISTORICAL_4B251_STATUS == "PASS"
        assert HISTORICAL_4B26_STATUS == "FAIL"
        assert HISTORICAL_4B261_STATUS == "PASS"
        assert HISTORICAL_4B262_STATUS == "PASS"
        assert HISTORICAL_4B27_STATUS == "PARTIAL"
        assert SELECTED_CASE_HUMAN_LABEL == "SUPPORTED"

    def test_execute_real_rejected_by_cli(self):
        from app.book_semantic_gate_4b271.__main__ import main

        assert main(["--execute-real"]) == 2

    def test_canonical_inputs_unchanged(self):
        identities = verify_canonical_inputs()
        assert identities["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert identities["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert identities["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
        assert production_book_absent(PROJECT_NAME) is True


class TestFrozenContracts:
    def test_historical_prompts_unchanged(self):
        assert content_hash(system_prompt()) == EXPECTED_PROMPT_SYSTEM_SHA256
        assert content_hash(instruction_prompt()) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
        eleven = candidate_prompt_bundle()
        assert eleven["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256
        bundle = candidate_111_prompt_bundle()
        assert bundle["version"] == PROMPT_VERSION_111
        assert bundle["prompt_sha256"] != eleven["prompt_sha256"]
        assert bundle["identical_to_1_1"] is False
        assert bundle["promoted"] is False
        blob = bundle["system"] + bundle["instructions"]
        for token in ("bargaining", "bargain with", "h01", "IDEA224", "4b22_p2"):
            assert token.lower() not in blob.lower()

    def test_comparison_does_not_promote(self):
        comparison = contract_comparison()
        assert comparison["historical_contracts_modified"] is False
        assert comparison["not_promoted"] is True
        assert comparison["versions"]["1.0"]["matches_frozen_expected"] is True
        assert comparison["versions"]["1.1-candidate"]["matches_frozen_expected"] is True


class TestEvidenceAndClause:
    def test_inventory_uses_exact_canonical_texts(self):
        inventory = build_canonical_evidence_inventory()
        assert inventory["paragraph"]["exact_text"].startswith("Do not ever be afraid")
        idea = inventory["ideas"][0]
        assert idea["id"] == "IDEA224"
        assert "no set time" in idea["exact_text"]
        by_id = {row["id"]: row for row in inventory["src"]}
        assert by_id["SRC006149"]["exact_text"] == "Don't ever be afraid of death."
        assert by_id["SRC006180"]["exact_text"] == "But you can see fear"
        assert by_id["SRC006182"]["exact_text"] == "It's not normal."
        assert by_id["SRC006183"]["exact_text"] == "It should be our joy."
        assert by_id["SRC006187"]["exact_text"] == "So if somebody has gone to heaven,"
        assert all(row["gate_text_matches_canonical"] for row in inventory["src"])
        assert inventory["external_religious_knowledge_used"] is False
        neighbor_ids = {
            item["id"]
            for item in inventory["neighboring_canonical_src_not_in_gate_request"]
        }
        assert "SRC006186" in neighbor_ids

    def test_disputed_clause_finding_is_a(self):
        clause = analyze_disputed_clause()
        assert clause["clause"] == DISPUTED_CLAUSE
        assert clause["finding_code"] == SEMANTIC_FINDING_CODE
        assert clause["components"]["fear"]["classification"] == "EXPLICITLY_SUPPORTED"
        assert clause["components"]["calculate"]["classification"] == "SEMANTICALLY_ENTAILED"
        assert clause["components"]["bargain with"]["classification"] == "SEMANTICALLY_ENTAILED"
        assert clause["lexical_scan"]["bargain_or_negotiate_or_deal_in_supplied_text"] is False
        assert clause["external_knowledge_used"] is False

    def test_human_label_stays_supported(self):
        review = review_human_label()
        assert review["historical_verdict"] == "SUPPORTED"
        assert review["historical_verdict_unmodified"] is True
        assert review["benchmark_unmodified"] is True
        assert review["HUMAN_LABEL_REVIEW_RECOMMENDED"] is False

    def test_src006180_is_available_not_decisive(self):
        review = review_src006180()
        assert review["exact_text"] == "But you can see fear"
        assert review["present_in_request"] is True
        assert review["cited_by_terra"] is False
        assert review["absence_from_citations"]["proves_non_reading"] is False
        assert review["relevance_to_bargain_with"]["decisive"] is False


class TestTerraAndSpans:
    def test_terra_reservation_is_lexical(self):
        forensics = terra_response_forensics()
        assert forensics["paragraph_verdict"] == "QUESTIONABLE"
        assert forensics["disputed_claim"]["recovered_text"].startswith(
            "that fear can calculate or bargain with"
        )
        assert "bargaining is not supplied" in forensics["reservation"]
        assert forensics["reason_codes_missing_on_questionable"] is True
        assert forensics["assessment"]["excessive_lexical_match"] is True
        assert forensics["assessment"]["detects_real_addition"] is False

    def test_recorded_gaps_are_periods_not_spaces(self):
        context = paragraph_context()
        text = context["paragraph_texts"]["h01"]
        parsed = load_saved_terra_payload()
        claims = next(item["c"] for item in parsed["pr"] if item["h"] == "h01")
        historical = [{"start_offset": c["s"], "end_offset": c["e"]} for c in claims]
        gaps = uncovered_spans(text, historical)
        assert gaps == [(140, 141), (209, 210)]
        assert text[140] == "."
        assert text[209] == "."
        assert text[141] == " "
        assert text[210] == " "
        classified = classify_uncovered_gaps(text, historical)
        kinds = {item["kind"] for item in classified if item["start"] in {140, 209}}
        assert kinds == {KIND_TERMINATOR}
        assert uncovered_significant_spans(text, historical) == []
        refined = validate_compact_payload_111(
            parsed,
            paragraph_texts=context["paragraph_texts"],
            required_handles=["h01"],
            paragraph_kinds=context["paragraph_kinds"],
        )
        assert refined["status"] == "PASS"
        assert refined["frozen_1_1_status_preserved_separately"] == "FAIL"

    def test_separator_matrix_never_drops_substance(self):
        text = "Alpha  because\nnot 42 café."
        claims = [{"start_offset": 0, "end_offset": 5}]
        kinds = {
            (item["start"], item["kind"], item["text"])
            for item in classify_uncovered_gaps(text, claims)
        }
        assert any(kind == KIND_SIGNIFICANT and "because" in snippet for _, kind, snippet in kinds)
        negation = "Do not go."
        uncovered = uncovered_significant_spans(
            negation, [{"start_offset": 0, "end_offset": 2}]
        )
        assert uncovered
        assert "not" in negation[uncovered[0][0] : uncovered[0][1]]
        unicode_ok = classify_uncovered_gaps("café👍", [{"s": 0, "e": 5}])
        assert unicode_ok == []
        multi_space = uncovered_spans(
            "ab   cd",
            [{"start_offset": 0, "end_offset": 2}, {"start_offset": 5, "end_offset": 7}],
        )
        assert multi_space == []
        newline = uncovered_spans(
            "ab\ncd",
            [{"start_offset": 0, "end_offset": 2}, {"start_offset": 3, "end_offset": 5}],
        )
        assert newline == []


class TestCalibrationAndFakeAI:
    def test_boundary_matrix_protects_negatives(self):
        matrix = paraphrase_boundary_matrix()
        assert matrix["architectural_principle"].startswith("high stylistic")
        assert "P3" in matrix["categories"]["D_new_causality"]["protected_case"]
        assert "FUNERAL" in matrix["categories"]["E_invented_example"]["protected_case"]
        assert "P8" in matrix["categories"]["F_external_completion"]["protected_case"]
        assert "CONNECTIVE" in matrix["categories"]["C_new_implication"]["protected_case"]

    def test_calibration_fixtures_and_historical_negatives(self):
        fixtures = run_calibration_fixtures()
        assert fixtures["passed"] is True
        assert fixtures["h01_gold_label_not_hardcoded"] is True
        historical = historical_ten_case_protection()
        protected = historical["protected"]
        assert all(protected.values()) is True
        prompt = candidate_111_system_prompt() + candidate_111_instruction_prompt()
        assert "must include at least one reason code" in prompt
        assert LEAK_KEY not in json.dumps(calibration_candidate())


class TestSecrets:
    def test_inventory_has_no_secret(self):
        blob = json.dumps(build_canonical_evidence_inventory())
        assert LEAK_KEY not in blob
        assert "sk-" not in blob
