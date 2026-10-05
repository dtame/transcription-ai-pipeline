"""Phase 4B.2.7.5 — offline semantic gate 1.1.2 stabilization. Network forbidden."""

from __future__ import annotations

import json

import pytest

from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b27.request import paragraph_context
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b271.evidence import load_saved_terra_payload as load_h01_payload
from app.book_semantic_gate_4b272.identity import load_p3_gate_paragraph
from app.book_semantic_gate_4b274.claims import load_saved_h02_payload
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle
from app.book_semantic_gate_4b274.coverage import uncovered_significant_spans_112
from app.file_utils import content_hash
from app.book_semantic_gate_4b275.canary import future_canary_selection_criteria
from app.book_semantic_gate_4b275.catalog import reason_code_catalog
from app.book_semantic_gate_4b275.constants import (
    AUTHORIZED_TERRA_CALLS,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_112_SHA256,
    EXPECTED_PROMPT_113_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_SOURCE_MAP,
    H02_INDETERMINATE_CLAIM,
    HISTORICAL_4B26_STATUS,
    HISTORICAL_4B261_STATUS,
    HISTORICAL_4B262_STATUS,
    HISTORICAL_4B27_STATUS,
    HISTORICAL_4B271_STATUS,
    HISTORICAL_4B272_STATUS,
    HISTORICAL_4B273_STATUS,
    HISTORICAL_4B274_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    OVERFIT_TOKENS,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_112,
    PROMPT_VERSION_113,
    TERRA_EXECUTION_AUTHORIZED,
    UNKNOWN_CODE_POLICY,
)
from app.book_semantic_gate_4b275.contract import (
    candidate_113_instruction_prompt,
    candidate_113_prompt_bundle,
    candidate_113_system_prompt,
    contract_113_review,
    contract_comparison,
    contract_inventory,
    transport_compatibility,
)
from app.book_semantic_gate_4b275.coverage import validate_compact_payload_113
from app.book_semantic_gate_4b275.diagnostic import extract_failure_diagnostic
from app.book_semantic_gate_4b275.fakeai import additional_fixtures, run_offline_fixtures
from app.book_semantic_gate_4b275.guard import assert_offline_only
from app.book_semantic_gate_4b275.indeterminate import review_h02_indeterminate_claim
from app.book_semantic_gate_4b275.matrix import verdict_reason_code_matrix
from app.book_semantic_gate_4b275.replay import historical_response_replays
from app.book_semantic_gate_4b275.unknown import diagnose_unknown_codes, unknown_reason_code_policy
from app.book_semantic_gate_4b275.verdicts import verdict_definitions_review


