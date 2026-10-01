"""Classification des causes A.40 et plus petit durcissement. 0 provider."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v31_global_drop_domain.constants import (
    FIELD_RENAME_ADOPTED,
    NEXT_PROMPT_VERSION,
    NEXT_TRANSPORT_VERSION,
    OLD_PROMPT_VERSION,
    OLD_TRANSPORT_VERSION,
    SCHEMA_CHANGED,
    SCHEMA_PATTERN_ADOPTED,
    SELECTED_HARDENING,
    V20_SCHEMA_ADAPTED_BYTES,
    V20_SCHEMA_HASH,
    V20_SCHEMA_RAW_BYTES,
)
from app.source_analysis_v31_global_output_architecture.prompt_v20 import (
    INSTRUCTIONS,
    SYSTEM_PROMPT,
)
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    build_global_consolidation_schema_v20,
)
from app.source_analysis_v31_global_v20_grammar_canary.handles import (
    inspect_global_handles_v20,
)


def evaluate_root_causes(*, fixture_has_relation: bool) -> dict[str, Any]:
    schema = build_global_consolidation_schema_v20()
    drop_schema = ((schema.get("properties") or {}).get("drop") or {})
    drop_id_schema = (
        ((drop_schema.get("items") or {}).get("properties") or {}).get("i") or {}
    )
    prompt = SYSTEM_PROMPT + "\n" + INSTRUCTIONS
    prompt_says_idea_absent = "a local IDEA absent from every global idea must appear in drop[]"
    prompt_says_every_idea = "Every local IDEA input id must appear in exactly one of"
    prompt_forbids_non_idea_drop = "LOCAL IDEA HANDLES ONLY" in prompt or (
        "Never place TOPIC" in prompt
    )
    prompt_drop_line = "drop[]: only true transport artifacts or non-substantive fragments"
    return {
        "PROMPT_DOMAIN_AMBIGUITY": {
            "applies": True,
            "evidence": [
                prompt_says_idea_absent,
                prompt_says_every_idea,
                prompt_drop_line,
                "Local RELATION rows are non-authoritative hints. Do not emit r[].",
                "Prompt never says drop[] rejects TOPIC/RELATION/EXAMPLE/REFERENCE/UNCERTAINTY.",
                "Generic drop[] line can be read as 'non-surviving local records'.",
            ],
            "explicit_idea_only_ban": prompt_forbids_non_idea_drop,
        },
        "SCHEMA_DOMAIN_UNDERCONSTRAINED": {
            "applies": True,
            "evidence": [
                "drop.i type=string with no enum, pattern, or const",
                drop_id_schema,
                "Runtime local IDs cannot be enumerated in static schema.",
            ],
        },
        "TRANSPORT_FIELD_NAMING_AMBIGUITY": {
            "applies": True,
            "severity": "secondary",
            "evidence": [
                "Field name drop is generic; schema comment says dropped local IDEA input ID.",
                "Provider never sees Python field_meanings; only prompt+schema.",
            ],
            "rename_adopted": FIELD_RENAME_ADOPTED,
        },
        "FIXTURE_PRESENTED_IRRELEVANT_LOCAL_OBJECT_AS_DROP_CANDIDATE": {
            "applies": fixture_has_relation,
            "evidence": [
                "A.40 fixture includes SYN:L001 RELATION in compact input.",
                "Correct: next canary must keep a local relation to prove omission is valid.",
                "Incorrect: treating the relation as a drop candidate.",
            ],
        },
        "VALIDATOR_ONLY_TYPE_RESTRICTION": {
            "applies": True,
            "evidence": [
                "validate_global_transport_v20 already rejects non-IDEA drop IDs.",
                "inspect_global_handles_v20 does not inspect drop[].",
                "Decoder accepts any drop.i string if fields i,w present.",
            ],
        },
        "not_root": [
            "grammar rejection",
            "JSON corruption",
            "max_tokens",
            "thinking",
            "membership failure of local IDEAs",
            "SRC derivation failure",
            "canonical reconstruction failure",
        ],
    }


def schema_pattern_analysis() -> dict[str, Any]:
    return {
        "can_enum_runtime_ids": False,
        "reason_enum_impossible": (
            "Local IDs are runtime values (WIN001:I012, SYN:I001). "
            "Static schema cannot list them."
        ),
        "anthropic_pattern_supported": (
            "pattern is not in the repository unsupported-keyword list "
            "(if/then/else, dependent*, oneOf/anyOf/allOf, $ref). "
            "minLength/maxLength are stripped. pattern is not used in transport 2.0."
        ),
        "candidate_pattern": r"^[^:]+:I[0-9]+$",
        "candidate_would_match": ["SYN:I001", "SYN001:I12"],
        "candidate_would_reject": ["SYN:L001", "SYN:T001", "SYN:E001"],
        "why_not_adopted": [
            "Changes schema bytes/hash → new grammar canary for a heuristic.",
            "Authoritative kind is local k, not ID spelling.",
            "Validator already has exact kind_by_input lookup.",
            "Smallest unambiguous fix is prompt + decoder/handle/publication gates.",
        ],
        "adopted": SCHEMA_PATTERN_ADOPTED,
        "schema_changed": SCHEMA_CHANGED,
        "next_schema_raw_adapted_hash": [
            V20_SCHEMA_RAW_BYTES,
            V20_SCHEMA_ADAPTED_BYTES,
            V20_SCHEMA_HASH,
        ],
    }


def field_rename_analysis() -> dict[str, Any]:
    return {
        "current": "drop",
        "alternatives": ["idea_drop", "dropped_ideas", "excluded_ideas"],
        "too_broad": True,
        "adopted": FIELD_RENAME_ADOPTED,
        "why_not": (
            "Renaming changes the wire shape and requires transport 2.1. "
            "Prompt 2.0.1 can bind drop[] to IDEA handles without a schema change."
        ),
    }


def validation_order_review() -> dict[str, Any]:
    return {
        "actual_a40_order": [
            "structured parse (schema)",
            "transport decode (shape; drop[] fields only)",
            "handle validation (owners + membership/satellite locals; NOT drop[])",
            "membership audit (IDEA set vs drop ids, unknown_drops)",
            "derived dispositions",
            "derived SRC",
            "global validator (includes IDEA-only drop domain)",
            "canonical reconstruction",
            "canonical validation",
            "semantic fixture review",
        ],
        "preferred_future_order": [
            "structured parse",
            "transport decode",
            "handle/type validation including drop domain",
            "IDEA membership/drop domain validation",
            "IDEA accountability",
            "derived SRC",
            "global semantic validation",
            "canonical reconstruction",
            "canonical validation",
        ],
        "handle_inspector_skips_drop": True,
        "reconstruction_ignores_drop": True,
        "reconstruction_why_passed": (
            "compact_to_source_map_payload walks i[], t[], x[], f[], u[] only. "
            "drop[] is not reconstructed into the SourceMap. SYN:L001 therefore "
            "cannot become a canonical IDEA. Accountability for reconstruction "
            "is membership of i[].m, not drop[]. Invalid relation drop is ignored, "
            "which is why reconstruction can PASS while the global validator FAILs."
        ),
    }


def smallest_hardening_decision() -> dict[str, Any]:
    return {
        "selected": SELECTED_HARDENING,
        "old_prompt": OLD_PROMPT_VERSION,
        "next_prompt": NEXT_PROMPT_VERSION,
        "old_transport": OLD_TRANSPORT_VERSION,
        "next_transport": NEXT_TRANSPORT_VERSION,
        "schema_changed": SCHEMA_CHANGED,
        "prompt_versioned_because": (
            "Wording change makes the provider contract materially clearer: "
            "drop[] is local IDEA handles only; relation hints need no disposition."
        ),
        "transport_not_versioned_because": (
            "Wire keys, drop reasons, and schema bytes stay 2.0. "
            "Field is still drop. No pattern added."
        ),
        "code_hardening": [
            "Next-contract handle inspector inspects drop[].i kinds.",
            "Publication eligibility requires global validator PASS.",
            "Invalid transport cannot become publishable even if reconstruction succeeds.",
        ],
        "not_selected": [
            "schema pattern on drop.i",
            "rename drop → idea_drop",
            "universal disposition ledger for 623 records",
            "mutate global-consolidation-2.0 bytes",
        ],
        "new_grammar_canary_required": False,
        "second_compact_contract_canary_required": True,
        "a40_grammar_proof_scope": "exact schema 2.0 only",
    }


def inspect_handles_including_drop(
    payload: dict[str, Any] | None,
    *,
    allowed_input_ids: set[str],
    kind_by_input: dict[str, str],
) -> dict[str, Any]:
    base = inspect_global_handles_v20(
        payload,
        allowed_input_ids=allowed_input_ids,
        kind_by_input=kind_by_input,
    )
    drop_wrong: list[str] = []
    drop_unknown: list[str] = []
    if isinstance(payload, dict):
        for index, row in enumerate(payload.get("drop") or []):
            if not isinstance(row, dict):
                continue
            local_id = str(row.get("i") or "")
            if local_id not in allowed_input_ids:
                drop_unknown.append(f"drop[{index}]:{local_id}")
                continue
            kind = kind_by_input.get(local_id)
            if kind != "IDEA":
                drop_wrong.append(f"drop[{index}]:{local_id}->{kind}")
    violations = int(base.get("root_violations") or 0) + len(drop_wrong) + len(drop_unknown)
    result = dict(base)
    result["drop_wrong_kind"] = drop_wrong
    result["drop_unknown"] = drop_unknown
    result["root_violations"] = violations
    result["handle_validation"] = "PASS" if violations == 0 else "FAIL"
    result["drop_domain_inspected"] = True
    return result


__all__ = [
    "evaluate_root_causes",
    "field_rename_analysis",
    "inspect_handles_including_drop",
    "schema_pattern_analysis",
    "smallest_hardening_decision",
    "validation_order_review",
]
