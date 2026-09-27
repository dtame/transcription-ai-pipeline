"""Audit du contrat IDEA vs EXAMPLE dans le prompt 1.3.1 et le schéma V3."""

from __future__ import annotations

from typing import Any

from app.source_analysis.models import EXAMPLE_KINDS, IDEA_KINDS, IMPORTANCE_LEVELS
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.prompt import (
    build_window_system_prompt_v131,
    build_window_system_prompt_v132,
    build_window_user_prompt_v131,
    build_window_user_prompt_v132,
    estimate_v131_request_tokens,
    estimate_v132_request_tokens,
)
from app.source_analysis_local_v3.schema import (
    build_semantic_transport_v3_schema,
    measure_v3_schema_pair,
    semantic_transport_v3_fingerprint,
)
from app.source_analysis_v3_a22_forensics.constants import (
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    EXPECTED_SCHEMA_HASH,
    IDEA_EXAMPLE_ROOT_CAUSE,
    MODE,
    PHASE,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SERVER_GRAMMAR_STATUS,
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
    WINDOW_ANALYSIS_PROMPT_VERSION_V132,
)

_NEGATIVE_RULE_CONCEPT = (
    "For IDEA records, the IDEA semantic kind MUST be one of: "
    "claim, explanation, principle, instruction, observation, question, testimony. "
    'NEVER use "example" as an IDEA semantic kind. '
    "If content is merely illustrative, use an EXAMPLE record instead."
)


def _placement(text: str, needle: str, *, region: str) -> dict[str, Any]:
    idx = text.find(needle)
    return {
        "region": region,
        "present": idx >= 0,
        "offset": idx,
        "near_end": idx >= 0 and idx > max(0, len(text) - 800),
    }


