"""Deterministic empty-paragraph removal. No editorial rewrite. No renumbering."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_ch002_offline_recovery_4b224.chapter_io import (
    deepcopy_chapter,
    find_candidate_paragraph,
    idea_handles,
    iter_candidate_paragraphs,
    paragraph_ids,
)
from app.book_ch002_offline_recovery_4b224.constants import (
    ARTIFACT_KIND,
    EMPTY_PARAGRAPH_ID,
    EMPTY_PROVIDER_HANDLE,
    EMPTY_SECTION_ID,
    NOT_ORIGINAL,
    PHASE,
    TARGET_CHAPTER_ID,
)
from app.book_ch002_offline_recovery_4b224.guard import BookCh002OfflineRecovery4224Error
from app.book_generation.evidence import classify_handle

PROVENANCE_FIELDS = (
    "evidence_handles",
    "source_refs",
    "idea_refs",
    "example_refs",
    "reference_refs",
    "uncertainty_refs",
)


def _handles(paragraph: Mapping[str, Any]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {field: [] for field in PROVENANCE_FIELDS}
    grouped["classified"] = []
    for field in PROVENANCE_FIELDS:
        for handle in paragraph.get(field) or []:
            text = str(handle)
            grouped[field].append(text)
            grouped["classified"].append(classify_handle(text))
    return grouped


def inspect_paragraph(paragraph: Mapping[str, Any] | None) -> dict[str, Any]:
    if paragraph is None:
        return {
            "exists": False,
            "text": None,
            "text_repr": None,
            "text_length": 0,
            "whitespace_only": False,
            "empty": False,
            "kind": None,
            "paragraph_id": None,
            "provider_handle": None,
            "handles": {},
            "has_editorial_content": False,
            "has_indispensable_provenance": False,
        }
    text = paragraph.get("text")
    text_str = "" if text is None else str(text)
    handles = _handles(paragraph)
    has_handles = any(handles[field] for field in PROVENANCE_FIELDS)
    empty = text_str.strip() == ""
    return {
        "exists": True,
        "text": text,
        "text_repr": repr(text_str),
        "text_length": len(text_str),
        "whitespace_only": bool(text_str) and empty,
        "empty": empty,
        "kind": paragraph.get("kind"),
        "paragraph_id": paragraph.get("paragraph_id"),
        "provider_handle": paragraph.get("provider_handle") or paragraph.get("h"),
        "handles": {field: handles[field] for field in PROVENANCE_FIELDS},
        "classified_handle_kinds": handles["classified"],
        "has_editorial_content": not empty,
        "has_indispensable_provenance": has_handles,
        "contains_idea": "IDEA" in handles["classified"] or bool(handles["idea_refs"]),
        "contains_src": "SRC" in handles["classified"] or bool(handles["source_refs"]),
        "contains_ex": "EX" in handles["classified"] or bool(handles["example_refs"]),
        "contains_ref": "REF" in handles["classified"] or bool(handles["reference_refs"]),
        "contains_unc": "UNC" in handles["classified"] or bool(handles["uncertainty_refs"]),
        "contains_metadata_keys": sorted(
            key for key in paragraph.keys() if key not in {"text", "t"}
        ),
    }


def removal_is_admissible(inspection: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not inspection.get("exists"):
        reasons.append("paragraph does not exist")
    if not inspection.get("empty"):
        reasons.append("paragraph is not empty")
    if inspection.get("has_editorial_content"):
        reasons.append("paragraph has editorial content")
    if inspection.get("has_indispensable_provenance"):
        reasons.append("paragraph carries provenance that must be kept")
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
    return (not reasons), reasons


def assess_chapter_recovery(
    chapter: Mapping[str, Any],
    *,
    paragraph_id: str = EMPTY_PARAGRAPH_ID,
    expected_chapter_id: str = TARGET_CHAPTER_ID,
) -> dict[str, Any]:
    located = find_candidate_paragraph(dict(chapter), paragraph_id)
    inspection = inspect_paragraph(None if located is None else located[2])
    if located is not None:
        inspection["section_id"] = located[0]
        inspection["section_index"] = located[1]
    referenced_elsewhere = [
        str(other.get("paragraph_id") or "")
        for _section_id, _index, other in iter_candidate_paragraphs(dict(chapter))
        if str(other.get("paragraph_id") or "") != paragraph_id
        and paragraph_id
        and paragraph_id in json_safe_values(other)
    ]
    admissible, reasons = removal_is_admissible(inspection)
    if str(chapter.get("chapter_id") or "") != expected_chapter_id:
        admissible = False
        reasons.append(f"chapter_id {chapter.get('chapter_id')!r} ≠ {expected_chapter_id}")
    if referenced_elsewhere:
        admissible = False
        reasons.append("paragraph id is referenced by another paragraph")
    return {
        "phase": PHASE,
        "chapter_id": chapter.get("chapter_id"),
        "target_paragraph_id": paragraph_id,
        "inspection": inspection,
        "referenced_by_other_paragraphs": referenced_elsewhere,
        "admissible": admissible,
        "block_reasons": reasons,
        "secrets_included": False,
    }


def json_safe_values(payload: Any) -> str:
    if isinstance(payload, Mapping):
        return " ".join(json_safe_values(value) for value in payload.values())
    if isinstance(payload, (list, tuple)):
        return " ".join(json_safe_values(value) for value in payload)
    return str(payload)


def remove_empty_paragraph(
    chapter: Mapping[str, Any],
    *,
    paragraph_id: str = EMPTY_PARAGRAPH_ID,
    expected_chapter_id: str = TARGET_CHAPTER_ID,
) -> dict[str, Any]:
    assessment = assess_chapter_recovery(
        chapter, paragraph_id=paragraph_id, expected_chapter_id=expected_chapter_id
    )
    if not assessment["admissible"]:
        raise BookCh002OfflineRecovery4224Error(
            "RECOVERY = BLOCKED: " + "; ".join(assessment["block_reasons"])
        )
    recovered = deepcopy_chapter(dict(chapter))
    removed = None
    for section in recovered.get("sections") or []:
        paragraphs = list(section.get("paragraphs") or [])
        kept: list[dict[str, Any]] = []
        for paragraph in paragraphs:
            if str(paragraph.get("paragraph_id") or "") == paragraph_id:
                removed = paragraph
                continue
            kept.append(paragraph)
        section["paragraphs"] = kept
    if removed is None:
        raise BookCh002OfflineRecovery4224Error(
            f"RECOVERY = BLOCKED: {paragraph_id} was not found during removal"
        )
    before_ids = paragraph_ids(dict(chapter))
    after_ids = paragraph_ids(recovered)
    before_ideas = sorted(set(idea_handles(dict(chapter))))
    after_ideas = sorted(set(idea_handles(recovered)))
    return {
        "recovered": recovered,
        "removed": removed,
        "assessment": assessment,
        "before_paragraph_ids": before_ids,
        "after_paragraph_ids": after_ids,
        "ids_renumbered": False,
        "other_paragraph_ids_unchanged": [item for item in before_ids if item != paragraph_id]
        == after_ids,
        "ideas_before": before_ideas,
        "ideas_after": after_ideas,
        "ideas_preserved": before_ideas == after_ideas,
        "artifact_kind": ARTIFACT_KIND,
        "not_provider_original": NOT_ORIGINAL,
        "expected_section": EMPTY_SECTION_ID,
        "expected_handle": EMPTY_PROVIDER_HANDLE,
    }


def proposed_empty_unprovenanced_strip(
    chapter: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Isolated future-phase proposal. Does not mutate production.
    Drops only strictly empty paragraphs that carry no provenance.
    Never renumbers. Never rewrites text. Never touches the raw response.
    """
    recovered = deepcopy_chapter(dict(chapter))
    removed_ids: list[str] = []
    refused: list[dict[str, Any]] = []
    for section in recovered.get("sections") or []:
        kept: list[dict[str, Any]] = []
        for paragraph in section.get("paragraphs") or []:
            inspection = inspect_paragraph(paragraph)
            admissible, reasons = removal_is_admissible(inspection)
            if admissible:
                removed_ids.append(str(paragraph.get("paragraph_id") or ""))
                continue
            if inspection.get("empty"):
                refused.append(
                    {
                        "paragraph_id": paragraph.get("paragraph_id"),
                        "reasons": reasons,
                    }
                )
            kept.append(paragraph)
        section["paragraphs"] = kept
    return {
        "phase": PHASE,
        "proposal_only": True,
        "production_pipeline_modified": False,
        "removed_paragraph_ids": removed_ids,
        "refused": refused,
        "renumbered": False,
        "raw_response_modified": False,
        "chapter": recovered,
        "secrets_included": False,
    }


__all__ = [
    "PROVENANCE_FIELDS",
    "assess_chapter_recovery",
    "inspect_paragraph",
    "proposed_empty_unprovenanced_strip",
    "removal_is_admissible",
    "remove_empty_paragraph",
]
