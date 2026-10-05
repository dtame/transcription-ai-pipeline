"""Independent h11 semantic review. Human labels stay local and are never sent to Terra."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b261.candidates import recover_claim_text
from app.book_semantic_gate_4b262.contract import validate_compact_span
from app.book_semantic_gate_4b276.identity import clause_offsets, human_reference_label
from app.book_semantic_gate_4b277.constants import (
    ACCEPTABLE_REASON_CODES,
    ACCEPTING_VERDICTS,
    BLOCKING_VERDICTS,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    DISPUTED_CLAUSE,
    EXPECTED_CLAUSE_END,
    EXPECTED_CLAUSE_START,
    P4_EVIDENCE_HANDLES,
    PHASE,
    RELEVANT_REASON_CODES,
    SELECTED_CASE_ACCEPTED_CLASSES,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    TARGET_FAILURE_FAMILY,
    VERDICT_REVIEW,
)

LOCAL_PROPOSITIONS = (
    {
        "id": "p1_mental_technique",
        "text": "But this is not a matter of mental technique",
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_prefix",
        "relevant_evidence": list(P4_EVIDENCE_HANDLES),
        "human_analysis": (
            "Stylistic restatement of the mind-over-matter refusal. "
            "Historically accepted inside 4b22_p4_supported."
        ),
    },
    {
        "id": "p2_mind_over_matter",
        "text": "It is not mind over matter",
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_prefix",
        "relevant_evidence": ["SRC006192", "IDEA226"],
        "human_analysis": "Direct paraphrase of SRC006192.",
    },
    {
        "id": "p3_positive_thinking",
        "text": "not a trick of positive thinking applied to a frightening subject",
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_prefix",
        "relevant_evidence": ["SRC006192", "IDEA226"],
        "human_analysis": (
            "Editorial expansion of 'not mind over matter' without a new relation."
        ),
    },
    {
        "id": "p4_lived_reality",
        "text": "Death as gain must become your reality",
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_prefix",
        "relevant_evidence": ["IDEA226", "SRC006193", "SRC006195"],
        "human_analysis": "Attested by IDEA226 and SRC006193/SRC006195.",
    },
    {
        "id": "p5_not_sermon_idea",
        "text": "not an idea you agree with in a sermon and set aside",
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_prefix",
        "relevant_evidence": ["IDEA226"],
        "human_analysis": (
            "Paraphrase of IDEA226: lived reality, not merely an intellectual idea."
        ),
    },
    {
        "id": "p6_substance_of_ending",
        "text": "the actual substance of how you face your own ending",
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_prefix",
        "relevant_evidence": ["IDEA226", "SRC006193", "SRC006195"],
        "human_analysis": "Lived-reality restatement, historically supported.",
    },
    {
        "id": "p7_universal_guarantee",
        "text": DISPUTED_CLAUSE,
        "human_verdict": CLASS_UNSUPPORTED,
        "family": "universal_guarantee",
        "relevant_evidence": [],
        "human_analysis": (
            "New universal guarantee. Evidence requires lived reality of death "
            "as gain; it does not entail that every believer is guaranteed a "
            "fearless death."
        ),
    },
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


def _best_overlap(
    claims: Sequence[Mapping[str, Any]],
    start: int,
    end: int,
) -> dict[str, Any] | None:
    best = None
    best_len = -1
    for claim in claims:
        cs = claim.get("start")
        ce = claim.get("end")
        if not isinstance(cs, int) or not isinstance(ce, int):
            continue
        if not _overlaps(cs, ce, start, end):
            continue
        overlap = min(ce, end) - max(cs, start)
        if overlap > best_len:
            best = dict(claim)
            best_len = overlap
    return best


def local_propositions(paragraph_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in LOCAL_PROPOSITIONS:
        text = str(item["text"])
        start = paragraph_text.find(text)
        end = start + len(text) if start >= 0 else None
        rows.append(
            {
                **item,
                "found": start >= 0,
                "start": start if start >= 0 else None,
                "end": end,
                "exact_match": (
                    start >= 0 and paragraph_text[start:end] == text
                ),
            }
        )
    return rows


def review_h11_semantic_response(
    payload: Mapping[str, Any] | None,
    *,
    paragraph_text: str,
    allowed_handles: Sequence[str],
    contract_status: str,
    coverage_ok: bool,
    spans_ok: bool,
    root=None,
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
    unknown_reason_codes: list[str] = []
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
                unknown_reason_codes.extend(unknown_reasons)
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
                    "contains_which_means": "which means" in recovered.lower(),
                    "contains_guaranteed": "guaranteed" in recovered.lower(),
                    "contains_every_believer": "every believer" in recovered.lower(),
                    "contains_clause_text": DISPUTED_CLAUSE in recovered,
                }
                claims.append(row)
                if row["overlaps_disputed_clause"]:
                    overlapping.append(row)

    flagged = [
        item
        for item in overlapping
        if item.get("class") in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED}
    ]
    accepted_guarantee = [
        item for item in overlapping if item.get("class") == CLASS_SUPPORTED
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
    acceptable_hits = sorted(
        {
            code
            for item in flagged
            for code in (item.get("reasons") or [])
            if code in ACCEPTABLE_REASON_CODES
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
    reason_acceptable = bool(acceptable_hits)
    disputed_verdict = None
    if flagged:
        disputed_verdict = str(flagged[0].get("class") or "") or None
    elif accepted_guarantee:
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
    accepted_wrong_clause = bool(accepted_guarantee) and not flagged
    wrong_target = (
        not flagged
        and bool(other_flagged)
        and (omitted or accepted_wrong_clause)
    )
    global_only = blocking and not flagged

    propositions = local_propositions(paragraph_text)
    claim_by_claim: list[dict[str, Any]] = []
    for proposition in propositions:
        start = proposition.get("start")
        end = proposition.get("end")
        match = None
        if isinstance(start, int) and isinstance(end, int):
            match = _best_overlap(claims, start, end)
        terra_verdict = str(match.get("class") or "") if match else None
        terra_reasons = list(match.get("reasons") or []) if match else []
        terra_ev = list(match.get("evidence") or []) if match else []
        human_verdict = str(proposition.get("human_verdict") or "")
        if terra_verdict is None:
            agreement = False
            agreement_note = "Terra omitted this proposition as a distinct or overlapping span."
        elif human_verdict == CLASS_SUPPORTED:
            agreement = terra_verdict == CLASS_SUPPORTED
            agreement_note = (
                "Agree: supported prefix kept as SUPPORTED."
                if agreement
                else "Disagree: historically supported prefix was rejected."
            )
        else:
            agreement = terra_verdict in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED}
            agreement_note = (
                "Agree: universal guarantee is blocked."
                if agreement
                else "Disagree: universal guarantee was accepted."
            )
        claim_by_claim.append(
            {
                "id": proposition.get("id"),
                "text": proposition.get("text"),
                "offsets": [start, end],
                "found": proposition.get("found"),
                "family": proposition.get("family"),
                "terra_verdict": terra_verdict,
                "terra_reason_codes": terra_reasons,
                "terra_evidence_handles": terra_ev,
                "relevant_evidence_available": proposition.get("relevant_evidence"),
                "human_verdict_audit_only": human_verdict,
                "human_analysis": proposition.get("human_analysis"),
                "agreement": agreement,
                "agreement_note": agreement_note,
                "terra_note": (match or {}).get("note"),
            }
        )

    guarantee_row = next(
        (item for item in claim_by_claim if item.get("id") == "p7_universal_guarantee"),
        None,
    )
    supported_rows = [
        item for item in claim_by_claim if item.get("family") == "supported_prefix"
    ]
    supported_agreements = [item for item in supported_rows if item.get("agreement")]
    supported_disagreements = [
        item for item in supported_rows if not item.get("agreement")
    ]

    semantic_fail_reasons: list[str] = []
    semantic_partial_reasons: list[str] = []
    if omitted:
        semantic_fail_reasons.append("omitted_universal_guarantee")
    if accepted_wrong_clause:
        semantic_fail_reasons.append("accepted_unsupported_universal_guarantee")
    if wrong_target:
        semantic_fail_reasons.append(
            "rejected_other_claim_but_accepted_universal_guarantee"
        )
    if all_questionable and not isolated:
        semantic_fail_reasons.append("all_claims_questionable_without_discrimination")
    if terra in ACCEPTING_VERDICTS:
        semantic_fail_reasons.append("global_verdict_accepts_paragraph")
    if not blocking and terra is not None:
        semantic_fail_reasons.append("global_verdict_does_not_block")
    if unknown_reason_codes:
        semantic_fail_reasons.append("unknown_reason_code")
    if invalid_refs:
        semantic_fail_reasons.append("invalid_evidence_references")
    if not spans_ok:
        semantic_fail_reasons.append("invalid_spans")
    if terra is None:
        semantic_fail_reasons.append("missing_global_verdict")

    if flagged and not any_reason:
        semantic_partial_reasons.append("guarantee_flagged_without_reason_code")
    if flagged and any_reason and not reason_acceptable:
        semantic_partial_reasons.append("guarantee_reason_code_not_acceptable")
    if flagged and reason_acceptable and not reason_relevant:
        semantic_partial_reasons.append("guarantee_reason_code_neighbor_not_primary")
    if flagged and not isolated:
        semantic_partial_reasons.append(
            "guarantee_not_isolated_from_supported_claims"
        )
    if unjustified_other_rejections:
        semantic_partial_reasons.append("supported_claims_rejected_without_justification")
    if other_flagged:
        semantic_partial_reasons.append("supported_claims_false_rejection")
    if global_only:
        semantic_partial_reasons.append("global_block_without_clause_verdict")
    if flagged and not blocking:
        semantic_partial_reasons.append("clause_flagged_but_global_verdict_not_blocking")
    if contract_status != "PASS":
        semantic_partial_reasons.append("contract_invalid_independent_of_semantics")
    if not coverage_ok:
        semantic_partial_reasons.append("coverage_incomplete")

    technical_ok = (
        contract_status == "PASS"
        and coverage_ok
        and spans_ok
        and not invalid_refs
        and not unknown_reason_codes
    )
    semantic_core = (
        bool(flagged)
        and reason_acceptable
        and blocking
        and not omitted
        and not accepted_wrong_clause
        and not wrong_target
        and not all_questionable
        and not other_flagged
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
    elif unknown_reason_codes:
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

    human = human_reference_label(root=root)
    human_comparison = {
        "phase": PHASE,
        "human_label_audit_only": SELECTED_CASE_HUMAN_LABEL,
        "human_accepted_classes_audit_only": list(SELECTED_CASE_ACCEPTED_CLASSES),
        "human_label_not_transmitted": True,
        "human_label_unmodified": True,
        "target_failure_family_audit_only": TARGET_FAILURE_FAMILY,
        "expected_paragraph_verdict": human.get("paragraph_verdict_expected"),
        "expected_global_verdicts": human.get("accepted_global_verdicts"),
        "terra_paragraph_or_global": terra,
        "terra_blocks_acceptance": blocking,
        "universal_guarantee_verdict": disputed_verdict,
        "universal_guarantee_reason_codes": any_reason,
        "agreement_on_guarantee": bool(flagged),
        "agreement_on_supported_prefix": not other_flagged,
        "global_block_alone_is_not_pass": True,
        "acceptance_criteria": human.get("acceptance_criteria"),
        "rejection_criteria": human.get("rejection_criteria"),
        "secrets_included": False,
    }

    return {
        "phase": PHASE,
        "case_id_audit_only": SELECTED_CASE_ID,
        "handle": SELECTED_CASE_HANDLE,
        "human_verdict_audit_only": SELECTED_CASE_HUMAN_LABEL,
        "human_accepted_classes_audit_only": list(SELECTED_CASE_ACCEPTED_CLASSES),
        "human_verdict_not_transmitted": True,
        "human_label_unmodified": True,
        "disputed_clause": DISPUTED_CLAUSE,
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
        "universal_guarantee_verdict": disputed_verdict,
        "universal_guarantee_reason_codes": any_reason,
        "universal_guarantee_reason_code": (
            relevant_hits[0]
            if relevant_hits
            else (acceptable_hits[0] if acceptable_hits else (any_reason[0] if any_reason else None))
        ),
        "reason_code_relevant": reason_relevant,
        "reason_code_acceptable": reason_acceptable,
        "clause_identified": bool(overlapping),
        "clause_flagged_questionable_or_unsupported": bool(flagged),
        "clause_accepted_as_supported": bool(accepted_guarantee) and not flagged,
        "clause_omitted": omitted,
        "clause_isolated": isolated,
        "discrimination": discrimination,
        "all_claims_questionable": all_questionable,
        "wrong_target": wrong_target,
        "overlapping_claims": overlapping,
        "claims": claims,
        "claim_by_claim": claim_by_claim,
        "guarantee_row": guarantee_row,
        "supported_prefix_agreements": len(supported_agreements),
        "supported_prefix_disagreements": len(supported_disagreements),
        "cited_evidence": sorted(set(cited)),
        "invalid_evidence_references": invalid_refs,
        "unknown_reason_codes": unknown_reason_codes,
        "notes": notes,
        "local_propositions": propositions,
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
        "human_reference_comparison": human_comparison,
        "secrets_included": False,
    }


__all__ = [
    "LOCAL_PROPOSITIONS",
    "local_propositions",
    "review_h11_semantic_response",
]
