"""Analyse forensique A.35 : DROP, dispositions, répétition, fixture, root causes."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_global_canary_forensics.constants import (
    A35_COMPANION_INPUT_ID,
    A35_COMPANION_OP,
    A35_DROP_FIELD_OP,
    A35_DROP_FIELD_REASON,
    A35_DROP_INPUT_ID,
    A35_DROP_PROSE,
    A35_REPETITION_COUNT,
    ALLOWED_DROP_REASONS,
    CANONICAL_DROP_TOKEN,
    DROP_REASON_CLASS,
    FIXTURE_OVERCONSTRAINED,
    LINK_RELATED_CONTRACT,
    OLD_PROMPT_VERSION,
    OLD_TRANSPORT_VERSION,
    REPETITION_REQUIREMENT,
    SELECTED_DISPOSITION_MODEL,
)
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    DROP_REASON_CODES,
    REASON_CODES,
    REPRESENTATION_OPS,
)
from app.source_analysis_v31_global_grammar_canary.fixture import expected_dispositions
from app.source_analysis_v31_global_preflight.prompt import SYSTEM_PROMPT as PROMPT_V10
from app.source_analysis_v31_global_preflight.transport import (
    DISP_FIELDS,
    build_global_consolidation_schema,
)


def classify_a35_failures(replay: Mapping[str, Any]) -> dict[str, Any]:
    transport = replay.get("transport") or {}
    nodes = [item for item in (transport.get("n") or []) if isinstance(item, dict)]
    dispositions = [item for item in (transport.get("d") or []) if isinstance(item, dict)]
    relations = [item for item in (transport.get("r") or []) if isinstance(item, dict)]
    companion = next(
        (row for row in dispositions if row.get("i") == A35_COMPANION_INPUT_ID),
        {},
    )
    drop = next(
        (row for row in dispositions if row.get("i") == A35_DROP_INPUT_ID),
        {},
    )
    companion_keep_has_relation = any(
        str(rel.get("a") or "") == "I3" or str(rel.get("b") or "") == "I3"
        for rel in relations
    )
    root = list(replay.get("root_validator_violations") or [])
    cascade = list(replay.get("cascade_validator_violations") or [])
    semantic_notes = list((replay.get("semantic_detail") or {}).get("notes") or [])
    return {
        "root_contract_violations": [
            {
                "id": "DROP_REASON_PROSE_NOT_TOKEN",
                "class": "ROOT_CONTRACT_VIOLATION",
                "input_id": A35_DROP_INPUT_ID,
                "field_op": A35_DROP_FIELD_OP,
                "field_reason": A35_DROP_FIELD_REASON,
                "observed": drop.get("w"),
                "required_tokens": list(ALLOWED_DROP_REASONS),
                "canonical_token": CANONICAL_DROP_TOKEN,
                "validator_errors": root,
            }
        ],
        "cascade_failures": [
            {
                "id": "SEMANTIC_FIXTURE_REVIEW_FAIL",
                "class": "CASCADE_FAILURE",
                "caused_by": "DROP_REASON_PROSE_NOT_TOKEN",
                "detail": (
                    "A.35 semantic review reuses the same exact-token DROP check. "
                    "No invented facts, lost ideas, unrelated merge, or kind-promotion "
                    "errors were recorded."
                ),
                "semantic_status": replay.get("semantic_review"),
                "semantic_notes": semantic_notes,
                "disposition_contract": (replay.get("semantic_detail") or {}).get(
                    "disposition_contract"
                ),
            }
        ],
        "semantic_expectation_differences": [
            {
                "id": "KEEP_VS_LINK_RELATED_COMPANION_PLANTING",
                "class": "SEMANTIC_EXPECTATION_DIFFERENCE",
                "input_id": A35_COMPANION_INPUT_ID,
                "fixture_expected": expected_dispositions().get(A35_COMPANION_INPUT_ID),
                "provider_op": companion.get("o"),
                "survives_as_own_idea": companion.get("o") == "KEEP" and companion.get("g") == "I3",
                "independent_relation_emitted": companion_keep_has_relation,
                "semantically_invalid": False,
                "finding": (
                    "KEEP was semantically valid: the companion-planting proposition "
                    "survives as its own global idea. The provider also emitted a "
                    "source-grounded r[] edge (I3 supports I2). LINK_RELATED was not "
                    "mandatory."
                ),
            },
            {
                "id": "MISSING_REPETITION_NODE",
                "class": "SEMANTIC_EXPECTATION_DIFFERENCE",
                "observed_count": A35_REPETITION_COUNT,
                "contract_required": False,
                "finding": (
                    "No REPETITION node. The compost pair is MERGE_EQUIVALENT of the "
                    "same proposition extracted in two windows, not an author recap. "
                    "Canary PASS must not depend on REPETITION."
                ),
            },
            {
                "id": "LOCAL_RELATION_KEEP_EMPTY_G",
                "class": "SEMANTIC_EXPECTATION_DIFFERENCE",
                "finding": (
                    "Local RELATION rows used KEEP with empty g and a prose note. "
                    "Under 1.0 this is not a validator error. Under 1.1 they are OTHER "
                    "with reason_code none."
                ),
            },
        ],
        "node_count": len(nodes),
        "relation_count": len(relations),
        "disposition_count": len(dispositions),
        "repetition_count": sum(1 for node in nodes if node.get("k") == "REPETITION"),
        "idea_count": sum(1 for node in nodes if node.get("k") == "IDEA"),
    }


def drop_contract_analysis() -> dict[str, Any]:
    schema = build_global_consolidation_schema()
    disp_schema = (
        ((schema.get("properties") or {}).get("d") or {}).get("items") or {}
    )
    reason_schema = ((disp_schema.get("properties") or {}).get("w") or {})
    prompt = PROMPT_V10
    prompt_lists_tokens = all(token in prompt for token in ALLOWED_DROP_REASONS)
    prompt_says_exact_token_only = "exact token" in prompt.lower()
    prompt_overloads_w = "explain in d.w" in prompt
    examples_show_tokens = "non_substantive_fragment" in prompt and "d.w" in prompt
    return {
        "disposition_operation_field": "o",
        "drop_reason_field": "w",
        "schema_type_of_reason": reason_schema.get("type"),
        "schema_enum_present": "enum" in reason_schema,
        "schema_required_fields": list(DISP_FIELDS),
        "schema_constrains_reason_to_enum": False,
        "prompt_version": OLD_PROMPT_VERSION,
        "prompt_lists_allowed_tokens": prompt_lists_tokens,
        "prompt_explicitly_requires_exact_token_only": prompt_says_exact_token_only,
        "prompt_examples_demonstrate_exact_token": bool(examples_show_tokens),
        "prompt_overloads_w_as_explanation": prompt_overloads_w,
        "validator_imposes_exact_token": True,
        "field_class": DROP_REASON_CLASS,
        "canonical_vocabulary": list(ALLOWED_DROP_REASONS),
        "vocabulary_expanded_to_accept_a35_prose": False,
        "heuristic_normalization_forbidden": True,
        "separate_prose_note_field": {
            "adopted": False,
            "reason": (
                "A machine enum is sufficient. Optional prose would recreate overload "
                "unless split; Anthropic objects require all properties listed, so an "
                "unused note field adds grammar without audit value."
            ),
        },
        "preferred_v11_reason_codes": list(REASON_CODES),
        "non_drop_must_use": "none",
        "conditional_if_then_rejected": (
            "Anthropic-compatible schema must not rely on JSON Schema if/then/else "
            "or dependentRequired. Unconditional enum including none is simpler."
        ),
    }


def disposition_semantics() -> dict[str, Any]:
    return {
        "selected_model": SELECTED_DISPOSITION_MODEL,
        "orthogonal_questions": {
            "representation": "What happened to the local proposition?",
            "relation": "Is it semantically related to another global proposition?",
            "one_enum_was_overloaded": True,
            "redesign": (
                "d.o answers representation only. r[] answers relation independently."
            ),
        },
        "KEEP": {
            "definition": (
                "The local proposition survives as its own global idea. g names that "
                "IDEA handle. KEEP does not mean unrelated to everything else. KEEP "
                "may coexist with r[] edges."
            ),
            "not": "unrelated / isolated / no relations allowed",
            "a35_companion_planting": {
                "provider_op": A35_COMPANION_OP,
                "semantically_invalid": False,
                "link_related_mandatory": False,
            },
        },
        "MERGE_EQUIVALENT": {
            "definition": (
                "Two or more local ideas express the same proposition. One global "
                "idea. Union of supporting SRC. Wording must not broaden beyond "
                "constituent source evidence."
            ),
            "minimum_inputs": 2,
        },
        "DROP": {
            "definition": (
                "The local idea does not survive as a global proposition. g empty. "
                "reason_code must be an exact allowed DROP token."
            ),
            "allowed_reason_codes": list(DROP_REASON_CODES),
            "forbidden": ["not_important", "prose explanations"],
        },
        "OTHER": {
            "definition": (
                "The local record is accounted for but is not a surviving global "
                "node of the same kind. Primary use: local RELATION hints "
                "(non-authoritative). For IDEA, allowed only when represented as "
                "another approved object and g names that handle. Not an escape hatch."
            ),
            "why_it_exists": (
                "100% disposition auditing of non-IDEA records, especially local "
                "RELATION hints that must not be copied as global truth."
            ),
            "narrowed": True,
            "removed": False,
        },
        "LINK_RELATED": {
            "contract": LINK_RELATED_CONTRACT,
            "rejected_meanings": {
                "A": "survives as own global idea AND a relation is added — redundant with KEEP + r[]",
                "B": "represented only through a relation — would silently drop a distinct proposition",
            },
            "no_drop_property": (
                "If the idea remains substantively distinct, its proposition must "
                "remain represented globally via KEEP or MERGE_EQUIVALENT."
            ),
            "keep_and_relation_independent": True,
            "a35_provider_semantically_correct_to_keep": True,
        },
        "representation_ops_v11": list(REPRESENTATION_OPS),
    }


def repetition_policy() -> dict[str, Any]:
    return {
        "requirement": REPETITION_REQUIREMENT,
        "a35_emitted_count": A35_REPETITION_COUNT,
        "a34_definition": (
            "Genuine source recurrence at distinct SRC positions where the author "
            "restates the same substantive proposition."
        ),
        "not_repetition": (
            "Two local extraction records of the same occurrence/duplicate, or two "
            "window-local encodings of one equivalent proposition (that is MERGE)."
        ),
        "a35_fixture_compost_pair": {
            "ids": ["SYN001:I2", "SYN002:I1"],
            "correct_behavior": "MERGE_EQUIVALENT",
            "is_author_recap": False,
            "required_repetition_node": False,
        },
        "fail_canary_for_missing_repetition": False,
        "next_fixture_depends_on_repetition": False,
    }


def fixture_expectation_review() -> dict[str, Any]:
    return {
        "overconstrained": FIXTURE_OVERCONSTRAINED,
        "canary_design_principle": (
            "A grammar/transport canary proves grammar acceptance, transport decoding, "
            "machine contract compliance, validator compatibility, and canonical "
            "reconstruction. It must not require one arbitrary semantic interpretation "
            "when multiple valid interpretations exist."
        ),
        "cases": [
            {
                "id": "SYN001:I1",
                "content": "Water garden beds at dawn so leaves dry before noon.",
                "fixture_expected": "KEEP",
                "classification": "REQUIRED_BY_CONTRACT",
                "notes": "Distinct watering proposition must survive independently.",
            },
            {
                "id": "SYN001:I2",
                "content": "Compost from kitchen scraps feeds soil without synthetic fertilizer.",
                "fixture_expected": "MERGE_EQUIVALENT",
                "classification": "REQUIRED_BY_CONTRACT",
                "notes": "Genuinely equivalent to SYN002:I1.",
            },
            {
                "id": "SYN001:I3",
                "content": "and then uh",
                "fixture_expected": "DROP",
                "classification": "REQUIRED_BY_CONTRACT",
                "notes": "Unmistakable non_substantive_fragment. Token must be exact.",
            },
            {
                "id": "SYN002:I1",
                "content": "Kitchen-scrap compost feeds garden soil without bottled fertilizer.",
                "fixture_expected": "MERGE_EQUIVALENT",
                "classification": "REQUIRED_BY_CONTRACT",
                "notes": "Same proposition as SYN001:I2. Union SRC required.",
            },
            {
                "id": "SYN002:I2",
                "content": "Pairing tomatoes with basil reduces pest pressure on the fruit.",
                "fixture_expected": "LINK_RELATED",
                "classification": "OVERCONSTRAINED_EXPECTATION",
                "a35_actual": "KEEP",
                "valid_options": ["KEEP"],
                "notes": (
                    "Distinct proposition. KEEP is correct. A relation may be added in "
                    "r[] independently. LINK_RELATED was a fixture preference, not a "
                    "contract requirement."
                ),
            },
            {
                "id": "REPETITION_NODE",
                "fixture_expected": "present",
                "classification": "OVERCONSTRAINED_EXPECTATION",
                "a35_actual": "absent",
                "notes": "Optional enrichment. Compost pair is MERGE, not recap.",
            },
            {
                "id": "UNCERTAINTY_U1",
                "classification": "REQUIRED_BY_CONTRACT",
                "notes": "Frost uncertainty must remain uncertainty.",
            },
            {
                "id": "EXAMPLES",
                "classification": "REQUIRED_BY_CONTRACT",
                "notes": "Examples remain examples; not promoted to IDEA.",
            },
            {
                "id": "REFERENCE_F1",
                "classification": "ONE_VALID_OPTION",
                "notes": "Partial almanac reference should survive as REFERENCE.",
            },
            {
                "id": "GLOBAL_FIELDS",
                "classification": "REQUIRED_BY_CONTRACT",
                "notes": "theme, intent, audience, voice must be non-empty.",
            },
        ],
        "actual_semantic_errors": [
            "None beyond the DROP reason-code contract miss. Companion-planting KEEP "
            "and missing REPETITION are not semantic errors under the frozen meanings."
        ],
        "fixture_expectation_mismatches": [
            "SYN002:I2 expected LINK_RELATED",
            "REPETITION node expected present",
        ],
        "a35_remains_fail": True,
    }


def root_causes() -> list[str]:
    return [
        "PROMPT_MACHINE_ENUM_AMBIGUITY",
        "SCHEMA_UNDERCONSTRAINED",
        "DISPOSITION_MODEL_OVERLOADED",
        "FIXTURE_EXPECTATION_OVERCONSTRAINED",
    ]


def redesign_decision() -> dict[str, Any]:
    return {
        "smallest_change": True,
        "old_transport_preserved": OLD_TRANSPORT_VERSION,
        "next_transport": "global-consolidation-transport-1.1",
        "old_prompt_preserved": OLD_PROMPT_VERSION,
        "next_prompt": "global-consolidation-1.0.1",
        "drop_reason": "unconditional enum including none",
        "representation_ops": list(REPRESENTATION_OPS),
        "link_related_retired": True,
        "relations_remain_independent_objects": True,
        "relation_policy": "C — NON-AUTHORITATIVE HINTS",
        "relation_quality_technical_debt": "YES",
        "idea_kind": "",
        "thinking": "disabled",
        "model": "claude-sonnet-5",
        "production_max_output": 32000,
        "one_global_call": "PRESERVED",
        "new_grammar_canary_required": True,
        "heuristic_normalization": False,
        "provider_response_repair": False,
        "selected_model": SELECTED_DISPOSITION_MODEL,
        "root_causes": root_causes(),
    }


__all__ = [
    "classify_a35_failures",
    "disposition_semantics",
    "drop_contract_analysis",
    "fixture_expectation_review",
    "redesign_decision",
    "repetition_policy",
    "root_causes",
]
