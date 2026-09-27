"""Worst-case synthétique du contrat local proposé. Fake / offline only."""

from __future__ import annotations

from typing import Any

from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.source_analysis.schema_complexity import analyze_schema_complexity
from app.source_analysis.ultra_compact_schema import build_ultra_compact_response_schema
from app.source_analysis.window_granularity import TEXT_HARD_LIMITS
from app.source_analysis_window_output_bounding.size_study import (
    build_scenario_transport,
    measure_transport,
)
from app.source_analysis_output_ceiling_review.constants import PROPOSED_TRANSPORT

LOCAL_KINDS = ("TOPIC", "IDEA", "EXAMPLE", "REFERENCE", "UNCERTAINTY", "RELATION")
DEFERRED_KINDS = ("REPETITION", "VOICE", "INTENT_KIND", "AUDIENCE_KIND")

PROPOSED_HARD = {
    "TOPIC": 14,
    "IDEA": 56,
    "RELATION": 24,
    "EXAMPLE": 14,
    "REFERENCE": 14,
    "UNCERTAINTY": 12,
}
PROPOSED_TOTAL_HARD = 134
PROPOSED_SOURCE_REFS_MAX = 12
RESERVED_THINKING_TOKENS = 8000
RESERVED_JSON_TOKENS = 24000
TARGET_JSON_LOCAL_TOKENS = 12000


def proposed_minimal_schema() -> dict:
    """
    Même forme records[] que Generation C — pas de maxItems.

    Grammar complexity SIMILAR. Ne mute pas Generation C historique.
    """
    return build_ultra_compact_response_schema()


def proposed_fixed_slot_schema() -> dict:
    item = {
        "type": "object",
        "required": ["v", "s", "l", "m"],
        "properties": {
            "v": {"type": "string"},
            "s": {"type": "array", "items": {"type": "string"}},
            "l": {"type": "array", "items": {"type": "integer"}},
            "m": {"type": "array", "items": {"type": "string"}},
        },
    }
    return {
        "type": "object",
        "required": ["theme", "intent", "ic", "aud", "ac", *LOCAL_KINDS],
        "properties": {
            "theme": {"type": "string"},
            "intent": {"type": "string"},
            "ic": {"type": "string"},
            "aud": {"type": "string"},
            "ac": {"type": "string"},
            **{kind.lower(): {"type": "array", "items": item} for kind in LOCAL_KINDS},
        },
    }


def build_proposed_worst_case() -> dict[str, Any]:
    transport = build_scenario_transport(
        counts=dict(PROPOSED_HARD),
        idea_refs=PROPOSED_SOURCE_REFS_MAX,
        topic_refs=PROPOSED_SOURCE_REFS_MAX,
        other_refs=min(8, PROPOSED_SOURCE_REFS_MAX),
        max_text=True,
    )
    # Drop deferred kinds if the shared builder added them.
    transport["records"] = [
        item
        for item in transport.get("records") or []
        if item.get("k") in LOCAL_KINDS
    ]
    measured = measure_transport(transport)
    generic = proposed_minimal_schema()
    slots = proposed_fixed_slot_schema()
    generic_adapted = prepare_anthropic_json_schema(generic)
    slots_adapted = prepare_anthropic_json_schema(slots)
    local = int(measured["local_estimated_tokens"])
    return {
        "transport_name": PROPOSED_TRANSPORT,
        "local_kinds": list(LOCAL_KINDS),
        "deferred_kinds": list(DEFERRED_KINDS),
        "proposed_hard": dict(PROPOSED_HARD),
        "proposed_total_hard": PROPOSED_TOTAL_HARD,
        "source_refs_max": PROPOSED_SOURCE_REFS_MAX,
        "text_limits": {key: TEXT_HARD_LIMITS[key] for key in TEXT_HARD_LIMITS},
        "synthetic": measured,
        "record_count": measured["record_count"],
        "within_proposed_total": measured["record_count"] <= PROPOSED_TOTAL_HARD,
        "local_tokens": local,
        "target_json_local_tokens": TARGET_JSON_LOCAL_TOKENS,
        "within_json_target": local <= TARGET_JSON_LOCAL_TOKENS,
        "reserved_thinking_tokens": RESERVED_THINKING_TOKENS,
        "reserved_json_tokens": RESERVED_JSON_TOKENS,
        "comfortably_below_32000_if_thinking_capped": (
            local <= TARGET_JSON_LOCAL_TOKENS
        ),
        "provider_enforced": False,
        "schema": {
            "generic_records": {
                "complexity": analyze_schema_complexity(generic),
                "adapted_complexity": analyze_schema_complexity(generic_adapted),
                "grammar_vs_generation_c": "SIMILAR",
            },
            "fixed_slots": {
                "complexity": analyze_schema_complexity(slots),
                "adapted_complexity": analyze_schema_complexity(slots_adapted),
                "grammar_vs_generation_c": "HIGHER",
            },
        },
    }
