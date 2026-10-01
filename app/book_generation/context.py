"""Deterministic continuity context. Plan-derived, never provider summaries."""

from __future__ import annotations

from typing import Any

from app.editorial_planning.models import EditorialChapter, EditorialPlan


def continuity_for_chapter(
    plan: EditorialPlan, chapter: EditorialChapter
) -> dict[str, Any]:
    previous = _previous_chapter(plan, chapter.chapter_id)
    previous_section_title = ""
    if previous and previous.sections:
        previous_section_title = previous.sections[-1].working_title
    return {
        "previous_chapter_id": previous.chapter_id if previous else "",
        "previous_chapter_title": previous.working_title if previous else "",
        "previous_chapter_purpose": previous.purpose if previous else "",
        "previous_section_title": previous_section_title,
        "book_progression": plan.book_concept.editorial_progression,
        "source": "editorial_plan",
        "provider_generated_summary": False,
        "do_not_restate": [
            "book thesis",
            "chapter thesis of previous chapters",
            "previous section conclusions",
        ],
    }


def _previous_chapter(
    plan: EditorialPlan, chapter_id: str
) -> EditorialChapter | None:
    previous = None
    for chapter in plan.chapters:
        if chapter.chapter_id == chapter_id:
            return previous
        previous = chapter
    return None
