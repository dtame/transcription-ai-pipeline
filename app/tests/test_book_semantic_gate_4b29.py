"""Phase 4B.2.9 — offline Semantic Gate 2.0 candidate. Network forbidden."""

from __future__ import annotations

import pytest

from app.book_generation.pipeline import materialize_chapter
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle
from app.book_semantic_gate_4b275.constants import EXPECTED_PROMPT_113_SHA256
from app.book_semantic_gate_4b28.canaries import load_canary_bundle
from app.book_semantic_gate_4b29.benchmark import benchmark_compatibility
from app.book_semantic_gate_4b29.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    DISPUTED_CAUSAL_CLAUSE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    H01_DISPUTED_CLAUSE,
    H01_EVIDENCE_HANDLES,
    H02_EVIDENCE_HANDLES,
    H11_DISPUTED_CLAUSE,
    H11_EVIDENCE_HANDLES,
    H11_DISPUTED_CLAUSE,
    HISTORICAL_4B26_STATUS,
    HISTORICAL_4B28_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    OFFSET_CONVENTION,
    PHASE,
    PRODUCTION_PIPELINE_HOOK,
    PROJECT_NAME,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_20_CANDIDATE,
    SEMANTIC_GATE_20_ENABLED,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_20_ACTIVATED,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b29.contract import semantic_contract_20_candidate
from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b29.engine import evaluate_paragraph
from app.book_semantic_gate_4b29.fakeai import FakeAITransport, SCENARIO_NAMES, wrap_simulated
from app.book_semantic_gate_4b29.guard import BookSemanticGate29Error, validate_authorization_scope
from app.book_semantic_gate_4b29.integration import SemanticGate20IntegrationCandidate
from app.book_semantic_gate_4b29.interface import BlockedRemoteTransport, RecordedResponseTransport
from app.book_semantic_gate_4b29.policy import apply_acceptance_policy
from app.book_semantic_gate_4b29.preparation import prepare_paragraph_units
from app.book_semantic_gate_4b29.provider_safety import provider_safety
from app.book_semantic_gate_4b29.replay import replay_historical_case
from app.book_semantic_gate_4b29.request import build_model_request
from app.book_semantic_gate_4b29.runner import run_phase
from app.book_semantic_gate_4b29.validator import validate_response_20


