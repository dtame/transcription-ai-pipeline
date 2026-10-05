"""One-shot provider authorization manifest. Not reusable."""

from __future__ import annotations

from typing import Any

from app.book_generation_4b221.constants import (
    AUTHORIZATION_SCOPE,
    BUDGET_CAP_DISPLAY,
    MODEL,
    PHASE,
    PROMPT_VERSION,
    PROVIDER,
    TARGET_CHAPTER_ID,
)


def authorization_manifest(
    *,
    consumed: bool,
    sha256: str | None,
    blocked: bool,
    block_reason: str | None,
    lock_state: str | None = None,
) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider": PROVIDER,
        "model": f"{PROVIDER}/{MODEL}",
        "chapter": TARGET_CHAPTER_ID,
        "calls": 1,
        "maximum_budget": BUDGET_CAP_DISPLAY,
        "prompt": PROMPT_VERSION,
        "openai": "forbidden",
        "terra": "forbidden",
        "other_anthropic_models": "forbidden",
        "other_chapters": "forbidden",
        "ch012_regeneration": "forbidden",
        "retry": 0,
        "fallback": "forbidden",
        "correction_loop": "forbidden",
        "additional_generation": "forbidden",
        "automatic_validation_calls": "forbidden",
        "production_writes": "forbidden",
        "global_prompt_activation": "forbidden",
        "reusable": False,
        "one_shot": True,
        "consumed": consumed,
        "blocked": blocked,
        "block_reason": block_reason,
        "lock_state": lock_state,
        "request_sha256": sha256,
        "secrets_included": False,
    }


__all__ = ["authorization_manifest"]