LEAK_KEY = "sk-SECRET-4B275-LEAK-TEST-VALUE-DO-NOT-PERSIST"


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
        assert PHASE == "4B.2.7.5"
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert HISTORICAL_4B26_STATUS == "FAIL"
        assert HISTORICAL_4B261_STATUS == "PASS"
        assert HISTORICAL_4B262_STATUS == "PASS"
        assert HISTORICAL_4B27_STATUS == "PARTIAL"
        assert HISTORICAL_4B271_STATUS == "PASS"
        assert HISTORICAL_4B272_STATUS == "PASS"
        assert HISTORICAL_4B273_STATUS == "PARTIAL"
        assert HISTORICAL_4B274_STATUS == "PASS"
        assert HISTORICAL_H01_STATUS == "PARTIAL"
        assert HISTORICAL_H02_STATUS == "PARTIAL"

    def test_execute_real_rejected_by_cli(self):
        from app.book_semantic_gate_4b275.__main__ import main

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
        c111 = candidate_111_prompt_bundle()
        assert c111["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256
        c112 = candidate_112_prompt_bundle()
        assert c112["version"] == PROMPT_VERSION_112
        assert c112["prompt_sha256"] == EXPECTED_PROMPT_112_SHA256
        bundle = candidate_113_prompt_bundle()
        assert bundle["version"] == PROMPT_VERSION_113
        assert bundle["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256
        assert bundle["prompt_sha256"] != c112["prompt_sha256"]
        assert bundle["identical_to_1_1_2"] is False
        assert bundle["promoted"] is False
        blob = bundle["system"] + bundle["instructions"]
        for token in OVERFIT_TOKENS:
            assert token.lower() not in blob.lower()
        for code in REASON_CODES:
            assert code in bundle["system"]

    def test_comparison_does_not_promote(self):
        comparison = contract_comparison()
        assert comparison["historical_contracts_modified"] is False
        assert comparison["not_promoted"] is True
        assert comparison["versions"]["1.0"]["matches_frozen_expected"] is True
        assert comparison["versions"]["1.1-candidate"]["matches_frozen_expected"] is True
        assert comparison["versions"]["1.1.1-candidate"]["matches_frozen_expected"] is True
        assert comparison["versions"]["1.1.2-candidate"]["matches_frozen_expected"] is True
        inventory = contract_inventory()
        assert inventory["silent_1_1_2_modification"] is False
        transport = transport_compatibility()
        assert transport["new_transport_created"] is False
        assert transport["indeterminate_not_a_provider_verdict"] is True
        review = contract_113_review()
        assert review["promoted"] is False
        assert review["justified"] is True
        assert review["candidate_1_1_2_unmodified"] is True


class TestVerdictsAndIndeterminate:
    def test_operational_definitions(self):
        review = verdict_definitions_review()
        assert review["coherence"] == "PASS"
        assert review["paraphrase_may_be_supported"] is True
        assert review["questionable_and_unsupported_block_acceptance"] is True
        assert review["non_substantive_cannot_mask_meaning"] is True
        assert "INDETERMINATE" in review["human_review_only"]

    def test_h02_indeterminate_not_forced(self):
        review = review_h02_indeterminate_claim()
        assert review["exact_text"] == H02_INDETERMINATE_CLAIM
        assert review["text_match"] is True
        assert review["human_label_unmodified"] is True
        assert review["human_review_conclusion"] == "INDETERMINATE"
        assert review["conclusion_forced"] is False
        assert review["conclusion_is_not_a_provider_verdict"] is True
        assert review["terra_verdict"] == "QUESTIONABLE"
        axes = review["five_axis_review"]
        assert axes["factual_assertion"]["present"] == "PARTIAL_PRESUPPOSITION"
        assert axes["origin_attribution"]["assigns_a_named_origin"] is False


class TestCatalogAndMatrix:
    def test_closed_catalog(self):
        catalog = reason_code_catalog()
        assert catalog["catalog_closed"] is True
        assert catalog["no_code_invented"] is True
        assert catalog["no_historical_code_removed"] is True
        assert catalog["codes"] == list(REASON_CODES)
        assert len(catalog["entries"]) == len(REASON_CODES)

    def test_unknown_policy_blocks(self):
        policy = unknown_reason_code_policy()
        assert policy["unknown_codes_handling"] == UNKNOWN_CODE_POLICY
        assert policy["never"]["silently_rewrite_code"] is True
        unknown = diagnose_unknown_codes("UNSUPPORTED", ["INVENTED_CAUSAL_LINK"])
        assert unknown["acceptance"] == "FAIL"
        assert unknown["silently_rewritten"] is False
        assert unknown["raw_codes_unmodified"] == ["INVENTED_CAUSAL_LINK"]

    def test_matrix_structural_vs_semantic(self):
        matrix = verdict_reason_code_matrix()
        assert matrix["structural_passed"] is True
        names = {item["name"]: item for item in matrix["structural_cases"]}
        assert names["supported_with_blocking_reason"]["observed"] == "FAIL"
        assert names["questionable_without_reason"]["observed"] == "FAIL"
        assert names["unsupported_without_reason"]["observed"] == "FAIL"
        assert names["unknown_code"]["observed"] == "FAIL"
        assert names["valid_code_semantically_inconsistent"]["observed"] == "PASS"


class TestCoverageAndDiagnostic:
    def test_h01_h02_coverage_and_diagnostic(self):
        h01_text = paragraph_context()["paragraph_texts"]["h01"]
        h02_text = load_p3_gate_paragraph()["text"]
        h01_payload = load_h01_payload()
        h02_payload = load_saved_h02_payload()
        h01_claims = next(item["c"] for item in h01_payload["pr"] if item["h"] == "h01")
        h02_claims = next(item["c"] for item in h02_payload["pr"] if item["h"] == "h02")
        assert uncovered_significant_spans_112(h01_text, h01_claims) == []
        assert uncovered_significant_spans_112(h02_text, h02_claims) == []
        h01_diag = extract_failure_diagnostic(
            h01_payload,
            paragraph_texts={"h01": h01_text},
            required_handles=["h01"],
            paragraph_kinds={"h01": "substantive"},
        )
        h02_diag = extract_failure_diagnostic(
            h02_payload,
            paragraph_texts={"h02": h02_text},
            required_handles=["h02"],
            paragraph_kinds={"h02": "substantive"},
        )
        assert h01_diag["acceptance"] == "FAIL"
        assert h02_diag["acceptance"] == "FAIL"
        assert h01_diag["diagnostic_is_not_acceptance"] is True
        assert h02_diag["diagnostic"]["unknown_reason_codes"]
        assert h02_diag["diagnostic"]["analyzable_propositions"]
        assert not h02_diag["diagnostic"]["coverage_errors"]
        h01_v113 = validate_compact_payload_113(
            h01_payload,
            paragraph_texts={"h01": h01_text},
            required_handles=["h01"],
            paragraph_kinds={"h01": "substantive"},
        )
        assert h01_v113["status"] == "FAIL"
        assert any("reason_code_missing" in item for item in h01_v113["errors"])


class TestReplayAndFakeAI:
    def test_replays_preserve_history(self):
        replays = historical_response_replays()
        assert replays["provider_calls"] == 0
        assert replays["h01"]["deterministic"] is True
        assert replays["h02"]["deterministic"] is True
        assert replays["h01"]["historical_status_preserved"] == "PARTIAL"
        assert replays["h02"]["historical_status_preserved"] == "PARTIAL"
        assert replays["h01"]["json_parse"] == "PASS"
        assert replays["h02"]["json_parse"] == "PASS"
        assert replays["h01"]["first"]["historical_semantic_verdict"]["paragraph"] == "QUESTIONABLE"
        assert replays["h02"]["first"]["historical_semantic_verdict"]["paragraph"] == "UNSUPPORTED"
        assert replays["h01"]["validator_1_1_3"]["status"] == "FAIL"
        assert replays["h02"]["validator_1_1_3"]["status"] == "FAIL"
        assert replays["h01"]["diagnostic"]["diagnostic_is_not_acceptance"] is True
        assert replays["h02"]["diagnostic"]["unknown_reason_codes"]

    def test_ten_case_protection_and_additional(self):
        fixtures = run_offline_fixtures()
        assert fixtures["passed"] is True
        assert fixtures["fakeai_positives"] == 6
        assert fixtures["fakeai_negatives"] == 4
        additional = additional_fixtures()
        failed = [item["name"] for item in additional["cases"] if not item["ok"]]
        assert failed == []
        prompt = candidate_113_system_prompt() + candidate_113_instruction_prompt()
        assert "closed catalog" in prompt.lower()
        assert "NON_SUBSTANTIVE" in prompt
        assert LEAK_KEY not in json.dumps(contract_113_review())


class TestCanaryAndSecrets:
    def test_future_canary_not_sent(self):
        criteria = future_canary_selection_criteria()
        assert criteria["not_built"] is True
        assert criteria["not_sent"] is True
        ids = {item["id"] for item in criteria["criteria"]}
        assert ids == {
            "independence",
            "informative_value",
            "clear_evidence",
            "low_benchmark_ambiguity",
            "cost_control",
            "unresolved_failure",
        }

    def test_no_secret_leak(self):
        blob = json.dumps(contract_inventory())
        assert LEAK_KEY not in blob
        assert "sk-" not in blob
