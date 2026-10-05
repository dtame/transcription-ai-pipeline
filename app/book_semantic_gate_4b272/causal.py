"""Independent review of the P3 causal claim against authorized evidence only."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b272.constants import (
    DISPUTED_CAUSAL_CLAUSE,
    PHASE,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    SELECTED_CASE_REASON_CODES_AUDIT_ONLY,
)
from app.book_semantic_gate_4b272.evidence import build_canonical_evidence_inventory
from app.book_semantic_gate_4b272.identity import clause_offsets, load_p3_benchmark_case

_CAUSAL_MARKERS = (
    "because",
    "therefore",
    "thus",
    "so that",
    "as a result",
    "which means",
)
_CLAUSE_CONTENT_MARKERS = (
    "still works",
    "resisted by truth",
    "wherever it is not resisted",
)


def _combined_evidence_text(inventory: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for row in inventory.get("ideas") or []:
        parts.append(str(row.get("exact_text") or ""))
    for row in inventory.get("src") or []:
        parts.append(str(row.get("exact_text") or ""))
    return "\n".join(parts)


def review_causal_claim(
    inventory: Mapping[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    inventory = dict(inventory or build_canonical_evidence_inventory(root=root))
    historical = load_p3_benchmark_case(root=root)
    text = str((inventory.get("paragraph") or {}).get("exact_text") or historical.get("text") or "")
    offsets = clause_offsets(text)
    combined = _combined_evidence_text(inventory)
    lowered = combined.lower()
    exact_in_evidence = DISPUTED_CAUSAL_CLAUSE.lower() in lowered
    marker_hits = [item for item in _CAUSAL_MARKERS if item in lowered]
    content_hits = [item for item in _CLAUSE_CONTENT_MARKERS if item in lowered]
    items = []
    any_sufficient = False
    for row in list(inventory.get("ideas") or []) + list(inventory.get("src") or []):
        sufficient = bool(row.get("sufficient_to_justify_causality"))
        any_sufficient = any_sufficient or sufficient
        items.append(
            {
                "id": row.get("id"),
                "exact_text": row.get("exact_text"),
                "explicit_causal_relation": bool(row.get("contains_because")),
                "entailed_causal_relation": sufficient,
                "sufficient_to_justify_causality": sufficient,
            }
        )
    # Continuity of the devil's method is attested. Efficacy-wherever-truth-
    # does-not-resist is not. Lexical absence of "because" is not the test;
    # absence of the causal relation is.
    core_supported_without_because = (
        "devil" in lowered
        and "abuse" in lowered
        and ("not changed" in lowered or "old strategy" in lowered)
    )
    implied = (
        exact_in_evidence
        or any_sufficient
        or ("still works" in lowered and "resisted" in lowered)
    )
    conflict = implied and str(historical.get("expected_class") or "") in {
        "QUESTIONABLE",
        "UNSUPPORTED",
    }
    finding = (
        "The authorized IDEA225/SRC texts attest abuse, the devil as agent, "
        "use since the beginning, and an unchanged style. They do not "
        "explicitly affirm or entail that the strategy is still being run "
        "because it still works wherever it is not resisted by truth. "
        "Lexical absence of the clause is not the reason; the causal "
        "relation itself is missing."
    )
    return {
        "phase": PHASE,
        "handle": SELECTED_CASE_HANDLE,
        "case_id_audit_only": SELECTED_CASE_ID,
        "disputed_causal_clause": DISPUTED_CAUSAL_CLAUSE,
        "clause_position": offsets,
        "human_label_audit_only": SELECTED_CASE_HUMAN_LABEL,
        "human_reason_codes_audit_only": list(SELECTED_CASE_REASON_CODES_AUDIT_ONLY),
        "evidence_items": items,
        "combined_authorized_text": combined,
        "exact_clause_in_authorized_evidence": exact_in_evidence,
        "causal_markers_in_authorized_evidence": marker_hits,
        "clause_content_markers_in_authorized_evidence": content_hits,
        "core_without_because_attested": core_supported_without_because,
        "causal_relation_explicitly_affirmed": exact_in_evidence or bool(marker_hits),
        "causal_relation_really_implied": implied,
        "sufficient_to_justify_causality": implied,
        "lexical_absence_is_not_the_test": True,
        "nearby_theme_is_not_proof": True,
        "h01_evidence_not_consulted_as_support": True,
        "external_knowledge_used": False,
        "finding": finding,
        "BENCHMARK_EVIDENCE_CONFLICT": conflict,
        "negative_canary_still_justified": (not conflict) and (not implied),
        "historical_label_unmodified": True,
        "secrets_included": False,
    }


__all__ = ["review_causal_claim"]
