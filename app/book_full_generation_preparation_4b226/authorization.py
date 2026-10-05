"""Future one-shot authorization proposal. Not activated in this phase."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_full_generation_preparation_4b226.constants import (
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_1_1_SHA256,
    EXPECTED_SOURCE_MAP,
    EXPECTED_TRANSCRIPT,
    FALLBACKS,
    FUTURE_AUTHORIZATION_ACTIVATED,
    FUTURE_AUTHORIZATION_SCOPE,
    FUTURE_MAX_CALLS,
    FUTURE_MAX_CALLS_PER_CHAPTER,
    MODEL,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    REMAINING_CHAPTER_IDS,
    RETRIES,
)


def global_authorization_proposal(
    *,
    cost: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "authorization_scope": FUTURE_AUTHORIZATION_SCOPE,
        "activated": FUTURE_AUTHORIZATION_ACTIVATED,
        "activation_forbidden_in_this_phase": True,
        "project_id": PROJECT_NAME,
        "chapter_ids": list(REMAINING_CHAPTER_IDS),
        "chapter_count": len(REMAINING_CHAPTER_IDS),
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
        "retry_forbidden": True,
        "fallback_forbidden": True,
        "openai_forbidden": True,
        "terra_forbidden": True,
        "accepted_chapters_forbidden": True,
        "publication_forbidden_until_human_acceptance": True,
        "future_financial_cap_usd": cost.get("RECOMMENDED_AUTHORIZATION_CAP"),
        "global_estimated_cost_usd": cost.get("GLOBAL_ESTIMATED_COST"),
        "global_preflight_max_cost_usd": cost.get("GLOBAL_PREFLIGHT_MAX_COST"),
        "this_proposal_is_not_an_authorization": True,
        "historical_remaining_budget_is_not_this_authorization": True,
        "plan_id": plan.get("plan_id"),
        "required_human_token": {
            "authorization_scope": FUTURE_AUTHORIZATION_SCOPE,
            "must_name_the_13_chapters": True,
            "must_name_the_global_financial_cap": True,
            "chapter_by_chapter_authorization_rejected": True,
        },
        "secrets_included": False,
    }


__all__ = ["global_authorization_proposal"]
