"""Independent P3 semantic review. Human labels stay local and are never sent to Terra."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b261.candidates import recover_claim_text
from app.book_semantic_gate_4b262.contract import validate_compact_span
from app.book_semantic_gate_4b272.coverage import p3_local_propositions
from app.book_semantic_gate_4b272.identity import clause_offsets
from app.book_semantic_gate_4b273.constants import (
    ACCEPTING_VERDICTS,
    BLOCKING_VERDICTS,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    DISPUTED_CAUSAL_CLAUSE,
    EXPECTED_CLAUSE_END,
    EXPECTED_CLAUSE_START,
    PHASE,
    RELEVANT_REASON_CODES,
    SELECTED_CASE_ACCEPTED_CLASSES,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    VERDICT_PASS,
    VERDICT_REVIEW,
)


def _terra_global_verdict(payload: Mapping[str, Any] | None) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    top = str(payload.get("v") or "") or None
    paragraph = None
    for para in payload.get("pr") or []:
        if str(para.get("h") or "") == SELECTED_CASE_HANDLE:
            paragraph = str(para.get("v") or "") or None
            break
    return paragraph or top


def _overlaps(start: int, end: int, clause_start: int, clause_end: int) -> bool:
    return start < clause_end and end > clause_start


def _blocks_acceptance(verdict: str | None) -> bool:
    if not verdict:
        return False
    if verdict in ACCEPTING_VERDICTS:
        return False
    return verdict in BLOCKING_VERDICTS or verdict in {
        CLASS_QUESTIONABLE,
        CLASS_UNSUPPORTED,
        VERDICT_REVIEW,
    }


def review_p3_semantic_response(
    payload: Mapping[str, Any] | None,
    *,
    paragraph_text: str,
    allowed_handles: Sequence[str],
    contract_status: str,
    coverage_ok: bool,
    spans_ok: bool,
) -> dict[str, Any]:
    allowed = {str(item) for item in allowed_handles if item}
    offsets = clause_offsets(paragraph_text)
    clause_start = int(offsets.get("start") or EXPECTED_CLAUSE_START)
    clause_end = int(offsets.get("end") or EXPECTED_CLAUSE_END)
    terra = _terra_global_verdict(payload)
    claims: list[dict[str, Any]] = []
    cited: list[str] = []
    notes: list[str] = []
    invalid_refs: list[str] = []
    overlapping: list[dict[str, Any]] = []
    if isinstance(payload, Mapping):
        for para in payload.get("pr") or []:
            if str(para.get("h") or "") != SELECTED_CASE_HANDLE:
                continue
            for claim in para.get("c") or []:
                ev = [str(item) for item in (claim.get("ev") or []) if item]
                cited.extend(ev)
                for handle in ev:
                    if handle not in allowed:
                        invalid_refs.append(handle)
                start = claim.get("s")
                end = claim.get("e")
                span = validate_compact_span(paragraph_text, start, end)
                recovered = str(span.get("recovered_text") or "")
                reasons = [str(item) for item in (claim.get("r") or []) if item]
                unknown_reasons = [code for code in reasons if code not in REASON_CODES]
                note = str(claim.get("n") or "")
                if note:
                    notes.append(note)
                kind = str(claim.get("k") or "")
                row = {
                    "index": claim.get("i"),
                    "class": kind,
                    "start": start,
                    "end": end,
                    "recovered_text": recover_claim_text(
                        paragraph_text,
                        int(start),
                        int(end),
                    )
                    if isinstance(start, int) and isinstance(end, int)
                    else recovered,
                    "evidence": ev,
                    "reasons": reasons,
                    "unknown_reasons": unknown_reasons,
                    "note": note,
                    "span_valid": span.get("valid"),
                    "overlaps_disputed_clause": (
                        isinstance(start, int)
                        and isinstance(end, int)
                        and _overlaps(start, end, clause_start, clause_end)
                    ),
                    "contains_because": "because" in recovered.lower(),
                    "contains_clause_text": DISPUTED_CAUSAL_CLAUSE in recovered,
                }
                claims.append(row)
                if row["overlaps_disputed_clause"]:
                    overlapping.append(row)

    flagged = [
        item
        for item in overlapping
        if item.get("class") in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED}
    ]
    accepted_causal = [
        item
        for item in overlapping
        if item.get("class") == CLASS_SUPPORTED
    ]
    omitted = not overlapping
    relevant_hits = sorted(
        {
            code
            for item in flagged
            for code in (item.get("reasons") or [])
            if code in RELEVANT_REASON_CODES
        }
    )
    any_reason = sorted(
        {
            code
            for item in flagged
            for code in (item.get("reasons") or [])
            if code
        }
    )
    reason_relevant = bool(relevant_hits)
    reason_present = bool(any_reason)
    clause_classes = [str(item.get("class") or "") for item in overlapping]
    disputed_verdict = None
    if flagged:
        disputed_verdict = str(flagged[0].get("class") or "") or None
    elif accepted_causal:
        disputed_verdict = CLASS_SUPPORTED
    elif overlapping:
        disputed_verdict = str(overlapping[0].get("class") or "") or None

    other_claims = [item for item in claims if not item.get("overlaps_disputed_clause")]
    other_flagged = [
        item
        for item in other_claims
        if item.get("class") in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED}
    ]
    other_supported = [
        item for item in other_claims if item.get("class") == CLASS_SUPPORTED
    ]
    unjustified_other_rejections = [
        item
        for item in other_flagged
        if not item.get("reasons") and not item.get("note")
    ]
    all_questionable = bool(claims) and all(
        item.get("class") in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED} for item in claims
    )
    discrimination = not all_questionable and (
        bool(other_supported) or (bool(flagged) and len(claims) > 1)
    )
    isolated = False
    if flagged:
        focused = flagged[0]
        start = focused.get("start")
        end = focused.get("end")
        if isinstance(start, int) and isinstance(end, int):
            isolated = (end - start) <= 180 or start >= clause_start - 40
        isolated = isolated or bool(other_supported)

    blocking = _blocks_acceptance(terra)
    accepted_wrong_clause = bool(accepted_causal) and not flagged
    wrong_target = (
        not flagged
        and bool(other_flagged)
        and (omitted or accepted_wrong_clause)
    )
    global_only = blocking and not flagged

    semantic_fail_reasons: list[str] = []
    semantic_partial_reasons: list[str] = []
    if omitted:
        semantic_fail_reasons.append("omitted_causal_clause")
    if accepted_wrong_clause:
        semantic_fail_reasons.append("accepted_unsupported_causality")
    if wrong_target:
        semantic_fail_reasons.append("rejected_other_claim_but_accepted_causal_clause")
    if all_questionable and not isolated:
        semantic_fail_reasons.append("all_claims_questionable_without_discrimination")
    if terra in ACCEPTING_VERDICTS:
        semantic_fail_reasons.append("global_verdict_accepts_paragraph")
    if not blocking and terra is not None:
        semantic_fail_reasons.append("global_verdict_does_not_block")

    if flagged and not reason_present:
        semantic_partial_reasons.append("causal_flagged_without_reason_code")
    if flagged and reason_present and not reason_relevant:
        semantic_partial_reasons.append("causal_reason_code_not_primary")
    if flagged and not isolated:
        semantic_partial_reasons.append("causal_not_isolated_from_supported_claims")
    if unjustified_other_rejections:
        semantic_partial_reasons.append("supported_claims_rejected_without_justification")
    if global_only:
        semantic_partial_reasons.append("global_questionable_without_clause_verdict")
    if flagged and not blocking:
        semantic_partial_reasons.append("clause_flagged_but_global_verdict_not_blocking")
    if contract_status != "PASS":
        semantic_partial_reasons.append("contract_invalid_independent_of_semantics")
    if not coverage_ok:
        semantic_partial_reasons.append("coverage_incomplete")
    if not spans_ok:
        semantic_fail_reasons.append("invalid_spans")
    if invalid_refs:
        semantic_fail_reasons.append("invalid_evidence_references")
    if terra is None:
        semantic_fail_reasons.append("missing_global_verdict")

    technical_ok = contract_status == "PASS" and coverage_ok and spans_ok and not invalid_refs
    semantic_core = (
        bool(flagged)
        and reason_relevant
        and blocking
        and not omitted
        and not accepted_wrong_clause
        and not wrong_target
        and not all_questionable
        and not unjustified_other_rejections
        and isolated
    )
    if semantic_fail_reasons and not flagged:
        semantic = "FAIL"
        review_status = "FAIL"
    elif accepted_wrong_clause or omitted or wrong_target or terra in ACCEPTING_VERDICTS:
        semantic = "FAIL"
        review_status = "FAIL"
    elif all_questionable and not isolated:
        semantic = "FAIL"
        review_status = "FAIL"
    elif semantic_core and technical_ok:
        semantic = "PASS"
        review_status = "PASS"
    elif flagged:
        semantic = "PARTIAL"
        review_status = "PARTIAL"
    elif terra is None:
        semantic = "MISSING_VERDICT"
        review_status = "FAIL"
    else:
        semantic = "MISMATCH"
        review_status = "PARTIAL"

    supported_review = "PASS"
    if unjustified_other_rejections:
        supported_review = "FAIL"
    elif other_flagged:
        supported_review = "PARTIAL"
    elif not other_claims and not isolated:
        supported_review = "UNOBSERVED"

    return {
        "phase": PHASE,
        "case_id_audit_only": SELECTED_CASE_ID,
        "handle": SELECTED_CASE_HANDLE,
        "human_verdict_audit_only": SELECTED_CASE_HUMAN_LABEL,
        "human_accepted_classes_audit_only": list(SELECTED_CASE_ACCEPTED_CLASSES),
        "human_verdict_not_transmitted": True,
        "human_label_unmodified": True,
        "disputed_causal_clause": DISPUTED_CAUSAL_CLAUSE,
        "clause_offsets": {
            "start": clause_start,
            "end": clause_end,
            "expected_start": EXPECTED_CLAUSE_START,
            "expected_end": EXPECTED_CLAUSE_END,
            "match": clause_start == EXPECTED_CLAUSE_START
            and clause_end == EXPECTED_CLAUSE_END,
        },
        "terra_global_verdict": terra,
        "global_verdict_blocks_acceptance": blocking,
        "global_questionable_is_not_semantic_pass_alone": True,
        "disputed_causal_clause_verdict": disputed_verdict,
        "disputed_causal_clause_reason_codes": any_reason,
        "disputed_causal_clause_reason_code": (
            relevant_hits[0] if relevant_hits else (any_reason[0] if any_reason else None)
        ),
        "reason_code_relevant": reason_relevant,
        "clause_identified": bool(overlapping),
        "clause_flagged_questionable_or_unsupported": bool(flagged),
        "clause_accepted_as_supported": bool(accepted_causal) and not flagged,
        "clause_omitted": omitted,
        "clause_isolated": isolated,
        "discrimination": discrimination,
        "all_claims_questionable": all_questionable,
        "wrong_target": wrong_target,
        "overlapping_claims": overlapping,
        "claims": claims,
        "cited_evidence": sorted(set(cited)),
        "invalid_evidence_references": invalid_refs,
        "notes": notes,
        "local_propositions": p3_local_propositions(paragraph_text),
        "supported_claims_review": supported_review,
        "supported_claims": other_supported,
        "other_flagged_claims": other_flagged,
        "unjustified_other_rejections": unjustified_other_rejections,
        "coverage_ok": coverage_ok,
        "spans_ok": spans_ok,
        "contract_status": contract_status,
        "semantic_core_pass": semantic_core,
        "technical_ok": technical_ok,
        "semantic_fail_reasons": semantic_fail_reasons,
        "semantic_partial_reasons": semantic_partial_reasons,
        "semantic_status": semantic,
        "review_status": review_status,
        "secrets_included": False,
    }


__all__ = ["review_p3_semantic_response"]
