"""Phase 4B.2.7.4 — offline semantic gate consolidation. Network forbidden."""

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
from app.book_semantic_gate_4b274.claims import disagreement_matrix, review_h02_claims
from app.book_semantic_gate_4b274.constants import (
    AUTHORIZED_TERRA_CALLS,
    DISPUTED_CAUSAL_CLAUSE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_SOURCE_MAP,
    H01_GAPS,
    H02_GAPS,
    HISTORICAL_4B26_STATUS,
    HISTORICAL_4B261_STATUS,
    HISTORICAL_4B262_STATUS,
    HISTORICAL_4B27_STATUS,
    HISTORICAL_4B271_STATUS,
    HISTORICAL_4B272_STATUS,
    HISTORICAL_4B273_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    OVERFIT_TOKENS,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_112,
    TERRA_EXECUTION_AUTHORIZED,
)
from app.book_semantic_gate_4b274.contract import (
    candidate_112_instruction_prompt,
    candidate_112_prompt_bundle,
    candidate_112_system_prompt,
    contract_112_review,
    contract_comparison,
    transport_compatibility,
)
from app.book_semantic_gate_4b274.coverage import (
    KIND_SEPARATOR,
    KIND_SIGNIFICANT,
    classify_uncovered_gaps_112,
    uncovered_significant_spans_112,
    validate_compact_payload_112,
    validate_coverage,
)
from app.book_semantic_gate_4b274.fakeai import (
    coverage_fixtures,
    reason_code_fixtures,
    run_offline_fixtures,
)
from app.book_semantic_gate_4b274.guard import assert_offline_only
from app.book_semantic_gate_4b274.inventory import historical_canary_inventory
from app.book_semantic_gate_4b274.punctuation import punctuation_coverage_inventory
from app.book_semantic_gate_4b274.reasons import classify_reason_payload, reason_code_policy
from app.book_semantic_gate_4b274.replay import historical_response_replays
from app.file_utils import content_hash


LEAK_KEY = "sk-SECRET-4B274-LEAK-TEST-VALUE-DO-NOT-PERSIST"


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
        assert PHASE == "4B.2.7.4"
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert HISTORICAL_4B26_STATUS == "FAIL"
        assert HISTORICAL_4B261_STATUS == "PASS"
        assert HISTORICAL_4B262_STATUS == "PASS"
        assert HISTORICAL_4B27_STATUS == "PARTIAL"
        assert HISTORICAL_4B271_STATUS == "PASS"
        assert HISTORICAL_4B272_STATUS == "PASS"
        assert HISTORICAL_4B273_STATUS == "PARTIAL"
        assert HISTORICAL_H01_STATUS == "PARTIAL"
        assert HISTORICAL_H02_STATUS == "PARTIAL"

    def test_execute_real_rejected_by_cli(self):
        from app.book_semantic_gate_4b274.__main__ import main

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
        bundle = candidate_112_prompt_bundle()
        assert bundle["version"] == PROMPT_VERSION_112
        assert bundle["prompt_sha256"] != eleven["prompt_sha256"]
        assert bundle["prompt_sha256"] != c111["prompt_sha256"]
        assert bundle["identical_to_1_1_1"] is False
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
        transport = transport_compatibility()
        assert transport["new_transport_created"] is False
        assert transport["field_meanings_unchanged"] is True
        review = contract_112_review()
        assert review["promoted"] is False
        assert review["justified"] is True


class TestInventoryAndH02Claims:
    def test_historical_inventory_is_complete(self):
        inventory = historical_canary_inventory()
        assert inventory["MISSING_HISTORICAL_EVIDENCE"] is False
        assert inventory["h01"]["request_sha256_match"] is True
        assert inventory["h02"]["request_sha256_match"] is True
        assert inventory["h02"]["not_considered_pass"] is True
        assert inventory["raw_responses_not_reconstructed_from_summaries"] is True

    def test_h02_claim_review(self):
        review = review_h02_claims()
        assert review["claims_reviewed"] == 11
        assert review["human_label_unmodified"] is True
        assert review["historical_h02_not_pass"] is True
        causal = review["causal_clause"]
        assert causal["text"] == DISPUTED_CAUSAL_CLAUSE
        assert causal["correctly_isolated"] is True
        assert causal["correctly_blocked"] is True
        assert review["false_rejection_count"] == 2
        assert review["justified_reservation_count"] >= 3
        assert review["indeterminate_count"] == 1
        indices = {item["index"] for item in review["false_rejections"]}
        assert indices == {2, 5}
        matrix = disagreement_matrix(review)
        assert matrix["human_label_unmodified"] is True


class TestReasonCodes:
    def test_policy_never_silently_accepts_unknown(self):
        policy = reason_code_policy()
        assert policy["catalog_closed"] is True
        assert policy["unknown_codes_handling"] == "COMPLIANCE_FAIL_NO_SILENT_ACCEPTANCE"
        assert policy["layers"]["C_optional_normalization"]["applied_by_validator"] is False
        fixtures = reason_code_fixtures()
        assert fixtures["passed"] is True
        assert fixtures["unknown_never_silently_accepted"] is True
        unknown = classify_reason_payload(
            classification="UNSUPPORTED", reasons=["INVENTED_CAUSAL_LINK"]
        )
        assert unknown["status"] == "FAIL"
        assert unknown["normalized"] is False


