"""Deterministic coverage and offset validation. No provider call."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_semantic_gate_4b28.segmentation import CONNECTOR_TOKENS, WORD_RE
from app.book_semantic_gate_4b29.constants import OFFSET_CONVENTION, OFFSET_CONVENTION_NOTES, PHASE


def _errors() -> list[str]:
    return []


def validate_prepared_coverage(prepared: Mapping[str, Any]) -> dict[str, Any]:
    """Verify unit slices, order, coverage, and absence of unauthorized overlap."""
    errors = _errors()
    paragraph = str(prepared.get("paragraph") or "")
    units = list(prepared.get("units") or [])
    convention = str(prepared.get("offset_convention") or "")
    if convention != OFFSET_CONVENTION:
        errors.append(f"offset_convention:{convention or 'missing'}")

    reconstructed_parts: list[str] = []
    previous_end = 0
    overlaps: list[dict[str, Any]] = []
    exact_slice_failures: list[str] = []
    order_failures: list[str] = []
    seen_ids: set[str] = set()
    duplicate_ids: list[str] = []

    for index, unit in enumerate(units):
        uid = str(unit.get("unit_id") or "")
        start = int(unit.get("start_offset") or 0)
        end = int(unit.get("end_offset") or 0)
        text = str(unit.get("text") or "")
        if uid in seen_ids:
            duplicate_ids.append(uid)
        seen_ids.add(uid)
        if start < 0 or end < start or end > len(paragraph):
            errors.append(f"{uid}:offset_range")
        if paragraph[start:end] != text:
            exact_slice_failures.append(uid)
            errors.append(f"{uid}:slice_mismatch")
        if index == 0 and start != 0:
            order_failures.append(f"{uid}:not_at_origin")
            errors.append(f"{uid}:not_at_origin")
        if start < previous_end:
            overlaps.append(
                {
                    "unit_id": uid,
                    "start_offset": start,
                    "previous_end": previous_end,
                }
            )
            errors.append(f"{uid}:unauthorized_overlap")
        if index > 0 and start != previous_end:
            errors.append(f"{uid}:gap_or_reordered")
            order_failures.append(uid)
        reconstructed_parts.append(text)
        previous_end = end

    reconstructed = "".join(reconstructed_parts)
    if units and previous_end != len(paragraph):
        errors.append("trailing_gap")
    if not units and paragraph:
        errors.append("missing_units")
    if reconstructed != paragraph:
        errors.append("character_loss")

    mapping = [""] * len(paragraph)
    for unit in units:
        uid = str(unit.get("unit_id") or "")
        start = int(unit.get("start_offset") or 0)
        end = int(unit.get("end_offset") or 0)
        for index in range(max(0, start), min(len(paragraph), end)):
            mapping[index] = uid
    uncovered = [index for index, owner in enumerate(mapping) if not owner]
    words = [(match.start(), match.end(), match.group(0)) for match in WORD_RE.finditer(paragraph)]
    uncovered_words = []
    for start, end, token in words:
        owners = {mapping[index] for index in range(start, end) if index < len(mapping)}
        if len(owners) != 1 or not next(iter(owners)):
            uncovered_words.append({"token": token, "start": start, "end": end})

    connector_rows = []
    lower = paragraph.lower()
    for token in CONNECTOR_TOKENS:
        start = 0
        while True:
            found = lower.find(token, start)
            if found < 0:
                break
            end = found + len(token)
            before_ok = found == 0 or not paragraph[found - 1].isalnum()
            after_ok = end >= len(paragraph) or not paragraph[end].isalnum()
            if before_ok and after_ok:
                owners = {
                    str(unit.get("unit_id") or "")
                    for unit in units
                    if int(unit.get("start_offset") or 0) <= found
                    and end <= int(unit.get("end_offset") or 0)
                }
                row = {
                    "token": token,
                    "start": found,
                    "end": end,
                    "fully_inside_one_unit": len(owners) == 1,
                    "owners": sorted(owners),
                }
                connector_rows.append(row)
                if not row["fully_inside_one_unit"]:
                    errors.append(f"connector_split:{token}:{found}")
            start = found + 1

    ids = [str(unit.get("unit_id") or "") for unit in units]
    expected_ids = [f"u{index:02d}" for index in range(len(units))]
    if ids != expected_ids:
        errors.append("unstable_unit_ids")
    if duplicate_ids:
        errors.append("duplicate_unit_ids")

    complete = (
        not uncovered
        and reconstructed == paragraph
        and not exact_slice_failures
        and not overlaps
        and not uncovered_words
        and (previous_end == len(paragraph) if units else not paragraph)
    )
    ok = not errors and complete
    return {
        "phase": PHASE,
        "ok": ok,
        "status": "PASS" if ok else "BLOCK",
        "offset_convention": OFFSET_CONVENTION,
        "offset_convention_notes": dict(OFFSET_CONVENTION_NOTES),
        "paragraph_id": prepared.get("paragraph_id"),
        "char_count": len(paragraph),
        "utf8_byte_count": len(paragraph.encode("utf-8")),
        "utf16_code_unit_count": len(paragraph.encode("utf-16-le")) // 2,
        "unit_count": len(units),
        "reconstructed_equals_paragraph": reconstructed == paragraph,
        "complete_chars": not uncovered and reconstructed == paragraph,
        "complete_words": not uncovered_words,
        "uncovered_char_indexes": uncovered,
        "uncovered_words": uncovered_words,
        "unauthorized_overlaps": overlaps,
        "exact_slice_failures": exact_slice_failures,
        "order_failures": order_failures,
        "duplicate_ids": duplicate_ids,
        "connector_coverage": {
            "occurrences": connector_rows,
            "present_count": len(connector_rows),
            "fully_covered_count": sum(1 for item in connector_rows if item["fully_inside_one_unit"]),
            "split_across_units": [item for item in connector_rows if not item["fully_inside_one_unit"]],
        },
        "separators_retained": reconstructed == paragraph,
        "errors": errors,
        "does_not_repair": True,
        "secrets_included": False,
    }


__all__ = ["validate_prepared_coverage"]
