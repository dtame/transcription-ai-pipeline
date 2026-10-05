"""
Finalized compact 1.1-candidate contract.

Reuses the 4B.2.6.1 candidate prompts and schema. Does not mutate 1.0.
Does not promote 1.1 to production.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.claims import uncovered_spans
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b23.schema import build_semantic_validation_schema
from app.book_semantic_gate_4b24.validate import validate_semantic_response
from app.book_semantic_gate_4b261.candidates import (
    build_candidate_schema,
    candidate_instruction_prompt,
    candidate_prompt_bundle,
    candidate_schema_identity,
    candidate_system_prompt,
    compact_claim,
    expand_candidate_to_historical,
    recover_claim_text,
    render_candidate_user_prompt,
)
from app.book_semantic_gate_4b262.constants import (
    CANDIDATE_PROMPT_VERSION,
    CANDIDATE_TRANSPORT_VERSION,
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    CLASSIFICATIONS,
    PHASE,
    PROMPT_VERSION_HISTORICAL,
    TRANSPORT_VERSION_HISTORICAL,
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_REVIEW,
)

OFFSET_CONVENTION = {
    "indexing": "python3_str_unicode_code_points",
    "interval": "half_open",
    "start_inclusive": True,
    "end_exclusive": True,
    "not_utf8_bytes": True,
    "not_utf16_code_units": True,
    "combining_characters_are_separate_code_points": True,
    "empty_span_invalid": True,
    "inconsistent_span_invalid": True,
    "out_of_bounds_invalid": True,
    "valid_offset_is_not_semantic_support": True,
    "recovery": "paragraph_text[start:end]",
    "documentation": (
        "Offsets are Python 3 str indices. text[s:e] recovers the evaluated "
        "span. A well-formed span identifies the evaluated passage; it does "
        "not prove the passage is supported by canonical evidence."
    ),
}

REQUIRED_CLAIM_FIELDS = ("i", "s", "e", "k", "ev", "r")
REQUIRED_PARAGRAPH_FIELDS = ("h", "v", "c", "ev", "r")
REQUIRED_TOP_FIELDS = ("ch", "v", "pr", "sc", "uh", "rr")
DROPPED_REQUIRED_CLAIM_FIELDS = ("t", "x")
OPTIONAL_RESERVATION_FIELD = "n"


def inventory_existing_contracts() -> dict[str, Any]:
    historical_schema = build_semantic_validation_schema()
    candidate = candidate_schema_identity()
    bundle = candidate_prompt_bundle()
    return {
        "phase": PHASE,
        "implemented": {
            "book-semantic-validator-1.0": {
                "status": "IMPLEMENTED_FROZEN",
                "module": "app.book_semantic_gate_4b23.prompt",
                "sha256": bundle["historical_system_sha256"],
            },
            "book-semantic-validation-transport-1.0": {
                "status": "IMPLEMENTED_FROZEN",
                "module": "app.book_semantic_gate_4b23.schema",
                "title": historical_schema.get("title"),
                "sha256": candidate["historical_schema_sha256"],
            },
            "book-semantic-validator-1.1-candidate": {
                "status": "IMPLEMENTED_CANDIDATE_FINALIZED_HERE",
                "module": "app.book_semantic_gate_4b261.candidates",
                "sha256": bundle["prompt_sha256"],
                "promoted": False,
            },
            "book-semantic-validation-transport-1.1-candidate": {
                "status": "IMPLEMENTED_CANDIDATE_FINALIZED_HERE",
                "module": "app.book_semantic_gate_4b261.candidates",
                "sha256": candidate["raw_schema_sha256"],
                "promoted": False,
            },
            "ten_historical_benchmark_cases": {
                "status": "IMPLEMENTED_FROZEN",
                "module": "app.book_semantic_gate_4b23.benchmark",
            },
            "fakeai_and_deterministic_validation": {
                "status": "IMPLEMENTED",
                "modules": [
                    "app.book_semantic_gate_4b23.fakeai",
                    "app.book_semantic_gate_4b24.validate",
                ],
            },
            "openai_adapter": {
                "status": "IMPLEMENTED",
                "module": "app.ai.providers.openai_engine",
            },
        },
        "proposal_only_before_this_phase": {
            "single_case_h01_canary_request": "PROPOSAL_IN_4B261_NOW_FROZEN_HERE",
            "reasoning_token_telemetry_fix": "GAP_IN_4B261_NOW_IMPLEMENTED",
            "preflight_for_single_case_compact_request": "NOW_IMPLEMENTED_OFFLINE",
        },
        "not_recreated": [
            "historical 1.0 prompt and schema",
            "4B.2.6.1 candidate prompt text",
            "frozen human labels",
            "OpenAI chat.completions adapter",
        ],
        "historical_1_0_unchanged": True,
        "candidate_1_1_promoted": False,
    }


def compact_contract_specification() -> dict[str, Any]:
    bundle = candidate_prompt_bundle()
    schema = candidate_schema_identity()
    return {
        "phase": PHASE,
        "prompt_version": CANDIDATE_PROMPT_VERSION,
        "transport_version": CANDIDATE_TRANSPORT_VERSION,
        "historical_prompt_version": PROMPT_VERSION_HISTORICAL,
        "historical_transport_version": TRANSPORT_VERSION_HISTORICAL,
        "promoted": False,
        "deterministic": True,
        "prompt_sha256": bundle["prompt_sha256"],
        "system_sha256": bundle["system_sha256"],
        "instructions_sha256": bundle["instructions_sha256"],
        "schema_sha256": schema["raw_schema_sha256"],
        "identical_to_historical": False,
        "inventory": inventory_existing_contracts(),
        "kept_minimum": {
            "case_identifier": "opaque paragraph handle h",
            "paragraph_identifier": "pr[].h",
            "global_verdict": "v in {PASS, REVIEW, FAIL}",
            "proposition_coverage": "pr[].c[] spans must cover the paragraph",
            "spans": "pr[].c[].s / pr[].c[].e",
            "canonical_evidence_references": "pr[].c[].ev and pr[].ev",
            "reason_codes": "pr[].c[].r closed list",
            "short_justification": "pr[].c[].n only when QUESTIONABLE or UNSUPPORTED",
        },
        "avoided": {
            "full_claim_text_copy": "t dropped; recovered from offsets",
            "long_explanations": "x dropped",
            "narrative_reformulations": True,
            "copied_evidence_text": True,
            "redundant_confidence": "cf dropped",
        },
        "offset_convention": OFFSET_CONVENTION,
        "required_claim_fields": list(REQUIRED_CLAIM_FIELDS),
        "required_paragraph_fields": list(REQUIRED_PARAGRAPH_FIELDS),
        "required_top_fields": list(REQUIRED_TOP_FIELDS),
        "dropped_required_claim_fields": list(DROPPED_REQUIRED_CLAIM_FIELDS),
        "optional_reservation_field": OPTIONAL_RESERVATION_FIELD,
        "verdicts": list(CLASSIFICATIONS),
        "chapter_verdicts": [VERDICT_PASS, VERDICT_REVIEW, VERDICT_FAIL],
        "reason_codes": list(REASON_CODES),
        "json_object_server_capability": "UNKNOWN_SERVER_SIDE",
        "native_json_schema_sent": False,
        "secrets_included": False,
    }


def compact_semantic_invariants() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "proposition_level_control_preserved": True,
        "do_not_drop_claim_coverage_to_save_tokens": True,
        "classifications": {
            CLASS_SUPPORTED: "accepted for a substantive claim",
            CLASS_QUESTIONABLE: "blocks paragraph acceptance",
            CLASS_UNSUPPORTED: "blocks paragraph acceptance",
            CLASS_NON_SUBSTANTIVE: (
                "forbidden as an escape hatch for a substantive claim that "
                "was not evaluated"
            ),
        },
        "unevaluated_substantive_claim_blocks_acceptance": True,
        "valid_offset_is_not_semantic_support": True,
        "canonical_reference_authorizes_only_supplied_text": True,
        "biblical_reference_identity_does_not_license_completion": True,
        "external_model_knowledge_is_not_evidence": True,
        "human_labels_never_enter_provider_request": True,
        "negative_cases_remain_detectable": {
            "FUNERAL": "invented example",
            "CONNECTIVE": "new argument, conclusion, or implication",
            "P3": "added causal relation in a secondary clause",
            "P8": "abusive completion of a partial 1 Corinthians 15 reference",
        },
        "compact_contract_must_identify_a_problematic_clause_inside_an_otherwise_supported_paragraph": True,
        "historical_labels_unmodified": True,
        "historical_1_0_unmodified": True,
        "candidate_not_promoted": True,
        "secrets_included": False,
    }


def validate_compact_span(
    text: str,
    start: Any,
    end: Any,
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(start, int) or isinstance(start, bool):
        errors.append("start_not_int")
    if not isinstance(end, int) or isinstance(end, bool):
        errors.append("end_not_int")
    if errors:
        return {
            "valid": False,
            "errors": errors,
            "recovered_text": "",
            "empty": True,
            "convention": OFFSET_CONVENTION["indexing"],
        }
    if start < 0:
        errors.append("start_negative")
    if end < start:
        errors.append("end_before_start")
    if start > len(text):
        errors.append("start_out_of_bounds")
    if end > len(text):
        errors.append("end_out_of_bounds")
    if start == end:
        errors.append("empty_span")
    recovered = ""
    if start >= 0 and end >= start and end <= len(text):
        recovered = text[start:end]
        if recovered == "" and start != end:
            errors.append("empty_after_slice")
    return {
        "valid": not errors,
        "errors": errors,
        "recovered_text": recovered,
        "empty": recovered == "",
        "start": start,
        "end": end,
        "text_code_points": len(text),
        "span_code_points": len(recovered),
        "convention": OFFSET_CONVENTION["indexing"],
        "valid_offset_is_not_semantic_support": True,
    }


def validate_compact_payload(
    payload: Mapping[str, Any] | None,
    *,
    paragraph_texts: Mapping[str, str],
    required_handles: Sequence[str],
    paragraph_kinds: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return {
            "status": "FAIL",
            "json_parse": "FAIL",
            "errors": ["payload_missing"],
            "missing_handles": list(required_handles),
            "acceptance_blocked": True,
        }
    for field in REQUIRED_TOP_FIELDS:
        if field not in payload:
            errors.append(f"missing_top_{field}")
    kinds = paragraph_kinds or {}
    span_errors: list[str] = []
    coverage_errors: list[str] = []
    claim_errors: list[str] = []
    returned: list[str] = []
    for para in payload.get("pr") or []:
        handle = str(para.get("h") or "")
        returned.append(handle)
        for field in REQUIRED_PARAGRAPH_FIELDS:
            if field not in para:
                errors.append(f"{handle}: missing_{field}")
        text = str(paragraph_texts.get(handle) or "")
        claims = list(para.get("c") or [])
        if not claims:
            coverage_errors.append(f"{handle}: no_claims")
            continue
        historical_claims: list[dict[str, Any]] = []
        substantive_evaluated = False
        for claim in claims:
            for field in REQUIRED_CLAIM_FIELDS:
                if field not in claim:
                    claim_errors.append(f"{handle}: missing_claim_{field}")
            kind = str(claim.get("k") or "")
            if kind not in CLASSIFICATIONS:
                claim_errors.append(f"{handle}: invalid_class_{kind}")
            if kind in {CLASS_SUPPORTED, CLASS_QUESTIONABLE, CLASS_UNSUPPORTED}:
                substantive_evaluated = True
            if kind == CLASS_NON_SUBSTANTIVE and kinds.get(handle) == "substantive":
                if len(claims) == 1:
                    claim_errors.append(
                        f"{handle}: non_substantive_escape_hatch_on_substantive"
                    )
            note = claim.get("n")
            if kind in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED} and not str(note or "").strip():
                claim_errors.append(f"{handle}: reservation_required")
            if kind in {CLASS_SUPPORTED, CLASS_NON_SUBSTANTIVE} and note:
                claim_errors.append(f"{handle}: reservation_forbidden")
            reasons = list(claim.get("r") or [])
            for code in reasons:
                if code not in REASON_CODES:
                    claim_errors.append(f"{handle}: unknown_reason_{code}")
            if kind in {CLASS_SUPPORTED, CLASS_NON_SUBSTANTIVE} and reasons:
                claim_errors.append(f"{handle}: reasons_forbidden_for_{kind}")
            span = validate_compact_span(text, claim.get("s"), claim.get("e"))
            if not span["valid"]:
                span_errors.append(f"{handle}: {','.join(span['errors'])}")
            historical_claims.append(
                {
                    "start_offset": claim.get("s"),
                    "end_offset": claim.get("e"),
                    "claim_text": recover_claim_text(
                        text, int(claim.get("s") or 0), int(claim.get("e") or 0)
                    ),
                    "classification": kind,
                }
            )
        if text:
            gaps = uncovered_spans(text, historical_claims)
            if gaps:
                coverage_errors.append(f"{handle}: coverage_gap_{gaps}")
        if kinds.get(handle) == "substantive" and not substantive_evaluated:
            claim_errors.append(f"{handle}: substantive_unevaluated")
    missing = [handle for handle in required_handles if handle not in returned]
    if missing:
        coverage_errors.append(f"missing_handles:{missing}")
    expanded = expand_candidate_to_historical(payload, paragraph_texts=paragraph_texts)
    historical = validate_semantic_response(
        expanded,
        required_handles=required_handles,
        paragraph_texts=paragraph_texts,
    )
    all_errors = errors + span_errors + coverage_errors + claim_errors
    status = "PASS" if not all_errors else "FAIL"
    return {
        "status": status,
        "json_parse": "PASS",
        "errors": all_errors,
        "span_errors": span_errors,
        "coverage_errors": coverage_errors,
        "claim_errors": claim_errors,
        "missing_handles": missing,
        "returned_handles": returned,
        "historical_validation": {
            "json_parse": historical.get("json_parse"),
            "case_coverage": historical.get("case_coverage"),
            "span_validation": historical.get("span_validation"),
            "acceptance_blocked": historical.get("acceptance", {}).get("cache_acceptance")
            is False,
        },
        "proposition_level_control_preserved": True,
        "acceptance_blocked_if_fail": status != "PASS",
        "offset_convention": OFFSET_CONVENTION,
    }


def unnecessary_duplication_absent(payload: Mapping[str, Any]) -> bool:
    for para in payload.get("pr") or []:
        for claim in para.get("c") or []:
            if "t" in claim or "x" in claim or "cf" in claim:
                return False
    return True


__all__ = [
    "OFFSET_CONVENTION",
    "compact_claim",
    "compact_contract_specification",
    "compact_semantic_invariants",
    "candidate_instruction_prompt",
    "candidate_prompt_bundle",
    "candidate_schema_identity",
    "candidate_system_prompt",
    "expand_candidate_to_historical",
    "inventory_existing_contracts",
    "recover_claim_text",
    "render_candidate_user_prompt",
    "unnecessary_duplication_absent",
    "validate_compact_payload",
    "validate_compact_span",
]
