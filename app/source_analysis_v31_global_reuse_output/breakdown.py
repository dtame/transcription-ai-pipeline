"""Décomposition du hard estimate transport 2.0 (41430). 0 provider."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.source_analysis_v31_global_drop_domain.constants import (
    COMPACT_20_CHARS_PER_TOKEN_CONSERVATIVE,
)
from app.source_analysis_v31_global_output_architecture.estimator import worst_case_transport
from app.source_analysis_v31_global_reuse_output.constants import (
    EXPECTED_EXAMPLE,
    EXPECTED_IDEA,
    EXPECTED_REFERENCE,
    EXPECTED_TOPIC,
    EXPECTED_UNCERTAINTY,
    TEXT_LIMITS,
    V20_HARD_OUTPUT,
    PRODUCTION_MAX_OUTPUT_TOKENS,
)


def _json_chars(payload: Mapping[str, Any]) -> int:
    return len(json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")))


def _tokens(chars: int, chars_per_token: float = COMPACT_20_CHARS_PER_TOKEN_CONSERVATIVE) -> int:
    import math

    return int(math.ceil(chars / chars_per_token))


def v20_hard_component_breakdown() -> dict[str, Any]:
    """Décompose le payload worst-case 2.0 qui produit hard=41430."""
    full = worst_case_transport(
        topics=EXPECTED_TOPIC,
        ideas=EXPECTED_IDEA,
        examples=EXPECTED_EXAMPLE,
        references=EXPECTED_REFERENCE,
        uncertainties=EXPECTED_UNCERTAINTY,
        drops=0,
        members_per_idea=1,
        members_per_topic=1,
    )
    full_chars = _json_chars(full)
    empty_v = json.loads(json.dumps(full))
    for idea in empty_v.get("i") or []:
        idea["v"] = ""
    no_idea_text = json.loads(json.dumps(full))
    for idea in no_idea_text.get("i") or []:
        idea["v"] = ""
    no_ideas = json.loads(json.dumps(full))
    no_ideas["i"] = []
    no_topics = json.loads(json.dumps(full))
    no_topics["t"] = []
    no_gm = json.loads(json.dumps(full))
    no_gm["gm"] = {
        "th": "",
        "in": "",
        "ic": "medium",
        "au": "",
        "ac": "medium",
        "vo": "",
    }
    no_x = json.loads(json.dumps(full))
    no_x["x"] = []
    no_f = json.loads(json.dumps(full))
    no_f["f"] = []
    no_u = json.loads(json.dumps(full))
    no_u["u"] = []
    handles_only = json.loads(json.dumps(full))
    for idea in handles_only.get("i") or []:
        idea["v"] = ""
        idea["m"] = []
    skeleton = {
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
    idea_text_chars = full_chars - _json_chars(empty_v)
    membership_chars = _json_chars(empty_v) - _json_chars(handles_only)
    idea_records_chars = full_chars - _json_chars(no_ideas)
    topic_chars = full_chars - _json_chars(no_topics)
    gm_chars = full_chars - _json_chars(no_gm)
    example_chars = full_chars - _json_chars(no_x)
    ref_chars = full_chars - _json_chars(no_f)
    unc_chars = full_chars - _json_chars(no_u)
    overhead_chars = _json_chars(skeleton)
    accounted = (
        idea_text_chars
        + (idea_records_chars - idea_text_chars)
        + topic_chars
        + gm_chars
        + example_chars
        + ref_chars
        + unc_chars
        + overhead_chars
    )
    residual = full_chars - accounted
    hard_tokens = _tokens(full_chars)
    idea_text_tokens = _tokens(idea_text_chars)
    return {
        "source": "transport 2.0 worst-case all-distinct 286 with max field lengths",
        "chars_per_token": COMPACT_20_CHARS_PER_TOKEN_CONSERVATIVE,
        "serialized_chars": full_chars,
        "hard_tokens_from_chars": hard_tokens,
        "frozen_hard_tokens": V20_HARD_OUTPUT,
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "components_chars": {
            "fixed_metadata_gm": gm_chars,
            "topics": topic_chars,
            "global_idea_records_including_text": idea_records_chars,
            "global_idea_text": idea_text_chars,
            "global_idea_handles_and_flags": idea_records_chars
            - idea_text_chars
            - membership_chars,
            "membership_arrays": membership_chars,
            "drops": 0,
            "examples": example_chars,
            "references": ref_chars,
            "uncertainties": unc_chars,
            "json_syntax_overhead": overhead_chars,
            "residual_other": residual,
        },
        "components_tokens": {
            "fixed_metadata_gm": _tokens(gm_chars),
            "topics": _tokens(topic_chars),
            "global_idea_handles": _tokens(
                idea_records_chars - idea_text_chars - membership_chars
            ),
            "global_idea_text": idea_text_tokens,
            "membership_arrays": _tokens(membership_chars),
            "drops": 0,
            "examples": _tokens(example_chars),
            "references": _tokens(ref_chars),
            "uncertainties": _tokens(unc_chars),
            "json_syntax_overhead": _tokens(overhead_chars),
            "other": _tokens(max(residual, 0)),
        },
        "idea_text_share_of_hard": round(idea_text_tokens / max(hard_tokens, 1), 4),
        "idea_text_share_of_41430": round(idea_text_tokens / max(V20_HARD_OUTPUT, 1), 4),
        "topics_share_of_hard": round(_tokens(topic_chars) / max(hard_tokens, 1), 4),
        "primary_bottleneck": "provider-generated global IDEA text",
        "do_not_over_optimize_topics": _tokens(topic_chars) < idea_text_tokens * 0.25,
        "text_limits": dict(TEXT_LIMITS),
    }


__all__ = ["v20_hard_component_breakdown"]
