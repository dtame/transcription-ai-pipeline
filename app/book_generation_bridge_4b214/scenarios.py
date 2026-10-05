"""Request-volume scenarios. Paragraph counts are assumed, not measured."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation_bridge_4b214.constants import (
    CANDIDATE_GRANULARITY,
    PHASE,
    STRATEGY_A,
    STRATEGY_B,
    STRATEGY_C,
)
from app.book_generation_bridge_4b214.granularity import validation_granularity


def request_volume_scenarios(volumes: Mapping[str, Any] | None = None) -> dict[str, Any]:
    chapters = int((volumes or {}).get("chapters") or 19)
    sections = int((volumes or {}).get("sections") or 72)
    granularity = validation_granularity()
    assumptions = {
        "paragraphs_per_section_low": 2,
        "paragraphs_per_section_central": 4,
        "paragraphs_per_section_high": 7,
        "units_per_paragraph_low": 2,
        "units_per_paragraph_central": 4,
        "units_per_paragraph_high": 8,
        "source": "ASSUMPTION_NOT_MEASURED",
        "why": (
            "No generated manuscript exists for the 19 chapters. "
            "h01 used 5 units in one short paragraph and is not a book-wide rate."
        ),
    }
    def _paras(rate: int) -> int:
        return sections * rate

    a_low = _paras(assumptions["paragraphs_per_section_low"])
    a_central = _paras(assumptions["paragraphs_per_section_central"])
    a_high = _paras(assumptions["paragraphs_per_section_high"])
    return {
        "phase": PHASE,
        "known": {
            "chapters": chapters,
            "sections": sections,
            "ideas": (volumes or {}).get("plan_stats", {}).get("assigned_idea_count"),
        },
        "unknown": {
            "generated_paragraphs": "UNKNOWN",
            "semantic_units": "UNKNOWN",
            "counted_as_zero": False,
        },
        "assumptions": assumptions,
        "strategy_a": {
            "name": STRATEGY_A,
            "requests_low": a_low,
            "requests_central": a_central,
            "requests_high": a_high,
            "units_are_not_requests": True,
            "compatible_with_current_validator": True,
            "single_chapter_low": None,
            "note": "Request count equals generated paragraph count, which remains UNKNOWN.",
        },
        "strategy_b": {
            "name": STRATEGY_B,
            "requests": "UNKNOWN_AND_NOT_CURRENTLY_COMPATIBLE",
            "compatible_with_current_validator": False,
            "schema_pr_is_array": True,
            "validator_requires_single_paragraph": True,
            "declared_compatible_without_verification": False,
        },
        "strategy_c": {
            "name": STRATEGY_C,
            "requests": chapters,
            "compatible_with_current_validator": False,
            "truncation_risk": "high_historical_terra_incomplete_outputs",
        },
        "candidate": CANDIDATE_GRANULARITY,
        "validator_constraint": granularity["current_builders"]["validator_error"],
        "secrets_included": False,
    }


__all__ = ["request_volume_scenarios"]
