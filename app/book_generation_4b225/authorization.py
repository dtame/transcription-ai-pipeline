"""CH003–CH004 resume authorization manifest. Not reusable."""

from __future__ import annotations

from typing import Any

from app.book_generation_4b225.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_CHAPTER_IDS,
    BATCH_ID,
    BUDGET_CAP_DISPLAY,
    CONSUMED_4B223_SCOPE,
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
        "batch_id": BATCH_ID,
        "provider": PROVIDER,
        "model": f"{PROVIDER}/{MODEL}",
        "chapters": list(AUTHORIZED_CHAPTER_IDS),
        "chapter": chapter_id,
        "calls_authorized": AUTHORIZED_ANTHROPIC_CALLS,
        "calls_consumed": consumed_calls,
        "max_calls_per_chapter": 1,
        "maximum_budget": BUDGET_CAP_DISPLAY,
        "prompt": PROMPT_VERSION,
        "previous_batch01_authorization": CONSUMED_4B223_SCOPE,
        "previous_authorization_reusable": False,
        "historical_remaining_is_not_this_authorization": True,
        "openai": "forbidden",
        "terra": "forbidden",
        "other_anthropic_models": "forbidden",
        "other_chapters": "forbidden",
        "ch001_regeneration": "forbidden",
        "ch002_regeneration": "forbidden",
        "ch012_regeneration": "forbidden",
        "ch018_regeneration": "forbidden",
        "batch02": "forbidden",
        "retry": 0,
        "fallback": "forbidden",
        "correction_loop": "forbidden",
        "additional_generation": "forbidden",
        "automatic_validation_calls": "forbidden",
        "production_writes": "forbidden",
        "global_prompt_activation": "forbidden",
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
