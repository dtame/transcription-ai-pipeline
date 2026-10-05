"""Single sequential execution plan for the remaining 13 chapters. Not executed."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_full_generation_preparation_4b226.constants import (
    ACCEPTED_CHAPTER_IDS,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_1_1_SHA256,
    EXPECTED_SOURCE_MAP,
    EXPECTED_TRANSCRIPT,
    FALLBACKS,
    FUTURE_AUTHORIZATION_SCOPE,
    FUTURE_MAX_CALLS,
    FUTURE_MAX_CALLS_PER_CHAPTER,
    MODEL,
    PHASE,
    PROMPT_VERSION,
    PROVIDER,
    REMAINING_CHAPTER_IDS,
    RETRIES,
    VALIDATOR_VERSION,
)


def remaining_chapters_generation_plan(
    *,
    inventory: Mapping[str, Any],
    cost: Mapping[str, Any],
) -> dict[str, Any]:
    steps = []
    for index, chapter_id in enumerate(REMAINING_CHAPTER_IDS, start=1):
        row = next(
            item
            for item in inventory.get("chapters") or []
            if item.get("chapter_id") == chapter_id
        )
        cost_row = next(
            item
            for item in cost.get("per_chapter") or []
            if item.get("chapter_id") == chapter_id
        )
        steps.append(
            {
                "order": index,
                "chapter_id": chapter_id,
                "working_title": row.get("working_title"),
                "anthropic_calls": 1,
                "retries": 0,
                "fallbacks": 0,
                "steps": [
                    "verify_canonical_hashes",
                    "verify_accepted_chapter_manifest",
                    "verify_model_and_prompt",
                    "verify_call_lock",
                    "verify_remaining_budget",
                    "hydrate_required_sources",
                    "build_generation_context",
                    "compute_preflight_maximum",
                    "persist_call_reservation",
                    "single_anthropic_call",
                    "save_raw_response_durably",
                    "normalize_admissible_empty_paragraphs",
                    "validate_derived_json",
                    "validate_sections",
                    "validate_ideas",
                    "validate_src",
                    "review_ex_ref_unc",
                    "render_markdown",
                    "record_actual_cost",
                    "update_progress_journal",
                    "continue_if_blocking_controls_pass",
                ],
                "empty_paragraph_normalization": "after_raw_save_before_structural_validation",
                "production_validator_required": True,
                "human_editorial_acceptance_required": True,
                "automatic_book_integration": False,
                "central_estimate_usd": cost_row.get("central_estimate_usd"),
                "preflight_max_cost_usd": cost_row.get("preflight_max_cost_usd"),
            }
        )
    return {
        "phase": PHASE,
        "plan_id": "REMAINING_13_CHAPTERS_ONE_SHOT_SEQUENTIAL",
        "future_authorization_scope": FUTURE_AUTHORIZATION_SCOPE,
        "future_authorization_activated": False,
        "executed_in_this_phase": False,
        "order": list(REMAINING_CHAPTER_IDS),
        "deterministic_order": True,
        "accepted_chapter_ids_excluded": list(ACCEPTED_CHAPTER_IDS),
        "model": f"{PROVIDER}/{MODEL}",
        "prompt": PROMPT_VERSION,
        "prompt_sha256": EXPECTED_PROMPT_1_1_SHA256,
        "canonical_hashes": {
            "source_map": EXPECTED_SOURCE_MAP,
            "editorial_plan": EXPECTED_EDITORIAL_PLAN,
            "clean_transcript": EXPECTED_TRANSCRIPT,
        },
        "max_calls": FUTURE_MAX_CALLS,
        "max_calls_per_chapter": FUTURE_MAX_CALLS_PER_CHAPTER,
        "retries": RETRIES,
        "fallbacks": FALLBACKS,
        "validator_version": VALIDATOR_VERSION,
        "sequential": True,
        "reasons_for_sequential": [
            "cost control",
            "durable lock persistence",
            "resume after interruption",
            "validation",
            "progress tracking",
            "stop on blocking error",
        ],
        "generated_candidates_remain_pending_human_acceptance": True,
        "must_not_integrate_into_canonical_accepted_book": True,
        "resume": {
            "ignore_already_accepted_chapters": True,
            "ignore_already_generated_and_validated_in_this_execution": True,
            "never_repeat_consumed_call": True,
            "never_repeat_uncertain_call": True,
            "keep_raw_responses": True,
            "keep_costs": True,
            "keep_errors": True,
            "resume_at_next_admissible_chapter": True,
            "never_execute_out_of_scope_chapter": True,
            "resume_is_not_a_new_financial_authorization": True,
        },
        "per_chapter": steps,
        "secrets_included": False,
    }


__all__ = ["remaining_chapters_generation_plan"]
