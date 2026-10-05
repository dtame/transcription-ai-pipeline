"""Deterministic preparation audit using the validated 4B.2.8 / 4B.2.9 path."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation_integration_4b213.constants import (
    OFFSET_CONVENTION,
    OFFSET_CONVENTION_NOTES,
    PHASE,
    PREPARATION_ALGORITHM_VERSION,
)
from app.book_generation_integration_4b213.fixtures import TEXTS, build_synthetic_chapter
from app.book_generation_integration_4b213.structure import iter_paragraphs
from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b29.preparation import prepare_paragraph_units, spans_preserved


def _span(text: str, needle: str) -> tuple[int, int, str] | None:
    start = text.find(needle)
    if start < 0:
        return None
    return (start, start + len(needle), needle)


def deterministic_preparation(*, chapter: Mapping[str, Any] | None = None) -> dict[str, Any]:
    chapter = chapter or build_synthetic_chapter("invented_causality")
    rows = []
    ok = True
    for para in iter_paragraphs(chapter):
        prepared = prepare_paragraph_units(
            str(para.get("paragraph_id") or ""),
            str(para.get("text") or ""),
            evidence_handles=list(para.get("evidence_handles") or []),
        )
        coverage = validate_prepared_coverage(prepared)
        text = str(para.get("text") or "")
        checks = []
        for needle in (
            "because",
            "which means",
            "guaranteed",
            "not",
            "unless",
            "however",
        ):
            span = _span(text, needle)
            if span is None:
                continue
            preserved = spans_preserved(prepared, [span])
            checks.extend(preserved)
            if not all(item.get("preserved_in_one_unit") for item in preserved):
                ok = False
        reconstructed = "".join(str(unit.get("text") or "") for unit in prepared.get("units") or [])
        if reconstructed != text or not coverage.get("ok"):
            ok = False
        rows.append(
            {
                "paragraph_id": para.get("paragraph_id"),
                "unit_count": prepared.get("unit_count"),
                "coverage_ok": coverage.get("ok"),
                "reconstructed_equals_paragraph": reconstructed == text,
                "offset_convention": prepared.get("offset_convention"),
                "stable_ids": [
                    str(unit.get("unit_id") or "") for unit in prepared.get("units") or []
                ],
                "preservation": checks,
                "does_not_ask_model_for_offsets": True,
            }
        )
    return {
        "phase": PHASE,
        "algorithm_version": PREPARATION_ALGORITHM_VERSION,
        "prototype_source": "app.book_semantic_gate_4b28.segmentation via app.book_semantic_gate_4b29.preparation",
        "offset_convention": OFFSET_CONVENTION,
        "offset_convention_notes": dict(OFFSET_CONVENTION_NOTES),
        "paragraphs": rows,
        "complete_coverage": ok and all(item.get("coverage_ok") for item in rows),
        "words_connectors_negations_conditions_causality_context_preserved": ok,
        "ok": ok,
        "sample_texts_used": {
            "invented_causality": TEXTS["invented_causality"],
            "invented_implication": TEXTS["invented_implication"],
            "universal_guarantee": TEXTS["universal_guarantee"],
        },
        "secrets_included": False,
    }


__all__ = ["deterministic_preparation"]