def audit_idea_example_contract(
    transcript: TranscriptInput,
    window: WindowInput,
) -> dict[str, Any]:
    system = build_window_system_prompt_v131(transcript.primary_language)
    user = build_window_user_prompt_v131(transcript, window)
    combined = system + "\n" + user
    idea_line = f"idea.kind : {', '.join(IDEA_KINDS)}"
    example_line = f"example.kind : {', '.join(EXAMPLE_KINDS)}"
    idea_shape = "IDEA : v=summary ; m=[kind, importance]"
    example_shape = "EXAMPLE : v=summary ; m=[kind]"
    compact_idea = 'm":["claim","central"]'
    compact_example = 'm":["anecdote"]'
    never_example = (
        'never use "example" as an idea' in combined.lower()
        or "never use 'example' as an idea" in combined.lower()
    )
    illustrative_rule = (
        "if content is merely illustrative" in combined.lower()
        or "if a passage merely illustrates" in combined.lower()
    )
    schema = build_semantic_transport_v3_schema()
    record_props = schema["properties"]["records"]["items"]["properties"]
    measured = measure_v3_schema_pair()
    system_132 = build_window_system_prompt_v132(transcript.primary_language)
    user_132 = build_window_user_prompt_v132(transcript, window)
    est_131 = estimate_v131_request_tokens(transcript, window)
    est_132 = estimate_v132_request_tokens(transcript, window)
    causes = {
        "A_PROMPT_VOCABULARY_AMBIGUITY": {
            "applies": True,
            "weight": "primary",
            "evidence": (
                "idea.kind and example.kind are listed as adjacent controlled "
                "vocabularies. Both use the overloaded word 'kind'. The token "
                "'example' is a valid EXAMPLE metadata value sitting next to "
                "the IDEA list. No negative exclusion is stated."
            ),
        },
        "B_IDEA_EXAMPLE_CONCEPTUAL_OVERLAP": {
            "applies": True,
            "weight": "secondary",
            "evidence": (
                "A concrete story can carry a proposition. The prompt never "
                "tells the model to split proposition (IDEA) from illustration "
                "(EXAMPLE)."
            ),
        },
        "C_METADATA_FIELD_OVERLOADING": {
            "applies": True,
            "weight": "secondary",
            "evidence": (
                "m[] is a single string array for every record kind: TOPIC "
                "summary, IDEA kind+importance, EXAMPLE kind, REFERENCE three "
                "slots, UNCERTAINTY kind+severity, RELATION empty. The same "
                "slot m[0] means different vocabularies."
            ),
        },
        "D_MODEL_NONCOMPLIANCE_DESPITE_CLEAR_CONTRACT": {
            "applies": False,
            "weight": "rejected",
            "evidence": (
                "The contract lists valid IDEA kinds but never forbids "
                "'example' as an IDEA kind and never contrasts IDEA vs EXAMPLE "
                "as record types. Noncompliance is not the primary reading."
            ),
        },
        "E_CANONICAL_TAXONOMY_TOO_RESTRICTIVE": {
            "applies": False,
            "weight": "rejected",
            "evidence": (
                "Each of the four records is representable with existing IDEA "
                "kinds (claim/explanation/observation) plus EXAMPLE. Taxonomy "
                "does not need a new IDEA kind."
            ),
        },
        "F_PROMPT_EXAMPLE_INSUFFICIENT": {
            "applies": True,
            "weight": "secondary",
            "evidence": (
                "The compact prompt example shows only IDEA m=[claim, …] and "
                "EXAMPLE m=[anecdote]. It never shows a split of a story that "
                "also states a proposition, and never shows a rejected "
                "IDEA m=[example, …] row."
            ),
        },
        "G_OTHER_EXAMPLE_KIND_TOKEN_COLLISION": {
            "applies": True,
            "weight": "secondary",
            "evidence": (
                f"EXAMPLE_KINDS includes 'example' ({', '.join(EXAMPLE_KINDS)}). "
                "That token collides with the EXAMPLE record kind name and is "
                "easy to copy into IDEA.m[0]."
            ),
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "effective_prompt_version_a22": WINDOW_ANALYSIS_PROMPT_VERSION_V131,
        "prompt_1_3_1_untouched": (
            "Never use \"example\" as an IDEA kind" not in system
            and "Never use \"example\" as an IDEA kind" not in user
        ),
        "system_chars_1_3_1": len(system),
        "user_chars_1_3_1": len(user),
        "idea_contract": {
            "record_kind": "IDEA",
            "value": "v=summary",
            "metadata_shape": "m=[kind, importance]",
            "valid_kinds": list(IDEA_KINDS),
            "valid_importance": list(IMPORTANCE_LEVELS),
            "owner_handle": "h=I1…",
            "links": "l=T labels",
            "source_refs": "s=SRC required",
            "wording_locations": [
                _placement(system, idea_line, region="system.vocabulary"),
                _placement(system, idea_shape, region="system.vocabulary"),
                _placement(system, compact_idea, region="system.handle_example"),
                _placement(user, idea_shape, region="user.absent_unless_repeated"),
            ],
        },
        "example_contract": {
            "record_kind": "EXAMPLE",
            "value": "v=summary",
            "metadata_shape": "m=[kind]",
            "valid_kinds": list(EXAMPLE_KINDS),
            "owner_handle": "h=\"\"",
            "links": "l=I labels or [] (A.20 optional association)",
            "source_refs": "s=SRC required",
            "wording_locations": [
                _placement(system, example_line, region="system.vocabulary"),
                _placement(system, example_shape, region="system.vocabulary"),
                _placement(system, compact_example, region="system.handle_example"),
            ],
        },
        "difference_idea_vs_example": {
            "explicit_record_kind_split": True,
            "explicit_metadata_vocabulary_split": True,
            "explicit_negative_rule_never_example_on_idea": never_example,
            "explicit_illustrative_content_uses_example_record": illustrative_rule,
            "exact_conceptual_distinction_already_exists": False,
            "requested_negative_rule_text": _NEGATIVE_RULE_CONCEPT,
            "closest_existing_wording": idea_line + " / " + example_line,
        },
        "prompt_placement": {
            "system_has_vocabularies": idea_line in system and example_line in system,
            "system_has_handle_rules": "IDEA : h=In" in system,
            "system_has_compact_example": compact_idea in system,
            "user_repeats_handle_rules": "IDEA : h=In" in user,
            "user_repeats_task_kinds": "Kinds locaux autorisés" in user,
            "user_does_not_repeat_idea_kind_list": idea_line not in user,
            "early_instructions": "IDENTIFIANTS CONTRÔLÉS" in system,
            "late_instructions": "SOURCE IDENTIFIERS" in system,
            "schema_descriptions": "none — schema has no enums or per-kind descriptions",
        },
        "prompt_salience": {
            "valid_idea_vocabulary_explicit": True,
            "valid_idea_vocabulary_complete": all(
                token in system for token in IDEA_KINDS
            ),
            "close_to_generation_instructions": False,
            "repeated_unnecessarily": False,
            "easy_to_confuse_with_record_kind": True,
            "reason": (
                "idea.kind appears once in the system vocabulary block, not in "
                "the user task block that sits next to the CLEAN window. "
                "example.kind is listed immediately after idea.importance / "
                "relation.type. The compact example never forbids IDEA/"
                "example."
            ),
        },
        "schema_enforcement": {
            "schema_name": "semantic-transport-v3",
            "raw_bytes": measured["raw_bytes"],
            "adapted_bytes": measured["adapted_bytes"],
            "hash": semantic_transport_v3_fingerprint(),
            "expected_hash": EXPECTED_SCHEMA_HASH,
            "hash_unchanged": semantic_transport_v3_fingerprint() == EXPECTED_SCHEMA_HASH,
            "m_type": record_props["m"],
            "k_has_enum": "enum" in record_props["k"],
            "m_has_enum": "enum" in record_props["m"],
            "conditional_per_kind_metadata_possible": False,
            "can_currently_enforce_idea_specific_vocabulary": False,
            "compactness_preserved": (
                measured["raw_bytes"] == EXPECTED_RAW_SCHEMA_BYTES
                and measured["adapted_bytes"] == EXPECTED_ADAPTED_SCHEMA_BYTES
            ),
            "do_not_enlarge_without_evidence": True,
            "schema_change_proposed": False,
            "reason_prompt_hardening_preferred": (
                "Four violations are explained by prompt ambiguity. JSON Schema "
                "would need if/then per-kind enums, enlarging the 588/650 byte "
                "grammar that A.18 already proved."
            ),
        },
        "m_field_semantics": {
            "TOPIC": "m=[summary] — free text, not a closed kind",
            "IDEA": "m=[kind, importance] — kind ∈ IDEA_KINDS",
            "RELATION": "m=[] required empty; type lives in v",
            "EXAMPLE": "m=[kind] — kind ∈ EXAMPLE_KINDS including 'example'",
            "REFERENCE": "m=[kind, completeness, normalized]",
            "UNCERTAINTY": "m=[kind, severity]",
            "overloaded": True,
            "redesign_m_now": False,
            "reason": (
                "Four violations do not justify redesigning m. Prompt "
                "hardening is the first remedy. Schema stays compact."
            ),
        },
        "root_cause": IDEA_EXAMPLE_ROOT_CAUSE,
        "cause_evaluation": causes,
        "prompt_hardening_justified": True,
        "prompt_1_3_2": {
            "version": WINDOW_ANALYSIS_PROMPT_VERSION_V132,
            "created": True,
            "mutates_1_3_1": False,
            "system_chars": len(system_132),
            "user_chars": len(user_132),
            "system_overhead_chars": len(system_132) - len(system),
            "user_overhead_chars": len(user_132) - len(user),
            "local_tokens_1_3_1": int(est_131["total_tokens"]),
            "local_tokens_1_3_2": int(est_132["total_tokens"]),
            "input_overhead_tokens": int(est_132["total_tokens"])
            - int(est_131["total_tokens"]),
            "contains_negative_rule": (
                'Never use "example" as an IDEA kind' in system_132
            ),
            "contains_split_rule": (
                "separate the proposition as IDEA" in system_132
            ),
            "keeps_example_links_optional": (
                "l[] on EXAMPLE remains optional" in system_132
            ),
            "does_not_force_supports_idea_refs": True,
        },
        "schema_changed": SCHEMA_CHANGED,
        "server_grammar_status": SERVER_GRAMMAR_STATUS,
        "supports_idea_refs_policy": "optional — A.20 retained",
    }


__all__ = ["audit_idea_example_contract"]
