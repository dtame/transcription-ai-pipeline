"""Phase 4B.2.8 — offline comparative forensics. Network forbidden."""

from __future__ import annotations

import pytest

from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle
from app.book_semantic_gate_4b275.constants import EXPECTED_PROMPT_113_SHA256
from app.book_semantic_gate_4b28.canaries import load_canary_bundle
from app.book_semantic_gate_4b28.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    DISPUTED_CAUSAL_CLAUSE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    H01_DISPUTED_CLAUSE,
    H11_DISPUTED_CLAUSE,
    HISTORICAL_4B26_STATUS,
    HISTORICAL_4B277_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_20_PROPOSAL,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_20_ACTIVATED,
)
from app.book_semantic_gate_4b28.contract import semantic_contract_20_proposal
from app.book_semantic_gate_4b28.fakeai import run_offline_fixtures, segmentation_fixtures
from app.book_semantic_gate_4b28.forensics import h11_claim_forensics
from app.book_semantic_gate_4b28.guard import BookSemanticGate28Error, validate_authorization_scope
from app.book_semantic_gate_4b28.runner import run_phase
from app.book_semantic_gate_4b28.segmentation import prepare_semantic_validation_units


@pytest.fixture(autouse=True)
def _no_network(no_ai_network, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("PROVIDER NETWORK FORBIDDEN")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.Client.send", forbidden)
    return None


class TestHistoricalStatus:
    def test_history_and_authorization_are_frozen(self):
        assert PHASE == "4B.2.8"
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert PROMPT_VERSION_20_ACTIVATED is False
        assert TRANSPORT_VERSION_20_ACTIVATED is False
        assert HISTORICAL_4B26_STATUS == "FAIL"
        assert HISTORICAL_4B277_STATUS == "PARTIAL"
        assert HISTORICAL_H01_STATUS == "PARTIAL"
        assert HISTORICAL_H02_STATUS == "PARTIAL"
        assert HISTORICAL_H11_STATUS == "PARTIAL"
        assert PROMPT_VERSION_20_PROPOSAL == "book-semantic-validator-2.0-proposal"


class TestCanonicalHashes:
    def test_canonical_artifacts_match_expected(self):
        identities = verify_canonical_inputs()
        assert identities["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert identities["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert identities["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
        assert production_book_absent(PROJECT_NAME)


class TestSegmentationPrototype:
    def test_simple_sentence_covers_all_characters(self):
        text = "Do not ever be afraid of death."
        result = prepare_semantic_validation_units(text)
        assert result["paragraph_unchanged"] is True
        assert result["coverage"]["complete_chars"] is True
        assert result["does_not_judge_fidelity"] is True

    def test_multi_sentence(self):
        text = "Do not ever be afraid of death. It should be our joy."
        result = prepare_semantic_validation_units(text)
        assert result["unit_count"] >= 2
        assert "".join(unit["text"] for unit in result["units"]) == text

    def test_causal_clause_keeps_because(self):
        text = (
            "The strategy is still being run today, because it still works "
            "wherever it is not resisted by truth."
        )
        result = prepare_semantic_validation_units(text)
        because_units = [unit for unit in result["units"] if "because" in unit["text"]]
        assert because_units
        split = result["coverage"]["connector_coverage"]["split_across_units"]
        assert not [item for item in split if item["token"] == "because"]

    def test_negation_not_detached(self):
        text = "This is not a trick of positive thinking."
        result = prepare_semantic_validation_units(text)
        assert any("not" in unit["text"] for unit in result["units"])
        owners = result["coverage"]["connector_coverage"]
        not_rows = [item for item in owners["occurrences"] if item["token"] == "not"]
        assert not_rows
        assert all(item["fully_inside_one_unit"] for item in not_rows)

    def test_condition_if_preserved(self):
        text = "If somebody has gone to heaven, that should not produce dread in us."
        result = prepare_semantic_validation_units(text)
        assert any(unit["text"].startswith("If") for unit in result["units"])

    def test_em_dash_and_apostrophe(self):
        text = "Death as gain must become your reality — the substance of one’s ending."
        result = prepare_semantic_validation_units(text)
        assert result["coverage"]["complete_chars"] is True
        assert "one’s" in result["paragraph"]
        assert result["unit_count"] >= 2

    def test_unicode_and_typographic_quotes(self):
        text = "He said, “Don’t ever be afraid.”"
        result = prepare_semantic_validation_units(text)
        assert result["paragraph_unchanged"] is True
        assert result["coverage"]["complete_chars"] is True

    def test_abbreviation_does_not_split_dr(self):
        text = "Dr. Smith said there is no set time."
        result = prepare_semantic_validation_units(text)
        assert result["unit_count"] == 1

    def test_biblical_reference_not_over_split(self):
        text = "This is the ground on which 1 Corinthians 15 stands."
        result = prepare_semantic_validation_units(text)
        assert result["unit_count"] == 1

    def test_no_punctuation_is_conservative(self):
        text = "Fear of death is an abuse to your person and the devil has used it since"
        result = prepare_semantic_validation_units(text)
        assert result["conservative_fallback"] is True
        assert result["unit_count"] == 1
        assert result["units"][0]["ambiguous"] is True

    def test_determinism_and_stable_ids(self):
        text = "A first sentence. A second sentence, because a clause follows."
        first = prepare_semantic_validation_units(text)
        second = prepare_semantic_validation_units(text)
        assert first["units"] == second["units"]
        ids = [unit["id"] for unit in first["units"]]
        assert ids == [f"u{index:02d}" for index in range(len(ids))]

    def test_not_because_stays_together(self):
        text = "This is rejected not because the source is silent."
        result = prepare_semantic_validation_units(text)
        assert result["unit_count"] == 1
        assert "not because" in result["units"][0]["text"]


class TestCanaryReplay:
    def test_h01_h02_h11_paragraphs_are_fully_covered(self):
        bundle = load_canary_bundle()
        for handle in ("h01", "h02", "h11"):
            text = str(bundle[handle]["text"])
            result = prepare_semantic_validation_units(text)
            assert text
            assert result["coverage"]["complete_chars"] is True
            assert result["paragraph_unchanged"] is True

    def test_disputed_clauses_are_preserved(self):
        bundle = load_canary_bundle()
        h01 = prepare_semantic_validation_units(bundle["h01"]["text"])
        h02 = prepare_semantic_validation_units(bundle["h02"]["text"])
        h11 = prepare_semantic_validation_units(bundle["h11"]["text"])
        assert any(H01_DISPUTED_CLAUSE in unit["text"] for unit in h01["units"])
        assert any(DISPUTED_CAUSAL_CLAUSE in unit["text"] for unit in h02["units"])
        assert any(H11_DISPUTED_CLAUSE in unit["text"] for unit in h11["units"])


class TestH11CoverageGaps:
    def test_gaps_are_word_endings_not_separators(self):
        review = h11_claim_forensics()
        assert review["coverage_gaps_classification"] == (
            "SUBSTANTIVE_WORD_ENDINGS_NOT_SEPARATORS"
        )
        assert review["coverage"]["contains_substantive_characters"] is True
        assert review["coverage_innocence_not_presumed"] is True


class TestContractProposal:
    def test_proposal_is_not_activated_and_1_1_3_unchanged(self):
        proposal = semantic_contract_20_proposal()
        assert proposal["proposal_activated"] is False
        assert proposal["does_not_replace_transport_1_1"] is True
        assert proposal["historical_1_1_3_sha256"] == EXPECTED_PROMPT_113_SHA256
        assert candidate_113_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256
        assert "bargain" not in proposal["system_proposal"].lower()
        assert "h01" not in proposal["instructions_proposal"]
        for code in REASON_CODES:
            assert code in proposal["closed_catalog"]


class TestFakeAIHistorical:
    def test_ten_cases_and_segmentation_fixtures(self):
        fixtures = run_offline_fixtures()
        assert fixtures["fakeai_positives"] == 6
        assert fixtures["fakeai_negatives"] == 4
        assert fixtures["fakeai_not_terra_quality"] is True
        assert segmentation_fixtures()["passed"] is True
        protected = (fixtures.get("historical") or {}).get("protected") or {}
        assert all(protected.values())


class TestGuards:
    def test_wrong_scope_is_rejected(self):
        with pytest.raises(BookSemanticGate28Error):
            validate_authorization_scope("WRONG")
        validate_authorization_scope(AUTHORIZATION_SCOPE)

    def test_run_phase_without_scope_is_rejected(self):
        result = run_phase(authorization_scope=None, write_artifacts=False, run_tests=False)
        assert result.mode == "REJECTED"
