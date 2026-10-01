"""Production output-budget re-evaluation. No linear 286/7 scaling."""

from __future__ import annotations

import json
import math
from typing import Any, Mapping

from app.ai.estimation import estimate_tokens
from app.editorial_planner_preflight_4a2.constants import (
    A1_OUTPUT_TOKENS,
    A1_TEXT_CHARS,
    A1_THINKING_TOKENS,
    MAX_OUTPUT_CANDIDATES,
    MODEL,
    MODEL_OUTPUT_CEILING,
    OLD_PROPOSED_MAX_OUTPUT,
    OUTPUT_UTILIZATION_TARGET,
    PHASE_4A_CONSERVATIVE_OUTPUT_TOKENS,
    PHASE_4A_EXPECTED_OUTPUT_TOKENS,
    PHASE_4A_HARD_OUTPUT_TOKENS,
    PLANNER_HARD_MAX_OUTPUT,
    THINKING_HEADROOM_TOKENS,
    UTILIZATION_TARGET_SOURCE,
)
from app.editorial_planner_preflight_4a2.scenarios import (
    conservative_transport,
    disposition_row_cost,
    expected_transport,
    hard_transport,
    strip_meta,
)
from app.editorial_planning.budget import (
    _PROVIDER_CHARS_PER_TOKEN_MID,
    _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC,
)
from app.editorial_planning.settings import frozen_production_settings
from app.source_analysis.models import SourceMap

_A1_CHARS_PER_TOKEN = A1_TEXT_CHARS / A1_OUTPUT_TOKENS
_A1_VISIBLE_IF_THINKING_INCLUDED = max(1, A1_OUTPUT_TOKENS - A1_THINKING_TOKENS)
_A1_CHARS_PER_VISIBLE = A1_TEXT_CHARS / _A1_VISIBLE_IF_THINKING_INCLUDED


def _provider_tokens(chars: int, chars_per_token: float) -> int:
    return int(math.ceil(max(0, chars) / chars_per_token))


def measure_transport(transport: Mapping[str, Any]) -> dict[str, Any]:
    payload = strip_meta(dict(transport))
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    chars = len(compact)
    local = estimate_tokens(compact, model=MODEL)
    a1_calibrated = _provider_tokens(chars, _A1_CHARS_PER_TOKEN)
    pessimistic = _provider_tokens(chars, _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC)
    mid = _provider_tokens(chars, _PROVIDER_CHARS_PER_TOKEN_MID)
    meta = dict(transport.get("_meta") or {})
    return {
        "name": transport.get("scenario") or meta.get("name"),
        "chars": chars,
        "utf8_bytes": len(compact.encode("utf-8")),
        "local_token_estimate": local.to_dict(),
        "provider_adjusted_mid": mid,
        "provider_adjusted_pessimistic": pessimistic,
        "a1_calibrated_tokens": a1_calibrated,
        "a1_chars_per_token": _A1_CHARS_PER_TOKEN,
        "structure": {
            "chapters": len(payload.get("chapters") or []),
            "sections": sum(
                len(chapter.get("sections") or [])
                for chapter in (payload.get("chapters") or [])
            ),
            "titles": len(payload.get("titles") or []),
            "deferred": len(payload.get("deferred") or []),
            "excluded": len(payload.get("excluded") or []),
            "assigned_idea_mentions": sum(
                len(section.get("i") or [])
                for chapter in (payload.get("chapters") or [])
                for section in (chapter.get("sections") or [])
            ),
        },
        "meta": meta,
        "output_tokens_for_budget": a1_calibrated,
        "pessimistic_sensitivity_tokens": pessimistic,
    }


