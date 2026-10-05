"""Phase 4B.2.14 — offline production bridge and cost preflight. Network forbidden."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.book_generation.pipeline import materialize_chapter
from app.book_generation.writer import production_book_absent
from app.book_generation_bridge_4b214.adapter import adapt_chapter_candidate
from app.book_generation_bridge_4b214.adapter_validation import adapter_validation
from app.book_generation_bridge_4b214.architecture import bridge_architecture
from app.book_generation_bridge_4b214.authorization import (
    mint_synthetic_authorization,
    consume_authorization,
)
from app.book_generation_bridge_4b214.budget import BudgetGuard
from app.book_generation_bridge_4b214.budget_tests import (
    budget_reconciliation_tests,
    budget_reservation_tests,
)
from app.book_generation_bridge_4b214.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    BRIDGE_ENABLED,
    BRIDGE_ENABLED_BY_DEFAULT,
    CANDIDATE_GRANULARITY,
    CODE_VERSION,
    COST_UNKNOWN,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    FALLBACKS,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    LEDGER_GLOBAL,
    LEDGER_SEMANTIC_GATE,
    PHASE,
    PRODUCTION_PIPELINE_HOOK,
    PROJECT_NAME,
    PROMPT_VERSION_202_ACTIVATED,
    PROMPT_VERSION_202_CANDIDATE,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    REAL_PROVIDERS_ENABLED,
    RETRIES,
    SEMANTIC_GATE_202_ENABLED,
    SONNET_EXECUTION_AUTHORIZED,
    STRATEGY_A,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_generation_bridge_4b214.costing import cost_estimates
from app.book_generation_bridge_4b214.granularity import validation_granularity
from app.book_generation_bridge_4b214.guard import (
    BookGenerationBridge214Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_generation_bridge_4b214.idempotence import idempotence
from app.book_generation_bridge_4b214.orchestrator import run_bridge_chapter
from app.book_generation_bridge_4b214.phase5 import phase5_boundary
from app.book_generation_bridge_4b214.recovery import interruption_recovery
from app.book_generation_bridge_4b214.review import apply_human_review
from app.book_generation_bridge_4b214.runner import run_phase
from app.book_generation_bridge_4b214.safety import provider_safety
from app.book_generation_bridge_4b214.scenarios import request_volume_scenarios
from app.book_generation_bridge_4b214.single_chapter import SingleChapterMode
from app.book_generation_bridge_4b214.traceability import traceability
from app.book_generation_bridge_4b214.volumes import canonical_volume_inventory
from app.book_generation_integration_4b213.chapter_validation import run_chapter_scenarios
from app.book_generation_integration_4b213.fakeai import (
    BlockedRemoteIntegrationTransport,
    FakeGeneratorTransport,
)
from app.book_generation_integration_4b213.preparation import deterministic_preparation
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
    def test_bridge_disabled_by_default(self):
        assert_offline_only()
        assert PHASE == "4B.2.14"
        assert BRIDGE_ENABLED is False
        assert BRIDGE_ENABLED_BY_DEFAULT is False
        assert PRODUCTION_PIPELINE_HOOK is False
        assert REAL_PROVIDERS_ENABLED is False
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert SONNET_EXECUTION_AUTHORIZED is False
        assert REAL_CHAPTER_GENERATION_AUTHORIZED is False
        assert PROMPT_VERSION_202_ACTIVATED is False
        assert SEMANTIC_GATE_202_ENABLED is False
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

    def test_import_has_no_side_effects(self):
        import app.book_generation_bridge_4b214 as pkg

        assert pkg.BRIDGE_ENABLED is False
        assert pkg.PRODUCTION_PIPELINE_HOOK is False

    def test_execute_real_rejected_by_cli(self):
        from app.book_generation_bridge_4b214.__main__ import main

        assert main(["--execute-real"]) == 2

    def test_wrong_scope_rejected(self):
        with pytest.raises(BookGenerationBridge214Error):
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
        assert identities["clean_transcript"]["path"].endswith(
            "transcripts/clean/transcript_data.json"
        )
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


class TestAdapterAndPreparation:
    def test_adapter_real_data_and_failures(self):
        result = adapter_validation()
        assert result["ok"] is True
        assert result["real_data_without_generated_paragraphs"]["ok"] is False
        assert result["missing_data_blocks"] is True
        assert result["invalid_evidence_handle_blocks"] is True
        assert result["does_not_invent_src"] is True
        assert result["canonical_objects_mutated"] is False

    def test_deterministic_preparation_and_coverage(self):
        chapter = FakeGeneratorTransport("fully_supported").produce_chapter()
        adapted = adapt_chapter_candidate(chapter, synthetic=True)
        assert adapted["ok"] is True
        prep = deterministic_preparation(chapter=chapter)
        assert prep["ok"] is True
        assert prep["complete_coverage"] is True

    def test_missing_evidence_blocks(self):
        result = run_bridge_chapter(scenario="missing_evidence")
        assert result["decision"] == "BLOCK"


class TestGranularityAndVolumes:
    def test_strategy_a_is_candidate_and_b_not_declared_compatible(self):
        gran = validation_granularity()
        assert gran["candidate"]["strategy"] == STRATEGY_A == CANDIDATE_GRANULARITY
        assert gran["strategy_a"]["compatible_with_validate_response_202"] is True
        assert gran["strategy_b"]["compatible_with_current_validator_without_change"] is False
        assert gran["strategy_b"]["compatible_declared_without_verification"] is False
        assert gran["strategy_c"]["compatible_with_validate_response_202"] is False
        assert gran["candidate"]["validated_on_terra"] is False

    def test_canonical_volumes_and_unknown_paragraphs(self):
        volumes = canonical_volume_inventory()
        assert volumes["chapters"] == 19
        assert volumes["sections"] == 72
        assert volumes["plan_stats"]["assigned_idea_count"] == 286
        assert volumes["paragraphs_status"] == "UNKNOWN"
        assert volumes["paragraphs_counted_as_zero"] is False
        assert volumes["language"] == "en"
        scenarios = request_volume_scenarios(volumes)
        assert scenarios["strategy_a"]["requests_central"] == 72 * 4
        assert scenarios["unknown"]["counted_as_zero"] is False


class TestBudget:
    def test_sufficient_insufficient_unknown_reservation(self):
        result = budget_reservation_tests()
        assert result["ok"] is True
        assert result["sufficient"]["authorized"] is True
        assert result["insufficient"]["authorized"] is False
        assert result["unknown"]["reason"] == "cost_unknown_blocks_execution"
        assert result["unknown"]["counted_as_zero"] is False

    def test_reconciliation_cases(self):
        result = budget_reconciliation_tests()
        assert result["ok"] is True
        assert result["cases"]["interrupt_after_send"]["reconciled"]["not_treated_as_free"] is True
        assert result["cases"]["usage_absent"]["reconciled"]["counted_as_zero"] is False
        assert result["cases"]["truncated"]["reconciled"]["counted_as_zero"] is False
        assert result["cases"]["full_known"]["replay"]["idempotent"] is True

    def test_cost_unknown_is_not_zero(self):
        costs = cost_estimates()
        assert costs["phase5"]["status"] == COST_UNKNOWN
        assert costs["phase5"]["counted_as_zero"] is False
        assert costs["total_complete_status"] == COST_UNKNOWN
        assert costs["unknown_not_treated_as_zero"] is True
        assert costs["semantic_gate"]["old_4b23_chapter_call_envelope_not_reused_as_primary"][
            "reused"
        ] is False
        assert costs["book_generator"]["central_usd"] is not None


class TestAuthorizationSingleChapterReview:
    def test_authorization_consumed_and_incompatible(self):
        auth = mint_synthetic_authorization(
            authorization_id="SYN-T",
            chapter_id="SYN-CH001",
            provider="FAKEAI_SIMULATED",
            model="fakeai",
            max_calls=1,
            max_budget_usd=0.05,
            objective="test",
        )
        consume_authorization(
            auth,
            phase=PHASE,
            chapter_id="SYN-CH001",
            provider="FAKEAI_SIMULATED",
            model="fakeai",
            calls=1,
            budget_usd=0.01,
        )
        with pytest.raises(BookGenerationBridge214Error):
            consume_authorization(
                auth,
                phase=PHASE,
                chapter_id="SYN-CH001",
                provider="FAKEAI_SIMULATED",
                model="fakeai",
                calls=1,
                budget_usd=0.01,
            )
        other = mint_synthetic_authorization(
            authorization_id="SYN-T2",
            chapter_id="SYN-CH001",
            provider="FAKEAI_SIMULATED",
            model="fakeai",
            max_calls=1,
            max_budget_usd=0.05,
            objective="test",
        )
        with pytest.raises(BookGenerationBridge214Error):
            consume_authorization(
                other,
                phase=PHASE,
                chapter_id="CH019",
                provider="openai",
                model="gpt-5.6-terra",
                calls=1,
                budget_usd=0.01,
            )

    def test_single_chapter_mode_blocks_others(self):
        mode = SingleChapterMode(enabled=True, chapter_id="SYN-CH001")
        result = run_bridge_chapter(
            scenario="fully_supported",
            chapter_id="SYN-CH001",
            single_chapter=mode,
        )
        assert result["decision"] == "PASS"
        with pytest.raises(BookGenerationBridge214Error):
            run_bridge_chapter(
                scenario="fully_supported",
                chapter_id="SYN-CH002",
                single_chapter=mode,
            )
        architecture = bridge_architecture()
        assert architecture["enabled_by_default"] is False
        assert architecture["connected"] is False

    def test_pass_review_block_and_human_review(self):
        isolated = run_chapter_scenarios()
        assert isolated["passed"] is True
        assert isolated["pass_review_block_covered"] is True
        passing = run_bridge_chapter(scenario="fully_supported")
        review = run_bridge_chapter(scenario="questionable")
        blocked = run_bridge_chapter(scenario="invented_causality")
        assert passing["decision"] == "PASS"
        assert review["decision"] == "REVIEW"
        assert blocked["decision"] == "BLOCK"
        human_review = apply_human_review(
            review,
            action="confirm_supported",
            reviewer="SYNTHETIC",
            note="ok",
        )
        human_block = apply_human_review(
            blocked,
            action="confirm_supported",
            reviewer="SYNTHETIC",
            note="cannot pass",
        )
        assert human_review["original_response_mutated"] is False
        assert human_block["human_decision"] == "BLOCK"
        assert human_block["block_cannot_become_pass_automatically"] is True


class TestRecoveryIdempotenceTracePhase5Safety:
    def test_interruption_recovery(self):
        recovery = interruption_recovery()
        assert recovery["ok"] is True
        assert recovery["no_automatic_second_call_after_uncertain_send"] is True
        assert recovery["interrupt_after_send_not_free"] is True
        points = {item["interrupt_at"] for item in recovery["cases"]}
        assert "before_reservation" in points
        assert "after_send" in points
        assert "after_review" in points
        assert "after_block" in points

    def test_idempotence_and_cache_invalidation(self):
        result = idempotence()
        assert result["ok"] is True
        assert result["double_debit"] is False
        assert result["double_accept"] is False
        assert result["old_pass_incompatible_contract_not_reused"] is True
        assert result["cache_invalidation"]["ok"] is True

    def test_traceability_documents_missing_generated_paragraphs(self):
        traces = traceability()
        assert traces["ok"] is True
        assert traces["generated_paragraphs_exist"] is False
        assert traces["does_not_fabricate_missing_links"] is True
        assert traces["canonical_idea_ids_resolve_in_source_map"] is True

    def test_phase5_boundary_not_executed(self):
        interface = phase5_boundary(run_bridge_chapter(scenario="fully_supported"))
        assert interface["executed"] is False
        assert interface["independent"] is True
        assert interface["semantic_gate_pass_does_not_make_book_publishable"] is True
        assert interface["cost"]["status"] == COST_UNKNOWN

    def test_provider_safety_and_production_pipeline_untouched(self):
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
        assert "book_generation_bridge_4b214" not in pipeline
        assert "book_generation_integration_4b213" not in pipeline


class TestRunner:
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
        assert result.bundle["readiness"]["READY_FOR_ONE_REAL_CHAPTER_EXPERIMENT"] is False
        assert result.bundle["readiness"]["READY_FOR_FULL_REAL_BOOK_GENERATION"] is False
        assert result.bundle["architecture"]["enabled_by_default"] is False
        assert CODE_VERSION == "app.book_generation_bridge_4b214"

    def test_book_json_unpublished(self):
        assert production_book_absent(PROJECT_NAME)
        assert AUTHORIZATION_SCOPE.endswith("ONLY")
        guard = BudgetGuard(
            ceilings={LEDGER_SEMANTIC_GATE: Decimal("1"), LEDGER_GLOBAL: Decimal("1")}
        )
        assert guard.snapshot()["unknown_never_becomes_zero"] is True
