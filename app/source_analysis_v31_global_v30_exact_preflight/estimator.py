"""Estimateur 3.0 calibré A.44. 0 provider. Pas l'estimateur 2.0."""

from __future__ import annotations

import json
import math
from typing import Any, Mapping

from app.source_analysis.consolidation_models import CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS
from app.source_analysis_v31_global_reuse_output.estimator import (
    per_object_costs,
    reuse_transport,
)
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    A38_INPUT_RATIO,
    A38_PRODUCTION_INPUT_TOKENS,
    A40_CHARS_PER_TOKEN,
    A42_CHARS_PER_TOKEN,
    A43_CONSERVATIVE_OUTPUT,
    A43_ESTIMATED_PRODUCTION_INPUT,
    A43_EXPECTED_OUTPUT,
    A43_HARD_OUTPUT,
    A44_CHARS_PER_TOKEN,
    A44_ESTIMATOR_ERROR_PERCENT,
    A44_INPUT_RATIO,
    CHARS_PER_TOKEN_CONSERVATIVE,
    CHARS_PER_TOKEN_EXPECTED,
    CONTEXT_WINDOW_TOKENS,
    DROP_STRESS_COUNT,
    ESTIMATOR_ERROR_BUFFER,
    EXPECTED_DROPS,
    EXPECTED_EXAMPLE,
    EXPECTED_GLOBAL_IDEAS,
    EXPECTED_IDEA,
    EXPECTED_REFERENCE,
    EXPECTED_REUSED_IDEAS,
    EXPECTED_SYNTHESIZED_IDEAS,
    EXPECTED_TOPIC,
    EXPECTED_UNCERTAINTY,
    MERGE_STRESS_SYNTHESIZED,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    SAFETY_70,
    SAFETY_75,
    SAFETY_80,
    SYNTHESIZED_IDEA_MAX_CHARS,
    TEXT_LIMITS,
)


def _provider_tokens(chars: int, chars_per_token: float) -> int:
    return int(math.ceil(chars / chars_per_token))


