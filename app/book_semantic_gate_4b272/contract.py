"""Inspect 1.1.1-candidate and 1.1-candidate transport for P3. Do not mutate frozen versions."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b261.candidates import (
    build_candidate_schema,
    candidate_prompt_bundle,
    candidate_schema_identity,
)
from app.book_semantic_gate_4b262.contract import (
    OFFSET_CONVENTION,
    REQUIRED_CLAIM_FIELDS,
    REQUIRED_PARAGRAPH_FIELDS,
    REQUIRED_TOP_FIELDS,
    compact_semantic_invariants,
)
from app.book_semantic_gate_4b271.calibration import (
    calibration_candidate,
    candidate_111_prompt_bundle,
    contract_comparison,
    overfit_tokens_absent,
)
from app.book_semantic_gate_4b272.constants import (
    DISPUTED_CAUSAL_CLAUSE,
    EXPECTED_PROMPT_111_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_111_SYSTEM_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_SCHEMA_11_SHA256,
    H01_EXCLUSION_TOKENS,
    PHASE,
    PROMPT_VERSION_111,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
    TRANSPORT_VERSION_11,
    TRANSPORT_VERSION_111,
)
from app.file_utils import content_hash
import json


def render_111_user_prompt(gate_input_json: str) -> str:
    from app.book_semantic_gate_4b271.calibration import candidate_111_instruction_prompt

    return (
        candidate_111_instruction_prompt()
        + "\nSEMANTIC_GATE_INPUT_JSON\n"
        + gate_input_json
        + "\n"
    )


def inspect_contract_111() -> dict[str, Any]:
    bundle = candidate_111_prompt_bundle()
    comparison = contract_comparison()
    calibration = calibration_candidate()
    schema = build_candidate_schema()
    schema_sha = content_hash(json.dumps(schema, ensure_ascii=False, sort_keys=True))
    prompt_blob = bundle["system"] + bundle["instructions"]
    lowered = prompt_blob.lower()
    p3_specific = [
        token
        for token in (
            SELECTED_CASE_ID,
            SELECTED_CASE_HANDLE,
            DISPUTED_CAUSAL_CLAUSE,
            "4b22_p3",
            "invented causality in p3",
        )
        if token.lower() in lowered
    ]
    protections = {
        "accepts_supported_paraphrase": "paraphrase is allowed" in lowered
        and "semantic entailment" in lowered,
        "does_not_require_lexical_match": "do not require the source wording to contain the same verb"
        in lowered,
        "blocks_unsupported_causal_relations": "new causal" in lowered
        and "because" in lowered,
        "blocks_new_implications": "new implications" in lowered or "new implication" in lowered,
        "blocks_invented_examples": "invented examples" in lowered,
        "blocks_reference_completion": "complete or expand" in lowered
        or "completion or expansion of partial references" in lowered,
        "requires_reason_code_for_questionable_unsupported": "must include at least one reason code"
        in lowered,
        "preserves_exact_spans": "exact start and end offsets" in lowered,
        "preserves_evidence_handles": "evidence handles" in lowered or "pr[].c[].ev" in lowered,
        "covers_all_substantive_propositions": "never leave a word" in lowered
        and "connective" in lowered
        and "clause" in lowered,
        "no_external_knowledge": "do not use your own knowledge" in lowered,
        "no_p3_answer_in_prompt": not p3_specific,
        "no_h01_overfit": overfit_tokens_absent(prompt_blob)
        and all(token.lower() not in lowered for token in H01_EXCLUSION_TOKENS if token != "h01"),
    }
    frozen_ok = (
        bundle["system_sha256"] == EXPECTED_PROMPT_111_SYSTEM_SHA256
        and bundle["instructions_sha256"] == EXPECTED_PROMPT_111_INSTRUCTIONS_SHA256
        and bundle["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256
        and bundle["promoted"] is False
        and comparison.get("historical_contracts_modified") is False
    )
    anomaly = None
    if not frozen_ok:
        anomaly = "1.1.1-candidate fingerprint drifted"
    if not all(protections.values()):
        anomaly = "1.1.1-candidate semantic protection missing"
    return {
        "phase": PHASE,
        "contract": PROMPT_VERSION_111,
        "prompt_sha256": bundle["prompt_sha256"],
        "system_sha256": bundle["system_sha256"],
        "instructions_sha256": bundle["instructions_sha256"],
        "matches_4b271_frozen_candidate": frozen_ok,
        "promoted": False,
        "historical_1_0_unmodified": True,
        "candidate_1_1_unmodified": candidate_prompt_bundle()["prompt_sha256"]
        == EXPECTED_PROMPT_11_SHA256,
        "schema_sha256": schema_sha,
        "schema_unchanged_from_1_1": schema_sha == EXPECTED_SCHEMA_11_SHA256,
        "protections": protections,
        "p3_specific_instruction_in_prompt": p3_specific,
        "calibration_from_4b271": {
            "transport_1_1_1_created": calibration.get("transport_1_1_1_created"),
            "why_no_new_transport": calibration.get("why_no_new_transport"),
        },
        "comparison": comparison["versions"]["1.1.1-candidate"],
        "anomaly": anomaly,
        "blocker": anomaly,
        "distinct_candidate_proposed": None,
        "secrets_included": False,
    }


def inspect_transport_compatibility() -> dict[str, Any]:
    schema = candidate_schema_identity()
    claim_props = set(
        ((build_candidate_schema().get("$defs") or {}).get("claim") or {})
        .get("properties")
        or {}
    )
    needed = {"i", "s", "e", "k", "ev", "r", "n"}
    schema_change_required = not needed.issubset(claim_props)
    return {
        "phase": PHASE,
        "transport": TRANSPORT_VERSION_11,
        "transport_1_1_1": TRANSPORT_VERSION_111,
        "new_transport_created": False,
        "schema_change_required": schema_change_required,
        "stop_before_freeze_if_schema_change": schema_change_required,
        "compact_json": True,
        "fields": {
            "case_identifiers": "pr[].h opaque handle",
            "paragraph_identifiers": "pr[].h",
            "verdicts": "v / pr[].v / pr[].c[].k",
            "spans": "pr[].c[].s / pr[].c[].e",
            "evidence_handles": "pr[].c[].ev / pr[].ev",
            "reason_codes": "pr[].c[].r",
            "short_reservations": "pr[].c[].n",
        },
        "required_claim_fields": list(REQUIRED_CLAIM_FIELDS),
        "required_paragraph_fields": list(REQUIRED_PARAGRAPH_FIELDS),
        "required_top_fields": list(REQUIRED_TOP_FIELDS),
        "offset_convention": dict(OFFSET_CONVENTION),
        "deterministic_validation": True,
        "separator_policy": "1.1.1 local validator allows sentence-final .?! after a covered span",
        "schema_sha256": schema["raw_schema_sha256"],
        "invariants_preserved": compact_semantic_invariants()[
            "proposition_level_control_preserved"
        ],
        "compatible_without_schema_change": not schema_change_required,
        "secrets_included": False,
    }


__all__ = [
    "inspect_contract_111",
    "inspect_transport_compatibility",
    "render_111_user_prompt",
]
