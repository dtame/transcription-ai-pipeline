"""One-shot provider authorization manifest. Not reusable."""

from __future__ import annotations

from typing import Any

from app.book_generation_4b217.constants import (
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
) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider": PROVIDER,
        "model": MODEL,
        "chapter": TARGET_CHAPTER_ID,
        "calls": 1,
        "maximum_budget": BUDGET_CAP_DISPLAY,
        "prompt": PROMPT_VERSION,
        "openai": "forbidden",
        "terra": "forbidden",
        "other_anthropic_models": "forbidden",
        "retry": 0,
        "fallback": "forbidden",
        "correction_loop": "forbidden",
        "additional_generation": "forbidden",
        "automatic_validation_calls": "forbidden",
        "production_writes": "forbidden",
        "reusable": False,
        "one_shot": True,
        "consumed": consumed,
        "blocked": blocked,
        "block_reason": block_reason,
        "request_sha256": sha256,
        "secrets_included": False,
    }


__all__ = ["authorization_manifest"]
