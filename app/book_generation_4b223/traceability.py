"""IDEA / EX / REF / UNC / SRC handle review. Does not rewrite paras[].e."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from app.book_generation.evidence import classify_handle
from app.book_generation_4b223.constants import PHASE
from app.book_generation_4b223.inventory import ChapterSpec


def _handles_from_raw(raw_parsed: Mapping[str, Any] | None, kind: str) -> list[str]:
    found: list[str] = []
    if not isinstance(raw_parsed, Mapping):
        return found
    for section in raw_parsed.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        for paragraph in section.get("paras") or []:
            if not isinstance(paragraph, Mapping):
                continue
            for handle in paragraph.get("e") or []:
                if classify_handle(str(handle)) == kind:
                    found.append(str(handle))
    return found


def _handles_from_candidate(payload: Mapping[str, Any] | None, kind: str) -> list[str]:
    found: list[str] = []
    if not isinstance(payload, Mapping):
        return found
    for section in payload.get("sections") or []:
        for paragraph in section.get("paragraphs") or []:
            bags = []
            bags.extend(paragraph.get("evidence_handles") or [])
            if kind == "IDEA":
                bags.extend(paragraph.get("idea_refs") or [])
            if kind == "EX":
                bags.extend(paragraph.get("example_refs") or [])
            if kind == "REF":
                bags.extend(paragraph.get("reference_refs") or [])
            if kind == "UNC":
                bags.extend(paragraph.get("uncertainty_refs") or [])
            if kind == "SRC":
                bags.extend(paragraph.get("source_refs") or [])
            for handle in bags:
                if classify_handle(str(handle)) == kind:
                    found.append(str(handle))
    return found


def _classify_element(handle: str, traced: set[str], expected: set[str]) -> str:
    if handle in traced:
        return "present_and_traced"
    if handle in expected:
        return "undetermined_handle_absent_is_not_omission"
    return "unknown"


def idea_traceability_review(
    *,
    spec: ChapterSpec,
    candidate_payload: Mapping[str, Any] | None,
    raw_parsed: Mapping[str, Any] | None,
    structural: Mapping[str, Any],
    allowed_handles: list[str],
) -> dict[str, Any]:
    checks = dict(structural.get("checks") or {})
    raw_e = _handles_from_raw(raw_parsed, "IDEA")
    candidate_e = _handles_from_candidate(candidate_payload, "IDEA")
    found = sorted(
        set(raw_e)
        | set(candidate_e)
        | set(checks.get("ideas_in_paragraph_evidence") or [])
    )
    expected = list(spec.idea_ids)
    invalid = [handle for handle in found if handle not in set(expected)]
    unknown = [handle for handle in found if handle not in set(allowed_handles)]
    missing = [idea_id for idea_id in expected if idea_id not in set(found)]
    out_of_chapter = [handle for handle in found if handle not in set(expected)]
    counts = Counter(raw_e + candidate_e)
    duplicates = sorted(handle for handle, count in counts.items() if count > 1)
    return {
        "phase": PHASE,
        "chapter_id": spec.chapter_id,
        "ideas_expected": expected,
        "ideas_expected_count": spec.idea_count,
        "ideas_found_in_paras_e": found,
        "ideas_found_count": len(found),
        "ideas_missing_from_paras_e": missing,
        "ideas_invalid": invalid,
        "ideas_unknown": unknown,
        "ideas_out_of_chapter": out_of_chapter,
        "ideas_duplicated": duplicates,
        "ideas_in_section_metadata_only": list(checks.get("ideas_metadata_only") or []),
        "src_handles_invalid": list(checks.get("invalid_src") or []),
        "unknown_identifiers": list(checks.get("unknown_identifiers") or []),
        "provider_response_modified": False,
        "handles_auto_filled": False,
        "identifier_alone_is_not_restatement": True,
        "semantic_certification": "NOT PERFORMED",
        "note": (
            "This review checks contract handles in paras[].e. "
            "It does not certify that the planned ideas were faithfully restated."
        ),
        "secrets_included": False,
    }


def ex_ref_traceability_review(
    *,
    spec: ChapterSpec,
    candidate_payload: Mapping[str, Any] | None,
    raw_parsed: Mapping[str, Any] | None,
    allowed_handles: list[str],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    kinds = (
        ("EX", spec.example_ids),
        ("REF", spec.reference_ids),
        ("UNC", spec.uncertainty_ids),
        ("SRC", spec.src_ids),
    )
    blocking_omission = False
    for kind, expected in kinds:
        traced = set(_handles_from_raw(raw_parsed, kind)) | set(
            _handles_from_candidate(candidate_payload, kind)
        )
        for handle in expected:
            status = _classify_element(handle, traced, set(expected))
            rows.append(
                {
                    "kind": kind,
                    "id": handle,
                    "status": status,
                    "traced": handle in traced,
                    "in_allowed_handles": handle in set(allowed_handles),
                }
            )
        unexpected = sorted(traced.difference(expected)) if kind != "SRC" else []
        for handle in unexpected:
            rows.append(
                {
                    "kind": kind,
                    "id": handle,
                    "status": "unknown_or_out_of_chapter",
                    "traced": True,
                    "in_allowed_handles": handle in set(allowed_handles),
                }
            )
    return {
        "phase": PHASE,
        "chapter_id": spec.chapter_id,
        "items": rows,
        "example_absence_is_not_automatic_omission": True,
        "ch018_lesson_applied": True,
        "provenance_invented": False,
        "provider_response_modified": False,
        "blocking_substantive_omission_established": blocking_omission,
        "semantic_certification": "NOT PERFORMED",
        "note": (
            "A missing EX/REF handle is not treated as a content omission. "
            "CH018 showed EX046 could be present in prose without a handle."
        ),
        "secrets_included": False,
    }


__all__ = ["ex_ref_traceability_review", "idea_traceability_review"]