def _json_chars(payload: Mapping[str, Any]) -> int:
    return len(json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")))


def _describe(payload: Mapping[str, Any]) -> dict[str, Any]:
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    chars = len(compact)
    return {
        "chars": chars,
        "bytes": len(compact.encode("utf-8")),
        "provider_tokens_a44_density": _provider_tokens(chars, A44_CHARS_PER_TOKEN),
        "provider_tokens_a42_density": _provider_tokens(chars, float(A42_CHARS_PER_TOKEN)),
        "provider_tokens_conservative": _provider_tokens(
            chars, CHARS_PER_TOKEN_CONSERVATIVE
        ),
        "ideas": len(payload.get("i") or []),
        "reused": sum(
            1
            for idea in payload.get("i") or []
            if len(idea.get("m") or []) == 1 and not idea.get("v")
        ),
        "synthesized": sum(
            1 for idea in payload.get("i") or [] if len(idea.get("m") or []) >= 2
        ),
        "drops": len(payload.get("drop") or []),
        "topics": len(payload.get("t") or []),
        "single_member_v_absent": all(
            not idea.get("v")
            for idea in payload.get("i") or []
            if len(idea.get("m") or []) == 1
        ),
    }


def component_breakdown(payload: Mapping[str, Any]) -> dict[str, Any]:
    full = dict(payload)
    full_chars = _json_chars(full)
    empty = {
        "gm": {
            "th": "",
            "in": "",
            "ic": "medium",
            "au": "",
            "ac": "medium",
            "vo": "",
        },
        "t": [],
        "i": [],
        "x": [],
        "f": [],
        "u": [],
        "drop": [],
    }
    skeleton_chars = _json_chars(empty)
    no_gm = dict(full)
    no_gm["gm"] = empty["gm"]
    no_topics = dict(full)
    no_topics["t"] = []
    no_ideas = dict(full)
    no_ideas["i"] = []
    no_x = dict(full)
    no_x["x"] = []
    no_f = dict(full)
    no_f["f"] = []
    no_u = dict(full)
    no_u["u"] = []
    no_drop = dict(full)
    no_drop["drop"] = []
    handles_only = json.loads(json.dumps(full))
    for idea in handles_only.get("i") or []:
        idea.pop("v", None)
        idea["m"] = list(idea.get("m") or [])
    no_members = json.loads(json.dumps(handles_only))
    for idea in no_members.get("i") or []:
        idea["m"] = []
    merge_chars = 0
    for idea in full.get("i") or []:
        if len(idea.get("m") or []) >= 2:
            merge_chars += len(str(idea.get("v") or ""))
    parts = {
        "fixed_root_metadata": skeleton_chars,
        "topics": full_chars - _json_chars(no_topics),
        "global_idea_handles_and_importance": _json_chars(no_members)
        - _json_chars(no_ideas),
        "members": _json_chars(handles_only) - _json_chars(no_members),
        "merge_v_text": merge_chars,
        "drops": full_chars - _json_chars(no_drop),
        "examples": full_chars - _json_chars(no_x),
        "references": full_chars - _json_chars(no_f),
        "uncertainties": full_chars - _json_chars(no_u),
        "gm_metadata": full_chars - _json_chars(no_gm),
    }
    accounted = sum(parts.values())
    parts["json_syntax_and_other"] = max(full_chars - accounted, 0)
    tokenized = {
        key: _provider_tokens(value, CHARS_PER_TOKEN_CONSERVATIVE)
        for key, value in parts.items()
    }
    largest = max(tokenized.items(), key=lambda item: item[1])
    return {
        "chars": parts,
        "tokens_conservative": tokenized,
        "largest_component": largest[0],
        "largest_tokens": largest[1],
        "total_chars": full_chars,
        "relations_output": "EXCLUDED",
        "repetitions_output": "DEFERRED",
        "single_member_v": "ABSENT",
    }


def calibrated_output_budget() -> dict[str, Any]:
    costs = per_object_costs()
    expected_payload = reuse_transport(
        reused=EXPECTED_REUSED_IDEAS,
        synthesized=EXPECTED_SYNTHESIZED_IDEAS,
        drops=EXPECTED_DROPS,
        topics=max(1, int(EXPECTED_TOPIC * 0.7)),
        synthesized_chars=140,
        topic_chars=80,
        limits={
            **TEXT_LIMITS,
            "theme": 240,
            "intent": 180,
            "audience": 120,
            "voice": 180,
        },
    )
    conservative_payload = reuse_transport(
        reused=EXPECTED_IDEA - MERGE_STRESS_SYNTHESIZED * 2,
        synthesized=MERGE_STRESS_SYNTHESIZED,
        drops=0,
        topics=EXPECTED_TOPIC,
        synthesized_chars=SYNTHESIZED_IDEA_MAX_CHARS,
    )
    all_distinct = reuse_transport(
        reused=EXPECTED_IDEA,
        synthesized=0,
        drops=0,
        topics=EXPECTED_TOPIC,
        synthesized_chars=SYNTHESIZED_IDEA_MAX_CHARS,
    )
    pair_synthesis = reuse_transport(
        reused=EXPECTED_IDEA % 2,
        synthesized=EXPECTED_IDEA // 2,
        drops=0,
        topics=EXPECTED_TOPIC,
        synthesized_chars=SYNTHESIZED_IDEA_MAX_CHARS,
        members_per_synth=2,
    )
    drop_payload = reuse_transport(
        reused=EXPECTED_IDEA - DROP_STRESS_COUNT,
        synthesized=0,
        drops=DROP_STRESS_COUNT,
        topics=EXPECTED_TOPIC,
        synthesized_chars=SYNTHESIZED_IDEA_MAX_CHARS,
    )
    expected = _describe(expected_payload)
    conservative_raw = _describe(conservative_payload)
    distinct = _describe(all_distinct)
    pairs = _describe(pair_synthesis)
    drops = _describe(drop_payload)
    expected_tokens = expected["provider_tokens_a44_density"]
    conservative_tokens = int(
        math.ceil(
            conservative_raw["provider_tokens_conservative"] * ESTIMATOR_ERROR_BUFFER
        )
    )
    unbuffered_hard = max(
        distinct["provider_tokens_conservative"],
        pairs["provider_tokens_conservative"],
        drops["provider_tokens_conservative"],
    )
    hard_tokens = int(math.ceil(unbuffered_hard * ESTIMATOR_ERROR_BUFFER))
    abs_headroom = PRODUCTION_MAX_OUTPUT_TOKENS - hard_tokens
    utilization = hard_tokens / PRODUCTION_MAX_OUTPUT_TOKENS
    if hard_tokens <= SAFETY_70:
        risk = "SAFE_FOR_ONE_REAL_CALL_BUDGET"
        output_safety = "HARD_LE_70_PERCENT"
    elif hard_tokens <= SAFETY_75:
        risk = "SAFE_BUT_REVIEW_REQUIRED"
        output_safety = "HARD_BETWEEN_70_AND_75"
    elif hard_tokens <= SAFETY_80:
        risk = "NEEDS_ARCHITECTURE_OR_BUDGET_REVIEW"
        output_safety = "HARD_BETWEEN_75_AND_80"
    else:
        risk = "NEEDS_MORE_OUTPUT_WORK"
        output_safety = "HARD_ABOVE_80"
    hard_case = "pair_synthesis_worst_text"
    if distinct["provider_tokens_conservative"] >= pairs["provider_tokens_conservative"]:
        hard_case = "all_distinct_286_reuse"
    if drops["provider_tokens_conservative"] >= max(
        distinct["provider_tokens_conservative"],
        pairs["provider_tokens_conservative"],
    ):
        hard_case = "drop_stress"
    breakdown = component_breakdown(
        pair_synthesis
        if hard_case == "pair_synthesis_worst_text"
        else all_distinct
        if hard_case == "all_distinct_286_reuse"
        else drop_payload
    )
    return {
        "calibration": {
            "a38_chars_per_token": A38_PRODUCTION_INPUT_TOKENS and 75150 / 32000,
            "a40_chars_per_token": A40_CHARS_PER_TOKEN,
            "a42_chars_per_token": float(A42_CHARS_PER_TOKEN),
            "a44_chars_per_token": A44_CHARS_PER_TOKEN,
            "generic_4_chars_per_token_used": False,
            "estimator_used": "global-consolidation-transport-3.0 reuse estimator",
            "old_2_0_estimator_used": False,
            "a44_estimator_error_percent": A44_ESTIMATOR_ERROR_PERCENT,
            "error_buffer": ESTIMATOR_ERROR_BUFFER,
            "chars_per_token_expected": CHARS_PER_TOKEN_EXPECTED,
            "chars_per_token_conservative": CHARS_PER_TOKEN_CONSERVATIVE,
        },
        "a43_reference": {
            "expected": A43_EXPECTED_OUTPUT,
            "conservative": A43_CONSERVATIVE_OUTPUT,
            "hard": A43_HARD_OUTPUT,
        },
        "per_object": costs,
        "scenarios": {
            "expected_mix": expected,
            "conservative_merge_stress": conservative_raw,
            "all_distinct_286_reuse": distinct,
            "pair_synthesis_worst_text": pairs,
            "drop_stress": drops,
        },
        "p50_expected": expected_tokens,
        "conservative": conservative_tokens,
        "hard_planning": hard_tokens,
        "unbuffered_hard": unbuffered_hard,
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "utilization_hard": round(utilization, 4),
        "hard_utilization_percent": round(100.0 * utilization, 2),
        "absolute_headroom": abs_headroom,
        "margin_70": SAFETY_70 - hard_tokens,
        "margin_75": SAFETY_75 - hard_tokens,
        "margin_80": SAFETY_80 - hard_tokens,
        "output_risk": risk,
        "output_safety": output_safety,
        "hard_case_used": hard_case,
        "all_distinct_still_reuse": True,
        "distinct_does_not_require_rewrite": True,
        "do_not_increase_max_output": True,
        "single_member_v_absent_in_all_scenarios": all(
            scenario["single_member_v_absent"]
            for scenario in (
                expected,
                conservative_raw,
                distinct,
                pairs,
                drops,
            )
        ),
        "differences_vs_a43": {
            "expected_delta": expected_tokens - A43_EXPECTED_OUTPUT,
            "conservative_delta": conservative_tokens - A43_CONSERVATIVE_OUTPUT,
            "hard_delta": hard_tokens - A43_HARD_OUTPUT,
            "reason": (
                "A.45 replaces A.42 density 2.064 with A.44 observed "
                f"{A44_CHARS_PER_TOKEN:.6f} chars/token and raises the "
                f"estimator error buffer from 1.10 to {ESTIMATOR_ERROR_BUFFER} "
                f"(A.44 error {A44_ESTIMATOR_ERROR_PERCENT}%). Conservative "
                f"merge stress uses {MERGE_STRESS_SYNTHESIZED} max-length "
                "synthesized v fields. Hard planning now includes the error "
                "buffer instead of unbuffered pair-synthesis only."
            ),
        },
        "breakdown": breakdown,
        "largest_output_component": breakdown["largest_component"],
    }


def classify_output_gate(hard_tokens: int) -> str:
    if hard_tokens <= SAFETY_70:
        return "READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY"
    if hard_tokens <= SAFETY_75:
        return "SAFE_BUT_REVIEW_REQUIRED"
    return "NEEDS_MORE_OUTPUT_WORK"


def input_budget(
    *,
    local_prompt_tokens: int,
    payload_tokens: int,
    request_chars: int,
    request_bytes: int,
    compact_chars: int,
) -> dict[str, Any]:
    a38_adjusted = int(round(local_prompt_tokens * A38_INPUT_RATIO))
    a44_adjusted = int(round(local_prompt_tokens * A44_INPUT_RATIO))
    primary = a38_adjusted
    usable = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS
    remaining = usable - primary
    comfortable = primary <= int(usable * 0.90)
    inside = primary < usable
    return {
        "request_chars": request_chars,
        "request_bytes": request_bytes,
        "compact_chars": compact_chars,
        "local_tokenizer_prompt_tokens": local_prompt_tokens,
        "local_tokenizer_full_payload_tokens": payload_tokens,
        "provider_adjusted_a38_ratio": a38_adjusted,
        "provider_adjusted_a44_ratio": a44_adjusted,
        "primary_estimated_input": primary,
        "primary_calibration": (
            "A.38 production-scale provider/local ratio 1.84386 applied to the "
            "exact 3.0 system+user local tokenizer estimate. A.44 tiny-canary "
            "ratio 2.336 is reported but not used as the production primary "
            "because schema overhead dominates short canary prompts."
        ),
        "a38_actual_input": A38_PRODUCTION_INPUT_TOKENS,
        "a43_estimated_input": A43_ESTIMATED_PRODUCTION_INPUT,
        "delta_vs_a38": primary - A38_PRODUCTION_INPUT_TOKENS,
        "delta_vs_a43": primary - A43_ESTIMATED_PRODUCTION_INPUT,
        "difference_explanation": (
            "A.38 used prompt 1.0.1 + transport 1.1 + max_output 32000 and "
            f"observed {A38_PRODUCTION_INPUT_TOKENS} input tokens on the same "
            "seven-window compact (hash 0277ec07…). A.43 estimated "
            f"{A43_ESTIMATED_PRODUCTION_INPUT} by adding the 3.0 vs 2.0.1 prompt "
            "character delta (~267 tokens) onto that A.38 observation. That mixed "
            "1.0.1-era actuals with a 2.0.1 baseline. A.45 measures the exact 3.0 "
            "system+user text and applies the A.38 production ratio. Prompt 3.0 is "
            "shorter than 1.0.1 (no disposition ledger, relations deferred) while "
            "the adapted schema grew 1337 → 1831 bytes; schema overhead remains "
            "inside the A.38 ratio rather than being double-counted. Remaining "
            "delta versus 68405 is that correction, not a live provider count."
        ),
        "usable_input_budget_phase_2b": usable,
        "context_window_tokens": CONTEXT_WINDOW_TOKENS,
        "headroom_vs_80k": remaining,
        "inside_usable_budget": inside,
        "comfortably_inside": comfortable,
        "input_safety": "SAFE" if comfortable else ("INSIDE" if inside else "BLOCKED"),
        "generic_4_chars_per_token_used": False,
    }


def recompute_precall_bounds(budget: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "hard_planning": int(budget.get("hard_planning") or 0),
        "expected": int(budget.get("p50_expected") or 0),
        "conservative": int(budget.get("conservative") or 0),
        "schema_hash_required": True,
        "request_hash_required": True,
        "material_delta_ratio": 0.02,
    }


__all__ = [
    "calibrated_output_budget",
    "classify_output_gate",
    "component_breakdown",
    "input_budget",
    "recompute_precall_bounds",
]
