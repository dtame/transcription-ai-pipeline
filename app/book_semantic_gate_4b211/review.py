"""Independent h01 unit review. Human labels stay local and are never sent to Terra."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b211.constants import (
    H01_EVIDENCE_HANDLES,
    PHASE,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    TARGET_CLAUSE,
    TARGET_UNIT_ID,
)
from app.book_semantic_gate_4b211.validation import extract_global_verdict

LOCAL_UNITS = (
    {
        "unit_id": "u00",
        "text": "Do not ever be afraid of death. ",
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_direct",
        "target": False,
        "relevant_evidence": ["SRC006149", "IDEA224"],
        "human_analysis": "Direct restatement of SRC006149. Historically accepted.",
    },
    {
        "unit_id": "u01",
        "text": "There is no fixed hour appointed that fear can calculate or bargain with, ",
        "human_verdict": CLASS_SUPPORTED,
        "family": "target_faithful_paraphrase",
        "target": True,
        "clause": TARGET_CLAUSE,
        "relevant_evidence": ["IDEA224"],
        "human_analysis": (
            "Faithful paraphrase of IDEA224 'no set time'. The verbs calculate "
            "and bargain personify the unavailability of an appointed hour. "
            "The old Semantic Gate rejected this clause for lacking those verbs "
            "in the evidence. Human reference remains SUPPORTED."
        ),
    },
    {
        "unit_id": "u02",
        "text": "and so fear itself is out of place. ",
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_connective",
        "target": False,
        "relevant_evidence": ["IDEA224", "SRC006149"],
        "human_analysis": (
            "Result connective of the attested 'do not fear' / 'no set time' "
            "claim. Historically accepted as SUPPORTED."
        ),
    },
    {
        "unit_id": "u03",
        "text": "If somebody has gone to heaven, that should not produce dread in us. ",
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_direct",
        "target": False,
        "relevant_evidence": ["SRC006187", "IDEA224"],
        "human_analysis": "Attested by SRC006187 and IDEA224.",
    },
    {
        "unit_id": "u04",
        "text": "It should be our joy.",
        "human_verdict": CLASS_SUPPORTED,
        "family": "supported_direct",
        "target": False,
        "relevant_evidence": ["SRC006183", "IDEA224"],
        "human_analysis": "Direct attestation in SRC006183.",
    },
)

_LEXICAL_MARKERS = (
    "bargain",
    "calculate",
    "same words",
    "verbatim",
    "not supplied",
    "not in the evidence",
    "lexical",
    "keyword",
    "exact wording",
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


def review_h01_semantic_response(
    payload: Mapping[str, Any] | None,
    *,
    prepared_units: Sequence[Mapping[str, Any]],
    allowed_handles: Sequence[str],
    contract_status: str,
    coverage_ok: bool,
    evidence_ok: bool,
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
    lexical_flags: list[str] = []

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
        if spec.get("target") and kind in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED}:
            lowered = note.lower()
            for marker in _LEXICAL_MARKERS:
                if marker in lowered:
                    lexical_flags.append(marker)
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
            }
        )

    target = next((item for item in unit_reviews if item.get("target")), None) or {}
    target_verdict = target.get("terra_verdict")
    target_recognized = target_verdict == CLASS_SUPPORTED
    other_false = [uid for uid in false_rejections if uid != TARGET_UNIT_ID]
    lexical_demand = bool(lexical_flags) and not target_recognized
    supported_review = (
        "PASS"
        if not other_false
        else "FALSE_REJECTION"
    )
    if not target_recognized:
        semantic = "FAIL"
        review_status = "FAIL"
        finding = "TARGET_PARAPHRASE_STILL_REJECTED"
    elif other_false:
        semantic = "PARTIAL"
        review_status = "PARTIAL"
        finding = "TARGET_RECOGNIZED_WITH_OTHER_FALSE_REJECTIONS"
    elif contract_status != "PASS" or not coverage_ok or not evidence_ok:
        semantic = "PARTIAL"
        review_status = "PARTIAL"
        finding = "TARGET_RECOGNIZED_WITH_CONTRACT_OR_COVERAGE_ISSUES"
    else:
        semantic = "PASS"
        review_status = "PASS"
        finding = "TARGET_PARAPHRASE_RECOGNIZED_AS_SUPPORTED"

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
        "target_paraphrase_verdict": target_verdict,
        "target_paraphrase_recognized": target_recognized,
        "still_requires_same_words": lexical_demand,
        "lexical_match_flags": lexical_flags,
        "unjustified_reservations": (
            [target.get("terra_note")]
            if target.get("terra_note") and not target_recognized
            else []
        ),
        "other_supported_false_rejections": other_false,
        "supported_claims_review": supported_review,
        "units": unit_reviews,
        "cited_evidence": sorted(set(cited)),
        "invalid_evidence_references": invalid_refs,
        "unknown_reason_codes": unknown_reason_codes,
        "notes": notes,
        "expected_handles": list(H01_EVIDENCE_HANDLES),
        "coverage_ok": coverage_ok,
        "evidence_ok": evidence_ok,
        "contract_status": contract_status,
        "full_paragraph_available_to_model": True,
        "finding": finding,
        "questions": {
            "terra_recognizes_paraphrase_as_faithful": target_recognized,
            "still_requires_same_words_as_evidence": lexical_demand,
            "introduces_unjustified_reservations": bool(
                target.get("terra_note") and not target_recognized
            ),
            "rejects_other_supported_propositions": bool(other_false),
            "uses_evidence_coherently": evidence_ok and not invalid_refs,
            "respects_full_paragraph_context": True,
        },
        "semantic_status": semantic,
        "review_status": review_status,
        "secrets_included": False,
    }


__all__ = ["LOCAL_UNITS", "review_h01_semantic_response"]
