"""Narrowest generic contract-hardening decision. Offline only."""

from __future__ import annotations

from typing import Any, Mapping

from app.editorial_planner_forensics_4a34.constants import (
    A33_PROMPT,
    CANARY_DECISION,
    HISTORICAL_PROMPT,
    NEW_GRAMMAR_CANARY_REQUIRED,
    NEW_SYNTHETIC_CONTRACT_CANARY_REQUIRED,
    SUCCESSOR_PROMPT,
    TRANSPORT_VERSION,
)
from app.editorial_planning.prompt_v102 import EDITORIAL_PLANNER_PROMPT_VERSION_V102


def contract_hardening_decision(
    *,
    root_cause: Mapping[str, Any],
    prompt: Mapping[str, Any],
    transport: Mapping[str, Any],
) -> dict[str, Any]:
    primary = str(root_cause.get("primary_root_cause") or "")
    prompt_only = (
        primary == "PROVIDER_COMPLIANCE_FAILURE"
        and transport.get("transport_defect") == "NO"
        and transport.get("schema_defect") == "NO"
        and transport.get("validator_defect") == "NO"
        and prompt.get("v102", {}).get("contains_hardening") is True
    )
    return {
        "selected_fix": "PROMPT_COVERAGE_HARDENING_1_0_2",
        "successor_prompt": SUCCESSOR_PROMPT,
        "successor_prompt_version_constant_unchanged": A33_PROMPT,
        "note_on_successor_constant": (
            "language_policy.SUCCESSOR_PROMPT_VERSION remains "
            "editorial-planner-1.0.1. Production 1.0.2 is a new module, "
            "not a silent replacement of the language-policy successor."
        ),
        "historical_prompt_1_0_mutated": False,
        "historical_prompt_1_0_1_mutated": False,
        "transport": TRANSPORT_VERSION,
        "transport_changed": False,
        "schema_changed": "NO",
        "language_rule_changed": False,
        "idea_specific_prompting": False,
        "pastoral_specific_prompting": False,
        "automatic_repair": False,
        "automatic_provider_retry": False,
        "expected_idea_ids_duplicated": False,
        "expected_idea_count_added": True,
        "expected_idea_count_derived_dynamically": True,
        "new_grammar_canary_required": NEW_GRAMMAR_CANARY_REQUIRED,
        "new_synthetic_contract_canary_required": NEW_SYNTHETIC_CONTRACT_CANARY_REQUIRED,
        "canary_decision": CANARY_DECISION,
        "canary_justification": (
            "The change is semantic completeness wording plus a cheap "
            "expected_idea_count signal. Grammar is unchanged (A.1 already "
            "proved it; A.3 produced 286/286 on this transport; A.3.3 "
            "decoded a valid English plan). A paid synthetic contract "
            "canary would not prove live Opus compliance. FakeAI proves "
            "the validator gate. One human-authorized real production "
            "retry is the remaining empirical test."
        ),
        "prompt_only_hardening_sufficient": prompt_only,
        "v102_version": EDITORIAL_PLANNER_PROMPT_VERSION_V102,
        "base_prompts": {
            "historical": HISTORICAL_PROMPT,
            "a33": A33_PROMPT,
        },
        "narrowest_fix_rationale": (
            "Harden the prompt/contract. Keep transport, schema, language "
            "rule, and the hard validator gate. Do not auto-assign omitted "
            "ideas and do not auto-retry."
        ),
    }


__all__ = ["contract_hardening_decision"]
