"""Offline inventory of unused historical cases and the selected synthetic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b24.constants import SCORED_CASE_ORDER
from app.book_semantic_gate_4b24.identity import load_frozen_benchmark, scored_cases
from app.book_semantic_gate_4b276.constants import (
    H01_CASE_HANDLE,
    H01_CASE_ID,
    H02_CASE_HANDLE,
    H02_CASE_ID,
    PHASE,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
    SELECTED_CASE_ORIGIN,
    SOURCE_CASE_ID,
    TARGET_FAILURE_FAMILY,
)
from app.book_semantic_gate_4b276.identity import selected_canary_provenance


def _score(
    *,
    independent: bool,
    mixed: bool,
    clear_evidence: bool,
    low_ambiguity: bool,
    different_family: bool,
    unused_terra: bool,
    cost_ok: bool,
    notes: str,
    eligible: bool,
) -> dict[str, Any]:
    axes = {
        "independent_of_h01_h02": independent,
        "mixed_supported_and_problematic": mixed,
        "clear_evidence": clear_evidence,
        "low_ambiguity": low_ambiguity,
        "different_error_family_from_h02": different_family,
        "unused_as_real_terra_canary": unused_terra,
        "cost_comparable": cost_ok,
    }
    return {
        **axes,
        "eligible": eligible and all(axes.values()),
        "notes": notes,
    }


def candidate_inventory(*, root: Path | None = None) -> dict[str, Any]:
    benchmark = load_frozen_benchmark(root=root)
    rows: list[dict[str, Any]] = []
    for opaque, case_id in SCORED_CASE_ORDER:
        item = next(
            row for row in scored_cases(benchmark) if str(row.get("case_id") or "") == case_id
        )
        used = case_id in {H01_CASE_ID, H02_CASE_ID}
        role = str(item.get("role") or "")
        evidence = list(item.get("evidence_handles") or [])
        clause = item.get("clause")
        reasons = list(item.get("expected_reason_codes") or [])
        text = str(item.get("text") or "")
        if used:
            score = _score(
                independent=False,
                mixed=role == "negative",
                clear_evidence=bool(evidence),
                low_ambiguity=False if case_id == H02_CASE_ID else True,
                different_family=case_id != H02_CASE_ID,
                unused_terra=False,
                cost_ok=True,
                notes=(
                    "Already used as real Terra canary h01 (PARTIAL false reject)."
                    if case_id == H01_CASE_ID
                    else "Already used as real Terra canary h02 (PARTIAL mixed result)."
                ),
                eligible=False,
            )
        elif role == "positive":
            score = _score(
                independent=True,
                mixed=False,
                clear_evidence=bool(evidence),
                low_ambiguity=True,
                different_family=True,
                unused_terra=True,
                cost_ok=len(text) < 600,
                notes=(
                    "Historical positive. No problematic proposition. "
                    "Reusing it would reproduce a paraphrase-only test close to h01."
                    if case_id == SOURCE_CASE_ID
                    else "Historical positive. No problematic proposition to refuse."
                ),
                eligible=False,
            )
        elif case_id == "4b22_p8_reference_completion":
            score = _score(
                independent=True,
                mixed=True,
                clear_evidence=True,
                low_ambiguity=False,
                different_family=True,
                unused_terra=True,
                cost_ok=True,
                notes=(
                    "REFERENCE_COMPLETION family is independent of h02. REF050 is "
                    "partial and SRC006788 only attests 'on 1 Corinthians 15'. "
                    "Neighboring clauses (admired argument, lived into, gain we "
                    "practice) are also unattested, so a Terra extra-reject would "
                    "be hard to interpret — similar to h02's neighboring false rejects."
                ),
                eligible=False,
            )
        elif case_id == "4b2_p8_invented_funeral":
            score = _score(
                independent=True,
                mixed=True,
                clear_evidence=True,
                low_ambiguity=False,
                different_family=True,
                unused_terra=True,
                cost_ok=True,
                notes=(
                    "INVENTED_EXAMPLE family is independent. Mind-over-matter and "
                    "must-be-reality are attested. 'This is exactly why' introduces "
                    "a causal-framing confound with h02. Not selected."
                ),
                eligible=False,
            )
        elif case_id == "4b2_p13_unsupported_connective":
            score = _score(
                independent=True,
                mixed=False,
                clear_evidence=False,
                low_ambiguity=True,
                different_family=True,
                unused_terra=True,
                cost_ok=True,
                notes=(
                    "No authorized evidence and no supported proposition. Tests "
                    "wholesale rejection, not discrimination."
                ),
                eligible=False,
            )
        else:
            score = _score(
                independent=True,
                mixed=False,
                clear_evidence=bool(evidence),
                low_ambiguity=False,
                different_family=True,
                unused_terra=True,
                cost_ok=True,
                notes="Not selected.",
                eligible=False,
            )
        rows.append(
            {
                "opaque_handle": opaque,
                "case_id_audit_only": case_id,
                "role_audit_only": role,
                "expected_class_audit_only": item.get("expected_class"),
                "expected_reason_codes_audit_only": reasons,
                "clause_audit_only": clause,
                "evidence_handles": evidence,
                "chars": len(text),
                "already_used_as_real_terra_canary": used,
                "used_as": opaque if used else None,
                "score": score,
            }
        )
    synthetic = {
        "opaque_handle": SELECTED_CASE_HANDLE,
        "case_id_audit_only": SELECTED_CASE_ID,
        "role_audit_only": "synthetic_negative",
        "origin": SELECTED_CASE_ORIGIN,
        "source_case_id_audit_only": SOURCE_CASE_ID,
        "already_used_as_real_terra_canary": False,
        "score": _score(
            independent=True,
            mixed=True,
            clear_evidence=True,
            low_ambiguity=True,
            different_family=True,
            unused_terra=True,
            cost_ok=True,
            notes=(
                "Controlled synthetic from canonical 4b22_p4_supported. Keeps the "
                "attested paraphrase and adds one which-means guarantee. Evidence "
                "unchanged. Not an authentic citation."
            ),
            eligible=True,
        ),
    }
    rows.append(synthetic)
    eligible = [row for row in rows if (row.get("score") or {}).get("eligible")]
    return {
        "phase": PHASE,
        "historical_ten_cases_unmodified": True,
        "h01_status_preserved": "PARTIAL",
        "h02_status_preserved": "PARTIAL",
        "candidates": rows,
        "eligible_candidates": [row["case_id_audit_only"] for row in eligible],
        "selected": SELECTED_CASE_ID,
        "secrets_included": False,
    }


def candidate_selection_matrix(*, root: Path | None = None) -> dict[str, Any]:
    inventory = candidate_inventory(root=root)
    provenance = selected_canary_provenance(root=root)
    return {
        "phase": PHASE,
        "criteria": [
            "independence_from_h01",
            "independence_from_h02",
            "mixed_supported_and_problematic",
            "clear_canonical_evidence",
            "low_interpretive_ambiguity",
            "different_error_family_from_invented_causality",
            "not_already_used_as_terra_canary",
            "cost_control",
            "contract_1_1_3_expressible",
        ],
        "rows": [
            {
                "case_id_audit_only": item.get("case_id_audit_only"),
                "opaque_handle": item.get("opaque_handle"),
                **(item.get("score") or {}),
            }
            for item in inventory.get("candidates") or []
        ],
        "selected": {
            "case_id": SELECTED_CASE_ID,
            "handle": SELECTED_CASE_HANDLE,
            "origin": SELECTED_CASE_ORIGIN,
            "failure_family": TARGET_FAILURE_FAMILY,
            "why": provenance.get("selection_reasons"),
        },
        "rejected_existing_best_alternatives": {
            "4b22_p8_reference_completion": "Independent family but overloaded unattested clauses.",
            "4b2_p8_invented_funeral": "Independent family but 'exactly why' causal confound.",
            "4b2_p13_unsupported_connective": "No supported proposition and no evidence.",
            "historical_positives": "No problematic proposition.",
            "h01_h02": "Already used; statuses remain PARTIAL.",
        },
        "historical_handles_not_reused_as_request_handle": True,
        "h01_handle": H01_CASE_HANDLE,
        "h02_handle": H02_CASE_HANDLE,
        "secrets_included": False,
    }


__all__ = ["candidate_inventory", "candidate_selection_matrix"]
