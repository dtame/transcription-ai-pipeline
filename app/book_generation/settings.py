"""Frozen Book Generator settings. No provider call."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.settings import resolve_stage_settings
from app.ai.thinking import (
    THINKING_MODE_DISABLED,
    resolve_thinking_capabilities,
)
from app.book_generation.constants import (
    BOOK_GENERATOR_SETTINGS_VERSION,
    BOOK_GENERATOR_THINKING_VALIDATED,
    DEFAULT_MAX_OUTPUT_TOKENS,
    HARD_MAX_OUTPUT_TOKENS,
    MODEL,
    PROVIDER,
    STAGE_BOOK_GENERATION,
    STRATEGY_CHAPTER,
)


@dataclass(frozen=True)
class GeneratorSettings:
    provider: str = PROVIDER
    model: str = MODEL
    strategy: str = STRATEGY_CHAPTER
    thinking_mode: str = THINKING_MODE_DISABLED
    effort: str | None = None
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    temperature: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "settings_version": BOOK_GENERATOR_SETTINGS_VERSION,
            "provider": self.provider,
            "model": self.model,
            "strategy": self.strategy,
            "thinking_mode": self.thinking_mode,
            "effort": self.effort,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
        }


def frozen_production_settings() -> GeneratorSettings:
    stage = resolve_stage_settings(STAGE_BOOK_GENERATION)
    if stage.provider != PROVIDER or stage.model != MODEL:
        raise RuntimeError(
            "AI_STAGE_SETTINGS[book_generation] n'est plus "
            f"{PROVIDER}/{MODEL} : {stage.provider}/{stage.model}."
        )
    return GeneratorSettings(
        provider=stage.provider,
        model=stage.model or MODEL,
        thinking_mode=THINKING_MODE_DISABLED,
        effort=None,
        max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
        temperature=None,
    )


def thinking_recommendation() -> dict[str, Any]:
    """
    Sonnet 5 thinking is known in-repo. Book Generator thinking behavior
    is not yet validated. Do not copy Opus Planner settings.
    Shared max_tokens means thinking can consume structured-output budget.
    """
    caps = resolve_thinking_capabilities(PROVIDER, MODEL)
    return {
        "audited_model": f"{PROVIDER}:{MODEL}",
        "capabilities_known": caps.known,
        "book_generator_thinking_validated": BOOK_GENERATOR_THINKING_VALIDATED,
        "phase4b1_thinking_mode": THINKING_MODE_DISABLED,
        "phase4b1_effort": None,
        "phase4b1_thinking_budget_tokens": None,
        "copied_opus_planner_settings": False,
        "rationale": (
            "Sonnet 5 thinking/effort is verified in this repository, but "
            "Book Generator thinking behavior is not yet measured. Thinking "
            "tokens share max_tokens with visible structured JSON "
            "(max_tokens_shared_output=True). Phase 4B.1 therefore disables "
            "thinking for the future canary (one call, zero retries) so the "
            "output budget remains available for manuscript JSON. Adaptive "
            "thinking is a later candidate only after a grammar canary."
        ),
        "future_candidate_after_canary": {
            "thinking_mode": "adaptive",
            "effort": "low",
            "blocked_until": "book-generator-grammar-canary",
        },
        "hard_max_output_cap": HARD_MAX_OUTPUT_TOKENS,
        "do_not_raise_max_output_blindly": True,
        "capabilities": caps.to_dict(),
    }
