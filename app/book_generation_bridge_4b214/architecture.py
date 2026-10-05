"""Candidate production bridge architecture. Not hooked. Disabled by default."""

from __future__ import annotations

from typing import Any

from app.book_generation_bridge_4b214.constants import (
    ADAPTER_VERSION,
    AUTHORIZATION_VERSION,
    BRIDGE_CONTRACT_VERSION,
    BRIDGE_ENABLED,
    BUDGET_POLICY_VERSION,
    CANDIDATE_GRANULARITY,
    CODE_VERSION,
    PHASE,
    PHASE5_INTERFACE_VERSION,
    PREPARATION_ALGORITHM_VERSION,
    PRODUCTION_PIPELINE_HOOK,
    PROMPT_VERSION_202_CANDIDATE,
    REAL_PROVIDERS_ENABLED,
    REVIEW_PROTOCOL_VERSION,
    SINGLE_CHAPTER_MODE_VERSION,
    TRANSPORT_VERSION_20_CANDIDATE,
    VALIDATOR_IMPLEMENTATION_VERSION,
)
from app.book_semantic_gate_4b29.integration import SemanticGate20IntegrationCandidate


def bridge_architecture() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "module": CODE_VERSION,
        "enabled_by_default": BRIDGE_ENABLED,
        "connected": PRODUCTION_PIPELINE_HOOK,
        "real_providers_enabled": REAL_PROVIDERS_ENABLED,
        "activated": False,
        "proposed_flow": [
            "Receive a real ChapterCandidate from Book Generator (this phase: FakeAI only).",
            "Adapt to the 4B.2.13 envelope via adapter.adapt_chapter_candidate.",
            "Fail closed if chapter/section/paragraph IDs, text, evidence, versions, or hashes are missing.",
            "Enforce single_chapter_only when that mode is selected.",
            "Consume a one-shot human authorization before any future real call.",
            "Reserve budget fail-closed before any future provider call.",
            "Prepare units (prepare_paragraph_units) and validate coverage.",
            "Build one Semantic Gate 2.0.2 request per paragraph (candidate granularity A).",
            "Obtain FakeSemanticTransport responses in this phase.",
            "Validate with validate_response_202 and apply_acceptance_policy_202.",
            "Aggregate chapter PASS/REVIEW/BLOCK.",
            "Apply the human review protocol without mutating the original model response.",
            "Store only in IsolatedChapterCache. Never production ChapterCache.",
            "Expose the Phase 5 boundary payload. Do not execute Phase 5.",
        ],
        "not_connected_to": [
            "app.book_generation.pipeline.materialize_chapter",
            "app.book_generation.pipeline.assemble_book",
            "app.book_generation.cache.ChapterCache",
            "app.book_generation.writer.write_book",
            "SemanticGate20IntegrationCandidate.enabled",
        ],
        "reused_validated_components": {
            "prepare_paragraph_units": "app.book_semantic_gate_4b29.preparation.prepare_paragraph_units",
            "validate_prepared_coverage": "app.book_semantic_gate_4b29.coverage.validate_prepared_coverage",
            "validate_response_202": "app.book_semantic_gate_4b212.validator.validate_response_202",
            "apply_acceptance_policy_202": "app.book_semantic_gate_4b212.policy.apply_acceptance_policy_202",
            "build_semantic_request": "app.book_generation_integration_4b213.request.build_semantic_request",
            "orchestrate_chapter": "app.book_generation_integration_4b213.orchestrator.orchestrate_chapter",
            "IsolatedChapterCache": "app.book_generation_integration_4b213.cache.IsolatedChapterCache",
            "FakeGeneratorTransport": "app.book_generation_integration_4b213.fakeai.FakeGeneratorTransport",
            "FakeSemanticTransport": "app.book_generation_integration_4b213.fakeai.FakeSemanticTransport",
        },
        "new_isolated_functions": {
            "adapt_chapter_candidate": "app.book_generation_bridge_4b214.adapter.adapt_chapter_candidate",
            "BudgetGuard": "app.book_generation_bridge_4b214.budget.BudgetGuard",
            "run_bridge_chapter": "app.book_generation_bridge_4b214.orchestrator.run_bridge_chapter",
            "SingleChapterMode": "app.book_generation_bridge_4b214.single_chapter.SingleChapterMode",
        },
        "semantic_gate_production_hook_enabled": SemanticGate20IntegrationCandidate.enabled,
        "candidate_granularity": CANDIDATE_GRANULARITY,
        "versions": {
            "bridge_contract": BRIDGE_CONTRACT_VERSION,
            "adapter": ADAPTER_VERSION,
            "budget_policy": BUDGET_POLICY_VERSION,
            "authorization": AUTHORIZATION_VERSION,
            "review_protocol": REVIEW_PROTOCOL_VERSION,
            "single_chapter_mode": SINGLE_CHAPTER_MODE_VERSION,
            "semantic_contract": PROMPT_VERSION_202_CANDIDATE,
            "semantic_transport": TRANSPORT_VERSION_20_CANDIDATE,
            "preparation": PREPARATION_ALGORITHM_VERSION,
            "validator": VALIDATOR_IMPLEMENTATION_VERSION,
            "phase5_interface": PHASE5_INTERFACE_VERSION,
        },
        "generator_and_validator_not_mixed": True,
        "production_pipeline_modified": False,
        "secrets_included": False,
    }


__all__ = ["bridge_architecture"]
