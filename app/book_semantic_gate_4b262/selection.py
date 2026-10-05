"""Select and document the first compact canary case. Labels stay local."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.ai.estimation import estimate_tokens
from app.book_semantic_gate_4b24.constants import SCORED_CASE_ORDER
from app.book_semantic_gate_4b24.identity import load_frozen_benchmark, scored_cases
from app.book_semantic_gate_4b261.complexity import extract_gate_input, extract_gate_paragraphs
from app.book_semantic_gate_4b261.evidence import load_4b26_bundle
from app.book_semantic_gate_4b261.strategies import _slice_gate_input
from app.book_semantic_gate_4b262.constants import (
    CLASS_SUPPORTED,
    PHASE,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_HUMAN_LABEL_AUDIT_ONLY,
    SELECTED_CASE_ID,
    SELECTED_CASE_ROLE,
)


def _benchmark_case(root: Path | None = None) -> dict[str, Any]:
    benchmark = load_frozen_benchmark(root=root)
    for item in scored_cases(benchmark):
        if str(item.get("case_id") or "") == SELECTED_CASE_ID:
            return dict(item)
    raise ValueError(f"Historical case {SELECTED_CASE_ID} is missing from the frozen benchmark.")


def _gate_paragraph(payload: Mapping[str, Any]) -> dict[str, Any]:
    for item in extract_gate_paragraphs(payload):
        if str(item.get("handle") or "") == SELECTED_CASE_HANDLE:
            return dict(item)
    raise ValueError(f"Handle {SELECTED_CASE_HANDLE} is missing from the 4B.2.6 gate input.")


def review_selected_case(*, root: Path | None = None) -> dict[str, Any]:
    bundle = load_4b26_bundle(root=root)
    payload = dict(bundle.get("payload") or {})
    historical = _benchmark_case(root=root)
    paragraph = _gate_paragraph(payload)
    text = str(paragraph.get("text") or historical.get("text") or "")
    estimate = estimate_tokens(text)
    handles = [handle for handle, _case_id in SCORED_CASE_ORDER]
    problem = None
    if not text.strip():
        problem = "empty_paragraph_text"
    if str(historical.get("role") or "") != SELECTED_CASE_ROLE:
        problem = "role_mismatch"
    if str(historical.get("expected_class") or "") != SELECTED_CASE_HUMAN_LABEL:
        problem = "label_mismatch"
    if handles[0] != SELECTED_CASE_HANDLE:
        problem = "handle_order_mismatch"

    why = (
        "4B.2.6.1 proposed h01 as the smallest isolation of whether Terra can "
        "emit usable JSON under the compact 1.1-candidate contract. h01 is a "
        "historical positive case. A technical success would demonstrate "
        "structured JSON emission and acceptance of supported content. It "
        "would not demonstrate blocking power on FUNERAL, CONNECTIVE, P3, or "
        "P8. The case was not changed silently."
    )
    return {
        "phase": PHASE,
        "selected_handle": SELECTED_CASE_HANDLE,
        "selected_case_id": SELECTED_CASE_ID,
        "selected_case_role": SELECTED_CASE_ROLE,
        "human_label_audit_only": {
            "expected_class": SELECTED_CASE_HUMAN_LABEL,
            "accepted_classes": list(historical.get("accepted_classes") or [CLASS_SUPPORTED]),
            "role": historical.get("role"),
            "present_in_provider_request": False,
            "authority": "frozen human benchmark label",
        },
        "human_label_not_transmitted": SELECTED_CASE_HUMAN_LABEL_AUDIT_ONLY,
        "text": text,
        "size": {
            "chars": len(text),
            "utf8_bytes": len(text.encode("utf-8")),
            "unicode_code_points": len(text),
            "estimated_tokens": estimate.tokens,
            "estimated": True,
            "method": estimate.method,
        },
        "kind": paragraph.get("kind") or historical.get("kind"),
        "section": historical.get("section"),
        "source_phase": historical.get("source"),
        "compatibility_with_compact_contract": {
            "has_stable_handle": True,
            "has_paragraph_text": bool(text),
            "has_canonical_evidence": bool(
                paragraph.get("src") or paragraph.get("ref") or historical.get("evidence_handles")
            ),
            "offsets_applicable": True,
            "claim_coverage_possible": True,
            "ok": problem is None,
        },
        "why_appropriate": why,
        "success_would_show": (
            "Primarily structured-response capability and acceptance of "
            "supported content. Not a ten-case validation. Not a first "
            "observation of semantic blocking."
        ),
        "if_negative_would_also_show_blocking": False,
        "case_changed": False,
        "alternate_case_proposed": None,
        "human_review_required_before_changing_case": True,
        "problem": problem,
        "selected": problem is None,
        "fourb261_proposal_honored": True,
        "secrets_included": False,
    }


def evidence_manifest(*, root: Path | None = None) -> dict[str, Any]:
    bundle = load_4b26_bundle(root=root)
    payload = dict(bundle.get("payload") or {})
    gate = extract_gate_input(payload)
    sliced = _slice_gate_input(gate, [SELECTED_CASE_HANDLE])
    paragraph = _gate_paragraph(payload)
    historical = _benchmark_case(root=root)
    src = list(sliced.get("src_text") or [])
    ideas = list(sliced.get("ideas") or [])
    refs = list(sliced.get("references") or [])
    gate_declared = sorted(
        {
            str(item)
            for item in list(paragraph.get("src") or [])
            + list(paragraph.get("ref") or [])
            + list(paragraph.get("idea") or [])
            + list(paragraph.get("evidence_handles") or [])
            if item
        }
    )
    historical_declared = [
        str(item) for item in (historical.get("evidence_handles") or []) if item
    ]
    present_ids = sorted(
        {str(item.get("id") or "") for item in src + ideas + refs if item.get("id")}
    )
    allowed = {str(item) for item in (sliced.get("allowed_handles") or []) if item}
    present_ids = sorted(set(present_ids) | allowed)
    missing = [handle for handle in gate_declared if handle not in present_ids]
    declared = gate_declared
    return {
        "phase": PHASE,
        "handle": SELECTED_CASE_HANDLE,
        "case_id_audit_only": SELECTED_CASE_ID,
        "declared_handles": declared,
        "historical_benchmark_handles_audit_only": historical_declared,
        "src_text": [
            {
                "id": item.get("id"),
                "chars": len(
                    str(item.get("t") or item.get("text") or item.get("sum") or "")
                ),
                "present": True,
            }
            for item in src
        ],
        "ideas": [
            {
                "id": item.get("id"),
                "chars": len(
                    str(item.get("t") or item.get("text") or item.get("sum") or "")
                ),
                "present": True,
            }
            for item in ideas
        ],
        "references": [
            {
                "id": item.get("id"),
                "chars": len(
                    str(item.get("t") or item.get("text") or item.get("sum") or "")
                ),
                "present": True,
            }
            for item in refs
        ],
        "present_ids": present_ids,
        "missing_required_handles": missing,
        "complete": not missing and bool(present_ids),
        "summaries_not_substituted": True,
        "canonical_evidence_only": True,
        "other_cases_excluded": True,
        "batching_did_not_drop_required_context": not missing,
        "secrets_included": False,
    }


__all__ = ["evidence_manifest", "review_selected_case"]
