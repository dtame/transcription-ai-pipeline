"""Audit conformité / position / conflit du prompt 1.2.1 effectivement envoyé."""

from __future__ import annotations

from typing import Any

from app.source_analysis_hybrid.materialize import materialize_window_content
from app.source_analysis_local_v2.prompt import (
    build_window_system_prompt_v12,
    build_window_system_prompt_v121,
    build_window_user_prompt_v121,
)
from app.source_analysis_local_v2.schema import build_semantic_transport_v2_schema
from app.source_analysis_v2_a15_forensics.constants import (
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V121,
)
from app.source_analysis_v2_link_semantics.prompt_audit import audit_prompt_1_2_1
from app.source_analysis_v2_real_win001.window import load_candidate_win001

_OLD_PHRASE = "index locaux de CE transport"
_LINK_HEADING = "LINK RULES"


def _position(haystack: str, needle: str) -> dict[str, Any]:
    idx = haystack.find(needle)
    length = max(len(haystack), 1)
    if idx < 0:
        return {
            "present": False,
            "char": None,
            "pct": None,
            "zone": "absent",
            "occurrences": 0,
        }
    pct = 100.0 * idx / length
    if pct < 20:
        zone = "early"
    elif pct < 55:
        zone = "middle"
    else:
        zone = "late"
    return {
        "present": True,
        "char": idx,
        "pct": round(pct, 2),
        "zone": zone,
        "occurrences": haystack.count(needle),
    }


def audit_effective_1_2_1_request(
    project_name: str | None = None,
    *,
    sortie_dir=None,
) -> dict[str, Any]:
    bundle = load_candidate_win001(project_name or PROJECT_NAME, sortie_dir=sortie_dir)
    transcript = bundle["transcript"]
    window = bundle["window"]
    content = materialize_window_content(transcript, window)
    system = build_window_system_prompt_v121(transcript.primary_language)
    user = build_window_user_prompt_v121(transcript, window, content)
    combined = system + "\n\n" + user
    v12_system = build_window_system_prompt_v12(transcript.primary_language)
    compact = combined.replace(" ", "")
    schema = build_semantic_transport_v2_schema()
    record_props = schema["properties"]["records"]["items"]["properties"]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V121,
        "historical_1_2_1_mutated": False,
        "system_chars": len(system),
        "user_chars": len(user),
        "combined_chars": len(combined),
        "compliance": {
            "zero_based_target_explicit": combined.count("0-based") >= 3
            and "TARGET" in combined,
            "per_kind_target_rules_explicit": (
                "exactly 2 distinct IDEA" in combined
                and "IDEA indexes only" in combined
                and "TOPIC : l=[] required" in combined
            ),
            "self_link_prohibition_explicit": "Self-link" in combined
            and "FORBIDDEN" in combined,
            "relation_rule_correct": "l = exactly 2 distinct IDEA indexes [from, to]"
            in combined,
            "relation_json_example_present": '{"k":"RELATION"' in compact,
            "example_rule_correct": "EXAMPLE : l = IDEA indexes only" in combined,
            "example_json_example_present": '{"k":"EXAMPLE"' in compact,
            "example_json_teaches_idea_target": '"l":[1]' in compact
            and "EXAMPLE" in combined,
            "forward_references_explained": "Forward and backward targets are legal"
            in combined
            and "Resolve links after the full records[] list" in combined,
            "record_order_recommendation_clear": "Recommended order: TOPIC, IDEA, RELATION, EXAMPLE, REFERENCE, UNCERTAINTY."
            in combined,
            "kind_order_required": False,
        },
        "position": {
            "link_rules_system": _position(system, _LINK_HEADING),
            "link_rules_user": _position(user, _LINK_HEADING),
            "link_rules_combined": _position(combined, _LINK_HEADING),
            "repeated": combined.count(_LINK_HEADING) == 2,
            "dilution": (
                "LINK RULES appear once late in the short system prompt and once "
                "early in the user prompt, then are followed by the owned-source "
                f"dump ({len(user)} user chars). Instruction dilution is real."
            ),
            "conflicting_later_instruction": False,
        },
        "conflicts": {
            "old_v1_phrase_present": _OLD_PHRASE in combined,
            "old_v1_phrase_in_1_2_only": _OLD_PHRASE in v12_system
            and _OLD_PHRASE not in combined,
            "conflicting_passages": [],
            "mini_example_index_collision": (
                "The Correct block uses a 3-record world where EXAMPLE l=[1] "
                "targets the IDEA at global index 1. Under recommended "
                "TOPIC-first order on WIN001, global index 1 is a TOPIC."
            ),
            "no_relation_worked_example": True,
            "never_topic_for_relation_example_unstated": (
                "Rules say RELATION/EXAMPLE target IDEA, but never say "
                "'do not target TOPIC even when the association is thematic'."
            ),
        },
        "schema_audit": {
            "schema_changed": SCHEMA_CHANGED,
            "l_type": record_props["l"],
            "k_type": record_props["k"],
            "can_enforce_relation_to_idea": False,
            "can_enforce_example_to_idea": False,
            "reason": (
                "Provider schema only guarantees l is an integer array. "
                "Target-kind graph rules live in decoder/validator, not grammar."
            ),
            "schema_enlarged": False,
        },
        "prompt_1_2_1_facts": audit_prompt_1_2_1(),
        "ambiguity_remaining": True,
    }


__all__ = ["audit_effective_1_2_1_request"]