def component_breakdown(measured: Mapping[str, Any]) -> dict[str, Any]:
    structure = dict(measured.get("structure") or {})
    chars = int(measured.get("chars") or 0)
    chapters = int(structure.get("chapters") or 0)
    sections = int(structure.get("sections") or 0)
    assigned = int(structure.get("assigned_idea_mentions") or 0)
    deferred = int(structure.get("deferred") or 0)
    excluded = int(structure.get("excluded") or 0)
    titles = int(structure.get("titles") or 0)
    disp = disposition_row_cost()
    idea_chars = assigned * int(disp["assigned_id_chars"])
    deferred_chars = deferred * int(disp["deferred_with_note_chars"])
    excluded_chars = excluded * int(disp["excluded_with_note_chars"])
    remainder = max(0, chars - idea_chars - deferred_chars - excluded_chars)
    return {
        "total_chars": chars,
        "idea_id_chars_approx": idea_chars,
        "deferred_row_chars_approx": deferred_chars,
        "excluded_row_chars_approx": excluded_chars,
        "fixed_and_prose_chars_approx": remainder,
        "per_chapter_prose_chars_approx": (remainder // chapters) if chapters else 0,
        "per_section_prose_chars_approx": (remainder // sections) if sections else 0,
        "titles": titles,
        "do_not_scale_a1_linearly": True,
        "invalid_linear_scale_tokens": int(
            round(A1_OUTPUT_TOKENS * (286 / 7))
        ),
        "why_linear_invalid": (
            "A.1 7-IDEA output includes fixed metadata, book concept, titles, "
            "and chapter/section prose. Multiplying 2058 by 286/7 double-counts "
            "fixed overhead and ignores disposition compactness."
        ),
        "disposition_unit_costs": disp,
    }


def scenario_assumptions() -> dict[str, Any]:
    settings = frozen_production_settings()
    return {
        "EXPECTED": {
            "chapters": 12,
            "sections": 36,
            "titles": 4,
            "assigned": "most ideas (272)",
            "deferred": 8,
            "excluded": 6,
            "reuse": "about 5% / one extra section",
            "wording": "A.1-like compact editorial fields",
            "note": "Budget modelling only. Not a real chapter count.",
        },
        "CONSERVATIVE": {
            "chapters": 16,
            "sections": 64,
            "titles": 6,
            "assigned": 250,
            "deferred": 20,
            "excluded": 16,
            "reuse": "about 10%",
            "wording": "1.6x A.1 field lengths, optional disposition notes",
            "note": "Still plausible. Not a real plan.",
        },
        "HARD": {
            "chapters": settings.max_chapters,
            "sections": settings.max_total_sections,
            "titles": settings.max_title_candidates,
            "assigned": "enough to fill every section (200)",
            "deferred": 50,
            "excluded": 36,
            "reuse": (
                f"warn-threshold ratio {settings.max_reused_idea_ratio_warn} "
                f"and {settings.max_idea_reuse_count_warn} placements"
            ),
            "wording": "A.1-like short fields (prompt requires courts; not 2x padded)",
            "bounds": {
                "max_chapters_fail": settings.max_chapters,
                "max_total_sections_fail": settings.max_total_sections,
                "max_sections_per_chapter_warn": settings.max_sections_per_chapter,
                "max_title_candidates": settings.max_title_candidates,
                "reuse_ratio_warn": settings.max_reused_idea_ratio_warn,
                "reuse_count_warn": settings.max_idea_reuse_count_warn,
            },
            "note": (
                "Safe structural maxima permitted by the frozen planner "
                "contract. String lengths are bounded; unbounded prose is "
                "forbidden by the prompt (no manuscript paragraphs)."
            ),
        },
    }


def select_max_output(*, hard_visible_tokens: int, thinking_headroom: int) -> dict[str, Any]:
    need = int(hard_visible_tokens) + int(thinking_headroom)
    target = OUTPUT_UTILIZATION_TARGET
    evaluated = []
    chosen = None
    for candidate in MAX_OUTPUT_CANDIDATES:
        if candidate > MODEL_OUTPUT_CEILING:
            continue
        utilization = need / candidate if candidate else 999.0
        fits = need <= candidate and utilization <= target
        evaluated.append(
            {
                "candidate": candidate,
                "hard_plus_thinking": need,
                "utilization": round(utilization, 4),
                "fits_target": fits,
                "at_or_below_model_ceiling": candidate <= MODEL_OUTPUT_CEILING,
                "planner_operational_hard_cap": PLANNER_HARD_MAX_OUTPUT,
            }
        )
        if fits and chosen is None:
            chosen = candidate
    decision = "NEEDS_MORE_EVIDENCE"
    transport_change = "NO"
    prompt_change = "NO"
    new_grammar = "NO"
    why_not_redesign = (
        "Assigned IDEA cost is ID-only (~9 chars). Hard-size is chapter/section "
        "purpose strings required by frozen transport 1.0, not duplicated source "
        "text. Preferred outcome: preserve prompt/schema/transport and change "
        "only runtime max_output."
    )
    if chosen is None:
        required = int(math.ceil(need / target)) if target else need
        bigger = [
            candidate
            for candidate in MAX_OUTPUT_CANDIDATES
            if candidate >= required and candidate <= MODEL_OUTPUT_CEILING
        ]
        if bigger:
            chosen = min(bigger)
            decision = "RAISE_MAX_OUTPUT"
        elif required <= MODEL_OUTPUT_CEILING:
            chosen = min(MODEL_OUTPUT_CEILING, int(math.ceil(required / 1024) * 1024))
            decision = "RAISE_MAX_OUTPUT"
        else:
            decision = "REDESIGN_TRANSPORT"
            transport_change = "YES"
            new_grammar = "YES"
    elif chosen == OLD_PROPOSED_MAX_OUTPUT:
        decision = "KEEP_16384"
    else:
        decision = "RAISE_MAX_OUTPUT"
    return {
        "hard_visible_tokens": hard_visible_tokens,
        "thinking_headroom_tokens": thinking_headroom,
        "hard_plus_thinking": need,
        "utilization_target": target,
        "utilization_target_source": UTILIZATION_TARGET_SOURCE,
        "candidates_evaluated": evaluated,
        "selected": chosen,
        "decision": decision,
        "transport_change_required": transport_change,
        "prompt_change_required": prompt_change,
        "new_grammar_canary_required": new_grammar,
        "do_not_blindly_select_32768": True,
        "model_output_ceiling": MODEL_OUTPUT_CEILING,
        "old_proposed_max_output": OLD_PROPOSED_MAX_OUTPUT,
        "authorization_token_method": (
            "A.1 observed chars/token on compact serialized transport; "
            "pessimistic Phase 3B density is sensitivity only"
        ),
        "why_not_redesign_if_raise": why_not_redesign,
        "hard_output_utilization": (
            round(need / chosen, 4) if chosen else None
        ),
    }


def measure_output_budget(source_map: SourceMap) -> dict[str, Any]:
    expected = measure_transport(expected_transport(source_map))
    conservative = measure_transport(conservative_transport(source_map))
    hard = measure_transport(hard_transport(source_map))
    expected_tokens = int(expected["output_tokens_for_budget"])
    conservative_tokens = int(conservative["output_tokens_for_budget"])
    hard_tokens = int(hard["output_tokens_for_budget"])
    selection = select_max_output(
        hard_visible_tokens=hard_tokens,
        thinking_headroom=THINKING_HEADROOM_TOKENS,
    )
    return {
        "phase_4a_preliminary": {
            "expected": PHASE_4A_EXPECTED_OUTPUT_TOKENS,
            "conservative": PHASE_4A_CONSERVATIVE_OUTPUT_TOKENS,
            "hard": PHASE_4A_HARD_OUTPUT_TOKENS,
            "proposed_max_output": OLD_PROPOSED_MAX_OUTPUT,
        },
        "a1_calibration": {
            "output_tokens": A1_OUTPUT_TOKENS,
            "thinking_tokens": A1_THINKING_TOKENS,
            "visible_text_chars": A1_TEXT_CHARS,
            "chars_per_reported_output_token": _A1_CHARS_PER_TOKEN,
            "chars_per_token_if_thinking_included_in_output": _A1_CHARS_PER_VISIBLE,
            "one_calibration_point_not_universal": True,
        },
        "methods": {
            "local": "app.ai.estimation.estimate_tokens on compact transport JSON",
            "provider_adjusted_pessimistic": (
                f"ceil(chars / {_PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC}) "
                "Phase 3B A.44 compact-output density"
            ),
            "a1_calibrated": f"ceil(chars / {_A1_CHARS_PER_TOKEN}) from A.1 text/output",
            "budget_token": (
                "A.1-calibrated tokens (visible structured JSON). "
                "Pessimistic Phase 3B density is reported as sensitivity, "
                "not the authorization figure."
            ),
        },
        "assumptions": scenario_assumptions(),
        "expected": expected,
        "conservative": conservative,
        "hard": hard,
        "expected_output_tokens": expected_tokens,
        "conservative_output_tokens": conservative_tokens,
        "hard_output_tokens": hard_tokens,
        "component_breakdown_hard": component_breakdown(hard),
        "disposition_costs": disposition_row_cost(),
        "selection": selection,
        "selected_max_output": selection.get("selected"),
        "output_budget_decision": selection.get("decision"),
        "transport_change_required": selection.get("transport_change_required"),
        "prompt_change_required": selection.get("prompt_change_required"),
        "new_grammar_canary_required": selection.get("new_grammar_canary_required"),
        "hard_output_utilization": selection.get("hard_output_utilization"),
        "thinking_headroom": THINKING_HEADROOM_TOKENS,
        "output_fits_selected": (
            selection.get("selected") is not None
            and hard_tokens + THINKING_HEADROOM_TOKENS <= int(selection["selected"] or 0)
        ),
    }


__all__ = ["measure_output_budget", "measure_transport", "select_max_output"]
