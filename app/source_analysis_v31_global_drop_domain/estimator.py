"""Calibration estimateur sortie compact 2.0. 0 provider. Ne change pas max_output."""

from __future__ import annotations

import json
import math
from typing import Any, Mapping

from app.ai.estimation import estimate_tokens
from app.source_analysis_v31_global_drop_domain.constants import (
    A37_OUTPUT_TOKENS,
    A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN,
    A39_EXPECTED_OUTPUT,
    A39_HARD_PLANNING,
    A39_SAFETY_MARGIN,
    A40_CHARS_PER_PROVIDER_OUTPUT_TOKEN,
    A40_ESTIMATOR_ERROR_PERCENT,
    A40_OUTPUT_TOKENS,
    A40_PREDICTED_OUTPUT,
    A40_RAW_TEXT_CHARS,
    COMPACT_20_CHARS_PER_TOKEN_CONSERVATIVE,
    COMPACT_20_CHARS_PER_TOKEN_OBSERVED,
    EXPECTED_EXAMPLE,
    EXPECTED_GLOBAL_IDEA_RANGE,
    EXPECTED_IDEA,
    EXPECTED_REFERENCE,
    EXPECTED_TOPIC,
    EXPECTED_UNCERTAINTY,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    SAFETY_70,
    SAFETY_75,
    SAFETY_80,
    TEXT_LIMITS,
)
from app.source_analysis_v31_global_output_architecture.constants import (
    OUTPUT_BUDGET_TEXT_LIMITS,
)
from app.source_analysis_v31_global_drop_domain.gate import output_precall_gate
from app.source_analysis_v31_global_output_architecture.estimator import (
    estimate_output,
    worst_case_transport,
)
from app.source_analysis_v31_global_v20_grammar_canary.fixture import (
    expected_valid_transport_v20,
)
from app.source_analysis_v31_global_v20_grammar_canary.payload import estimate_canary_output


def _provider_tokens(chars: int, chars_per_token: float) -> int:
    return int(math.ceil(chars / chars_per_token))


