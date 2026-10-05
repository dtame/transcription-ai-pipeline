"""Future batch authorization template. Not granted in this phase."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_batch_preparation_4b222.constants import (
    AUTHORIZATION_TEMPLATE_VERSION,
    AUTHORIZED_SPEND_USD,
    FAITHFUL_PROMPT_1_1,
    FIRST_BATCH_ID,
    MODEL,
    PHASE,
    PROVIDER,
)


def batch_authorization_template(
    *,
    plan: Mapping[str, Any],
    cost: Mapping[str, Any],
) -> dict[str, Any]:
    first = next(
        (row for row in plan.get("batches") or [] if row.get("batch_id") == FIRST_BATCH_ID),
        {},
    )
    first_cost = next(
        (row for row in cost.get("batches") or [] if row.get("batch_id") == FIRST_BATCH_ID),
        {},
    )
    per_chapter = [
        row
        for row in cost.get("per_chapter") or []
        if row.get("chapter_id") in (first.get("chapter_ids") or [])
    ]
    return {
        "phase": PHASE,
        "template_version": AUTHORIZATION_TEMPLATE_VERSION,
        "not_granted_now": True,
        "authorized_now_usd": float(AUTHORIZED_SPEND_USD),
        "this_estimate_is_not_an_authorization": True,
        "required_human_token": {
            "authorization_scope": (
                "BOOK_GENERATION_LATER_PHASE_BATCH_01_"
                "CH001_CH002_CH003_CH004_ONE_SHOT_EACH_ONLY"
            ),
            "batch_id": FIRST_BATCH_ID,
            "chapter_ids": list(first.get("chapter_ids") or []),
            "provider": PROVIDER,
            "model": MODEL,
            "prompt_version": FAITHFUL_PROMPT_1_1,
            "prompt_activation": "isolated_explicit_option_only",
            "global_cap_usd": first_cost.get("proposed_cap_usd"),
            "calculable_maximum_usd": first_cost.get("calculable_maximum_usd"),
            "per_chapter_cap_usd": {
                row["chapter_id"]: row.get("proposed_cap_usd") for row in per_chapter
            },
            "maximum_remote_calls": len(first.get("chapter_ids") or []),
            "maximum_remote_calls_per_chapter": 1,
            "retries": 0,
            "fallbacks": 0,
            "retry_policy": "forbidden",
            "fallback_policy": "forbidden",
            "central_estimate_must_not_be_the_cap": True,
            "precall_verification": True,
            "stop_if_cost_unknown": True,
            "stop_if_cap_exceeded": True,
            "stop_if_idea_handles_missing_or_invented": True,
            "stop_if_src_invalid": True,
            "stop_if_truncated": True,
            "stop_if_uncertain_lock": True,
            "stop_if_prompt_or_model_changes": True,
            "isolated_audit_directory_required": True,
            "one_chapter_per_provider_call": True,
            "publication": False,
            "ch012_regeneration": False,
            "ch018_regeneration": False,
            "seventeen_chapter_run": False,
        },
        "prepared_by_phase": PHASE,
        "secrets_included": False,
    }


__all__ = ["batch_authorization_template"]
