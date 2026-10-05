"""Isolated integration architecture. Not hooked to production."""

from __future__ import annotations

from typing import Any

from app.book_generation_integration_4b213.constants import (
    CODE_VERSION,
    INTEGRATION_CONTRACT_VERSION,
    PHASE,
    PHASE5_INTERFACE_VERSION,
    PREPARATION_ALGORITHM_VERSION,
    PRODUCTION_PIPELINE_HOOK,
    PROMPT_VERSION_202_CANDIDATE,
    TRANSPORT_VERSION_20_CANDIDATE,
    VALIDATOR_IMPLEMENTATION_VERSION,
)


def integration_architecture() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "module": CODE_VERSION,
        "connected": PRODUCTION_PIPELINE_HOOK,
        "proposed_strategy_from_4b212": "C_HYBRID_SUPERVISED_CANDIDATE_FOR_HUMAN_REVIEW",
        "activated": False,
        "steps": [
            "Receive a generated chapter (FakeGeneratorTransport).",
            "Validate structure (structure.validate_chapter_structure).",
            "Prepare paragraphs (iter_paragraphs).",
            "Build deterministic units (prepare_paragraph_units from 4B.2.9 / 4B.2.8).",
            "Associate evidence (evidence.validate_paragraph_evidence; missing => BLOCK).",
            "Build Semantic Gate 2.0.2 requests (request.build_semantic_request).",
            "Obtain injected FakeSemanticTransport responses.",
            "Validate with validate_response_202.",
            "Compute paragraph PASS/BLOCK/REVIEW (apply_acceptance_policy_202).",
            "Aggregate chapter decision (apply_chapter_policy).",
            "Store in IsolatedChapterCache; PASS only may be a future-acceptance candidate.",
            "Expose Phase 5 interface payload (not executed).",
        ],
        "real_functions_reused": {
            "prepare_paragraph_units": "app.book_semantic_gate_4b29.preparation.prepare_paragraph_units",
            "validate_prepared_coverage": "app.book_semantic_gate_4b29.coverage.validate_prepared_coverage",
            "validate_response_202": "app.book_semantic_gate_4b212.validator.validate_response_202",
            "apply_acceptance_policy_202": "app.book_semantic_gate_4b212.policy.apply_acceptance_policy_202",
            "materialize_chapter": "app.book_generation.pipeline.materialize_chapter (inspected, not invoked for real generation)",
            "ChapterCache": "app.book_generation.cache.ChapterCache (not written)",
        },
        "isolated_functions": {
            "orchestrate_chapter": "app.book_generation_integration_4b213.orchestrator.orchestrate_chapter",
            "FakeGeneratorTransport": "app.book_generation_integration_4b213.fakeai.FakeGeneratorTransport",
            "FakeSemanticTransport": "app.book_generation_integration_4b213.fakeai.FakeSemanticTransport",
            "IsolatedChapterCache": "app.book_generation_integration_4b213.cache.IsolatedChapterCache",
        },
        "versions": {
            "integration_contract": INTEGRATION_CONTRACT_VERSION,
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


__all__ = ["integration_architecture"]
