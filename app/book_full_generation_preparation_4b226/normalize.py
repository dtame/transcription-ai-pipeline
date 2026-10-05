"""
Deterministic empty-paragraph normalization.

Removes a paragraph only when every admissibility condition is demonstrated.
Never rewrites prose. Never renumbers. Never mutates the raw provider response.
Never fabricates provenance. Idempotent.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from app.book_ch002_offline_recovery_4b224.chapter_io import (
    deepcopy_chapter,
    idea_handles,
    iter_candidate_paragraphs,
    paragraph_ids,
)
from app.book_full_generation_preparation_4b226.constants import (
    ACCEPTED_CHAPTER_IDS,
    ATTRIBUTION_KEYS,
    CITATION_KEYS,
    NORMALIZER_VERSION,
    PHASE,
    PROVENANCE_FIELDS,
    STRUCTURAL_PARAGRAPH_KEYS,
)
from app.book_generation.evidence import classify_handle


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []


def _json_safe_values(payload: Any) -> str:
    if isinstance(payload, Mapping):
        return " ".join(_json_safe_values(value) for value in payload.values())
    if isinstance(payload, (list, tuple)):
        return " ".join(_json_safe_values(value) for value in payload)
    return str(payload)


def inspect_paragraph(paragraph: Mapping[str, Any] | None) -> dict[str, Any]:
    if paragraph is None:
        return {
            "exists": False,
            "empty": False,
            "whitespace_only": False,
            "has_editorial_content": False,
            "contains_idea": False,
            "contains_src": False,
            "contains_ex": False,
            "contains_ref": False,
            "contains_unc": False,
            "contains_attribution": False,
            "contains_citation": False,
            "unknown_metadata_keys": [],
            "has_significant_editorial_metadata": False,
        }
    text = paragraph.get("text")
    if text is None and paragraph.get("t") is not None:
        text = paragraph.get("t")
    text_str = "" if text is None else str(text)
    empty = text_str.strip() == ""
    handles: list[str] = []
    for field in PROVENANCE_FIELDS:
        handles.extend(_as_list(paragraph.get(field)))
    classified = [classify_handle(handle) for handle in handles]
    unknown_keys = sorted(
        key
        for key in paragraph.keys()
        if key not in STRUCTURAL_PARAGRAPH_KEYS
        and key not in ATTRIBUTION_KEYS
        and key not in CITATION_KEYS
    )
    attribution_present = any(key in paragraph for key in ATTRIBUTION_KEYS)
    citation_present = any(key in paragraph for key in CITATION_KEYS)
    return {
        "exists": True,
        "paragraph_id": paragraph.get("paragraph_id"),
        "text": text,
        "text_length": len(text_str),
        "empty": empty,
        "whitespace_only": bool(text_str) and empty,
        "has_editorial_content": not empty,
        "handles": handles,
        "classified_handle_kinds": classified,
        "contains_idea": "IDEA" in classified or bool(_as_list(paragraph.get("idea_refs"))),
        "contains_src": "SRC" in classified or bool(_as_list(paragraph.get("source_refs"))),
        "contains_ex": "EX" in classified or bool(_as_list(paragraph.get("example_refs"))),
        "contains_ref": "REF" in classified or bool(_as_list(paragraph.get("reference_refs"))),
        "contains_unc": "UNC" in classified or bool(_as_list(paragraph.get("uncertainty_refs"))),
        "contains_attribution": attribution_present,
        "contains_citation": citation_present,
        "unknown_metadata_keys": unknown_keys,
        "has_significant_editorial_metadata": bool(
            attribution_present or citation_present or unknown_keys
        ),
        "keys": sorted(paragraph.keys()),
    }


def referenced_elsewhere(
    chapter: Mapping[str, Any],
    *,
    paragraph_id: str,
    section_id: str,
    index: int,
) -> list[str]:
    if not paragraph_id:
        return []
    found: list[str] = []
    for other_section in chapter.get("sections") or []:
        other_section_id = str(other_section.get("section_id") or "")
        section_copy = dict(other_section)
        paragraphs = list(section_copy.get("paragraphs") or [])
        for other_index, other in enumerate(paragraphs):
            if other_section_id == section_id and other_index == index:
                continue
            if paragraph_id in _json_safe_values(other):
                found.append(str(other.get("paragraph_id") or other_section_id))
        section_meta = {
            key: value for key, value in other_section.items() if key != "paragraphs"
        }
        if paragraph_id in _json_safe_values(section_meta):
            found.append(other_section_id or "section")
    chapter_meta = {key: value for key, value in chapter.items() if key != "sections"}
    if paragraph_id in _json_safe_values(chapter_meta):
        found.append("chapter")
    return found


def removal_is_admissible(
    inspection: Mapping[str, Any],
    *,
    dependents: list[str] | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not inspection.get("exists"):
        reasons.append("paragraph does not exist")
    if not inspection.get("empty"):
        reasons.append("paragraph is not empty")
    if inspection.get("has_editorial_content"):
        reasons.append("paragraph has editorial content")
    if inspection.get("contains_idea"):
        reasons.append("paragraph carries an IDEA handle")
    if inspection.get("contains_src"):
        reasons.append("paragraph carries a SRC handle")
    if inspection.get("contains_ex"):
        reasons.append("paragraph carries an EX handle")
    if inspection.get("contains_ref"):
        reasons.append("paragraph carries a REF handle")
    if inspection.get("contains_unc"):
        reasons.append("paragraph carries a UNC handle")
    if inspection.get("contains_attribution"):
        reasons.append("paragraph carries attribution")
    if inspection.get("contains_citation"):
        reasons.append("paragraph carries a citation")
    if inspection.get("unknown_metadata_keys"):
        reasons.append(
            "paragraph carries unknown metadata: "
            + ",".join(inspection.get("unknown_metadata_keys") or [])
        )
    if inspection.get("has_significant_editorial_metadata") and not reasons:
        reasons.append("paragraph carries significant editorial metadata")
    if dependents:
        reasons.append("paragraph id is referenced by another object")
    return (not reasons), reasons


def normalize_empty_paragraphs(
    chapter: Mapping[str, Any],
    *,
    raw_response: Mapping[str, Any] | None = None,
    protect_accepted: bool = True,
) -> dict[str, Any]:
    original = deepcopy_chapter(dict(chapter))
    raw_copy = deepcopy(raw_response) if raw_response is not None else None
    chapter_id = str(original.get("chapter_id") or "")
    if protect_accepted and chapter_id in ACCEPTED_CHAPTER_IDS:
        return {
            "phase": PHASE,
            "normalizer_version": NORMALIZER_VERSION,
            "chapter_id": chapter_id,
            "accepted_chapter_protected": True,
            "changed": False,
            "removed_paragraph_ids": [],
            "refused": [],
            "derived": original,
            "raw_response_unchanged": True,
            "ids_renumbered": False,
            "other_paragraphs_modified": False,
            "prose_rewritten": False,
            "provenance_fabricated": False,
            "idempotent_input": True,
            "artifact_kind": "UNCHANGED_ACCEPTED_CHAPTER",
            "not_provider_original": True,
            "secrets_included": False,
        }

    derived = deepcopy_chapter(original)
    removed: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    for section in derived.get("sections") or []:
        section_id = str(section.get("section_id") or "")
        kept: list[dict[str, Any]] = []
        for index, paragraph in enumerate(list(section.get("paragraphs") or [])):
            inspection = inspect_paragraph(paragraph)
            dependents = referenced_elsewhere(
                original,
                paragraph_id=str(paragraph.get("paragraph_id") or ""),
                section_id=section_id,
                index=index,
            )
            admissible, reasons = removal_is_admissible(
                inspection, dependents=dependents
            )
            if admissible:
                removed.append(
                    {
                        "paragraph_id": paragraph.get("paragraph_id"),
                        "section_id": section_id,
                        "index": index,
                        "reasons": ["strictly_empty_unprovenanced_unreferenced"],
                    }
                )
                continue
            if inspection.get("empty"):
                refused.append(
                    {
                        "paragraph_id": paragraph.get("paragraph_id"),
                        "section_id": section_id,
                        "reasons": reasons,
                    }
                )
            kept.append(paragraph)
        section["paragraphs"] = kept

    before_ids = paragraph_ids(original)
    after_ids = paragraph_ids(derived)
    removed_ids = [str(row["paragraph_id"] or "") for row in removed]
    expected_after = [item for item in before_ids if item not in removed_ids]
    other_ids_unchanged = after_ids == expected_after
    remaining_before = [
        (section_id, dict(paragraph))
        for section_id, _index, paragraph in iter_candidate_paragraphs(original)
        if str(paragraph.get("paragraph_id") or "") not in removed_ids
    ]
    remaining_after = [
        (section_id, dict(paragraph))
        for section_id, _index, paragraph in iter_candidate_paragraphs(derived)
    ]
    other_paragraphs_modified = remaining_before != remaining_after
    ideas_before = sorted(set(idea_handles(original)))
    ideas_after = sorted(set(idea_handles(derived)))
    raw_unchanged = raw_copy == raw_response if raw_response is not None else True
    changed = bool(removed)
    return {
        "phase": PHASE,
        "normalizer_version": NORMALIZER_VERSION,
        "chapter_id": chapter_id,
        "accepted_chapter_protected": False,
        "changed": changed,
        "removed_paragraph_ids": removed_ids,
        "removed": removed,
        "refused": refused,
        "derived": derived,
        "original_paragraph_ids": before_ids,
        "derived_paragraph_ids": after_ids,
        "ids_renumbered": False,
        "other_paragraph_ids_unchanged": other_ids_unchanged,
        "other_paragraphs_modified": other_paragraphs_modified,
        "prose_rewritten": False,
        "provenance_fabricated": False,
        "ideas_before": ideas_before,
        "ideas_after": ideas_after,
        "idea_coverage_unchanged": ideas_before == ideas_after,
        "raw_response_unchanged": raw_unchanged,
        "raw_response": raw_copy,
        "artifact_kind": "OFFLINE_DERIVED_ARTIFACT",
        "not_provider_original": True,
        "secrets_included": False,
    }


def normalize_empty_paragraphs_idempotent(
    chapter: Mapping[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    first = normalize_empty_paragraphs(chapter, **kwargs)
    second = normalize_empty_paragraphs(first["derived"], **kwargs)
    first["idempotent"] = (
        second["changed"] is False
        and second["removed_paragraph_ids"] == []
        and second["derived_paragraph_ids"] == first["derived_paragraph_ids"]
    )
    first["second_pass"] = {
        "changed": second["changed"],
        "removed_paragraph_ids": second["removed_paragraph_ids"],
    }
    return first


def normalizer_spec() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "name": "strip_strictly_empty_unprovenanced_paragraphs",
        "version": NORMALIZER_VERSION,
        "authorized_in_this_phase": True,
        "integration_point": (
            "After durable save of the raw provider response and after "
            "materialization of the derived candidate, before the existing "
            "production structural validator runs."
        ),
        "does_not_modify_production_validator": True,
        "does_not_modify_raw_provider_response": True,
        "does_not_modify_accepted_chapters": True,
        "idempotent": True,
        "applies_only_when": [
            "text is empty or whitespace-only",
            "no IDEA identifier",
            "no SRC identifier",
            "no EX identifier",
            "no REF identifier",
            "no UNC identifier",
            "no attribution, citation, or other significant editorial metadata",
            "no other object depends on the paragraph identifier",
            "removal does not modify remaining paragraphs",
            "full structural validation succeeds afterwards",
        ],
        "never": [
            "modify the raw provider response",
            "delete a paragraph that contains an idea",
            "delete a paragraph that contains evidence",
            "delete a paragraph with significant metadata",
            "renumber existing identifiers",
            "rewrite prose",
            "fabricate provenance",
            "convert a semantic failure into a structural success",
        ],
        "after_strip": [
            "run the existing production structural validator",
            "keep the original response immutable",
            "label the result OFFLINE_DERIVED_ARTIFACT / NOT_PROVIDER_ORIGINAL",
            "reject the candidate if the validator fails",
        ],
        "secrets_included": False,
    }


__all__ = [
    "inspect_paragraph",
    "normalize_empty_paragraphs",
    "normalize_empty_paragraphs_idempotent",
    "normalizer_spec",
    "referenced_elsewhere",
    "removal_is_admissible",
]
