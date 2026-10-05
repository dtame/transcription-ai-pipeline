"""Inspect prompt 1.1 fidelity, organization, voice, and traceability clauses."""

from __future__ import annotations

from typing import Any

from app.book_scale_up_preparation_4b220.constants import (
    EXPECTED_PROMPT_1_1_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_1_1_SHA256,
    EXPECTED_PROMPT_1_1_SYSTEM_SHA256,
    FAITHFUL_PROMPT_1_0,
    FAITHFUL_PROMPT_1_1,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    HISTORICAL_PROMPT_V101_ID,
    HISTORICAL_PROMPT_V10_ID,
    HISTORICAL_SEMANTIC,
    PHASE,
)
from app.book_scale_up_preparation_4b220.prompt_select import (
    inspect_prompt_1_1,
    prompt_1_1_registered_in_production,
    prompt_select_contract,
)


def generator_prompt_11_readiness() -> dict[str, Any]:
    prompt = inspect_prompt_1_1()
    system = str(prompt.get("system") or "")
    instructions = str(prompt.get("instructions") or "")
    compact = " ".join(system.split())
    compact_instructions = " ".join(instructions.split())
    checks = {
        "no_substantial_invention": (
            "new facts, arguments, examples, references, or interpretations" in compact
        ),
        "no_added_causality": (
            "new causal relations" in compact
            and "Proximity in the chapter does not mean" in compact
        ),
        "no_unjustified_strengthening": "strengthening of certainty" in compact,
        "preserve_reservations_and_nuances": (
            "Keep each claim with the conditions, reservations, and examples"
            in system
        ),
        "preserve_examples_and_references": (
            "Keep references as the source gave them." in system
            and "dropping an important idea, reasoning, example" in system
        ),
        "preserve_sense_relations": (
            "Do not write that link unless the supplied evidence" in system
        ),
        "preserve_split_ideas": (
            "Every assigned IDEA must be represented by its content in the prose"
            in compact_instructions
        ),
        "thematic_reorganization_allowed": "Thematic reorganization" in system,
        "grouping_related_passages": (
            "EditorialPlan has grouped them" in system
            and "they treat the same subject" in system
        ),
        "no_artificial_proximity_links": (
            "Proximity in the chapter does not mean" in system
        ),
        "no_generic_unsupported_conclusion": (
            "Do not add a section summary or a chapter conclusion" in system
        ),
        "first_person_for_author_testimony": (
            "Use I, me, my, we, and our when the supplied evidence shows the author"
            in system
        ),
        "second_person_for_address": "Keep you when the speaker addresses" in system,
        "third_person_for_other_people": (
            "Keep third person when the referent is another person" in system
        ),
        "respect_quotations": "Keep quotations as quotations." in system,
        "prudent_uncertain_attribution": (
            "If attribution is uncertain, keep the original person." in system
        ),
        "idea_content_must_appear_in_prose": (
            "Every assigned IDEA must be represented by its content in the prose"
            in compact_instructions
            and "not merely by its identifier in metadata" in compact_instructions
        ),
        "idea_handles_in_provenance_when_justified": (
            "include that IDEA handle in paras[].e" in compact
            and "When the supplied evidence makes the IDEA-to-paragraph correspondence"
            in compact_instructions
        ),
        "content_and_handle_are_distinct_obligations": (
            "represented by its content in the prose" in compact_instructions
            and "include that IDEA handle in paras[].e" in compact
        ),
        "no_invented_correspondence": (
            "Do not invent IDEA-to-paragraph correspondences." in system
        ),
        "no_post_hoc_handle_completion": (
            "Do not list an IDEA merely to mark it covered." in system
        ),
        "validator_output_contract": (
            "paras[].e = evidence handles" in instructions
            and "paras[].sid" not in instructions
            and "sections[].sid" in instructions
        ),
    }
    blocking = [name for name, ok in checks.items() if not ok]
    hashes_ok = (
        prompt.get("prompt_sha256") == EXPECTED_PROMPT_1_1_SHA256
        and prompt.get("system_sha256") == EXPECTED_PROMPT_1_1_SYSTEM_SHA256
        and prompt.get("instructions_sha256") == EXPECTED_PROMPT_1_1_INSTRUCTIONS_SHA256
    )
    if not hashes_ok:
        blocking.append("prompt_1_1_hash_mismatch")
    if prompt.get("activated") or FAITHFUL_PROMPT_1_1_ACTIVATED:
        blocking.append("prompt_1_1_must_remain_inactive")
    if prompt_1_1_registered_in_production():
        blocking.append("prompt_1_1_must_not_be_registered_in_production")
    return {
        "phase": PHASE,
        "version": FAITHFUL_PROMPT_1_1,
        "available": True,
        "isolated": True,
        "activated": False,
        "registered_in_prompt_select": prompt_1_1_registered_in_production(),
        "replaces_historical_prompt": False,
        "replaces_faithful_prompt_1_0_candidate": False,
        "historical_versions_left_in_place": [
            HISTORICAL_PROMPT_V10_ID,
            HISTORICAL_PROMPT_V101_ID,
            FAITHFUL_PROMPT_1_0,
            HISTORICAL_SEMANTIC,
        ],
        "selector": prompt_select_contract(),
        "checks": checks,
        "blocking_gaps": blocking,
        "handle_mention_is_not_content_restatement": True,
        "must_not_invent_paras_e_after_generation": True,
        "untested_in_real_call": True,
        "ready_as_isolated_candidate": not blocking,
        "ready_for_production": False,
        "automatically_promoted": False,
        "hashes_match_4b219": hashes_ok,
        "prompt_sha256": prompt["prompt_sha256"],
        "system_sha256": prompt["system_sha256"],
        "instructions_sha256": prompt["instructions_sha256"],
        "secrets_included": False,
    }


__all__ = ["generator_prompt_11_readiness"]
