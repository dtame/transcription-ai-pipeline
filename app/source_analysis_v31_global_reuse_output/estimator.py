"""Estimateur déterministe transport 3.0 — REUSE vs SYNTHESIZE. 0 provider."""

from __future__ import annotations

import json
import math
from typing import Any, Mapping

from app.ai.estimation import estimate_tokens
from app.source_analysis_v31_global_output_architecture.constants import (
    MAX_EXAMPLE_IDEA_REFS,
    MAX_LOCAL_IDS_PER_SATELLITE,
    OUTPUT_BUDGET_TEXT_LIMITS,
    TEXT_LIMITS,
)
from app.source_analysis_v31_global_reuse_output.constants import (
    A42_CHARS_PER_TOKEN,
    A42_ESTIMATOR_ERROR_PERCENT,
    CHARS_PER_TOKEN_CONSERVATIVE,
    CHARS_PER_TOKEN_EXPECTED,
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
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    SAFETY_70,
    SAFETY_75,
    SAFETY_80,
    SYNTHESIZED_IDEA_MAX_CHARS,
    V20_CONSERVATIVE_OUTPUT,
    V20_EXPECTED_OUTPUT,
    V20_HARD_OUTPUT,
)


def _provider_tokens(chars: int, chars_per_token: float) -> int:
    return int(math.ceil(chars / chars_per_token))


