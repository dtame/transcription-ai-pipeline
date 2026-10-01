"""IDEA / section accountability helpers. Generic — no corpus counts."""

from __future__ import annotations

from typing import Iterable, Mapping

from app.book_generation.constants import IDEA_ACCOUNTABILITY_POLICY_VERSION
from app.editorial_planning.models import EditorialChapter, EditorialPlan, EditorialSection


def disposition_map(plan: EditorialPlan) -> dict[str, str]:
    return {item.idea_id: item.disposition for item in plan.idea_coverage}


def deferred_idea_ids(plan: EditorialPlan) -> frozenset[str]:
    return frozenset(
        item.idea_id for item in plan.idea_coverage if item.disposition == "DEFERRED"
    )


def excluded_idea_ids(plan: EditorialPlan) -> frozenset[str]:
    return frozenset(
        item.idea_id for item in plan.idea_coverage if item.disposition == "EXCLUDED"
    )


def assigned_idea_ids_for_section(section: EditorialSection) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for idea_id in section.idea_refs:
        seen.setdefault(idea_id, None)
    return tuple(seen)


def assigned_idea_ids_for_chapter(chapter: EditorialChapter) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for section in chapter.sections:
        for idea_id in section.idea_refs:
            seen.setdefault(idea_id, None)
    return tuple(seen)


def reused_idea_ids(plan: EditorialPlan) -> frozenset[str]:
    return frozenset(
        item.idea_id
        for item in plan.idea_coverage
        if item.additional_section_ids
    )


def section_allowed_ideas(
    chapter: EditorialChapter, section: EditorialSection
) -> frozenset[str]:
    return frozenset(section.idea_refs)


def chapter_by_id(plan: EditorialPlan, chapter_id: str) -> EditorialChapter:
    for chapter in plan.chapters:
        if chapter.chapter_id == chapter_id:
            return chapter
    raise KeyError(chapter_id)


def section_by_id(plan: EditorialPlan, section_id: str) -> EditorialSection:
    for section in plan.all_sections():
        if section.section_id == section_id:
            return section
    raise KeyError(section_id)


def coverage_policy_dict() -> dict[str, object]:
    return {
        "version": IDEA_ACCOUNTABILITY_POLICY_VERSION,
        "assigned_must_appear": True,
        "verbatim_not_required": True,
        "silent_omission": "FAIL",
        "unknown_idea": "FAIL",
        "deferred_must_not_enter": True,
        "excluded_must_not_enter": True,
        "representation": (
            "An IDEA is represented when at least one substantive paragraph "
            "in an allowed section cites its canonical IDEA handle."
        ),
        "limitation": (
            "Handle presence does not prove every sentence is supported. "
            "Phase 5 Book Validator owns unsupported-claim detection."
        ),
    }


def represented_idea_ids(handles: Iterable[str]) -> frozenset[str]:
    return frozenset(
        handle for handle in handles if str(handle).startswith("IDEA")
    )


def idea_ids_from_paragraphs(paragraphs: Iterable[Mapping] | Iterable[object]) -> frozenset[str]:
    found: set[str] = set()
    for paragraph in paragraphs:
        refs = getattr(paragraph, "idea_refs", None)
        handles = getattr(paragraph, "evidence_handles", None)
        if refs is None and isinstance(paragraph, Mapping):
            refs = paragraph.get("idea_refs") or ()
            handles = paragraph.get("evidence_handles") or ()
        for handle in tuple(refs or ()) + tuple(handles or ()):
            if str(handle).startswith("IDEA"):
                found.add(str(handle))
    return frozenset(found)
