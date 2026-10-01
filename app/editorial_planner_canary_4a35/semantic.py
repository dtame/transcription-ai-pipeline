"""Semantic review for the 1.0.2 English production candidate."""

from __future__ import annotations

from typing import Any, Mapping

from app.editorial_planner_canary_4a33.semantic import review_semantics as _review_a33
from app.editorial_planner_canary_4a35.constants import (
    FINAL_TITLE_APPROVED,
    HISTORICAL_ENGLISH_TITLE,
    HISTORICAL_FRENCH_TITLE,
)
from app.source_analysis.models import SourceMap


def _title_status(base: Mapping[str, Any]) -> str:
    selected = str(base.get("selected_title") or "")
    reviews = list(base.get("title_review") or [])
    selected_row = next(
        (
            row
            for row in reviews
            if isinstance(row, Mapping) and str(row.get("title") or "") == selected
        ),
        None,
    )
    if not selected:
        return "UNSUPPORTED"
    if selected_row and selected_row.get("unsupported_promise") == "FAIL":
        return "UNSUPPORTED"
    flags = list(base.get("review_flags") or [])
    title_flags = [flag for flag in flags if "title" in str(flag).lower()]
    support = str((selected_row or {}).get("source_support") or "")
    intent = str((selected_row or {}).get("fit_with_author_intent") or "")
    if support == "REVIEW" or intent == "REVIEW" or title_flags:
        return "SUPPORTED_BUT_HUMAN_REVIEW"
    if selected_row and selected_row.get("scope") == "REVIEW":
        return "OVERWEIGHTED"
    if support == "PASS":
        return "SUPPORTED_WORKING_TITLE"
    return "SUPPORTED_BUT_HUMAN_REVIEW"


def review_semantics(
    plan: Mapping[str, Any] | None,
    source_map: SourceMap,
    *,
    contract: Mapping[str, Any] | None = None,
    chapter_audit: Mapping[str, Any] | None = None,
    section_audit: Mapping[str, Any] | None = None,
    language: Mapping[str, Any] | None = None,
    accountability: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base = _review_a33(
        plan,
        source_map,
        contract=contract,
        chapter_audit=chapter_audit,
        section_audit=section_audit,
        language=language,
    )
    accountability = dict(accountability or {})
    issues = list(base.get("issues") or [])
    review_flags = list(base.get("review_flags") or [])
    notes = list(base.get("notes") or [])

    if accountability.get("status") == "FAIL":
        issues.append(
            "Exact IDEA accountability failed. Silent omission or duplicate "
            "primary disposition is a hard FAIL. No repair."
        )
    elif accountability.get("exactly_once"):
        notes.append(
            "Exact accountability equation holds: every input IDEA has "
            "exactly one primary disposition."
        )
    if not accountability.get("deferred_excluded_reasons_valid", True):
        issues.append("One or more DEFERRED/EXCLUDED reasons are not auditable.")

    selected = str(base.get("selected_title") or "")
    already = HISTORICAL_ENGLISH_TITLE.lower()
    deja = HISTORICAL_FRENCH_TITLE.lower()
    notes.append(
        "Historical titles are not required. "
        f"Already Given reproduced={already in selected.lower()}. "
        f"Déjà héritiers reproduced={deja in selected.lower()}."
    )
    title_status = _title_status(base)
    status = str(base.get("status") or "FAIL")
    if issues:
        status = "FAIL"
    elif review_flags:
        status = "REVIEW_REQUIRED"
    elif (
        language
        and language.get("editorial_language_match") == "PASS"
        and accountability.get("status") == "PASS"
        and status == "PASS"
    ):
        status = "PASS"

    chapter_arch = "PASS"
    if chapter_audit and chapter_audit.get("status") == "FAIL":
        chapter_arch = "FAIL"
    elif chapter_audit and chapter_audit.get("status") == "REVIEW":
        chapter_arch = "REVIEW"
    section_arch = "PASS"
    if section_audit and section_audit.get("status") == "FAIL":
        section_arch = "FAIL"
    elif section_audit and section_audit.get("status") == "REVIEW":
        section_arch = "REVIEW"

    book_concept = "PASS"
    if any("book concept" in str(item).lower() for item in issues):
        book_concept = "FAIL"
    elif any("book concept" in str(item).lower() for item in review_flags):
        book_concept = "REVIEW"

    return {
        **base,
        "status": status,
        "primary_question": status,
        "title_status": title_status,
        "working_title": selected,
        "final_title_approved": FINAL_TITLE_APPROVED,
        "book_concept_review": book_concept,
        "chapter_architecture": chapter_arch,
        "section_architecture": section_arch,
        "accountability_status": accountability.get("status"),
        "issues": issues,
        "review_flags": review_flags,
        "notes": notes,
    }


__all__ = ["review_semantics"]
