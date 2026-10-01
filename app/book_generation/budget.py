"""Per-chapter context/output budget. Uses Phase 2B Sonnet 5 capabilities."""

from __future__ import annotations

import math
from statistics import mean, median
from typing import Any, Sequence

from app.ai.capabilities import resolve_capabilities
from app.ai.estimation import estimate_tokens
from app.ai.settings import resolve_stage_settings
from app.book_generation.constants import (
    CONSERVATIVE_MAX_OUTPUT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    FALLBACK_OUTPUT_TRIGGER,
    FALLBACK_SECTION,
    FALLBACK_UTILIZATION_TRIGGER,
    GENERATION_UNIT_CHAPTER,
    GENERATION_UNIT_SECTION,
    HARD_MAX_OUTPUT_TOKENS,
    MIN_MAX_OUTPUT_TOKENS,
    STAGE_BOOK_GENERATION,
)
from app.book_generation.evidence import evidence_metrics
from app.book_generation.payload import payload_audit
from app.book_generation.settings import GeneratorSettings, frozen_production_settings

_PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC = 1.9365384615384615
_PROVIDER_CHARS_PER_TOKEN_MID = 2.5
# Manuscript estimate only — not a length target.
_WORDS_PER_IDEA_MID = 120
_WORDS_PER_IDEA_HIGH = 220
_TOKENS_PER_WORD = 1.3
_JSON_OVERHEAD = 1.25


def _provider_tokens(chars: int, chars_per_token: float) -> int:
    return int(math.ceil(max(0, chars) / chars_per_token))


def usable_context(*, max_output_tokens: int) -> dict[str, Any]:
    stage = resolve_stage_settings(STAGE_BOOK_GENERATION)
    caps = resolve_capabilities(stage.provider, stage.model or "")
    ratio = stage.context_safety_ratio
    usable = int(caps.context_window * ratio) - int(max_output_tokens)
    return {
        "provider": stage.provider,
        "model": stage.model,
        "context_window": caps.context_window,
        "model_max_output_tokens": caps.max_output_tokens,
        "reserved_output_tokens": int(max_output_tokens),
        "safety_ratio": ratio,
        "capabilities_known": caps.known,
        "usable_input_tokens": usable,
        "formula": "context_window * safety_ratio - reserved_output",
    }


def estimate_manuscript_output(idea_count: int, section_count: int) -> dict[str, int]:
    mid_words = max(1, idea_count) * _WORDS_PER_IDEA_MID + section_count * 40
    high_words = max(1, idea_count) * _WORDS_PER_IDEA_HIGH + section_count * 80
    expected = int(math.ceil(mid_words * _TOKENS_PER_WORD * _JSON_OVERHEAD))
    conservative = int(math.ceil(high_words * _TOKENS_PER_WORD * _JSON_OVERHEAD))
    return {
        "expected_output_tokens": expected,
        "conservative_output_tokens": conservative,
        "estimated_mid_words": mid_words,
        "estimated_high_words": high_words,
    }


def recommend_max_output(expected: int, conservative: int) -> int:
    raw = max(expected * 3, conservative * 2, MIN_MAX_OUTPUT_TOKENS)
    stepped = max(DEFAULT_MAX_OUTPUT_TOKENS, raw)
    return min(HARD_MAX_OUTPUT_TOKENS, max(MIN_MAX_OUTPUT_TOKENS, stepped))


def measure_request_budget(
    evidence: dict[str, Any],
    *,
    settings: GeneratorSettings | None = None,
    idea_count: int,
    section_count: int,
    prompt_version: str | None = None,
) -> dict[str, Any]:
    settings = settings or frozen_production_settings()
    output = estimate_manuscript_output(idea_count, section_count)
    recommended = recommend_max_output(
        output["expected_output_tokens"], output["conservative_output_tokens"]
    )
    audit = payload_audit(
        evidence,
        settings=settings,
        max_output_tokens=recommended,
        prompt_version=prompt_version,
    )
    request_chars = audit["system_prompt_chars"] + audit["user_prompt_chars"]
    local = audit["local_input_token_estimate"]
    mid = max(
        int(local.get("tokens") or 0),
        _provider_tokens(request_chars, _PROVIDER_CHARS_PER_TOKEN_MID),
    )
    pessimistic = _provider_tokens(
        request_chars, _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC
    )
    usable = usable_context(max_output_tokens=recommended)
    usable_tokens = int(usable["usable_input_tokens"])
    utilization = pessimistic / usable_tokens if usable_tokens else 1.0
    fallback = utilization >= FALLBACK_UTILIZATION_TRIGGER or recommended >= (
        FALLBACK_OUTPUT_TRIGGER
    )
    return {
        "evidence": evidence_metrics(evidence),
        "request": {
            "system_chars": audit["system_prompt_chars"],
            "user_chars": audit["user_prompt_chars"],
            "payload_sha256": audit["payload_sha256"],
            "local_token_estimate": local,
            "provider_adjusted_mid": mid,
            "provider_adjusted_pessimistic": pessimistic,
        },
        "output": output,
        "recommended_max_output": recommended,
        "usable": usable,
        "context_utilization_pessimistic": round(utilization, 4),
        "context_safe": pessimistic < usable_tokens and mid < usable_tokens,
        "generation_unit": GENERATION_UNIT_SECTION if fallback else GENERATION_UNIT_CHAPTER,
        "fallback_unit": FALLBACK_SECTION,
        "fallback_triggered": fallback,
        "payload_audit": {
            "structured_output": audit["structured_output"],
            "thinking_present": audit["thinking_present"],
            "max_tokens": audit["max_tokens"],
            "http_sent": False,
        },
    }


def conservative_needs_fallback(conservative_output: int) -> bool:
    return conservative_output > HARD_MAX_OUTPUT_TOKENS


def distribution(values: Sequence[int | float]) -> dict[str, float]:
    if not values:
        return {"min": 0, "median": 0, "mean": 0, "p90": 0, "max": 0}
    ordered = sorted(float(value) for value in values)
    index = min(len(ordered) - 1, max(0, int(math.ceil(0.9 * len(ordered)) - 1)))
    return {
        "min": ordered[0],
        "median": float(median(ordered)),
        "mean": float(mean(ordered)),
        "p90": ordered[index],
        "max": ordered[-1],
    }
