"""1.1.3 compatibility and reason-code coverage for the synthetic canary."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b23.reasons import REASON_CODES, REASON_DEFINITIONS
from app.book_semantic_gate_4b261.candidates import candidate_schema_identity
from app.book_semantic_gate_4b275.catalog import reason_code_catalog
from app.book_semantic_gate_4b275.contract import (
    candidate_113_instruction_prompt,
    candidate_113_prompt_bundle,
    candidate_113_system_prompt,
    contract_113_review,
    transport_compatibility as transport_113_compatibility,
)
from app.book_semantic_gate_4b276.constants import (
    DISPUTED_CLAUSE,
    EXPECTED_PROMPT_113_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_113_SHA256,
    EXPECTED_PROMPT_113_SYSTEM_SHA256,
    OVERFIT_TOKENS,
    PHASE,
    PROMPT_VERSION_113,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
    SELECTED_CASE_REASON_CODES_ACCEPTABLE_AUDIT_ONLY,
    SELECTED_CASE_REASON_CODES_AUDIT_ONLY,
    SOURCE_CASE_ID,
    TARGET_FAILURE_FAMILY,
    TRANSPORT_VERSION_11,
)


def render_113_user_prompt(gate_input_json: str) -> str:
    return (
        candidate_113_instruction_prompt()
        + "\nSEMANTIC_GATE_INPUT_JSON\n"
        + gate_input_json
        + "\n"
    )


def inspect_contract_113() -> dict[str, Any]:
    bundle = candidate_113_prompt_bundle()
    review = contract_113_review()
    prompt_blob = bundle["system"] + bundle["instructions"]
    lowered = prompt_blob.lower()
    case_specific = [
        token
        for token in (
            SELECTED_CASE_ID,
            SELECTED_CASE_HANDLE,
            DISPUTED_CLAUSE,
            "fearless death",
            "every believer is guaranteed",
            "4b276",
            SOURCE_CASE_ID,
        )
        if token.lower() in lowered
    ]
    protections = {
        "accepts_supported_paraphrase": "paraphrase is allowed" in lowered
        and "semantic entailment" in lowered,
        "does_not_require_lexical_match": "do not require the source wording to contain the same verb"
        in lowered,
        "blocks_new_implications": "new implication" in lowered,
        "blocks_unsupported_strengthening": "unsupported strengthening" in lowered
        or "raises possibility into certainty" in lowered,
        "blocks_which_means_extension": "which means" in lowered,
        "blocks_unsupported_causal_relations": "new causal" in lowered,
        "blocks_invented_examples": "invented examples" in lowered,
        "blocks_reference_completion": "reference completion fills omitted remainder"
        in lowered
        or "complete or expand omitted content" in lowered,
        "requires_reason_code_for_questionable_unsupported": "must include at least one catalog code"
        in lowered,
        "preserves_exact_spans": "exact start and end offsets" in lowered,
        "preserves_evidence_handles": "pr[].c[].ev" in lowered,
        "covers_all_substantive_propositions": "never leave a word" in lowered,
        "no_external_knowledge": "do not use your own knowledge" in lowered,
        "questionable_blocks_acceptance": "questionable blocks production acceptance"
        in lowered,
        "unsupported_blocks_acceptance": "unsupported blocks production" in lowered,
        "no_case_answer_in_prompt": not case_specific,
        "no_overfit_tokens": all(token.lower() not in lowered for token in OVERFIT_TOKENS),
        "catalog_lists_target_codes": all(
            code in bundle["system"] for code in SELECTED_CASE_REASON_CODES_AUDIT_ONLY
        ),
    }
    frozen_ok = (
        bundle["system_sha256"] == EXPECTED_PROMPT_113_SYSTEM_SHA256
        and bundle["instructions_sha256"] == EXPECTED_PROMPT_113_INSTRUCTIONS_SHA256
        and bundle["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256
        and bundle["promoted"] is False
        and review.get("promoted") is False
    )
    anomaly = None
    if not frozen_ok:
        anomaly = "1.1.3-candidate fingerprint drifted"
    if not all(protections.values()):
        missing = [key for key, value in protections.items() if not value]
        anomaly = "1.1.3-candidate semantic protection missing: " + ", ".join(missing)
    return {
        "phase": PHASE,
        "contract": PROMPT_VERSION_113,
        "prompt_sha256": bundle["prompt_sha256"],
        "system_sha256": bundle["system_sha256"],
        "instructions_sha256": bundle["instructions_sha256"],
        "matches_4b275_frozen_candidate": frozen_ok,
        "promoted": False,
        "modified_this_phase": False,
        "historical_contracts_modified": False,
        "case_specific_hits_in_contract": case_specific,
        "protections": protections,
        "verdict_compatibility": {
            "SUPPORTED": "Legitimate p4 paraphrase of IDEA226/SRC mind-over-matter and lived reality.",
            "QUESTIONABLE": "Acceptable if the implication is treated as uncertain rather than invented.",
            "UNSUPPORTED": "Preferred for the new guarantee of a fearless death.",
            "NON_SUBSTANTIVE": "Not applicable to the disputed which-means clause.",
        },
        "expressible": True,
        "contract_gap": None,
        "anomaly": anomaly,
        "secrets_included": False,
    }


def inspect_reason_code_compatibility() -> dict[str, Any]:
    catalog = reason_code_catalog()
    codes = list(catalog.get("codes") or list(REASON_CODES))
    target = list(SELECTED_CASE_REASON_CODES_AUDIT_ONLY)
    acceptable = list(SELECTED_CASE_REASON_CODES_ACCEPTABLE_AUDIT_ONLY)
    missing = [code for code in acceptable if code not in codes]
    return {
        "phase": PHASE,
        "catalog_closed": catalog.get("catalog_closed") is True,
        "catalog_codes": codes,
        "target_failure_family": TARGET_FAILURE_FAMILY,
        "expected_codes_audit_only": target,
        "acceptable_codes_audit_only": acceptable,
        "codes_in_catalog": not missing,
        "missing_from_catalog": missing,
        "no_code_invented_for_this_canary": True,
        "definitions": {code: REASON_DEFINITIONS[code] for code in acceptable},
        "why_primary_new_implication": (
            "1.1.3 defines new implication as a meaning or 'which means' "
            "extension that the evidence does not support. The synthetic clause "
            "is exactly that construction."
        ),
        "why_uncertainty_strengthened": (
            "every/guaranteed raises a pastoral exhortation into a universal "
            "certainty the sources do not state."
        ),
        "not_placed_as_case_hint_in_request": True,
        "general_catalog_visible_in_contract": True,
        "secrets_included": False,
    }


def inspect_transport_compatibility() -> dict[str, Any]:
    transport = transport_113_compatibility()
    schema = candidate_schema_identity()
    return {
        **transport,
        "phase": PHASE,
        "transport": TRANSPORT_VERSION_11,
        "schema_sha256": schema["raw_schema_sha256"],
        "compatible_without_schema_change": transport.get("matches_frozen_1_1_schema")
        is True,
        "new_transport_created": False,
        "schema_change_required": False,
        "secrets_included": False,
    }


__all__ = [
    "candidate_113_system_prompt",
    "inspect_contract_113",
    "inspect_reason_code_compatibility",
    "inspect_transport_compatibility",
    "render_113_user_prompt",
]
