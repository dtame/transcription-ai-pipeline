"""Future one-chapter authorization template. Not granted in this phase."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_scale_up_preparation_4b220.constants import (
    AUTHORIZED_SPEND_USD,
    EXPECTED_FIRST_CHAPTER_ID,
    FAITHFUL_PROMPT_1_1,
    MODEL,
    PHASE,
    PROVIDER,
)


def future_first_chapter_authorization_template(
    *,
    selection: Mapping[str, Any],
    cost: Mapping[str, Any],
) -> dict[str, Any]:
    first = dict(cost.get("first_chapter") or {})
    chapter_id = str(selection.get("selected_chapter_id") or EXPECTED_FIRST_CHAPTER_ID)
    maximum = first.get("calculable_maximum_usd")
    return {
        "phase_that_would_consume_it": "later_explicit_real_chapter_phase",
        "not_granted_now": True,
        "authorized_now_usd": float(AUTHORIZED_SPEND_USD),
        "required_human_token": {
            "authorization_scope": (
                f"BOOK_GENERATION_LATER_PHASE_{chapter_id}_FIRST_REMAINING_"
                "CHAPTER_ONE_SHOT_ONLY"
            ),
            "chapter_id": chapter_id,
            "section_ids": list(selection.get("section_ids") or []),
            "provider": PROVIDER,
            "model": MODEL,
            "prompt_version": FAITHFUL_PROMPT_1_1,
            "prompt_activation": "isolated_explicit_option_only",
            "maximum_remote_calls": 1,
            "retries": 0,
            "fallbacks": 0,
            "cost_cap_usd": "human_must_set_at_or_above_calculable_maximum",
            "calculable_maximum_usd": maximum,
            "central_estimate_must_not_be_the_cap": True,
            "precall_verification": True,
            "stop_if_cost_unknown": True,
            "stop_if_cap_exceeded": True,
            "stop_if_idea_handles_missing_or_invented": True,
            "isolated_audit_directory_required": True,
            "publication": False,
            "other_chapters": False,
            "ch012_regeneration": False,
            "eighteen_chapter_run": False,
        },
        "prepared_by_phase": PHASE,
        "secrets_included": False,
    }


__all__ = ["future_first_chapter_authorization_template"]