class TestCoverage:
    def test_fixtures(self):
        fixtures = coverage_fixtures()
        failed = [item["name"] for item in fixtures["cases"] if not item["ok"]]
        assert failed == []
        assert fixtures["passed"] is True

    def test_h01_and_h02_real_gaps(self):
        h01_text = paragraph_context()["paragraph_texts"]["h01"]
        h02_text = load_p3_gate_paragraph()["text"]
        h01_payload = load_h01_payload()
        from app.book_semantic_gate_4b274.claims import load_saved_h02_payload

        h02_payload = load_saved_h02_payload()
        h01_claims = next(item["c"] for item in h01_payload["pr"] if item["h"] == "h01")
        h02_claims = next(item["c"] for item in h02_payload["pr"] if item["h"] == "h02")
        for start, end in H01_GAPS:
            assert h01_text[start:end] in {".", ". "} or h01_text[start] == "."
        assert h02_text[93:96] == " — "
        assert h02_text[124:126] == ", "
        assert h02_text[270:272] == "; "
        assert h02_text[404:406] == ", "
        h01_sig = uncovered_significant_spans_112(h01_text, h01_claims)
        h02_sig = uncovered_significant_spans_112(h02_text, h02_claims)
        assert h01_sig == []
        assert h02_sig == []
        h02_kinds = {
            (item["start"], item["end"], item["kind"])
            for item in classify_uncovered_gaps_112(h02_text, h02_claims)
        }
        assert any(kind == KIND_SEPARATOR for _, _, kind in h02_kinds)
        assert not any(kind == KIND_SIGNIFICANT for _, _, kind in h02_kinds)
        inventory = punctuation_coverage_inventory(
            h01_text=h01_text,
            h01_claims=h01_claims,
            h02_text=h02_text,
            h02_claims=h02_claims,
        )
        assert inventory["h01"]["coverage_1_1_2"] == "PASS"
        assert inventory["h02"]["coverage_1_1_2"] == "PASS"
        assert inventory["policy"]["do_not_strip_all_punctuation_before_validation"] is True

    def test_because_cannot_hide_behind_punctuation(self):
        text = "True, because, false."
        claims = [{"s": 0, "e": 4}, {"s": 14, "e": 20}]
        audit = validate_coverage(text, claims)
        assert audit["status"] == "FAIL"
        joined = " ".join(item["text"] for item in audit["significant_gaps"])
        assert "because" in joined


class TestReplayAndFakeAI:
    def test_replays_are_deterministic_and_do_not_rewrite_history(self):
        replays = historical_response_replays()
        assert replays["provider_calls"] == 0
        assert replays["h01"]["deterministic"] is True
        assert replays["h02"]["deterministic"] is True
        assert replays["h01"]["json_parse"] == "PASS"
        assert replays["h02"]["json_parse"] == "PASS"
        h01 = replays["h01"]["first"]
        h02 = replays["h02"]["first"]
        assert h01["historical_verdict_not_rewritten"] is True
        assert h02["raw_response_not_corrected"] is True
        assert h01["historical_semantic_verdict"]["paragraph"] == "QUESTIONABLE"
        assert h02["historical_semantic_verdict"]["paragraph"] == "UNSUPPORTED"
        assert h01["validator_1_1_1"]["status"] == "PASS"
        assert h01["validator_1_1_2"]["status"] == "FAIL"
        assert "reason_code_missing" in " ".join(h01["validator_1_1_2"]["errors"])
        assert h02["validator_1_1_1"]["status"] == "FAIL"
        assert h02["validator_1_1_2"]["status"] == "FAIL"
        assert not any(
            "significant_coverage_gap_" in str(item)
            for item in h02["validator_1_1_2"]["coverage_errors"]
        )
        assert any(
            "unknown_reason_" in str(item)
            for item in h02["validator_1_1_2"]["reason_code_errors"]
        )

    def test_ten_case_protection(self):
        fixtures = run_offline_fixtures()
        assert fixtures["passed"] is True
        assert fixtures["fakeai_positives"] == 6
        assert fixtures["fakeai_negatives"] == 4
        protected = fixtures["historical"]["protected"]
        assert all(protected.values()) is True
        prompt = candidate_112_system_prompt() + candidate_112_instruction_prompt()
        assert "closed catalog" in prompt.lower()
        assert LEAK_KEY not in json.dumps(contract_112_review())


class TestPayloadReasonMissingFails112:
    def test_empty_reason_on_questionable_fails(self):
        text = "An unsupported extension."
        payload = {
            "ch": "CH016",
            "v": "REVIEW",
            "pr": [
                {
                    "h": "hX",
                    "v": "QUESTIONABLE",
                    "c": [
                        {
                            "i": 0,
                            "s": 0,
                            "e": len(text),
                            "k": "QUESTIONABLE",
                            "ev": [],
                            "r": [],
                            "n": "no code",
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
        result = validate_compact_payload_112(
            payload,
            paragraph_texts={"hX": text},
            required_handles=["hX"],
            paragraph_kinds={"hX": "substantive"},
        )
        assert result["status"] == "FAIL"
        assert any("reason_code_missing" in item for item in result["errors"])


class TestSecrets:
    def test_inventory_has_no_secret(self):
        blob = json.dumps(historical_canary_inventory())
        assert LEAK_KEY not in blob
        assert "sk-" not in blob
