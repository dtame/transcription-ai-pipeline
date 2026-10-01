"""Budgets d'entrée et de sortie. Estimations uniquement, jamais un coût."""

from __future__ import annotations

import json
import math
from typing import Any, Mapping

from app.ai.capabilities import resolve_capabilities
from app.ai.estimation import estimate_tokens
from app.ai.settings import resolve_stage_settings
from app.editorial_planning.constants import (
    CONSERVATIVE_MAX_OUTPUT_TOKENS,
    HARD_MAX_OUTPUT_TOKENS,
    PROPOSED_MAX_OUTPUT_TOKENS,
    STAGE_EDITORIAL_PLANNING,
)
from app.editorial_planning.digest import render_digest
from app.editorial_planning.payload import payload_audit
from app.editorial_planning.settings import PlannerSettings, frozen_production_settings
from app.source_analysis.models import SourceMap

# Densité Anthropic compacte mesurée en consolidation 3B (sortie).
# Borne pessimiste pour du JSON mixte ; ce n'est pas un tarif.
_PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC = 1.9365384615384615
_PROVIDER_CHARS_PER_TOKEN_MID = 2.5


def _provider_tokens(chars: int, chars_per_token: float) -> int:
    return int(math.ceil(max(0, chars) / chars_per_token))


def usable_input_budget(*, max_output_tokens: int) -> dict[str, Any]:
    stage = resolve_stage_settings(STAGE_EDITORIAL_PLANNING)
    caps = resolve_capabilities(stage.provider, stage.model or "")
    ratio = stage.context_safety_ratio
    usable = int(caps.context_window * ratio) - int(max_output_tokens)
    return {
        "provider": stage.provider,
        "model": stage.model,
        "context_window": caps.context_window,
        "model_max_output_tokens": caps.max_output_tokens,
        "planner_max_output_tokens": int(max_output_tokens),
        "safety_ratio": ratio,
        "capabilities_known": caps.known,
        "usable_input_tokens": usable,
        "formula": "context_window * safety_ratio - max_output_tokens",
    }


def measure_source_map_text(text: str, *, model: str) -> dict[str, Any]:
    raw = text.encode("utf-8")
    local = estimate_tokens(text, model=model)
    chars = len(text)
    return {
        "chars": chars,
        "utf8_bytes": len(raw),
        "local_token_estimate": local.to_dict(),
        "provider_adjusted_pessimistic": {
            "tokens": _provider_tokens(chars, _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC),
            "chars_per_token": _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC,
            "basis": "Phase 3B A.44 compact-output density (pessimistic for input)",
            "estimated": True,
        },
        "provider_adjusted_mid": {
            "tokens": _provider_tokens(chars, _PROVIDER_CHARS_PER_TOKEN_MID),
            "chars_per_token": _PROVIDER_CHARS_PER_TOKEN_MID,
            "basis": "mid JSON/text mix",
            "estimated": True,
        },
    }


def measure_input_budget(
    source_map: SourceMap,
    source_map_text: str,
    *,
    settings: PlannerSettings | None = None,
) -> dict[str, Any]:
    settings = settings or frozen_production_settings()
    source_metrics = measure_source_map_text(source_map_text, model=settings.model)
    digest = render_digest(source_map)
    digest_metrics = measure_source_map_text(digest, model=settings.model)
    audit = payload_audit(source_map, settings=settings)
    budget_proposed = usable_input_budget(max_output_tokens=settings.max_output_tokens)
    budget_model_ceiling = usable_input_budget(
        max_output_tokens=budget_proposed["model_max_output_tokens"]
    )
    request_chars = audit["system_prompt_chars"] + audit["user_prompt_chars"]
    request_estimate = audit["local_input_token_estimate"]
    adjusted = max(
        int(request_estimate.get("tokens") or 0),
        _provider_tokens(request_chars, _PROVIDER_CHARS_PER_TOKEN_MID),
    )
    pessimistic = _provider_tokens(
        request_chars, _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC
    )
    usable = int(budget_proposed["usable_input_tokens"])
    headroom = usable - pessimistic
    feasible = pessimistic < usable and adjusted < usable
    return {
        "source_map": source_metrics,
        "planner_digest": digest_metrics,
        "request": {
            "system_chars": audit["system_prompt_chars"],
            "user_chars": audit["user_prompt_chars"],
            "digest_chars": audit["digest_chars"],
            "local_token_estimate": request_estimate,
            "provider_adjusted_mid": adjusted,
            "provider_adjusted_pessimistic": pessimistic,
            "payload_sha256": audit["payload_sha256"],
        },
        "usable_with_proposed_max_output": budget_proposed,
        "usable_with_model_max_output": budget_model_ceiling,
        "headroom_tokens_pessimistic": headroom,
        "one_global_call_feasible": feasible,
        "windowed_planning": "NOT_INTRODUCED",
        "decision": "ONE_GLOBAL_EDITORIAL_PLANNING_CALL" if feasible else "STOP_HUMAN_REVIEW",
    }


def measure_output_budget(transport: Mapping[str, Any]) -> dict[str, Any]:
    compact = json.dumps(dict(transport), ensure_ascii=False, separators=(",", ":"))
    chars = len(compact)
    local = estimate_tokens(compact, model=frozen_production_settings().model)
    expected = max(local.tokens, _provider_tokens(chars, _PROVIDER_CHARS_PER_TOKEN_MID))
    conservative = max(
        expected * 2,
        _provider_tokens(chars, _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC) * 2,
    )
    hard = max(conservative * 2, HARD_MAX_OUTPUT_TOKENS // 2)
    proposed = PROPOSED_MAX_OUTPUT_TOKENS
    fits = hard <= HARD_MAX_OUTPUT_TOKENS and expected < proposed
    return {
        "synthetic_transport_chars": chars,
        "synthetic_transport_bytes": len(compact.encode("utf-8")),
        "local_token_estimate": local.to_dict(),
        "expected_output_tokens": expected,
        "conservative_output_tokens": conservative,
        "hard_output_tokens": hard,
        "proposed_max_output": proposed,
        "conservative_max_output": CONSERVATIVE_MAX_OUTPUT_TOKENS,
        "hard_max_output": HARD_MAX_OUTPUT_TOKENS,
        "output_fits_proposed": expected < proposed,
        "output_fits_hard_cap": hard <= HARD_MAX_OUTPUT_TOKENS and expected < HARD_MAX_OUTPUT_TOKENS,
        "redesign_required": not fits,
        "note": (
            "Do not raise max_output blindly. Compact ID-only transport is "
            "the control surface if output does not fit."
        ),
    }
