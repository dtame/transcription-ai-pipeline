"""Phase 4B.2.13 — offline Book Generator × Semantic Gate 2.0 integration. Network forbidden."""

from __future__ import annotations

import pytest

from app.book_generation.pipeline import materialize_chapter
from app.book_generation.writer import production_book_absent
from app.book_generation_integration_4b213.cache import IsolatedChapterCache, validation_key
from app.book_generation_integration_4b213.chapter_validation import (
    CHAPTER_EXPECTATIONS,
    run_chapter_scenarios,
)
from app.book_generation_integration_4b213.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CODE_VERSION,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    FALLBACKS,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    INTEGRATION_CONTRACT_ACTIVATED,
    INTEGRATION_CONTRACT_VERSION,
    INTERRUPT_AFTER_BLOCK,
    INTERRUPT_AFTER_GENERATION,
    INTERRUPT_AFTER_PASS,
    INTERRUPT_AFTER_REVIEW,
    INTERRUPT_BEFORE_VALIDATION,
    INTERRUPT_DURING_VALIDATION,
    PHASE,
    PRODUCTION_PIPELINE_HOOK,
    PROJECT_NAME,
    PROMPT_VERSION_202_ACTIVATED,
    PROMPT_VERSION_202_CANDIDATE,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    RETRIES,
    SEMANTIC_GATE_202_ENABLED,
    SONNET_EXECUTION_AUTHORIZED,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_generation_integration_4b213.contract import integration_contract
