"""Unit integrity and context preservation for Semantic Gate 2.0 requests."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b28.canaries import load_canary_bundle
from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b29.preparation import prepare_paragraph_units, spans_preserved
from app.book_semantic_gate_4b210.constants import (
    DISPUTED_CAUSAL_CLAUSE,
    H01_CASE_HANDLE,
    H01_DISPUTED_CLAUSE,
    H01_EVIDENCE_HANDLES,
    H02_CASE_HANDLE,
    H02_EVIDENCE_HANDLES,
    H11_CASE_HANDLE,
    H11_DISPUTED_CLAUSE,
    H11_EVIDENCE_HANDLES,
    OFFSET_CONVENTION,
    PHASE,
    SELECTED_CASE_HANDLE,
)


def _evidence_for(handle: str) -> tuple[str, ...]:
    mapping = {
        H01_CASE_HANDLE: H01_EVIDENCE_HANDLES,
        H02_CASE_HANDLE: H02_EVIDENCE_HANDLES,
        H11_CASE_HANDLE: H11_EVIDENCE_HANDLES,
    }
    return tuple(mapping[handle])


def _spans(handle: str, text: str) -> list[tuple[int, int, str]]:
    rows: list[tuple[int, int, str]] = []
    needles = {
        H01_CASE_HANDLE: ((H01_DISPUTED_CLAUSE, "bargain_clause"),),
        H02_CASE_HANDLE: ((DISPUTED_CAUSAL_CLAUSE, "because_clause"),),
        H11_CASE_HANDLE: ((H11_DISPUTED_CLAUSE, "universal_guarantee"),),
    }
    for needle, label in needles.get(handle) or ():
        start = text.find(needle)
        if start >= 0:
            rows.append((start, start + len(needle), label))
    return rows


def _negation_and_condition_flags(text: str) -> dict[str, bool]:
    lowered = text.lower()
    return {
        "negation_present": any(
            token in lowered.split() or f" {token} " in f" {lowered} "
            for token in ("not", "never", "no", "n't")
        )
        or "n't" in lowered
        or " not " in f" {lowered} ",
        "condition_present": lowered.startswith("if ") or " if " in lowered,
        "causal_present": "because" in lowered or "therefore" in lowered,
        "reference_present": '"' in text or "“" in text or "said" in lowered,
    }


def inspect_prepared_case(handle: str, *, root=None) -> dict[str, Any]:
    bundle = load_canary_bundle(root=root)
    case = dict(bundle.get(handle) or {})
    text = str(case.get("text") or "")
    prepared = prepare_paragraph_units(
        handle,
        text,
        evidence_handles=list(_evidence_for(handle)),
    )
    coverage = validate_prepared_coverage(prepared)
    preserved = spans_preserved(prepared, _spans(handle, text))
    flags = _negation_and_condition_flags(text)
    return {
        "handle": handle,
        "paragraph_chars": len(text),
        "unit_count": prepared.get("unit_count"),
        "unit_ids": [unit.get("unit_id") for unit in prepared.get("units") or []],
        "coverage_ok": coverage.get("ok"),
        "complete_chars": coverage.get("complete_chars"),
        "complete_words": coverage.get("complete_words"),
        "reconstructed_equals_paragraph": coverage.get("reconstructed_equals_paragraph"),
        "separators_retained": coverage.get("separators_retained"),
        "connector_split": coverage.get("connector_coverage", {}).get("split_across_units") or [],
        "offset_convention": prepared.get("offset_convention"),
        "paragraph_unchanged": prepared.get("paragraph_unchanged"),
        "does_not_copy_paragraph_onto_each_unit": prepared.get(
            "does_not_copy_paragraph_onto_each_unit"
        ),
        "context_paragraph_once": str((prepared.get("context") or {}).get("paragraph") or "")
        == text,
        "preserved_propositions": preserved,
        "flags": flags,
        "errors": coverage.get("errors") or [],
        "units": [
            {
                "unit_id": unit.get("unit_id"),
                "start_offset": unit.get("start_offset"),
                "end_offset": unit.get("end_offset"),
                "text": unit.get("text"),
                "boundary_type": unit.get("boundary_type"),
            }
            for unit in prepared.get("units") or []
        ],
        "prepared": prepared,
        "coverage": coverage,
    }


def unit_integrity_review(*, root=None) -> dict[str, Any]:
    h01 = inspect_prepared_case(H01_CASE_HANDLE, root=root)
    h02 = inspect_prepared_case(H02_CASE_HANDLE, root=root)
    h11 = inspect_prepared_case(H11_CASE_HANDLE, root=root)
    selected = h01 if SELECTED_CASE_HANDLE == H01_CASE_HANDLE else None
    ok = all(item.get("coverage_ok") for item in (h01, h02, h11))
    return {
        "phase": PHASE,
        "offset_convention": OFFSET_CONVENTION,
        "offsets_owned_by_python": True,
        "model_must_not_emit_offsets": True,
        "h01": {key: value for key, value in h01.items() if key not in {"prepared", "coverage"}},
        "h02": {key: value for key, value in h02.items() if key not in {"prepared", "coverage"}},
        "h11": {key: value for key, value in h11.items() if key not in {"prepared", "coverage"}},
        "selected_handle": SELECTED_CASE_HANDLE,
        "selected_coverage_ok": bool(selected and selected.get("coverage_ok")),
        "words_not_lost": ok,
        "connectors_preserved": not any(
            item.get("connector_split") for item in (h01, h02, h11)
        ),
        "context_preservation": "PARAGRAPH_ONCE_PLUS_UNIT_TEXTS",
        "ok": ok,
        "secrets_included": False,
        "_prepared_selected": selected.get("prepared") if selected else None,
        "_coverage_selected": selected.get("coverage") if selected else None,
        "_text_selected": str(
            ((load_canary_bundle(root=root).get(SELECTED_CASE_HANDLE) or {}).get("text") or "")
        ),
    }


__all__ = ["inspect_prepared_case", "unit_integrity_review"]