def _json_chars(payload: Mapping[str, Any]) -> int:
    return len(json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")))


def component_char_model() -> dict[str, Any]:
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
    base = _json_chars(empty)
    one_topic = dict(empty)
    one_topic["t"] = [{"h": "T1", "v": "x" * TEXT_LIMITS["topic"], "m": ["SYN001:T1"]}]
    one_idea = dict(empty)
    one_idea["i"] = [
        {
            "h": "I1",
            "v": "x" * TEXT_LIMITS["idea"],
            "m": ["SYN001:I1"],
            "p": "supporting",
        }
    ]
    two_members = dict(empty)
    two_members["i"] = [
        {
            "h": "I1",
            "v": "x" * TEXT_LIMITS["idea"],
            "m": ["SYN001:I1", "SYN002:I2"],
            "p": "supporting",
        }
    ]
    one_drop = dict(empty)
    one_drop["drop"] = [{"i": "SYN001:I9", "w": "transport_artifact"}]
    one_example = dict(empty)
    one_example["x"] = [{"h": "E1", "l": ["SYN001:E1"], "g": ["I1"]}]
    one_ref = dict(empty)
    one_ref["f"] = [{"h": "F1", "l": ["SYN001:F1"]}]
    one_unc = dict(empty)
    one_unc["u"] = [{"h": "U1", "l": ["SYN001:U1"]}]
    gm_full = dict(empty)
    gm_full["gm"] = {
        "th": "x" * TEXT_LIMITS["theme"],
        "in": "x" * OUTPUT_BUDGET_TEXT_LIMITS["intent"],
        "ic": "medium",
        "au": "x" * TEXT_LIMITS["audience"],
        "ac": "medium",
        "vo": "x" * TEXT_LIMITS["voice"],
    }
    return {
        "fixed_overhead_empty_json_chars": base,
        "gm_full_minus_empty": _json_chars(gm_full) - base,
        "per_topic_max_text": _json_chars(one_topic) - base,
        "per_global_idea_max_text_one_member": _json_chars(one_idea) - base,
        "per_extra_member": _json_chars(two_members) - _json_chars(one_idea),
        "per_drop": _json_chars(one_drop) - base,
        "per_example": _json_chars(one_example) - base,
        "per_reference": _json_chars(one_ref) - base,
        "per_uncertainty": _json_chars(one_unc) - base,
        "text_limits_match_schema_prompt": dict(OUTPUT_BUDGET_TEXT_LIMITS),
    }


def serialize_scenarios() -> dict[str, Any]:
    all_distinct = worst_case_transport(
        topics=EXPECTED_TOPIC,
        ideas=EXPECTED_IDEA,
        examples=EXPECTED_EXAMPLE,
        references=EXPECTED_REFERENCE,
        uncertainties=EXPECTED_UNCERTAINTY,
        drops=0,
        members_per_idea=1,
        members_per_topic=1,
    )
    merge = worst_case_transport(
        topics=max(1, int(EXPECTED_TOPIC * 0.7)),
        ideas=283,
        examples=EXPECTED_EXAMPLE,
        references=EXPECTED_REFERENCE,
        uncertainties=EXPECTED_UNCERTAINTY,
        drops=0,
        members_per_idea=2,
        members_per_topic=1,
        limits={
            **OUTPUT_BUDGET_TEXT_LIMITS,
            "idea": 140,
            "topic": 80,
            "theme": 240,
        },
    )
    drop = worst_case_transport(
        topics=EXPECTED_TOPIC,
        ideas=EXPECTED_IDEA - 6,
        examples=EXPECTED_EXAMPLE,
        references=EXPECTED_REFERENCE,
        uncertainties=EXPECTED_UNCERTAINTY,
        drops=6,
        members_per_idea=1,
        members_per_topic=1,
    )
    rows = {}
    for name, payload in (
        ("all_distinct_286", all_distinct),
        ("plausible_merge", merge),
        ("bounded_drop", drop),
    ):
        compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        local = estimate_tokens(compact, model=MODEL)
        rows[name] = {
            "chars": len(compact),
            "bytes": len(compact.encode("utf-8")),
            "local_tokens": local.tokens,
            "local_method": local.method,
            "provider_tokens_a40_density": _provider_tokens(
                len(compact), COMPACT_20_CHARS_PER_TOKEN_OBSERVED
            ),
            "provider_tokens_conservative": _provider_tokens(
                len(compact), COMPACT_20_CHARS_PER_TOKEN_CONSERVATIVE
            ),
            "provider_tokens_a38_density": _provider_tokens(
                len(compact), A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN
            ),
            "ideas": len(payload.get("i") or []),
            "members_first_idea": len(((payload.get("i") or [{}])[0]).get("m") or []),
            "drops": len(payload.get("drop") or []),
        }
    return rows


def a40_estimator_audit() -> dict[str, Any]:
    canary = estimate_canary_output()
    expected_json = json.dumps(
        expected_valid_transport_v20(), ensure_ascii=False, separators=(",", ":")
    )
    actual_cpt = A40_CHARS_PER_PROVIDER_OUTPUT_TOKEN
    predicted_from_actual_chars = _provider_tokens(A40_RAW_TEXT_CHARS, A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN)
    return {
        "methodology": (
            "A.40 predicted 514 = ceil(len(expected FakeAI JSON compact)/A.38 chars/token). "
            "A.38 chars/token = 75150/32000 ≈ 2.3484 from truncated transport 1.1 JSON. "
            "Local estimate_tokens uses 4 chars/token heuristic unless tiktoken is present."
        ),
        "predicted": A40_PREDICTED_OUTPUT,
        "actual": A40_OUTPUT_TOKENS,
        "error_percent": A40_ESTIMATOR_ERROR_PERCENT,
        "expected_fakeai_chars": len(expected_json),
        "actual_provider_chars": A40_RAW_TEXT_CHARS,
        "a38_chars_per_token": A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN,
        "a40_chars_per_token": actual_cpt,
        "do_not_use_generic_4_chars_per_token_for_provider_json": True,
        "tiny_canary_fixed_overhead_distortion": True,
        "do_not_scale_28735_by_1_286": True,
        "contributions": {
            "chars_per_token_assumption": {
                "used": A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN,
                "observed_a40": actual_cpt,
                "effect": (
                    "A.40 JSON denser than A.38 (2.05 vs 2.35). Using 2.35 undercounts tokens."
                ),
            },
            "json_syntax": "Compact keys still emit quotes/brackets; punctuation-heavy JSON.",
            "provider_wording_length": (
                f"Actual text {A40_RAW_TEXT_CHARS} chars vs FakeAI expected "
                f"{len(expected_json)} chars."
            ),
            "metadata": "gm strings in actual response were longer than the FakeAI fixture.",
            "handles": "T1/I1 style; small.",
            "membership_arrays": "Small in tiny canary; dominate at 286 members.",
            "fixed_transport_overhead": "Empty 2.0 object is a large fraction of a 5-idea canary.",
            "tokenizer_approximation": (
                "Local heuristic 4 chars/token (302 local vs 514 provider predicted vs 661 actual)."
            ),
        },
        "a37_tiny_canary_output_tokens": A37_OUTPUT_TOKENS,
        "a37_note": "Transport 1.1 tiny canary; not compact 2.0 density.",
        "a38_production_attempt_output_tokens": 32000,
        "canary_estimate_function": canary,
        "if_predicted_with_a38_on_actual_chars": predicted_from_actual_chars,
    }


def revised_production_budget() -> dict[str, Any]:
    components = component_char_model()
    scenarios = serialize_scenarios()
    distinct = scenarios["all_distinct_286"]
    merge = scenarios["plausible_merge"]
    drop = scenarios["bounded_drop"]
    # P50/expected: plausible merge-ish compact text (140-char ideas) at observed 2.05 cpt,
    # but use conservative 2.00 for planning numbers reported as expected? Spec wants
    # P50/expected, conservative, hard/planning separately.
    expected = merge["provider_tokens_a40_density"]
    conservative = max(
        merge["provider_tokens_conservative"],
        distinct["provider_tokens_a40_density"],
    )
    hard = distinct["provider_tokens_conservative"]
    a39_expected = estimate_output()
    a39_planning = a39_expected.get("provider_planning_tokens") or {}
    gate = output_precall_gate(
        expected_tokens=expected,
        conservative_tokens=conservative,
        hard_tokens=hard,
        chars_per_token=COMPACT_20_CHARS_PER_TOKEN_CONSERVATIVE,
        safety_factor=1.0,
    )
    # Tiny canary error must not blindly scale 28735.
    naive_scale = int(round(A39_EXPECTED_OUTPUT * (A40_OUTPUT_TOKENS / A40_PREDICTED_OUTPUT)))
    risk = "TIGHT_BUT_MANAGEABLE"
    if hard > SAFETY_80:
        risk = "NEEDS_OUTPUT_REDESIGN"
    elif hard <= SAFETY_70:
        risk = "SAFE_FOR_REAL_PREFLIGHT"
    # A.41 analysis only — still do not authorize real call.
    if hard > SAFETY_75:
        risk = "TIGHT_BUT_MANAGEABLE" if hard <= SAFETY_80 else "NEEDS_OUTPUT_REDESIGN"
    return {
        "a39_expected": A39_EXPECTED_OUTPUT,
        "a39_hard": A39_HARD_PLANNING,
        "a39_75_margin": A39_SAFETY_MARGIN,
        "a39_estimator_chars_per_token": A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN,
        "naive_scale_28735_x_1_286": naive_scale,
        "naive_scale_rejected": True,
        "components": components,
        "scenarios": scenarios,
        "chars_per_token_compact_2_0_observed": COMPACT_20_CHARS_PER_TOKEN_OBSERVED,
        "chars_per_token_compact_2_0_conservative": COMPACT_20_CHARS_PER_TOKEN_CONSERVATIVE,
        "chars_per_token_a38_preserved": A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN,
        "expected_global_idea_range": list(EXPECTED_GLOBAL_IDEA_RANGE),
        "p50_expected": expected,
        "conservative": conservative,
        "hard_planning": hard,
        "max_output_unchanged": PRODUCTION_MAX_OUTPUT_TOKENS,
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "margin_70": SAFETY_70 - hard,
        "margin_75": SAFETY_75 - hard,
        "margin_80": SAFETY_80 - hard,
        "a39_live_estimate": {
            "expected": a39_planning.get("expected"),
            "hard": a39_planning.get("hard"),
        },
        "text_limits": dict(TEXT_LIMITS),
        "output_risk": risk,
        "gate": gate,
        "do_not_change_max_output": True,
        "ready_for_real_preflight": "NO",
    }


__all__ = [
    "a40_estimator_audit",
    "component_char_model",
    "revised_production_budget",
    "serialize_scenarios",
]
