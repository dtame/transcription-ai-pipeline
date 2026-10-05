"""Prepare a CH012 semantic-validation manifesto. Does not call Terra."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.book_editorial_acceptance_4b219.chapter_io import iter_paragraphs
from app.book_editorial_acceptance_4b219.constants import (
    CHAPTER_ID,
    H01_ANALOG_USD,
    HISTORICAL_SEMANTIC,
    PARAGRAPH_COUNT,
    PHASE,
)


def semantic_validation_readiness(chapter: dict[str, Any]) -> dict[str, Any]:
    paragraphs = list(iter_paragraphs(chapter))
    substantive = sum(1 for _pid, row in paragraphs if row.get("kind") == "substantive")
    connective = len(paragraphs) - substantive
    estimated_calls = len(paragraphs)
    estimated_cost = float(H01_ANALOG_USD * Decimal(estimated_calls))
    return {
        "phase": PHASE,
        "chapter_id": CHAPTER_ID,
        "terra_calls_this_phase": 0,
        "semantic_certification": "not_performed",
        "semantic_gate_promoted": False,
        "historical_contract_left_in_place": HISTORICAL_SEMANTIC,
        "historical_verdicts_not_modified": True,
        "actual_paragraph_count": len(paragraphs),
        "expected_paragraph_count": PARAGRAPH_COUNT,
        "substantive_paragraphs": substantive,
        "connective_paragraphs": connective,
        "validation_strategy": {
            "id": "proportionate_paragraph_review_if_authorized_later",
            "granularity": "A_ONE_REQUEST_PER_PARAGRAPH",
            "units": [
                "new_claims",
                "strengthened_claims",
                "unsupported_causal_relations",
                "personal_testimonies",
                "biblical_references",
                "speaker_attribution",
                "nuances",
                "reservations",
                "idea_coverage",
                "example_preservation",
            ],
            "not_executed_in_this_phase": True,
            "current_gate_can_false_reject": True,
        },
        "estimated_terra_calls": estimated_calls,
        "estimated_terra_cost_usd": estimated_cost,
        "estimated_terra_cost_is_hypothesis": True,
        "h01_analog_usd": str(H01_ANALOG_USD),
        "h01_is_not_a_generated_book_paragraph": True,
        "reasoning_token_billing": "UNKNOWN",
        "long_context_pricing": "UNKNOWN",
        "unknown_not_treated_as_zero": True,
        "complete_cost": "UNKNOWN",
        "false_positive_and_false_rejection_risks": [
            "UNC029 Isaiah 26 versus 28 must stay unresolved and can look like error.",
            "French/English biblical labels (Jude vers 20, 1 Corinthiens 14) can fail token match.",
            "Thematic grouping of AUDIO003 and AUDIO004 may look like new causality.",
            "Faithful restatement may be scored as invention if distinctive tokens differ.",
            "P000002 'the failure was not in the gift itself' may be read as a new claim.",
            "P000010 'meaning He was not absent' may be read as interpretive gloss.",
            "P000011 'the promise attached to correction' may be read as strengthening.",
            "P000012 'has always been' and P000013 'this same disposition is fulfilled' "
            "may be read as new causality even though IDEA212 already states fulfillment.",
            "Empty paras[].e IDEA handles can produce a historical-validator FAIL that "
            "is not a missing teaching.",
        ],
        "block_conditions": [
            "No new authorization exists for a Terra call.",
            "Canonical SourceMap, EditorialPlan, or transcript hash changes.",
            "The accepted CH012 pair hash changes.",
            "A request is made to rewrite the accepted chapter to satisfy the gate.",
            "Publication, book.json, or production-cache write is requested.",
            "The historical Semantic Gate contract is treated as promoted.",
        ],
        "human_review_conditions": [
            "Any future Terra FAIL on a reservation that the accepted prose preserves.",
            "Any future Terra FAIL based only on missing IDEA handles in paras[].e.",
            "Any alleged new causality in P000002, P000010, P000011, P000012, or P000013.",
            "Any request to complete REF037, REF038, or REF043 from memory.",
            "Any request to add the EX030 'losing strength' neighboring detail.",
        ],
        "authorization_required_before_any_terra_call": True,
        "this_estimate_is_not_an_authorization": True,
        "secrets_included": False,
    }


__all__ = ["semantic_validation_readiness"]
