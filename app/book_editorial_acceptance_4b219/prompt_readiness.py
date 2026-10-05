"""Evaluate whether prompt 1.1 may become the next-chapter reference candidate."""

from __future__ import annotations

from typing import Any

from app.book_authorial_voice_4b218.prompt_candidate import prompt_bundle
from app.book_editorial_acceptance_4b219.constants import (
    FAITHFUL_PROMPT_1_0,
    FAITHFUL_PROMPT_1_1,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    HISTORICAL_PROMPT_V10,
    HISTORICAL_PROMPT_V101,
    HISTORICAL_SEMANTIC,
    PHASE,
)
from app.book_generation.prompt_select import resolve_prompt_module


def _registered(version: str) -> bool:
    try:
        resolve_prompt_module(version)
    except ValueError:
        return False
    return True


def generator_prompt_readiness() -> dict[str, Any]:
    prompt = prompt_bundle()
    system = prompt["system"]
    instructions = prompt["instructions"]
    checks = {
        "strict_content_fidelity": (
            "Do not reformulate a sentence merely to produce more impressive prose."
            in system
            and "new facts, arguments, examples, references, or interpretations" in system
        ),
        "controlled_thematic_reorganization": (
            "Thematic reorganization" in system
            and "EditorialPlan has grouped them" in system
        ),
        "authorial_voice_preservation": (
            "preserve the main author's narrative voice" in system
        ),
        "prudent_attribution": (
            "If attribution is uncertain, keep the original person." in system
            and "AUDIO identifiers name recordings, not distinct persons." in system
        ),
        "nuance_preservation": (
            "Keep each claim with the conditions, reservations, and examples"
            in system
        ),
        "example_preservation": "dropping an important idea, reasoning, example" in system,
        "reference_preservation": (
            "Keep references as the source gave them." in system
            and "Do not complete" in system
            and "incomplete reference from memory." in system
        ),
        "idea_traceability_requirement": (
            "include that IDEA handle in paras[].e" in system
            and "Do not invent IDEA-to-paragraph correspondences." in system
        ),
        "validator_compatible_output_contract": (
            "paras[].e = evidence handles" in instructions
            and "paras[].u = optional UNC handles" in instructions
        ),
    }
    blocking = []
    if prompt["activated"] or FAITHFUL_PROMPT_1_1_ACTIVATED:
        blocking.append("prompt_1_1_must_remain_inactive_in_this_phase")
    if _registered(FAITHFUL_PROMPT_1_1):
        blocking.append("prompt_1_1_must_not_be_registered_in_prompt_select")
    untested_real_call = True
    ready_as_candidate = all(checks.values()) and not blocking
    return {
        "phase": PHASE,
        "version": FAITHFUL_PROMPT_1_1,
        "activated": False,
        "registered_in_prompt_select": _registered(FAITHFUL_PROMPT_1_1),
        "replaces_historical_prompt": False,
        "replaces_faithful_prompt_1_0_candidate": False,
        "historical_versions_left_in_place": [
            HISTORICAL_PROMPT_V10,
            HISTORICAL_PROMPT_V101,
            FAITHFUL_PROMPT_1_0,
            HISTORICAL_SEMANTIC,
        ],
        "checks": checks,
        "blocking_gaps": blocking,
        "operational_risks_not_textual_gaps": [
            "Prompt 1.1 has never been used in a real provider call.",
            "CH012 was generated with 1.0-candidate and has empty paragraph IDEA handles.",
            "The historical validator still accounts ideas by handle in paras[].e.",
            "A future isolated execution must stop if IDEA handles are invented or sprayed.",
        ],
        "untested_in_real_call": untested_real_call,
        "ready_as_reference_candidate": ready_as_candidate,
        "ready_for_production": False,
        "automatically_promoted": False,
        "prompt_sha256": prompt["prompt_sha256"],
        "system_sha256": prompt["system_sha256"],
        "instructions_sha256": prompt["instructions_sha256"],
        "secrets_included": False,
    }


__all__ = ["generator_prompt_readiness"]
