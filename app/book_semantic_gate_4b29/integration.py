"""Integration preflight for Semantic Gate 2.0. Not connected to production."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_generation.constants import (
    BOOK_FILENAME,
    BOOK_GENERATOR_PROMPT_VERSION,
    BOOK_GENERATOR_VALIDATOR_VERSION,
)
from app.book_semantic_gate_4b29.constants import (
    PHASE,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PROMPT_VERSION_20_CANDIDATE,
    SEMANTIC_GATE_20_ENABLED,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b29.engine import evaluate_paragraph
from app.book_semantic_gate_4b29.guard import BookSemanticGate29Error
from app.book_semantic_gate_4b29.interface import SemanticModelTransport


class SemanticGate20IntegrationCandidate:
    """Candidate hook. Disabled. Must not be imported by the production pipeline."""

    enabled = SEMANTIC_GATE_20_ENABLED
    production_hook_connected = PRODUCTION_PIPELINE_HOOK
    production_cache_acceptance = PRODUCTION_CACHE_ACCEPTANCE

    def review_paragraph(
        self,
        *,
        paragraph_id: str,
        text: str,
        evidence_handles: Sequence[str],
        transport: SemanticModelTransport,
        chapter_handle: str,
    ) -> dict[str, Any]:
        if self.enabled or self.production_hook_connected:
            raise BookSemanticGate29Error("Semantic Gate 2.0 must not run in production.")
        return evaluate_paragraph(
            paragraph_id=paragraph_id,
            text=text,
            transport=transport,
            evidence_handles=evidence_handles,
            chapter_handle=chapter_handle,
        )


def integration_preflight() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "connected": False,
        "enabled_by_default": SEMANTIC_GATE_20_ENABLED,
        "entry_point": (
            "After Book Generator materialize_chapter / validate_chapter_candidate "
            "and before ChapterCache.remember, Book Validator, and book.json publication."
        ),
        "inputs": {
            "chapter_candidate": "app.book_generation.models.ChapterCandidate",
            "paragraph_id": "canonical P000001-style identifiers assigned locally",
            "paragraph_text": "generated paragraph, unmodified",
            "evidence_handles": "declared canonical SRC/IDEA/EX/REF handles",
            "chapter_handle": "editorial chapter id such as CH016 identity, not regeneration",
            "transport": "explicit FakeAI or future authorized provider; never implicit",
        },
        "outputs": {
            "decision": "PASS | BLOCK | REVIEW",
            "prepared_units": "stable unit_id + offsets",
            "verdicts": "per unit_id",
            "diagnostics": "raw response preserved on BLOCK/REVIEW",
        },
        "errors": {
            "coverage": "BLOCK",
            "contract": "BLOCK",
            "missing_unit": "BLOCK",
            "remote_without_authorization": "BLOCK",
        },
        "cache": {
            "production_cache": "UNCHANGED",
            "acceptance": False,
            "REVIEW_does_not_accept": True,
            "signature_would_need_gate_version": (
                "A future connected gate would add "
                f"{PROMPT_VERSION_20_CANDIDATE} / {TRANSPORT_VERSION_20_CANDIDATE} "
                "to ChapterSignatureInputs. Not done in this phase."
            ),
        },
        "versioning": {
            "generator_prompt": BOOK_GENERATOR_PROMPT_VERSION,
            "generator_validator": BOOK_GENERATOR_VALIDATOR_VERSION,
            "semantic_contract_candidate": PROMPT_VERSION_20_CANDIDATE,
            "semantic_transport_candidate": TRANSPORT_VERSION_20_CANDIDATE,
            "book_filename": BOOK_FILENAME,
        },
        "audit": "audit/book_semantic_gate_4b29/ plus per-paragraph diagnostics",
        "resume": "Would resume from last structurally valid chapter; semantic REVIEW is not a cache hit.",
        "cost": "No provider spend in 4B.2.9. Future Terra cost remains unmeasured.",
        "structural_validation": "Book Generator validator remains first.",
        "semantic_validation": "Semantic Gate 2.0 candidate, isolated.",
        "acceptance_conditions": {
            "PASS": "local preparation + contract + all substantive SUPPORTED",
            "BLOCK": "UNSUPPORTED / invalid contract / coverage / evidence",
            "REVIEW": "QUESTIONABLE / ambiguous boundary / human reservation",
        },
        "does_not_replace_book_validator": True,
        "production_pipeline_modified": False,
        "module": "app.book_semantic_gate_4b29.integration.SemanticGate20IntegrationCandidate",
        "secrets_included": False,
    }


def pipeline_imports_gate20(pipeline_source: str) -> bool:
    return "book_semantic_gate_4b29" in pipeline_source


def assert_disconnected_from(module: Mapping[str, Any] | None = None) -> None:
    if SEMANTIC_GATE_20_ENABLED or PRODUCTION_PIPELINE_HOOK:
        raise BookSemanticGate29Error("Semantic Gate 2.0 production hook is enabled.")
    if module and pipeline_imports_gate20(str(module)):
        raise BookSemanticGate29Error("Production module imports 4B.2.9.")


__all__ = [
    "SemanticGate20IntegrationCandidate",
    "assert_disconnected_from",
    "integration_preflight",
    "pipeline_imports_gate20",
]
