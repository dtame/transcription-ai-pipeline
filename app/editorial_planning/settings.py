"""Réglages du planner : bornes, thinking, provider figé. Aucun appel réseau."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.settings import resolve_stage_settings
from app.ai.thinking import (
    THINKING_MODE_PROVIDER_DEFAULT,
    resolve_thinking_capabilities,
)
from app.editorial_planning.constants import (
    DEFAULT_MAX_CHAPTER_IDEA_SHARE_WARN,
    DEFAULT_MAX_CHAPTERS,
    DEFAULT_MAX_IDEA_REUSE_COUNT_WARN,
    DEFAULT_MAX_IDEAS_PER_SECTION_WARN,
    DEFAULT_MAX_REUSED_IDEA_RATIO_WARN,
    DEFAULT_MAX_SECTIONS_PER_CHAPTER,
    DEFAULT_MAX_TITLE_CANDIDATES,
    DEFAULT_MAX_TOTAL_SECTIONS,
    DEFAULT_MIN_CHAPTER_IDEA_SHARE_WARN,
    DEFAULT_MIN_CHAPTERS,
    DEFAULT_MIN_SECTIONS_PER_CHAPTER,
    HARD_MAX_OUTPUT_TOKENS,
    MODEL,
    PLANNER_SETTINGS_VERSION,
    PROPOSED_MAX_OUTPUT_TOKENS,
    PROVIDER,
    STAGE_EDITORIAL_PLANNING,
    STRATEGY_GLOBAL,
)


@dataclass(frozen=True)
class PlannerSettings:
    provider: str = PROVIDER
    model: str = MODEL
    strategy: str = STRATEGY_GLOBAL
    thinking_mode: str = THINKING_MODE_PROVIDER_DEFAULT
    effort: str | None = None
    max_output_tokens: int = PROPOSED_MAX_OUTPUT_TOKENS
    min_chapters: int = DEFAULT_MIN_CHAPTERS
    max_chapters: int = DEFAULT_MAX_CHAPTERS
    min_sections_per_chapter: int = DEFAULT_MIN_SECTIONS_PER_CHAPTER
    max_sections_per_chapter: int = DEFAULT_MAX_SECTIONS_PER_CHAPTER
    max_total_sections: int = DEFAULT_MAX_TOTAL_SECTIONS
    max_ideas_per_section_warn: int = DEFAULT_MAX_IDEAS_PER_SECTION_WARN
    max_chapter_idea_share_warn: float = DEFAULT_MAX_CHAPTER_IDEA_SHARE_WARN
    min_chapter_idea_share_warn: float = DEFAULT_MIN_CHAPTER_IDEA_SHARE_WARN
    max_idea_reuse_count_warn: int = DEFAULT_MAX_IDEA_REUSE_COUNT_WARN
    max_reused_idea_ratio_warn: float = DEFAULT_MAX_REUSED_IDEA_RATIO_WARN
    max_title_candidates: int = DEFAULT_MAX_TITLE_CANDIDATES
    temperature: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "settings_version": PLANNER_SETTINGS_VERSION,
            "provider": self.provider,
            "model": self.model,
            "strategy": self.strategy,
            "thinking_mode": self.thinking_mode,
            "effort": self.effort,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "min_chapters": self.min_chapters,
            "max_chapters": self.max_chapters,
            "min_sections_per_chapter": self.min_sections_per_chapter,
            "max_sections_per_chapter": self.max_sections_per_chapter,
            "max_total_sections": self.max_total_sections,
            "max_ideas_per_section_warn": self.max_ideas_per_section_warn,
            "max_chapter_idea_share_warn": self.max_chapter_idea_share_warn,
            "min_chapter_idea_share_warn": self.min_chapter_idea_share_warn,
            "max_idea_reuse_count_warn": self.max_idea_reuse_count_warn,
            "max_reused_idea_ratio_warn": self.max_reused_idea_ratio_warn,
            "max_title_candidates": self.max_title_candidates,
        }


def frozen_production_settings() -> PlannerSettings:
    stage = resolve_stage_settings(STAGE_EDITORIAL_PLANNING)
    if stage.provider != PROVIDER or stage.model != MODEL:
        raise RuntimeError(
            "AI_STAGE_SETTINGS[editorial_planning] n'est plus "
            f"{PROVIDER}/{MODEL} : {stage.provider}/{stage.model}."
        )
    return PlannerSettings(
        provider=stage.provider,
        model=stage.model or MODEL,
        thinking_mode=THINKING_MODE_PROVIDER_DEFAULT,
        effort=None,
        max_output_tokens=PROPOSED_MAX_OUTPUT_TOKENS,
        temperature=None,
    )


def thinking_recommendation() -> dict[str, Any]:
    """
    Phase 4A n'appelle pas le provider. Le contrat thinking d'Opus 5 n'est
    PAS vérifié dans ce dépôt (contrairement à Sonnet 5). Fail-closed :
    provider_default, pas d'effort, pas de budget_tokens.
    """
    caps = resolve_thinking_capabilities(PROVIDER, MODEL)
    return {
        "audited_model": f"{PROVIDER}:{MODEL}",
        "capabilities_known": caps.known,
        "sonnet5_contract_generalized": False,
        "phase4a_thinking_mode": THINKING_MODE_PROVIDER_DEFAULT,
        "phase4a_effort": None,
        "phase4a_thinking_budget_tokens": None,
        "rationale": (
            "Editorial planning is high-complexity organization with a tight "
            "structured-output budget. Opus 5 thinking/effort is unverified "
            "in this repository (known=False). Source Analyzer Sonnet 5 "
            "thinking must not be copied. Phase 4A therefore omits thinking "
            "and effort (provider_default). A future Opus 5 thinking audit "
            "is required before adaptive thinking. If that audit confirms a "
            "Sonnet-like shared max_tokens contract, adaptive+medium may "
            "help planning quality but risks eating the JSON budget; keep "
            "provider_default until measured."
        ),
        "future_candidate_after_audit": {
            "thinking_mode": "adaptive",
            "effort": "medium",
            "blocked_until": "opus-5-thinking-capability-audit",
        },
        "hard_max_output_cap": HARD_MAX_OUTPUT_TOKENS,
        "do_not_raise_max_output_blindly": True,
        "capabilities": caps.to_dict(),
    }
