"""Explicit Book Generator ↔ Semantic Gate 2.0.2 integration contract."""

from __future__ import annotations

from typing import Any

from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION,
    BOOK_GENERATOR_VALIDATOR_VERSION,
    BOOK_SCHEMA_VERSION,
    PARAGRAPH_KIND_CONNECTIVE,
    PARAGRAPH_KIND_SUBSTANTIVE,
)
from app.book_generation_integration_4b213.constants import (
    CODE_VERSION,
    DECISION_BLOCK,
    INTEGRATION_CONTRACT_ACTIVATED,
    INTEGRATION_CONTRACT_VERSION,
    OFFSET_CONVENTION,
    PHASE,
    PHASE5_INTERFACE_VERSION,
    PREPARATION_ALGORITHM_VERSION,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PROMPT_VERSION_202_CANDIDATE,
    SYNTHETIC_PREFIX,
    TRANSPORT_VERSION_20_CANDIDATE,
    VALIDATOR_IMPLEMENTATION_VERSION,
)
from app.book_generation.models import BookParagraph, BookSection, ChapterCandidate


def integration_contract() -> dict[str, Any]:
    required_paragraph_fields = [
        "chapter_id",
        "section_id",
        "paragraph_id",
        "text",
        "kind",
        "source_refs",
        "evidence_handles",
        "source_map_sha256",
        "editorial_plan_sha256",
        "generator_prompt_version",
        "semantic_contract_version",
        "semantic_transport_version",
    ]
    existing = {
        "chapter_id": "app.book_generation.models.ChapterCandidate.chapter_id / BookChapter.chapter_id",
        "section_id": "app.book_generation.models.BookSection.section_id",
        "paragraph_id": (
            "app.book_generation.models.BookParagraph.paragraph_id "
            "(empty on ChapterCandidate; assigned by pipeline.assign_paragraph_ids as P000001)"
        ),
        "text": "app.book_generation.models.BookParagraph.text",
        "kind": "app.book_generation.models.BookParagraph.kind (substantive|connective)",
        "source_refs": "app.book_generation.models.BookParagraph.source_refs",
        "evidence_handles": "app.book_generation.models.BookParagraph.evidence_handles",
        "idea_refs": "app.book_generation.models.BookParagraph.idea_refs",
        "source_map_sha256": "app.book_generation.models.BookIdentity.source_map_sha256",
        "editorial_plan_sha256": "app.book_generation.models.BookIdentity.editorial_plan_sha256",
        "generator_prompt_version": "app.book_generation.constants.BOOK_GENERATOR_PROMPT_VERSION",
        "generator_transport_version": "app.book_generation.constants.BOOK_GENERATION_TRANSPORT_VERSION",
        "semantic_contract_version": "not stored on production ChapterCandidate; supplied by this isolated contract",
        "semantic_transport_version": "not stored on production ChapterCandidate; supplied by this isolated contract",
    }
    missing_from_production_chapter = [
        "semantic_contract_version",
        "semantic_transport_version",
        "preparation_algorithm_version",
        "validator_implementation_version",
        "integration_contract_version",
    ]
    return {
        "phase": PHASE,
        "version": INTEGRATION_CONTRACT_VERSION,
        "activated": INTEGRATION_CONTRACT_ACTIVATED,
        "code_version": CODE_VERSION,
        "does_not_invent_absent_references": True,
        "missing_required_evidence": DECISION_BLOCK,
        "does_not_generate_artificial_evidence": True,
        "required_paragraph_association": required_paragraph_fields,
        "existing_production_fields": existing,
        "fields_absent_from_production_chapter_candidate": missing_from_production_chapter,
        "how_absent_fields_are_supplied": (
            "This isolated layer attaches semantic contract, transport, "
            "preparation, and validator versions onto the integration envelope. "
            "They are not written into production ChapterCache."
        ),
        "paragraph_id_rule": (
            "Production candidates may have empty paragraph_id. Isolated fixtures "
            "assign SYN-CH001-P000001 style identifiers. Canonical P000001 IDs "
            "are assigned only during assemble_book, which this phase does not run."
        ),
        "synthetic_handle_rule": (
            f"Synthetic fixtures use the {SYNTHETIC_PREFIX} prefix. They are never "
            "presented as SourceMap SRC/IDEA identifiers."
        ),
        "real_models": {
            "ChapterCandidate": ChapterCandidate.__module__,
            "BookSection": BookSection.__module__,
            "BookParagraph": BookParagraph.__module__,
        },
        "kinds": [PARAGRAPH_KIND_SUBSTANTIVE, PARAGRAPH_KIND_CONNECTIVE],
        "versions": {
            "book_schema": BOOK_SCHEMA_VERSION,
            "generator_prompt": BOOK_GENERATOR_PROMPT_VERSION,
            "generator_transport": BOOK_GENERATION_TRANSPORT_VERSION,
            "generator_validator": BOOK_GENERATOR_VALIDATOR_VERSION,
            "semantic_contract": PROMPT_VERSION_202_CANDIDATE,
            "semantic_transport": TRANSPORT_VERSION_20_CANDIDATE,
            "preparation_algorithm": PREPARATION_ALGORITHM_VERSION,
            "validator_implementation": VALIDATOR_IMPLEMENTATION_VERSION,
            "phase5_interface": PHASE5_INTERFACE_VERSION,
            "offset_convention": OFFSET_CONVENTION,
        },
        "production_pipeline_hook": PRODUCTION_PIPELINE_HOOK,
        "production_cache_acceptance": PRODUCTION_CACHE_ACCEPTANCE,
        "book_validator_independent": True,
        "secrets_included": False,
    }


__all__ = ["integration_contract"]
