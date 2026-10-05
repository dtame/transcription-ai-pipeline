"""Scale-up options. No provider call. An estimate is not an authorization."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.book_editorial_acceptance_4b219.constants import (
    CH012_ACTUAL_COST_USD,
    CHAPTER_ID,
    H01_ANALOG_USD,
    HISTORICAL_CHAPTER_CENTRAL_USD,
    PARAGRAPH_COUNT,
    PHASE,
    RECOMMENDED_OPTION,
    REMAINING_CHAPTER_COUNT,
    TOTAL_CHAPTER_COUNT,
)
from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.identity import load_production_inputs
from app.book_generation_4b217.constants import PROJECT_NAME


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000001")))


def remaining_chapter_inventory(plan) -> list[dict[str, Any]]:
    rows = []
    for chapter in plan.chapters:
        if chapter.chapter_id == CHAPTER_ID:
            continue
        rows.append(
            {
                "chapter_id": chapter.chapter_id,
                "working_title": chapter.working_title,
                "section_count": len(chapter.sections),
                "idea_count": len(assigned_idea_ids_for_chapter(chapter)),
            }
        )
    return rows


def scale_up_options(*, plan=None) -> dict[str, Any]:
    if plan is None:
        plan = load_production_inputs(PROJECT_NAME).plan
    remaining = remaining_chapter_inventory(plan)
    if len(remaining) != REMAINING_CHAPTER_COUNT:
        remaining_count = len(remaining)
    else:
        remaining_count = REMAINING_CHAPTER_COUNT
    option_a_cost = _money(H01_ANALOG_USD * Decimal(PARAGRAPH_COUNT))
    option_b_central = _money(HISTORICAL_CHAPTER_CENTRAL_USD)
    option_b_actual_analog = _money(CH012_ACTUAL_COST_USD)
    remaining_central = _money(HISTORICAL_CHAPTER_CENTRAL_USD * Decimal(remaining_count))
    remaining_actual_analog = _money(CH012_ACTUAL_COST_USD * Decimal(remaining_count))
    return {
        "phase": PHASE,
        "provider_calls_this_phase": 0,
        "this_estimate_is_not_an_authorization": True,
        "remaining_chapter_count": remaining_count,
        "total_chapter_count": TOTAL_CHAPTER_COUNT,
        "accepted_chapter_excluded": CHAPTER_ID,
        "remaining_chapters": remaining,
        "recommended_option": RECOMMENDED_OPTION,
        "options": {
            "A": {
                "name": "Additional semantic validation of CH012",
                "choose_only_if": (
                    "A substantial unresolved risk really justifies a new provider call."
                ),
                "benefits": [
                    "Would inspect new claims, causality, testimony, and references with Terra.",
                    "Would produce a paragraph-level semantic dossier for the accepted chapter.",
                ],
                "risks": [
                    "The current Semantic Gate can false-reject preserved reservations and restatement.",
                    "Empty IDEA handles in paras[].e can fail the historical validator without a missing teaching.",
                    "A FAIL could pressure a rewrite of an already accepted chapter.",
                    "Spends a provider call without changing the editorial acceptance already recorded.",
                ],
                "forecast_cost_usd": {
                    "terra_h01_analog_14_paragraphs": option_a_cost,
                    "reasoning_token_billing": "UNKNOWN",
                    "long_context_pricing": "UNKNOWN",
                    "complete_cost": "UNKNOWN",
                    "counted_as_zero": False,
                },
                "prerequisites": [
                    "A new explicit Terra authorization.",
                    "A rule that a false rejection must go to human review, not automatic rewrite.",
                    "The accepted chapter pair remains frozen.",
                ],
                "schedule_impact": (
                    "Adds one validation cycle before any remaining chapter can be prepared."
                ),
                "justified_now": False,
                "why_not_chosen": (
                    "The remaining CH012 questions are editorial glosses and a possible "
                    "minor EX030 neighboring detail. They do not constitute a substantial "
                    "unresolved risk that requires a provider call before recording acceptance."
                ),
            },
            "B": {
                "name": "Second pilot chapter",
                "choose_if": (
                    "A second sample is required to test narrative voice and IDEA-handle robustness."
                ),
                "benefits": [
                    "Would be the first real call of prompt 1.1.",
                    "Would test whether IDEA handles appear in paras[].e without invention.",
                    "Would sample a harder remaining chapter before a wider queue.",
                ],
                "risks": [
                    "Multiplies pilots and consumes another one-shot authorization.",
                    "CH012 already demonstrated voice, section order, and readable restatement.",
                    "A second isolated pilot still would not authorize the other 17 chapters.",
                    "Harder remaining chapters (CH006, CH013, CH001, CH016) would still need "
                    "their own controls.",
                ],
                "forecast_cost_usd": {
                    "generator_historical_central": option_b_central,
                    "generator_ch012_actual_analog": option_b_actual_analog,
                    "semantic_gate": "UNKNOWN",
                    "complete_cost": "UNKNOWN",
                    "counted_as_zero": False,
                    "note": (
                        "CH012 actual spend was 0.036152 USD. Remaining chapters are not "
                        "the same size. CH006 has 38 ideas and 8 sections."
                    ),
                },
                "prerequisites": [
                    "A new explicit one-chapter Sonnet authorization.",
                    "Prompt 1.1 used only as an isolated candidate.",
                    "A hard stop if IDEA handles are invented or missing after a clear correspondence.",
                ],
                "schedule_impact": (
                    "Inserts another full pilot cycle before controlled remaining-chapter preparation."
                ),
                "justified_now": False,
                "why_not_chosen": (
                    "Voice and four-section restatement are already accepted on CH012. "
                    "The untested 1.1 handle instruction can be controlled by a first "
                    "remaining-chapter hard stop rather than by multiplying dedicated pilots."
                ),
            },
            "C": {
                "name": "Preparation of controlled generation of the remaining 18 chapters",
                "prefer_if": (
                    "Remaining risks can be mastered without multiplying dedicated pilots."
                ),
                "benefits": [
                    "Closes the CH012 editorial review and moves the pipeline to a queue design.",
                    "Keeps generation chapter-by-chapter with per-chapter authorization and caps.",
                    "Can use prompt 1.1 as the reference candidate without promoting it.",
                    "Can place the first remaining chapter under a hard IDEA-handle stop.",
                ],
                "risks": [
                    "Prompt 1.1 is untested in a real call.",
                    "Chapter sizes vary sharply; CH006, CH013, CH001, and CH016 are harder.",
                    "Semantic certification of CH012 has not been performed.",
                    "A queue without per-chapter stops could become an unauthorized 18-call run.",
                ],
                "forecast_cost_usd": {
                    "this_preparation_phase": 0.0,
                    "later_18_chapter_generator_historical_central_envelope": remaining_central,
                    "later_18_chapter_generator_ch012_actual_analog": remaining_actual_analog,
                    "later_semantic_gate": "UNKNOWN",
                    "phase5": "UNKNOWN",
                    "complete_cost": "UNKNOWN",
                    "counted_as_zero": False,
                    "not_an_authorization": True,
                },
                "prerequisites": [
                    "Human decision to open a controlled-generation preparation phase.",
                    "Per-chapter authorization, cost cap, and stop conditions.",
                    "Prompt 1.1 remains a candidate until a later explicit promotion.",
                    "No publication and no production-cache write.",
                    "No global 18-chapter authorization in a single token.",
                ],
                "schedule_impact": (
                    "The next operational phase is offline preparation, then a later "
                    "human-authorized first remaining chapter. No generation occurs now."
                ),
                "justified_now": True,
                "why_chosen": (
                    "CH012 is editorially accepted, frozen by hash, internally consistent, "
                    "and the 11 planned ideas are content-supported in the accepted prose. "
                    "Remaining risks — untested 1.1 handles, harder chapters, no semantic "
                    "certificate — can be mastered by per-chapter controls rather than by "
                    "another dedicated CH012-style pilot or a Terra call on the accepted text."
                ),
            },
        },
        "harder_remaining_chapters": [
            row
            for row in remaining
            if row["idea_count"] >= 17
            or row["section_count"] >= 6
            or row["chapter_id"] in {"CH001", "CH016"}
        ],
        "ready_for_controlled_scale_up": False,
        "ready_for_full_real_book_generation": False,
        "why_not_ready_to_execute": (
            "Preparation is recommended. Execution is not authorized. Prompt 1.1 is "
            "inactive and unregistered. No remaining-chapter authorization exists. "
            "Semantic certification has not been performed. book.json stays unpublished."
        ),
        "secrets_included": False,
    }


__all__ = ["remaining_chapter_inventory", "scale_up_options"]
