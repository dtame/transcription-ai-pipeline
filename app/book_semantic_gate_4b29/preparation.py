"""
Deterministic validation-unit preparation.

Reuses the 4B.2.8 conservative segmentation prototype. Does not judge
semantic fidelity. Does not invent evidence. Does not mutate the paragraph.
Offsets are Python 3 Unicode code points, half-open [start, end).
Context is stored once at paragraph level — units are not given a full
paragraph copy.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b28.segmentation import prepare_semantic_validation_units
from app.book_semantic_gate_4b29.constants import OFFSET_CONVENTION, PHASE


def _as_handles(evidence: Sequence[str] | None) -> list[str]:
    handles: list[str] = []
    seen: set[str] = set()
    for item in evidence or ():
        handle = str(item or "").strip()
        if not handle or handle in seen:
            continue
        seen.add(handle)
        handles.append(handle)
    return handles


def prepare_paragraph_units(
    paragraph_id: str,
    text: str,
    *,
    context: Mapping[str, Any] | None = None,
    evidence_handles: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Prepare conservative validation units from a generated paragraph.

    Inputs are the paragraph identifier, original text, optional surrounding
    context, and the canonical evidence handles already authorized for this
    paragraph. Evidence is never invented here.
    """
    pid = str(paragraph_id or "").strip()
    source = text if isinstance(text, str) else str(text or "")
    prototype = prepare_semantic_validation_units(source)
    units: list[dict[str, Any]] = []
    for raw in prototype.get("units") or []:
        units.append(
            {
                "unit_id": str(raw.get("id") or ""),
                "paragraph_id": pid,
                "text": str(raw.get("text") or ""),
                "start_offset": int(raw.get("start_offset") or 0),
                "end_offset": int(raw.get("end_offset") or 0),
                "boundary_type": str(raw.get("boundary_type") or ""),
                "boundary_ambiguity": bool(raw.get("ambiguous")),
            }
        )
    compact_context = {
        "paragraph_id": pid,
        "paragraph": source,
        "unit_order": [unit["unit_id"] for unit in units],
        "surrounding": dict(context) if isinstance(context, Mapping) else {},
    }
    return {
        "phase": PHASE,
        "paragraph_id": pid,
        "paragraph": source,
        "context": compact_context,
        "evidence_handles": _as_handles(evidence_handles),
        "units": units,
        "unit_count": len(units),
        "ambiguous_unit_count": sum(1 for unit in units if unit["boundary_ambiguity"]),
        "boundary_positions": list(prototype.get("boundary_positions") or []),
        "coverage_map_owners": list(prototype.get("coverage_map_owners") or []),
        "prototype_coverage": dict(prototype.get("coverage") or {}),
        "conservative_fallback": bool(prototype.get("conservative_fallback")),
        "paragraph_unchanged": bool(prototype.get("paragraph_unchanged")),
        "offset_convention": OFFSET_CONVENTION,
        "prototype_source": "app.book_semantic_gate_4b28.segmentation",
        "does_not_copy_paragraph_onto_each_unit": True,
        "does_not_modify_paragraph": True,
        "does_not_drop_words": bool(prototype.get("does_not_drop_words")),
        "does_not_invent_evidence": True,
        "does_not_judge_fidelity": True,
        "not_a_semantic_analysis": True,
        "deterministic": True,
        "evidence_level": "DETERMINISTICALLY_VERIFIED",
        "secrets_included": False,
    }


def unit_containing(prepared: Mapping[str, Any], start: int, end: int) -> dict[str, Any] | None:
    for unit in prepared.get("units") or []:
        if int(unit["start_offset"]) <= start and end <= int(unit["end_offset"]):
            return dict(unit)
    return None


def spans_preserved(
    prepared: Mapping[str, Any],
    spans: Sequence[tuple[int, int, str]],
) -> list[dict[str, Any]]:
    rows = []
    for start, end, label in spans:
        unit = unit_containing(prepared, start, end)
        rows.append(
            {
                "label": label,
                "start": start,
                "end": end,
                "preserved_in_one_unit": unit is not None,
                "unit_id": None if unit is None else unit["unit_id"],
                "unit_text": None if unit is None else unit["text"],
                "evidence_level": "DETERMINISTICALLY_VERIFIED",
            }
        )
    return rows


__all__ = ["prepare_paragraph_units", "spans_preserved", "unit_containing"]
