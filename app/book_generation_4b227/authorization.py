"""Remaining-13 one-shot authorization manifest. Not reusable."""

from __future__ import annotations

from typing import Any

from app.book_generation_4b227.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_CHAPTER_IDS,
    BUDGET_CAP_DISPLAY,
    CONSUMED_4B226_SCOPE,
    FORBIDDEN_CHAPTER_IDS,
    MODEL,
    PHASE,
    PROMPT_VERSION,
    PROVIDER,
)


def authorization_manifest(
    *,
    consumed_calls: int,
    sha256: str | None,
    blocked: bool,
    block_reason: str | None,
    lock_state: str | None = None,
    chapter_id: str | None = None,
) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider": PROVIDER,
        "model": f"{PROVIDER}/{MODEL}",
        "chapters": list(AUTHORIZED_CHAPTER_IDS),
        "accepted_chapters_excluded": list(FORBIDDEN_CHAPTER_IDS),
        "chapter": chapter_id,
        "calls_authorized": AUTHORIZED_ANTHROPIC_CALLS,
        "calls_consumed": consumed_calls,
        "max_calls_per_chapter": 1,
        "maximum_budget": BUDGET_CAP_DISPLAY,
        "prompt": PROMPT_VERSION,
        "previous_preparation_scope": CONSUMED_4B226_SCOPE,
        "previous_authorization_reusable": False,
        "historical_remaining_is_not_this_authorization": True,
        "openai": "forbidden",
        "terra": "forbidden",
        "other_anthropic_models": "forbidden",
        "accepted_chapter_regeneration": "forbidden",
        "retry": 0,
        "fallback": "forbidden",
        "correction_loop": "forbidden",
        "additional_generation": "forbidden",
        "automatic_validation_calls": "forbidden",
        "production_writes": "forbidden",
        "global_prompt_activation": "forbidden",
        "publication": "forbidden",
        "reusable": False,
        "one_shot_per_chapter": True,
        "unspent_budget_is_not_new_authorization": True,
        "consumed": consumed_calls > 0,
        "blocked": blocked,
        "block_reason": block_reason,
        "lock_state": lock_state,
        "request_sha256": sha256,
        "secrets_included": False,
    }


__all__ = ["authorization_manifest"]