from app.book_generation_integration_4b213.costing import cost_estimates
from app.book_generation_integration_4b213.fakeai import (
    BlockedRemoteIntegrationTransport,
    FakeGeneratorTransport,
    FakeSemanticTransport,
)
from app.book_generation_integration_4b213.guard import (
    BookGenerationIntegration213Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_generation_integration_4b213.invalidation import cache_invalidation
from app.book_generation_integration_4b213.orchestrator import orchestrate_chapter
from app.book_generation_integration_4b213.phase5 import phase5_interface
from app.book_generation_integration_4b213.preparation import deterministic_preparation
from app.book_generation_integration_4b213.recovery import interruption_recovery
from app.book_generation_integration_4b213.runner import run_phase
from app.book_generation_integration_4b213.safety import provider_safety
from app.book_generation_integration_4b213.structure import validate_chapter_structure
from app.book_generation_integration_4b213.traceability import traceability
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle
from app.book_semantic_gate_4b275.constants import (
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_112_SHA256,
    EXPECTED_PROMPT_113_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
)
from app.book_semantic_gate_4b29.contract import semantic_contract_20_candidate
from app.book_semantic_gate_4b210.contract import semantic_contract_201_candidate
from app.book_semantic_gate_4b212.contract import semantic_contract_202_candidate
from app.file_utils import content_hash


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
        assert PHASE == "4B.2.13"
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert SONNET_EXECUTION_AUTHORIZED is False
        assert REAL_CHAPTER_GENERATION_AUTHORIZED is False
        assert PROMPT_VERSION_202_ACTIVATED is False
        assert SEMANTIC_GATE_202_ENABLED is False
        assert PRODUCTION_PIPELINE_HOOK is False
        assert INTEGRATION_CONTRACT_ACTIVATED is False
        assert HISTORICAL_H01_STATUS == "PARTIAL"
        assert HISTORICAL_H02_STATUS == "PARTIAL"
        assert HISTORICAL_H11_STATUS == "PARTIAL"
        assert HISTORICAL_4B211_STATUS == "PARTIAL"
        assert RETRIES == 0
        assert FALLBACKS == 0
        assert PROMPT_VERSION_202_CANDIDATE == "book-semantic-validator-2.0.2-candidate"
        assert TRANSPORT_VERSION_20_CANDIDATE == (
            "book-semantic-validation-transport-2.0-candidate"
        )

    def test_execute_real_rejected_by_cli(self):
        from app.book_generation_integration_4b213.__main__ import main

        assert main(["--execute-real"]) == 2

    def test_wrong_scope_rejected(self):
        with pytest.raises(BookGenerationIntegration213Error):
            validate_authorization_scope("wrong")
        result = run_phase(
            authorization_scope=None,
            write_artifacts=False,
            run_tests=False,
        )
        assert result.mode == "REJECTED"


class TestCanonicalAndHistoricalPreservation:
    def test_canonical_artifacts_match_expected(self):
        identities = verify_canonical_inputs()
        assert identities["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert identities["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert identities["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
        assert production_book_absent(PROJECT_NAME)

    def test_historical_contracts_unmodified(self):
        assert content_hash(system_prompt()) == EXPECTED_PROMPT_SYSTEM_SHA256
        assert content_hash(instruction_prompt()) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
        assert candidate_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256
        assert candidate_111_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256
        assert candidate_112_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_112_SHA256
        assert candidate_113_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256
        frozen_20 = semantic_contract_20_candidate()
        frozen_201 = semantic_contract_201_candidate()
        consolidated = semantic_contract_202_candidate()
        assert frozen_20["candidate_activated"] is False
        assert frozen_201["candidate_activated"] is False
        assert consolidated["candidate_activated"] is False
        assert consolidated["does_not_overwrite_2_0_candidate"] is True
        assert consolidated["does_not_overwrite_2_0_1_candidate"] is True


class TestFakeAIIntegration:
    def test_generator_and_semantic_roles_are_distinct(self):
        generator = FakeGeneratorTransport("fully_supported")
        semantic = FakeSemanticTransport("fully_supported")
        assert generator.role != semantic.role
        assert generator.not_sonnet is True
        assert semantic.not_terra is True
        chapter = generator.produce_chapter()
        assert chapter["synthetic"] is True
        assert chapter["source"] == "FAKEAI_SIMULATED"

    def test_structure_and_preparation(self):
        chapter = FakeGeneratorTransport("fully_supported").produce_chapter()
        structure = validate_chapter_structure(chapter)
        assert structure["ok"] is True
        prep = deterministic_preparation(chapter=chapter)
        assert prep["ok"] is True
        assert prep["complete_coverage"] is True
        assert prep["offset_convention"] == "python3_str_unicode_code_points_half_open"

    def test_chapter_scenarios_cover_pass_review_block(self):
        result = run_chapter_scenarios()
        assert result["passed"] is True
        assert result["pass_review_block_covered"] is True
        by_name = {row["scenario"]: row for row in result["scenarios"]}
        assert by_name["fully_supported"]["decision"] == "PASS"
        assert by_name["legitimate_paraphrase"]["decision"] == "PASS"
        assert by_name["questionable"]["decision"] == "REVIEW"
        assert by_name["invented_causality"]["decision"] == "BLOCK"
        assert by_name["invented_implication"]["decision"] == "BLOCK"
        assert by_name["universal_guarantee"]["decision"] == "BLOCK"
        assert by_name["unsupported_reference"]["decision"] == "BLOCK"
        assert by_name["invalid_json"]["decision"] == "BLOCK"
        assert by_name["missing_response"]["decision"] == "BLOCK"
        assert by_name["invalid_evidence_handle"]["decision"] == "BLOCK"
        assert by_name["missing_evidence"]["decision"] == "BLOCK"
        assert CHAPTER_EXPECTATIONS["questionable"] == "REVIEW"
        for row in result["scenarios"]:
            assert row["source"] == "FAKEAI_SIMULATED"
            assert row["presented_as_validated_chapter"] is False
            if row["decision"] in {"REVIEW", "BLOCK"}:
                assert row["isolated_acceptance_candidate"] is False

    def test_pass_is_not_a_validated_production_chapter(self):
        result = orchestrate_chapter(scenario="fully_supported")
        assert result["decision"] == "PASS"
        assert result["isolated_acceptance_candidate"] is True
        assert result["presented_as_validated_chapter"] is False
        assert result["production_cache_write"] is False
        assert result["accepted_without_validation"] is False
        for para in result["paragraph_results"]:
            assert para["reconstructed_equals_paragraph"] is True
            assert para["coverage_ok"] is True


class TestCacheAndRecovery:
    def test_isolated_cache_and_invalidation(self):
        cache = IsolatedChapterCache()
        first = orchestrate_chapter(scenario="fully_supported", cache=cache)
        assert cache.reusable_as_pass(first["key"]) is True
        review = orchestrate_chapter(scenario="questionable", cache=cache)
        assert cache.reusable_as_pass(review["key"]) is False
        blocked = orchestrate_chapter(scenario="invented_causality", cache=cache)
        assert cache.reusable_as_pass(blocked["key"]) is False
        invalidation = cache_invalidation()
        assert invalidation["ok"] is True
        assert invalidation["text_change_invalidates"] is True
        assert invalidation["contract_change_invalidates"] is True
        assert invalidation["evidence_change_invalidates"] is True
        assert invalidation["historical_partial_not_converted_to_pass"] is True
        mutated = validation_key(
            generated_text_sha256="abc",
            chapter_id="SYN-CH001",
            paragraph_ids=["a"],
            source_map_sha256="x",
            editorial_plan_sha256="y",
            evidence_bundle_sha256="z",
        )
        assert mutated != first["key"]

    def test_interruption_recovery(self):
        recovery = interruption_recovery()
        assert recovery["ok"] is True
        assert recovery["no_chapter_accepted_without_validation"] is True
        assert recovery["no_invalid_result_reused_as_pass"] is True
        points = {item["interrupt_at"] for item in recovery["cases"]}
        assert points >= {
            INTERRUPT_AFTER_GENERATION,
            INTERRUPT_BEFORE_VALIDATION,
            INTERRUPT_DURING_VALIDATION,
            INTERRUPT_AFTER_PASS,
            INTERRUPT_AFTER_REVIEW,
            INTERRUPT_AFTER_BLOCK,
        }
        after_gen = next(
            item
            for item in recovery["cases"]
            if item["interrupt_at"] == INTERRUPT_AFTER_GENERATION
        )
        assert after_gen["accepted_without_validation"] is False
        assert after_gen["resume_decision"] == "PASS"


class TestTraceabilityPhase5AndSafety:
    def test_traceability_is_synthetic_and_complete(self):
        traces = traceability()
        assert traces["ok"] is True
        assert traces["synthetic_handles_only"] is True
        assert traces["does_not_fabricate_real_src"] is True
        assert traces["chains"]
        first = traces["chains"][0]
        assert first["chapter_id"]
        assert first["section_id"]
        assert first["paragraph_id"]
        assert first["unit_id"]
        assert first["presented_as_real_src"] is False

    def test_phase5_interface_is_documented_not_executed(self):
        interface = phase5_interface(orchestrate_chapter(scenario="fully_supported"))
        assert interface["executed"] is False
        assert interface["independent"] is True
        assert interface["semantic_gate_does_not_replace_phase5"] is True
        for field in (
            "chapter",
            "text",
            "structure",
            "sources",
            "evidence_handles",
            "semantic_gate_results",
            "versions",
            "hashes",
            "decisions",
            "anomalies",
            "traceability",
        ):
            assert field in interface["required_inputs"]

    def test_cost_unknown_is_not_zero(self):
        costs = cost_estimates()
        assert costs["phase5"]["status"] == "UNKNOWN"
        assert costs["phase5"]["counted_as_zero"] is False
        assert costs["total_complete_status"] == "UNKNOWN"
        assert costs["unknown_not_treated_as_zero"] is True
        assert costs["book_generator"]["central_usd"] is not None
        assert costs["semantic_gate"]["h01_canary_limit"]["not_a_19_chapter_estimate"] is True

    def test_provider_safety_blocks_remote(self):
        safety = provider_safety()
        assert safety["ok"] is True
        assert safety["imports_network"] == []
        assert safety["invokes_provider"] == []
        with pytest.raises(Exception):
            BlockedRemoteIntegrationTransport(provider="openai", model="gpt-5.6-terra")
        assert materialize_chapter.__module__ == "app.book_generation.pipeline"
        pipeline = (
            __import__("pathlib")
            .Path("app/book_generation/pipeline.py")
            .read_text(encoding="utf-8")
        )
        assert "book_generation_integration_4b213" not in pipeline

    def test_integration_contract_does_not_invent_fields(self):
        contract = integration_contract()
        assert contract["version"] == INTEGRATION_CONTRACT_VERSION
        assert contract["activated"] is False
        assert contract["does_not_invent_absent_references"] is True
        assert contract["missing_required_evidence"] == "BLOCK"
        assert "semantic_contract_version" in contract["fields_absent_from_production_chapter_candidate"]


class TestRunnerAndNonRegression:
    def test_run_phase_offline_without_nested_tests(self):
        result = run_phase(
            authorization_scope=AUTHORIZATION_SCOPE,
            write_artifacts=False,
            run_tests=False,
        )
        assert result.mode == "OFFLINE"
        header = result.bundle["header"]
        assert header["provider_calls"] == 0
        assert header["result"] in {"PASS", "PARTIAL", "FAIL", "BLOCKED"}
        assert header["semantic_contract"] == PROMPT_VERSION_202_CANDIDATE
        assert result.bundle["readiness"]["READY_FOR_ONE_REAL_CHAPTER_EXPERIMENT"] is False
        assert result.bundle["readiness"]["READY_FOR_FULL_REAL_BOOK_GENERATION"] is False
        assert CODE_VERSION == "app.book_generation_integration_4b213"

    def test_book_json_unpublished(self):
        assert production_book_absent(PROJECT_NAME)
        assert AUTHORIZATION_SCOPE.endswith("ONLY")
