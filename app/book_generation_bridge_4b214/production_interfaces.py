"""Exact production interfaces inspected for the 4B.2.14 bridge. No invented names."""

from __future__ import annotations

from typing import Any

from app.book_generation.cache import ChapterCache, GenerationState
from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION,
    BOOK_GENERATOR_VALIDATOR_VERSION,
    BOOK_SCHEMA_VERSION,
    GENERATION_UNIT_CHAPTER,
    MODEL,
    PROVIDER,
    STRATEGY_CHAPTER,
)
from app.book_generation.models import (
    Book,
    BookChapter,
    BookIdentity,
    BookParagraph,
    BookSection,
    ChapterCandidate,
)
from app.book_generation.pipeline import (
    assemble_book,
    assign_paragraph_ids,
    materialize_chapter,
    remember_chapter,
)
from app.book_generation.settings import frozen_production_settings
from app.book_generation.validator import validate_chapter_candidate
from app.book_generation_bridge_4b214.constants import PHASE
from app.book_generation_integration_4b213.orchestrator import orchestrate_chapter
from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b29.integration import SemanticGate20IntegrationCandidate
from app.book_semantic_gate_4b29.preparation import prepare_paragraph_units
from app.book_semantic_gate_4b29.request import build_model_request
from app.book_semantic_gate_4b212.policy import apply_acceptance_policy_202
from app.book_semantic_gate_4b212.validator import validate_response_202
from app.editorial_planning.models import EditorialChapter, EditorialPlan, EditorialSection
from app.source_analysis.models import SourceMap


def production_interfaces() -> dict[str, Any]:
    settings = frozen_production_settings()
    return {
        "phase": PHASE,
        "generation_inputs": {
            "EditorialPlan": f"{EditorialPlan.__module__}.{EditorialPlan.__name__}",
            "EditorialChapter": f"{EditorialChapter.__module__}.{EditorialChapter.__name__}",
            "EditorialSection": f"{EditorialSection.__module__}.{EditorialSection.__name__}",
            "SourceMap": f"{SourceMap.__module__}.{SourceMap.__name__}",
            "BookIdentity": f"{BookIdentity.__module__}.{BookIdentity.__name__}",
            "loader": "app.book_generation.identity.load_production_inputs",
        },
        "chapter_objects": {
            "ChapterCandidate": f"{ChapterCandidate.__module__}.{ChapterCandidate.__name__}",
            "BookChapter": f"{BookChapter.__module__}.{BookChapter.__name__}",
            "fields": [
                "chapter_id",
                "title",
                "sections",
                "idea_refs",
                "source_refs",
                "provider_raw_sha256",
                "cache_signature",
            ],
        },
        "paragraph_objects": {
            "BookParagraph": f"{BookParagraph.__module__}.{BookParagraph.__name__}",
            "BookSection": f"{BookSection.__module__}.{BookSection.__name__}",
            "fields": [
                "text",
                "kind",
                "evidence_handles",
                "source_refs",
                "idea_refs",
                "example_refs",
                "reference_refs",
                "uncertainty_refs",
                "paragraph_id",
                "provider_handle",
            ],
            "paragraph_id_rule": (
                "Canonical paragraph_id is empty on ChapterCandidate and assigned "
                f"by {assign_paragraph_ids.__module__}.{assign_paragraph_ids.__name__} "
                "during assemble_book as P000001."
            ),
        },
        "source_references": {
            "BookParagraph.source_refs": "tuple[str, ...]",
            "BookParagraph.evidence_handles": "tuple[str, ...]",
            "BookParagraph.idea_refs": "tuple[str, ...]",
            "resolve_src_for_handles": "app.book_generation.evidence.resolve_src_for_handles",
            "classify_handle": "app.book_generation.evidence.classify_handle",
        },
        "evidence_bundles": {
            "build_chapter_evidence": "app.book_generation.evidence.build_chapter_evidence",
            "evidence_metrics": "app.book_generation.evidence.evidence_metrics",
            "hydrate_src_ids": "app.book_generation.hydrate.hydrate_src_ids",
        },
        "validators": {
            "structural": f"{validate_chapter_candidate.__module__}.{validate_chapter_candidate.__name__}",
            "semantic_202": f"{validate_response_202.__module__}.{validate_response_202.__name__}",
            "coverage": f"{validate_prepared_coverage.__module__}.{validate_prepared_coverage.__name__}",
            "policy_202": f"{apply_acceptance_policy_202.__module__}.{apply_acceptance_policy_202.__name__}",
        },
        "transports": {
            "generator_version": BOOK_GENERATION_TRANSPORT_VERSION,
            "semantic_request_builder": f"{build_model_request.__module__}.{build_model_request.__name__}",
            "integration_request_builder": (
                "app.book_generation_integration_4b213.request.build_semantic_request"
            ),
            "fake_generator": "app.book_generation_integration_4b213.fakeai.FakeGeneratorTransport",
            "fake_semantic": "app.book_generation_integration_4b213.fakeai.FakeSemanticTransport",
        },
        "caches": {
            "production": f"{ChapterCache.__module__}.{ChapterCache.__name__}",
            "isolated_4b213": "app.book_generation_integration_4b213.cache.IsolatedChapterCache",
            "production_writes_this_phase": False,
        },
        "resume_states": {
            "GenerationState": f"{GenerationState.__module__}.{GenerationState.__name__}",
            "isolated_states": "app.book_generation_integration_4b213.cache.ISOLATED_CACHE_STATES",
        },
        "extension_points": {
            "materialize_chapter": f"{materialize_chapter.__module__}.{materialize_chapter.__name__}",
            "remember_chapter": f"{remember_chapter.__module__}.{remember_chapter.__name__}",
            "assemble_book": f"{assemble_book.__module__}.{assemble_book.__name__}",
            "orchestrate_chapter_isolated": (
                f"{orchestrate_chapter.__module__}.{orchestrate_chapter.__name__}"
            ),
            "semantic_gate_hook": (
                f"{SemanticGate20IntegrationCandidate.__module__}."
                "SemanticGate20IntegrationCandidate"
            ),
            "semantic_gate_enabled": SemanticGate20IntegrationCandidate.enabled,
            "prepare_paragraph_units": (
                f"{prepare_paragraph_units.__module__}.{prepare_paragraph_units.__name__}"
            ),
        },
        "activation_controls": {
            "bridge_enabled": False,
            "production_pipeline_hook": False,
            "semantic_gate_20_enabled": SemanticGate20IntegrationCandidate.enabled,
            "publication_authorized": False,
        },
        "side_effect_risks": [
            "Hooking materialize_chapter or remember_chapter would write production cache.",
            "Calling assemble_book would assign canonical P IDs across the book.",
            "write_book would publish book.json if PUBLICATION_AUTHORIZED were flipped.",
            "A live OpenAIEngine/AnthropicEngine generate() would leave this phase.",
        ],
        "versions": {
            "book_schema": BOOK_SCHEMA_VERSION,
            "generator_prompt": BOOK_GENERATOR_PROMPT_VERSION,
            "generator_transport": BOOK_GENERATION_TRANSPORT_VERSION,
            "generator_validator": BOOK_GENERATOR_VALIDATOR_VERSION,
            "generation_unit": GENERATION_UNIT_CHAPTER,
            "strategy": STRATEGY_CHAPTER,
            "provider": PROVIDER,
            "model": MODEL,
            "frozen_settings_provider": settings.provider,
            "frozen_settings_model": settings.model,
        },
        "book_model": f"{Book.__module__}.{Book.__name__}",
        "does_not_invent_function_names": True,
        "secrets_included": False,
    }


__all__ = ["production_interfaces"]