def _json_chars(payload: Mapping[str, Any]) -> int:
    return len(json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")))


def _fill(length: int, glyph: str = "x") -> str:
    return glyph * int(length)


def _member(index: int, kind: str = "I") -> str:
    window = (index % 7) + 1
    return f"SYN{window:03d}:{kind}{index}"


def _gm(limits: Mapping[str, int]) -> dict[str, str]:
    return {
        "th": _fill(limits["theme"]),
        "in": _fill(limits["intent"]),
        "ic": "medium",
        "au": _fill(limits["audience"]),
        "ac": "medium",
        "vo": _fill(limits["voice"]),
    }


def _satellites(*, examples: int, references: int, uncertainties: int, ideas: int) -> dict[str, Any]:
    return {
        "x": [
            {
                "h": f"E{index}",
                "l": [_member(index, "E") for _ in range(min(1, MAX_LOCAL_IDS_PER_SATELLITE))],
                "g": [f"I{min(index, max(ideas, 1))}"][:MAX_EXAMPLE_IDEA_REFS],
            }
            for index in range(1, examples + 1)
        ],
        "f": [
            {"h": f"F{index}", "l": [_member(index, "F")]}
            for index in range(1, references + 1)
        ],
        "u": [
            {"h": f"U{index}", "l": [_member(index, "U")]}
            for index in range(1, uncertainties + 1)
        ],
    }


def reuse_transport(
    *,
    reused: int,
    synthesized: int,
    drops: int = 0,
    topics: int = EXPECTED_TOPIC,
    examples: int = EXPECTED_EXAMPLE,
    references: int = EXPECTED_REFERENCE,
    uncertainties: int = EXPECTED_UNCERTAINTY,
    synthesized_chars: int = SYNTHESIZED_IDEA_MAX_CHARS,
    members_per_synth: int = 2,
    topic_chars: int | None = None,
    limits: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    bounds = dict(OUTPUT_BUDGET_TEXT_LIMITS if limits is None else limits)
    topic_len = bounds["topic"] if topic_chars is None else int(topic_chars)
    ideas: list[dict[str, Any]] = []
    member_index = 1
    for index in range(1, reused + 1):
        ideas.append(
            {
                "h": f"I{index}",
                "m": [_member(member_index, "I")],
                "p": "supporting",
            }
        )
        member_index += 1
    for offset in range(synthesized):
        members = [
            _member(member_index + extra, "I") for extra in range(members_per_synth)
        ]
        member_index += members_per_synth
        ideas.append(
            {
                "h": f"I{reused + offset + 1}",
                "v": _fill(synthesized_chars),
                "m": members,
                "p": "supporting",
            }
        )
    payload = {
        "gm": _gm(bounds),
        "t": [
            {
                "h": f"T{index}",
                "v": _fill(topic_len),
                "m": [_member(index, "T")],
            }
            for index in range(1, topics + 1)
        ],
        "i": ideas,
        **_satellites(
            examples=examples,
            references=references,
            uncertainties=uncertainties,
            ideas=max(len(ideas), 1),
        ),
        "drop": [
            {"i": _member(900 + index, "I"), "w": "transport_artifact"}
            for index in range(1, drops + 1)
        ],
    }
    return payload


def per_object_costs() -> dict[str, Any]:
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
    reused = dict(empty)
    reused["i"] = [{"h": "I1", "m": ["SYN001:I1"], "p": "supporting"}]
    synth = dict(empty)
    synth["i"] = [
        {
            "h": "I1",
            "v": "x" * SYNTHESIZED_IDEA_MAX_CHARS,
            "m": ["SYN001:I1", "SYN002:I2"],
            "p": "supporting",
        }
    ]
    topic = dict(empty)
    topic["t"] = [{"h": "T1", "v": "x" * TEXT_LIMITS["topic"], "m": ["SYN001:T1"]}]
    drop = dict(empty)
    drop["drop"] = [{"i": "SYN001:I9", "w": "transport_artifact"}]
    example = dict(empty)
    example["x"] = [{"h": "E1", "l": ["SYN001:E1"], "g": ["I1"]}]
    ref = dict(empty)
    ref["f"] = [{"h": "F1", "l": ["SYN001:F1"]}]
    unc = dict(empty)
    unc["u"] = [{"h": "U1", "l": ["SYN001:U1"]}]
    gm = dict(empty)
    gm["gm"] = _gm(OUTPUT_BUDGET_TEXT_LIMITS)
    return {
        "fixed_overhead_empty_json_chars": base,
        "per_reused_idea": _json_chars(reused) - base,
        "per_synthesized_idea_max": _json_chars(synth) - base,
        "per_topic_max": _json_chars(topic) - base,
        "per_drop": _json_chars(drop) - base,
        "per_example": _json_chars(example) - base,
        "per_reference": _json_chars(ref) - base,
        "per_uncertainty": _json_chars(unc) - base,
        "gm_full": _json_chars(gm) - base,
        "chars_per_token_expected": CHARS_PER_TOKEN_EXPECTED,
        "chars_per_token_conservative": CHARS_PER_TOKEN_CONSERVATIVE,
    }


def _describe(payload: Mapping[str, Any]) -> dict[str, Any]:
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    local = estimate_tokens(compact, model=MODEL)
    chars = len(compact)
    return {
        "chars": chars,
        "bytes": len(compact.encode("utf-8")),
        "local_tokens": local.tokens,
        "local_method": local.method,
        "provider_tokens_a42_density": _provider_tokens(chars, A42_CHARS_PER_TOKEN),
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
    }


def reuse_savings_vs_v20() -> dict[str, Any]:
    """Économie si une fraction des 286 single-member omet v."""
    from app.source_analysis_v31_global_output_architecture.estimator import (
        worst_case_transport,
    )

    v20 = worst_case_transport(
        topics=EXPECTED_TOPIC,
        ideas=EXPECTED_IDEA,
        examples=EXPECTED_EXAMPLE,
        references=EXPECTED_REFERENCE,
        uncertainties=EXPECTED_UNCERTAINTY,
        drops=0,
        members_per_idea=1,
        members_per_topic=1,
    )
    v20_chars = _json_chars(v20)
    per_idea_text = 0
    if v20.get("i"):
        with_text = dict(v20)
        clone = json.loads(json.dumps(v20))
        clone["i"][0]["v"] = ""
        per_idea_text = _json_chars(v20) - _json_chars(clone)
    rows = {}
    for rate in (0.50, 0.75, 0.90, 0.95, 0.98):
        reused = int(round(EXPECTED_IDEA * rate))
        still_emitted = EXPECTED_IDEA - reused
        saved_chars = reused * per_idea_text
        remaining = v20_chars - saved_chars
        rows[str(rate)] = {
            "reused_single_member": reused,
            "still_emitting_text": still_emitted,
            "saved_chars": saved_chars,
            "remaining_chars": remaining,
            "remaining_tokens_conservative": _provider_tokens(
                remaining, CHARS_PER_TOKEN_CONSERVATIVE
            ),
            "saved_tokens_conservative": _provider_tokens(
                saved_chars, CHARS_PER_TOKEN_CONSERVATIVE
            ),
        }
    return {
        "v20_hard_chars": v20_chars,
        "v20_hard_tokens": V20_HARD_OUTPUT,
        "per_single_member_text_chars": per_idea_text,
        "rates": rows,
        "note": (
            "These rates assume all 286 remain single-member and only omit v. "
            "They are not a production mix forecast."
        ),
    }


def revised_reuse_budget() -> dict[str, Any]:
    costs = per_object_costs()
    expected_payload = reuse_transport(
        reused=EXPECTED_REUSED_IDEAS,
        synthesized=EXPECTED_SYNTHESIZED_IDEAS,
        drops=EXPECTED_DROPS,
        topics=max(1, int(EXPECTED_TOPIC * 0.7)),
        synthesized_chars=140,
        topic_chars=80,
        limits={
            **OUTPUT_BUDGET_TEXT_LIMITS,
            "theme": 240,
            "intent": 180,
            "audience": 120,
            "voice": 180,
        },
    )
    conservative_payload = reuse_transport(
        reused=280,
        synthesized=6,
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
    expected = _describe(expected_payload)
    conservative_raw = _describe(conservative_payload)
    distinct = _describe(all_distinct)
    pairs = _describe(pair_synthesis)
    expected_tokens = expected["provider_tokens_a42_density"]
    conservative_tokens = int(
        math.ceil(
            conservative_raw["provider_tokens_conservative"] * ESTIMATOR_ERROR_BUFFER
        )
    )
    hard_tokens = max(
        distinct["provider_tokens_conservative"],
        pairs["provider_tokens_conservative"],
    )
    abs_headroom = PRODUCTION_MAX_OUTPUT_TOKENS - hard_tokens
    utilization = hard_tokens / PRODUCTION_MAX_OUTPUT_TOKENS
    if hard_tokens <= SAFETY_70:
        risk = "SAFE_FOR_GRAMMAR_CANARY_BUDGET"
    elif hard_tokens <= SAFETY_75:
        risk = "WITHIN_75_PERCENT"
    elif hard_tokens <= SAFETY_80:
        risk = "TIGHT_BUT_MANAGEABLE"
    else:
        risk = "NEEDS_OUTPUT_REDESIGN"
    return {
        "v20_expected": V20_EXPECTED_OUTPUT,
        "v20_conservative": V20_CONSERVATIVE_OUTPUT,
        "v20_hard": V20_HARD_OUTPUT,
        "per_object": costs,
        "scenarios": {
            "expected_a38_a34_mix": expected,
            "conservative_six_merges": conservative_raw,
            "all_distinct_286_reuse": distinct,
            "pair_synthesis_worst_text": pairs,
        },
        "chars_per_token_expected": CHARS_PER_TOKEN_EXPECTED,
        "chars_per_token_conservative": CHARS_PER_TOKEN_CONSERVATIVE,
        "a42_estimator_error_percent": A42_ESTIMATOR_ERROR_PERCENT,
        "error_buffer": ESTIMATOR_ERROR_BUFFER,
        "p50_expected": expected_tokens,
        "conservative": conservative_tokens,
        "hard_planning": hard_tokens,
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "utilization_hard": round(utilization, 4),
        "absolute_headroom": abs_headroom,
        "margin_70": SAFETY_70 - hard_tokens,
        "margin_75": SAFETY_75 - hard_tokens,
        "margin_80": SAFETY_80 - hard_tokens,
        "output_risk": risk,
        "hard_case_used": (
            "pair_synthesis_worst_text"
            if pairs["provider_tokens_conservative"]
            >= distinct["provider_tokens_conservative"]
            else "all_distinct_286_reuse"
        ),
        "all_distinct_still_reuse": True,
        "distinct_does_not_require_rewrite": True,
        "do_not_increase_max_output": True,
    }


__all__ = [
    "per_object_costs",
    "reuse_savings_vs_v20",
    "reuse_transport",
    "revised_reuse_budget",
]
