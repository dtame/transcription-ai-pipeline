"""Semantic review for the 1.0.1 English production candidate."""

from __future__ import annotations

from typing import Any, Mapping

from app.editorial_planner_canary_4a3.semantic import review_semantics as _review_a3
from app.editorial_planner_canary_4a33.constants import (
    FINAL_TITLE_APPROVED,
    HISTORICAL_FRENCH_TITLE,
    HISTORICAL_LEFTOVER_SECTION,
    HISTORICAL_QUESTIONABLE_FIT_IDEAS,
)
from app.source_analysis.models import SourceMap


def _placement_for(plan: Mapping[str, Any], idea_id: str) -> dict[str, Any]:
    coverage = [
        row
        for row in (plan.get("idea_coverage") or [])
        if isinstance(row, Mapping) and row.get("idea_id") == idea_id
    ]
    sections: list[dict[str, Any]] = []
    for chapter in plan.get("chapters") or []:
        if not isinstance(chapter, Mapping):
            continue
        for section in chapter.get("sections") or []:
            if not isinstance(section, Mapping):
                continue
            refs = list(section.get("idea_refs") or [])
            if idea_id in refs:
                sections.append(
                    {
                        "chapter_id": chapter.get("chapter_id"),
                        "section_id": section.get("section_id"),
                        "working_title": section.get("working_title"),
                    }
                )
    row = coverage[0] if coverage else {}
    return {
        "idea_id": idea_id,
        "disposition": row.get("disposition"),
        "primary_section_id": row.get("primary_section_id"),
        "additional_section_ids": list(row.get("additional_section_ids") or []),
        "reason": row.get("reason"),
        "note": row.get("note"),
        "sections": sections,
        "attention_only": True,
        "provider_not_instructed": True,
        "different_placement_not_required": True,
    }


def review_semantics(
    plan: Mapping[str, Any] | None,
    source_map: SourceMap,
    *,
    contract: Mapping[str, Any] | None = None,
    chapter_audit: Mapping[str, Any] | None = None,
    section_audit: Mapping[str, Any] | None = None,
    language: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base = _review_a3(
        plan,
        source_map,
        contract=contract,
        chapter_audit=chapter_audit,
        section_audit=section_audit,
    )
    language = dict(language or {})
    language_status = str(language.get("editorial_language_match") or language.get("status") or "")
    notes = list(base.get("notes") or [])
    issues = list(base.get("issues") or [])
    review_flags = list(base.get("review_flags") or [])

    if language_status == "FAIL":
        issues.append(
            "EDITORIAL_LANGUAGE_MATCH=FAIL. No translation, no repair, no retry."
        )
    elif language_status == "REVIEW":
        review_flags.append(
            "EDITORIAL_LANGUAGE_MATCH=REVIEW. Detector not confident enough for publication."
        )
    elif language_status == "PASS":
        notes.append("Provider-generated editorial prose matches canonical document language.")

    selected = str(base.get("selected_title") or "")
    titles = list(base.get("title_review") or [])
    deja = HISTORICAL_FRENCH_TITLE.lower()
    reproduced = deja in selected.lower() or any(
        deja in str(row.get("title") or "").lower()
        for row in titles
        if isinstance(row, Mapping)
    )
    notes.append(
        "Historical working title « Déjà héritiers » is not required. "
        f"Reproduced={reproduced}."
    )

    attention = []
    leftover = None
    if isinstance(plan, Mapping):
        attention = [_placement_for(plan, idea_id) for idea_id in HISTORICAL_QUESTIONABLE_FIT_IDEAS]
        for chapter in plan.get("chapters") or []:
            if not isinstance(chapter, Mapping):
                continue
            for section in chapter.get("sections") or []:
                if not isinstance(section, Mapping):
                    continue
                if section.get("section_id") == HISTORICAL_LEFTOVER_SECTION:
                    leftover = {
                        "section_id": HISTORICAL_LEFTOVER_SECTION,
                        "working_title": section.get("working_title"),
                        "idea_count": len(list(section.get("idea_refs") or [])),
                        "review_evidence_only": True,
                        "structure_not_forced": True,
                    }

    status = str(base.get("status") or "FAIL")
    if issues:
        status = "FAIL"
    elif review_flags:
        status = "REVIEW_REQUIRED"
    elif language_status == "PASS" and status == "PASS":
        status = "PASS"

    return {
        **base,
        "status": status,
        "primary_question": status,
        "language": language_status or "n/a",
        "language_hard_publication_criterion": True,
        "final_title_approved": FINAL_TITLE_APPROVED,
        "historical_french_title_required": False,
        "historical_french_title_reproduced": reproduced,
        "historical_questionable_fit": attention,
        "historical_sec028": leftover,
        "issues": issues,
        "review_flags": review_flags,
        "notes": notes,
        "assignment_reviewed_independently": True,
        "historical_286_assigned_not_assumed": True,
    }


__all__ = ["review_semantics"]
