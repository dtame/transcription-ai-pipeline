"""Prepare a Terra validation manifesto. Does not call Terra."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.book_generation.constants import PARAGRAPH_KIND_SUBSTANTIVE
from app.book_generation_4b217.constants import (
    PHASE,
    TARGET_CHAPTER_ID,
    TERRA_H01_ANALOG_USD,
)


def prepare_terra_manifest(*, candidate, structural: dict[str, Any]) -> dict[str, Any]:
    sections = 0
    paragraphs = 0
    substantive = 0
    connective = 0
    if candidate is not None:
        sections = len(candidate.sections)
        for section in candidate.sections:
            for paragraph in section.paragraphs:
                paragraphs += 1
                if paragraph.kind == PARAGRAPH_KIND_SUBSTANTIVE:
                    substantive += 1
                else:
                    connective += 1
    estimated_calls = paragraphs
    estimated_cost = None
    if estimated_calls:
        estimated_cost = float(TERRA_H01_ANALOG_USD * Decimal(estimated_calls))
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "terra_calls_this_phase": 0,
        "sections": sections,
        "paragraphs": paragraphs,
        "substantive_paragraphs": substantive,
        "connective_paragraphs": connective,
        "semantic_units_offline_proxy": substantive,
        "granularity": "A_ONE_REQUEST_PER_PARAGRAPH",
        "estimated_terra_calls": estimated_calls,
        "estimated_terra_cost_usd": estimated_cost,
        "estimated_terra_cost_is_hypothesis": True,
        "h01_analog_usd": str(TERRA_H01_ANALOG_USD),
        "h01_is_not_a_generated_book_paragraph": True,
        "reasoning_token_billing": "UNKNOWN",
        "long_context_pricing": "UNKNOWN",
        "unknown_not_treated_as_zero": True,
        "false_rejection_risks": [
            "UNC029 Isaiah 26 versus 28 must stay unresolved.",
            "SEC048 references without shared SRC may look unsupported.",
            "Thematic grouping of AUDIO003 and AUDIO004 may look like new causality.",
            "Faithful restatement may be scored as invention if distinctive tokens differ.",
        ],
        "anomalies_not_converted_to_pass": True,
        "semantic_gate_not_promoted": True,
        "authorization_required_before_any_terra_call": True,
        "structural_status": structural.get("status"),
        "secrets_included": False,
    }


__all__ = ["prepare_terra_manifest"]