@pytest.fixture(autouse=True)
def _no_network(no_ai_network, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("PROVIDER NETWORK FORBIDDEN")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.Client.send", forbidden)
    return None


class TestHistoricalStatus:
    def test_history_and_authorization_are_frozen(self):
        assert PHASE == "4B.2.9"
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert PROMPT_VERSION_20_ACTIVATED is False
        assert TRANSPORT_VERSION_20_ACTIVATED is False
        assert SEMANTIC_GATE_20_ENABLED is False
        assert PRODUCTION_PIPELINE_HOOK is False
        assert HISTORICAL_4B26_STATUS == "FAIL"
        assert HISTORICAL_4B28_STATUS == "PASS"
        assert HISTORICAL_H01_STATUS == "PARTIAL"
        assert HISTORICAL_H02_STATUS == "PARTIAL"
        assert HISTORICAL_H11_STATUS == "PARTIAL"
        assert PROMPT_VERSION_20_CANDIDATE == "book-semantic-validator-2.0-candidate"
        assert TRANSPORT_VERSION_20_CANDIDATE == (
            "book-semantic-validation-transport-2.0-candidate"
        )


class TestCanonicalHashes:
    def test_canonical_artifacts_match_expected(self):
        identities = verify_canonical_inputs()
        assert identities["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert identities["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert identities["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
        assert production_book_absent(PROJECT_NAME)


class TestPreparation:
    def test_simple_sentence_covers_all_characters(self):
        result = prepare_paragraph_units("p1", "Do not ever be afraid of death.")
        coverage = validate_prepared_coverage(result)
        assert result["paragraph_unchanged"] is True
        assert coverage["complete_chars"] is True
        assert result["does_not_judge_fidelity"] is True
        assert "context" not in result["units"][0]
        assert result["offset_convention"] == OFFSET_CONVENTION

    def test_multi_sentence(self):
        text = "Do not ever be afraid of death. It should be our joy."
        result = prepare_paragraph_units("p1", text)
        assert result["unit_count"] >= 2
        assert "".join(unit["text"] for unit in result["units"]) == text

    def test_causal_clause_keeps_because(self):
        text = (
            "The strategy is still being run today, because it still works "
            "wherever it is not resisted by truth."
        )
        result = prepare_paragraph_units("p1", text)
        coverage = validate_prepared_coverage(result)
        assert any("because" in unit["text"] for unit in result["units"])
        assert not coverage["connector_coverage"]["split_across_units"]

    def test_negation_not_detached(self):
        result = prepare_paragraph_units("p1", "This is not a trick of positive thinking.")
        coverage = validate_prepared_coverage(result)
        not_rows = [
            item
            for item in coverage["connector_coverage"]["occurrences"]
            if item["token"] == "not"
        ]
        assert not_rows
        assert all(item["fully_inside_one_unit"] for item in not_rows)

    def test_condition_if_preserved(self):
        result = prepare_paragraph_units(
            "p1",
            "If somebody has gone to heaven, that should not produce dread in us.",
        )
        assert any(unit["text"].startswith("If") for unit in result["units"])

    def test_adversative_em_dash(self):
        text = "Death as gain must become your reality — not an idea you agree with."
        result = prepare_paragraph_units("p1", text)
        assert validate_prepared_coverage(result)["ok"] is True
        assert result["unit_count"] >= 2

    def test_citation_and_unicode(self):
        text = "He said, “Don’t ever be afraid.” La crainte n’est pas à sa place."
        result = prepare_paragraph_units("p1", text)
        assert result["paragraph_unchanged"] is True
        assert validate_prepared_coverage(result)["complete_chars"] is True

    def test_biblical_reference_not_over_split(self):
        result = prepare_paragraph_units(
            "p1",
            "This is the ground on which 1 Corinthians 15 stands.",
        )
        assert result["unit_count"] == 1

    def test_abbreviation_does_not_split_dr(self):
        result = prepare_paragraph_units("p1", "Dr. Smith said there is no set time.")
        assert result["unit_count"] == 1

    def test_complex_punctuation(self):
        text = "Fear of death is an abuse — an abuse to your person; he has not changed."
        result = prepare_paragraph_units("p1", text)
        assert validate_prepared_coverage(result)["ok"] is True
        assert result["unit_count"] >= 2

    def test_no_punctuation_is_conservative(self):
        text = "Fear of death is an abuse to your person and the devil has used it since"
        result = prepare_paragraph_units("p1", text)
        assert result["conservative_fallback"] is True
        assert result["units"][0]["boundary_ambiguity"] is True

    def test_ambiguous_ellipsis(self):
        result = prepare_paragraph_units("p1", "Wait... is that the appointed hour?")
        coverage = validate_prepared_coverage(result)
        assert coverage["complete_chars"] is True
        assert result["ambiguous_unit_count"] or coverage["ok"]

    def test_emoji_uses_python_code_points(self):
        text = "Joy 😀 remains."
        result = prepare_paragraph_units("p1", text)
        coverage = validate_prepared_coverage(result)
        assert coverage["ok"] is True
        assert coverage["char_count"] == len(text)
        assert coverage["utf8_byte_count"] == len(text.encode("utf-8"))
        assert coverage["utf16_code_unit_count"] == len(text.encode("utf-16-le")) // 2
        assert coverage["utf8_byte_count"] != coverage["char_count"]

    def test_determinism_and_stable_ids(self):
        text = "A first sentence. A second sentence, because a clause follows."
        first = prepare_paragraph_units("p1", text)
        second = prepare_paragraph_units("p1", text)
        assert first["units"] == second["units"]
        ids = [unit["unit_id"] for unit in first["units"]]
        assert ids == [f"u{index:02d}" for index in range(len(ids))]

    def test_full_coverage_and_no_overlap(self):
        text = "One sentence. Two sentences."
        prepared = prepare_paragraph_units("p1", text)
        coverage = validate_prepared_coverage(prepared)
        assert coverage["ok"] is True
        assert not coverage["unauthorized_overlaps"]
        assert coverage["reconstructed_equals_paragraph"] is True


class TestValidationAndPolicy:
    def _prepared(self, text="Do not ever be afraid of death. It should be our joy."):
        return prepare_paragraph_units("h01", text, evidence_handles=["IDEA224"])

    def test_all_supported_is_pass(self):
        prepared = self._prepared()
        result = evaluate_paragraph(
            paragraph_id="h01",
            text=prepared["paragraph"],
            transport=FakeAITransport("all_supported", prepared),
            evidence_handles=["IDEA224"],
        )
        assert result["decision"] == "PASS"
        assert result["validation"]["ok"] is True

    def test_invalid_json_blocks(self):
        prepared = self._prepared()
        result = evaluate_paragraph(
            paragraph_id="h01",
            text=prepared["paragraph"],
            transport=FakeAITransport("invalid_json", prepared),
            evidence_handles=["IDEA224"],
        )
        assert result["decision"] == "BLOCK"
        assert "invalid_json" in result["validation"]["errors"]

    def test_missing_unit_not_completed(self):
        prepared = self._prepared()
        result = evaluate_paragraph(
            paragraph_id="h01",
            text=prepared["paragraph"],
            transport=FakeAITransport("missing_unit", prepared),
            evidence_handles=["IDEA224"],
        )
        assert result["decision"] == "BLOCK"
        assert any("missing_units" in error for error in result["validation"]["errors"])
        assert result["validation"]["does_not_complete_missing_units"] is True

    def test_duplicate_and_unknown_units_block(self):
        prepared = self._prepared()
        dup = evaluate_paragraph(
            paragraph_id="h01",
            text=prepared["paragraph"],
            transport=FakeAITransport("duplicate_unit", prepared),
            evidence_handles=["IDEA224"],
        )
        unknown = evaluate_paragraph(
            paragraph_id="h01",
            text=prepared["paragraph"],
            transport=FakeAITransport("unknown_unit", prepared),
            evidence_handles=["IDEA224"],
        )
        assert dup["decision"] == "BLOCK"
        assert unknown["decision"] == "BLOCK"

    def test_unknown_reason_and_evidence_block(self):
        prepared = self._prepared()
        reason = evaluate_paragraph(
            paragraph_id="h01",
            text=prepared["paragraph"],
            transport=FakeAITransport("unknown_reason_code", prepared),
            evidence_handles=["IDEA224"],
        )
        evidence = evaluate_paragraph(
            paragraph_id="h01",
            text=prepared["paragraph"],
            transport=FakeAITransport("unknown_evidence_handle", prepared),
            evidence_handles=["IDEA224"],
        )
        assert reason["decision"] == "BLOCK"
        assert evidence["decision"] == "BLOCK"
        assert reason["validation"]["does_not_repair_reason_codes"] is True

    def test_incoherent_global_verdict_blocks(self):
        prepared = self._prepared()
        result = evaluate_paragraph(
            paragraph_id="h01",
            text=prepared["paragraph"],
            transport=FakeAITransport("incoherent_global_verdict", prepared),
            evidence_handles=["IDEA224"],
        )
        assert result["decision"] == "BLOCK"

    def test_questionable_is_review_not_cache(self):
        prepared = self._prepared()
        result = evaluate_paragraph(
            paragraph_id="h01",
            text=prepared["paragraph"],
            transport=FakeAITransport("questionable", prepared),
            evidence_handles=["IDEA224"],
        )
        assert result["decision"] == "REVIEW"
        assert result["policy"]["production_cache_acceptance"] is False

    def test_unsupported_blocks(self):
        prepared = self._prepared()
        result = evaluate_paragraph(
            paragraph_id="h01",
            text=prepared["paragraph"],
            transport=FakeAITransport("invented_causality", prepared),
            evidence_handles=["IDEA224"],
        )
        assert result["decision"] == "BLOCK"

    def test_abusive_non_substantive_blocks(self):
        prepared = self._prepared()
        result = evaluate_paragraph(
            paragraph_id="h01",
            text=prepared["paragraph"],
            transport=FakeAITransport("abusive_non_substantive", prepared),
            evidence_handles=["IDEA224"],
        )
        assert result["decision"] == "BLOCK"

    def test_recorded_truncated_response_blocks(self):
        prepared = self._prepared()
        raw = FakeAITransport("truncated_response", prepared).evaluate({})
        validation = validate_response_20(raw, prepared, allowed_evidence=["IDEA224"])
        policy = apply_acceptance_policy(prepared, {"ok": True, "errors": []}, validation)
        assert policy["decision"] == "BLOCK"

    def test_required_fields_and_types(self):
        prepared = self._prepared()
        validation = validate_response_20({"ch": 1}, prepared, allowed_evidence=["IDEA224"])
        assert validation["ok"] is False
        assert any("ch" in error or "v" in error for error in validation["errors"])


class TestFakeAIAndReplay:
    def test_scenarios_are_labeled_simulated(self):
        wrapped = wrap_simulated({"ch": "CH016"}, "all_supported")
        assert wrapped["source"] == "FAKEAI_SIMULATED"
        assert wrapped["not_terra"] is True
        assert len(SCENARIO_NAMES) == 15

    def test_h01_h02_h11_replay(self):
        bundle = load_canary_bundle()
        for handle, clause, evidence in (
            ("h01", H01_DISPUTED_CLAUSE, H01_EVIDENCE_HANDLES),
            ("h02", DISPUTED_CAUSAL_CLAUSE, H02_EVIDENCE_HANDLES),
            ("h11", H11_DISPUTED_CLAUSE, H11_EVIDENCE_HANDLES),
        ):
            text = bundle[handle]["text"]
            prepared = prepare_paragraph_units(
                handle,
                text,
                evidence_handles=list(evidence),
            )
            coverage = validate_prepared_coverage(prepared)
            assert coverage["ok"] is True
            assert any(clause in unit["text"] for unit in prepared["units"])
        h01 = replay_historical_case("h01")
        h02 = replay_historical_case("h02")
        h11 = replay_historical_case("h11")
        assert h01["historical_status"] == "PARTIAL"
        assert h02["historical_status"] == "PARTIAL"
        assert h11["historical_status"] == "PARTIAL"
        assert h01["false_rejection_not_declared_corrected"] is True
        assert h01["historical_terra_response_not_converted"] is True

    def test_benchmark_labels_stay_local(self):
        report = benchmark_compatibility()
        assert report["labels_unmodified"] is True
        assert report["labels_absent_from_model_request"] is True
        assert report["cases_representable"] is True
        assert report["fakeai_is_orchestration_not_terra_quality"] is True


class TestContractAndRequest:
    def test_candidate_distinct_and_1_1_3_frozen(self):
        candidate = semantic_contract_20_candidate()
        assert candidate["candidate_activated"] is False
        assert candidate["historical_1_1_3_sha256"] == EXPECTED_PROMPT_113_SHA256
        assert candidate_113_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256
        assert "bargain" not in candidate["system_candidate"].lower()
        assert "h01" not in candidate["instructions_candidate"]
        for code in REASON_CODES:
            assert code in candidate["closed_catalog"]

    def test_request_omits_labels_and_offsets(self):
        prepared = prepare_paragraph_units(
            "h01",
            "Do not ever be afraid of death.",
            evidence_handles=["IDEA224"],
        )
        request = build_model_request(prepared, chapter_handle="CH016")
        payload = request["model_input"]
        assert "start_offset" not in str(payload)
        assert "SUPPORTED" not in str(payload)
        assert request["human_labels_included"] is False
        assert request["model_asked_to_emit_offsets"] is False
        assert payload["pr"][0]["t"] == prepared["paragraph"]


class TestProviderSafety:
    def test_remote_transport_fails_closed(self):
        with pytest.raises(BookSemanticGate29Error):
            BlockedRemoteTransport(provider="openai")
        with pytest.raises(BookSemanticGate29Error):
            BlockedRemoteTransport().evaluate({})
        safety = provider_safety()
        assert safety["ok"] is True
        assert safety["retries"] == 0
        assert safety["fallbacks"] == 0

    def test_recorded_transport_is_local(self):
        prepared = prepare_paragraph_units("h01", "Do not ever be afraid of death.")
        payload = FakeAITransport("all_supported", prepared).evaluate({})
        result = evaluate_paragraph(
            paragraph_id="h01",
            text=prepared["paragraph"],
            transport=RecordedResponseTransport(payload),
            evidence_handles=[],
        )
        assert result["transport_source"] == "RECORDED_SIMULATED"
        assert result["not_terra"] is True

    def test_pipeline_not_connected(self):
        assert SemanticGate20IntegrationCandidate.enabled is False
        assert SemanticGate20IntegrationCandidate.production_hook_connected is False
        assert "book_semantic_gate_4b29" not in materialize_chapter.__module__
        assert production_book_absent(PROJECT_NAME)


class TestGuards:
    def test_wrong_scope_is_rejected(self):
        with pytest.raises(BookSemanticGate29Error):
            validate_authorization_scope("WRONG")
        validate_authorization_scope(AUTHORIZATION_SCOPE)

    def test_run_phase_without_scope_is_rejected(self):
        result = run_phase(authorization_scope=None, write_artifacts=False, run_tests=False)
        assert result.mode == "REJECTED"
