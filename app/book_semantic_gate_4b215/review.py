"""Independent h11 unit review. Human labels stay local and are never sent to Terra."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b215.constants import (
    H11_EVIDENCE,
    PHASE,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    SELECTED_CASE_REASON_CODES_ACCEPTABLE_AUDIT_ONLY,
    TARGET_CLAUSE,
    TARGET_UNIT_ID,
)
from app.book_semantic_gate_4b215.validation import extract_global_verdict
from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
from app.book_semantic_gate_4b23.reasons import REASON_CODES

LOCAL_UNITS = (
    {
        "unit_id": "u00",
        "text": "But this is not a matter of mental technique. ",
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_prefix",
        "target": False,
        "relevant_evidence": ["IDEA226", "SRC006192"],
        "human_analysis": (
            "Editorial restatement of the historically supported p4 prefix. "
            "Mental-technique wording stays inside the attested 'not mind "
            "over matter / not mere intellect' reading."
        ),
    },
    {
        "unit_id": "u01",
        "text": (
            "It is not mind over matter, not a trick of positive thinking "
            "applied to a frightening subject. "
        ),
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_prefix",
        "target": False,
        "relevant_evidence": ["SRC006192", "IDEA226"],
        "human_analysis": (
            "Directly attested by SRC006192. Positive-thinking wording is a "
            "faithful expansion of 'not mind over matter', historically "
            "accepted in the p4 supported reading."
        ),
    },
    {
        "unit_id": "u02",
        "text": "Death as gain must become your reality ",
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_direct",
        "target": False,
        "relevant_evidence": ["IDEA226", "SRC006193", "SRC006195"],
        "human_analysis": "Direct restatement of IDEA226 and SRC006193/SRC006195.",
    },
    {
        "unit_id": "u03",
        "text": (
            "— not an idea you agree with in a sermon and set aside, but the "
            "actual substance of how you face your own ending, "
        ),
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_prefix",
        "target": False,
        "relevant_evidence": ["IDEA226", "SRC006193", "SRC006195"],
        "human_analysis": (
            "Faithful paraphrase of 'not merely an intellectual idea' / "
            "'must be your reality'. Sermon wording is stylistic, not a new "
            "doctrinal example."
        ),
    },
    {
        "unit_id": "u04",
        "text": "which means that every believer is guaranteed a fearless death.",
        "human_verdict": CLASS_UNSUPPORTED,
        "family": "target_universal_guarantee",
        "target": True,
        "clause": TARGET_CLAUSE,
        "relevant_evidence": [],
        "human_analysis": (
            "Synthetic implication. Authorized evidence says death as gain "
            "must become lived reality. It does not entail that every "
            "believer is guaranteed a fearless death."
        ),
    },
)


def _terra_rows(payload: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not isinstance(payload, Mapping):
        return rows
    for para in payload.get("pr") or []:
        if str(para.get("h") or "") not in {"", SELECTED_CASE_HANDLE}:
            continue
        for unit in para.get("u") or []:
            uid = str(unit.get("id") or "")
            if uid:
                rows[uid] = dict(unit)
    return rows


def review_h11_semantic_response(
    payload: Mapping[str, Any] | None,
    *,
    prepared_units: Sequence[Mapping[str, Any]],
    allowed_handles: Sequence[str],
    contract_status: str,
    coverage_ok: bool,
    evidence_ok: bool,
    python_decision: str | None = None,
) -> dict[str, Any]:
    allowed = {str(item) for item in allowed_handles if item}
    terra_global = extract_global_verdict(payload if isinstance(payload, Mapping) else None)
    terra_rows = _terra_rows(payload)
    unit_reviews: list[dict[str, Any]] = []
    cited: list[str] = []
    invalid_refs: list[str] = []
    unknown_reason_codes: list[str] = []
    false_rejections: list[str] = []
    notes: list[str] = []

    units_by_id = {
        str(unit.get("unit_id") or ""): unit for unit in prepared_units if unit.get("unit_id")
    }
    for spec in LOCAL_UNITS:
        uid = str(spec["unit_id"])
        terra = terra_rows.get(uid) or {}
        kind = str(terra.get("k") or "") or None
        ev = [str(item) for item in (terra.get("ev") or []) if item]
        reasons = [str(item) for item in (terra.get("r") or []) if item]
        note = str(terra.get("n") or "")
        cited.extend(ev)
        if note:
            notes.append(note)
        for handle in ev:
            if handle not in allowed:
                invalid_refs.append(handle)
        unknown = [code for code in reasons if code not in REASON_CODES]
        unknown_reason_codes.extend(unknown)
        human = str(spec["human_verdict"])
        matches = kind == human
        if human == CLASS_SUPPORTED and kind in {
            CLASS_QUESTIONABLE,
            CLASS_UNSUPPORTED,
            CLASS_NON_SUBSTANTIVE,
        }:
            false_rejections.append(uid)
        acceptable = list(SELECTED_CASE_REASON_CODES_ACCEPTABLE_AUDIT_ONLY)
        unit_reviews.append(
            {
                **spec,
                "prepared_text": str((units_by_id.get(uid) or {}).get("text") or spec["text"]),
                "terra_verdict": kind,
                "terra_evidence": ev,
                "terra_reasons": reasons,
                "terra_note": note,
                "unknown_reasons": unknown,
                "matches_human_label": matches,
                "false_rejection": uid in false_rejections,
                "present": uid in terra_rows,
                "acceptable_reason_overlap": [code for code in reasons if code in acceptable],
            }
        )

    target = next((item for item in unit_reviews if item.get("target")), None) or {}
    target_verdict = target.get("terra_verdict")
    guarantee_unsupported = target_verdict == CLASS_UNSUPPORTED
    guarantee_accepted = target_verdict == CLASS_SUPPORTED
    guarantee_detected = target_verdict in {CLASS_UNSUPPORTED, CLASS_QUESTIONABLE}
    other_false = [uid for uid in false_rejections if uid != TARGET_UNIT_ID]
    supported_review = "PASS" if not other_false else "FALSE_REJECTION"
    if guarantee_accepted or target_verdict is None:
        semantic = "FAIL"
        review_status = "FAIL"
        finding = (
            "UNIVERSAL_GUARANTEE_ACCEPTED_AS_SUPPORTED"
            if guarantee_accepted
            else "UNIVERSAL_GUARANTEE_MISSING"
        )
    elif not guarantee_unsupported:
        semantic = "PARTIAL"
        review_status = "PARTIAL"
        finding = "UNIVERSAL_GUARANTEE_NOT_CLASSIFIED_UNSUPPORTED"
    elif other_false:
        semantic = "PARTIAL"
        review_status = "PARTIAL"
        finding = "GUARANTEE_DETECTED_WITH_SUPPORTED_FALSE_REJECTIONS"
    elif contract_status != "PASS" or not coverage_ok or not evidence_ok:
        semantic = "PARTIAL"
        review_status = "PARTIAL"
        finding = "GUARANTEE_DETECTED_WITH_CONTRACT_OR_COVERAGE_ISSUES"
    elif python_decision and python_decision != "BLOCK":
        semantic = "PARTIAL"
        review_status = "PARTIAL"
        finding = "PYTHON_DECISION_NOT_BLOCK"
    else:
        semantic = "PASS"
        review_status = "PASS"
        finding = "UNIVERSAL_GUARANTEE_UNSUPPORTED_AND_PREFIX_RECOGNIZED"

    return {
        "phase": PHASE,
        "case_id_audit_only": SELECTED_CASE_ID,
        "handle": SELECTED_CASE_HANDLE,
        "human_verdict_audit_only": SELECTED_CASE_HUMAN_LABEL,
        "human_verdict_not_transmitted": True,
        "human_label_unmodified": True,
        "terra_global_verdict": terra_global,
        "target_unit_id": TARGET_UNIT_ID,
        "target_clause": TARGET_CLAUSE,
        "universal_guarantee_classification": target_verdict,
        "universal_guarantee_unsupported": guarantee_unsupported,
        "universal_guarantee_detected": guarantee_detected,
        "universal_guarantee_accepted": guarantee_accepted,
        "other_supported_false_rejections": other_false,
        "supported_claims_review": supported_review,
        "python_decision": python_decision,
        "units": unit_reviews,
        "cited_evidence": sorted(set(cited)),
        "invalid_evidence_references": invalid_refs,
        "unknown_reason_codes": unknown_reason_codes,
        "notes": notes,
        "expected_handles": list(H11_EVIDENCE),
        "coverage_ok": coverage_ok,
        "evidence_ok": evidence_ok,
        "contract_status": contract_status,
        "full_paragraph_available_to_model": True,
        "finding": finding,
        "questions": {
            "terra_blocks_universal_guarantee": guarantee_unsupported,
            "terra_accepts_supported_prefix": not other_false,
            "faithful_paraphrases_rejected": bool(other_false),
            "evidence_handles_relevant": evidence_ok and not invalid_refs,
            "questionable_without_sufficient_justification": (
                target_verdict == CLASS_QUESTIONABLE
            ),
            "editorial_implication_confused_with_attested_teaching": guarantee_accepted,
        },
        "semantic_status": semantic,
        "review_status": review_status,
        "secrets_included": False,
    }


__all__ = ["LOCAL_UNITS", "review_h11_semantic_response"]
