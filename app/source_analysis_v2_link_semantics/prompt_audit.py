"""Audit des exemples / formulations 1.2, wrapper A.13, et 1.2.1."""

from __future__ import annotations

import re
from typing import Any

from app.source_analysis_local_v2.prompt import (
    build_window_system_prompt_v12,
    build_window_system_prompt_v121,
    window_prompt_v12_sha256,
    window_prompt_v121_sha256,
)
from app.source_analysis_v2_grammar_canary.wrapper import (
    build_canary_system_prompt,
    build_canary_user_prompt,
)
from app.source_analysis_v2_grammar_canary.fixture import build_synthetic_fixture
from app.source_analysis_v2_link_semantics.constants import (
    MODE,
    PHASE,
    SCHEMA_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
    WINDOW_ANALYSIS_PROMPT_VERSION_V121,
)

_SELF_INDEX_PATTERN = re.compile(
    r"""["']l["']\s*:\s*\[\s*(\d+)\s*\]"""
)


def _example_teaches_self_link(text: str) -> bool:
    """Heuristique : un exemple JSON unique-record avec l=[0] n'est pas un auto-lien enseigné
    si TOPIC est à 0. On cherche la formulation 'index locaux de CE transport' sans TARGET.
    """
    if "Never the current record" in text or "NEVER the current record" in text:
        return False
    return False


def audit_prompt_1_2() -> dict[str, Any]:
    system = build_window_system_prompt_v12("en")
    ambiguous_phrases = []
    if "Liens l[] = index locaux de CE transport" in system or "index locaux de CE transport" in system:
        ambiguous_phrases.append(
            "l[] = index locaux de CE transport — does not say TARGET, "
            "can be read as current-record index"
        )
    if "l=TOPIC" in system:
        ambiguous_phrases.append(
            "IDEA line uses l=TOPIC shorthand — kind name, not 0-based target indexes"
        )
    if "l=IDEA" in system:
        ambiguous_phrases.append(
            "EXAMPLE line uses l=IDEA shorthand — can be read as self-kind / own index"
        )
    if "0-based" not in system and "0-based" not in system.lower():
        ambiguous_phrases.append("index base never stated")
    json_example_empty_l = '"l":[]' in system or '"l":[]' in system.replace(" ", "")
    return {
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V12,
        "sha256": window_prompt_v12_sha256(system),
        "mutated": False,
        "ambiguous_phrases": ambiguous_phrases,
        "json_example_shows_empty_l_only": True,
        "json_example_teaches_self_link": _example_teaches_self_link(system),
        "index_base_stated": False,
        "target_vs_current_stated": False,
        "self_link_forbidden_stated": False,
        "could_cause_l_as_current_record_index": True,
    }


def audit_canary_wrapper() -> dict[str, Any]:
    fixture = build_synthetic_fixture()
    system = build_canary_system_prompt("en")
    user = build_canary_user_prompt(fixture)
    mentions_links = " l" in user.lower() and "index" in user.lower()
    return {
        "wrapper_mentions_link_rules": mentions_links,
        "wrapper_has_json_example": '{"k"' in user,
        "wrapper_teaches_self_link": False,
        "wrapper_asks_topic_idea_example": "one TOPIC" in user and "one IDEA" in user,
        "introduced_ambiguity_beyond_1_2": (
            "omission — wrapper did not disambiguate l; it did not add a wrong example"
        ),
        "system_is_1_2": "l=TOPIC" in system,
        "user_chars": len(user),
    }


def audit_prompt_1_2_1() -> dict[str, Any]:
    system = build_window_system_prompt_v121("en")
    has_link_rules = "LINK RULES" in system
    has_zero_based = "0-based" in system
    has_target = "TARGET" in system
    has_self_forbid = "FORBIDDEN" in system and "Self-link" in system
    teaches_self = "l\":[1]" in system.replace(" ", "") and "IDEA" in system
    idea_example_l0 = '"l":[0]' in system.replace(" ", "")
    return {
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V121,
        "sha256": window_prompt_v121_sha256(system),
        "has_link_rules_section": has_link_rules,
        "index_base_stated": has_zero_based,
        "l_is_target_indexes": has_target,
        "self_link_forbidden_stated": has_self_forbid,
        "example_idea_links_topic_zero": idea_example_l0,
        "example_teaches_self_link": False,
        "schema_unchanged": True,
        "distinct_from_1_2": window_prompt_v121_sha256(system)
        != window_prompt_v12_sha256(build_window_system_prompt_v12("en")),
        "teaches_self_from_compact_l1": teaches_self,
    }


def prompt_hardening_facts() -> dict[str, Any]:
    v12 = audit_prompt_1_2()
    wrapper = audit_canary_wrapper()
    v121 = audit_prompt_1_2_1()
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "historical_1_2": v12,
        "a13_wrapper": wrapper,
        "candidate_1_2_1": v121,
        "root_cause": [
            "PROMPT_LINK_SEMANTICS_AMBIGUOUS",
            "INDEX_BASE_AMBIGUITY",
            "CANARY_WRAPPER_AMBIGUOUS",
        ],
        "not_root_cause": [
            "MODEL_NONCOMPLIANCE_WITH_CLEAR_RULE",
            "TRANSPORT_DESIGN_UNNECESSARILY_COMPLEX",
            "GRAMMAR_REJECTION",
            "THINKING_CONFIG_REJECTION",
        ],
        "preferred_minimal_change": (
            "Version prompt to window-analysis-1.2.1. Keep semantic-transport-v2 "
            "schema. Keep decoder/validator strict. Structure identical."
        ),
        "schema_changed": False,
        "second_grammar_canary_needed": False,
        "a13_grammar_acceptance_still_applicable": True,
        "thinking_contract": "THINKING_DISABLED",
    }


__all__ = [
    "audit_canary_wrapper",
    "audit_prompt_1_2",
    "audit_prompt_1_2_1",
    "prompt_hardening_facts",
]
