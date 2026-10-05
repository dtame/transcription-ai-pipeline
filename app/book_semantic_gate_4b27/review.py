"""Semantic review of the single positive case. Labels stay local."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b261.candidates import recover_claim_text
from app.book_semantic_gate_4b262.contract import validate_compact_span
from app.book_semantic_gate_4b27.constants import (
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    PHASE,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
)

_EXTERNAL_MARKERS = (
    "il est bien connu",
    "tout le monde sait",
    "en général",
    "selon les experts",
    "historiquement on sait",
)
_CAUSAL_MARKERS = (
    "parce que",
    "c'est pourquoi",
    "par conséquent",
    "donc cela prouve",
    "ainsi on conclut",
)


def _terra_verdict(payload: Mapping[str, Any] | None) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    for para in payload.get("pr") or []:
        if str(para.get("h") or "") == SELECTED_CASE_HANDLE:
            return str(para.get("v") or "") or None
    return str(payload.get("v") or "") or None


def review_semantic_response(
    payload: Mapping[str, Any] | None,
    *,
    paragraph_text: str,
    allowed_handles: Sequence[str],
    contract_status: str,
    coverage_ok: bool,
    spans_ok: bool,
) -> dict[str, Any]:
    allowed = {str(item) for item in allowed_handles if item}
    terra = _terra_verdict(payload)
    claims: list[dict[str, Any]] = []
    cited: list[str] = []
    notes: list[str] = []
    invention_flags: list[str] = []
    causal_flags: list[str] = []
    external_flags: list[str] = []
    invalid_refs: list[str] = []
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
                span = validate_compact_span(
                    paragraph_text, claim.get("s"), claim.get("e")
                )
                recovered = str(span.get("recovered_text") or "")
                if recovered and recovered not in paragraph_text:
                    invention_flags.append("recovered_span_not_in_paragraph")
                note = str(claim.get("n") or "")
                if note:
                    notes.append(note)
                    lowered = note.lower()
                    for marker in _EXTERNAL_MARKERS:
                        if marker in lowered:
                            external_flags.append(marker)
                    for marker in _CAUSAL_MARKERS:
                        if marker in lowered:
                            causal_flags.append(marker)
                reasons = [str(item) for item in (claim.get("r") or []) if item]
                unknown_reasons = [code for code in reasons if code not in REASON_CODES]
                claims.append(
                    {
                        "index": claim.get("i"),
                        "class": claim.get("k"),
                        "start": claim.get("s"),
                        "end": claim.get("e"),
                        "recovered_text": recover_claim_text(
                            paragraph_text,
                            int(claim.get("s") or 0),
                            int(claim.get("e") or 0),
                        )
                        if isinstance(claim.get("s"), int)
                        and isinstance(claim.get("e"), int)
                        else "",
                        "evidence": ev,
                        "reasons": reasons,
                        "unknown_reasons": unknown_reasons,
                        "note": note,
                        "span_valid": span.get("valid"),
                    }
                )

    human = SELECTED_CASE_HUMAN_LABEL
    matches_human = terra == human
    justification_ok = (
        matches_human
        and coverage_ok
        and spans_ok
        and not invalid_refs
        and not invention_flags
        and not causal_flags
        and not external_flags
        and all(not claim.get("unknown_reasons") for claim in claims)
        and bool(claims)
    )
    if terra in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED}:
        semantic = "POTENTIAL_FALSE_REJECTION"
        review_status = "PARTIAL"
    elif terra is None:
        semantic = "MISSING_VERDICT"
        review_status = "FAIL"
    elif justification_ok and contract_status == "PASS":
        semantic = "PASS"
        review_status = "PASS"
    elif terra == human:
        semantic = "SUPPORTED_BUT_NOT_FULLY_JUSTIFIED"
        review_status = "PARTIAL"
    else:
        semantic = "MISMATCH"
        review_status = "PARTIAL"

    return {
        "phase": PHASE,
        "case_id_audit_only": SELECTED_CASE_ID,
        "handle": SELECTED_CASE_HANDLE,
        "human_verdict_audit_only": human,
        "human_verdict_not_transmitted": True,
        "terra_verdict": terra,
        "matches_human_label": matches_human,
        "supported_alone_is_not_semantic_pass": True,
        "claims": claims,
        "cited_evidence": sorted(set(cited)),
        "invalid_evidence_references": invalid_refs,
        "notes": notes,
        "invention_flags": invention_flags,
        "added_causal_relation_flags": causal_flags,
        "external_knowledge_flags": external_flags,
        "coverage_ok": coverage_ok,
        "spans_ok": spans_ok,
        "justification_compatible_with_supplied_evidence": justification_ok,
        "semantic_status": semantic,
        "review_status": review_status,
        "human_label_unmodified": True,
        "secrets_included": False,
    }


__all__ = ["review_semantic_response"]
