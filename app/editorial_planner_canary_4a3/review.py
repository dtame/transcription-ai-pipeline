"""Chapter-by-chapter and section-by-section review from reconstructed plan."""

from __future__ import annotations

from typing import Any, Mapping

from app.editorial_planning.settings import frozen_production_settings
from app.source_analysis.models import SourceMap

_MANUSCRIPT_CHAR_WARN = 280
_MANUSCRIPT_SENTENCE_WARN = 3


def _sentences(text: str) -> int:
    stripped = (text or "").strip()
    if not stripped:
        return 0
    return max(1, stripped.count(".") + stripped.count("!") + stripped.count("?"))


def _manuscript_leak(text: str) -> bool:
    value = text or ""
    return len(value) > _MANUSCRIPT_CHAR_WARN and _sentences(value) > _MANUSCRIPT_SENTENCE_WARN


def _idea_index(source_map: SourceMap) -> dict[str, Any]:
    return {idea.idea_id: idea for idea in source_map.ideas}


def _topic_index(source_map: SourceMap) -> dict[str, Any]:
    return {topic.topic_id: topic for topic in source_map.topics}


def _support_verdict(*, idea_count: int, unknown: int, empty: bool) -> str:
    if empty or idea_count == 0:
        return "FAIL"
    if unknown:
        return "FAIL"
    return "PASS"


def chapter_review(
    plan: Mapping[str, Any] | None,
    source_map: SourceMap,
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    settings = frozen_production_settings()
    contract = dict(contract or {})
    if not isinstance(plan, Mapping):
        return {"status": "FAIL", "chapters": [], "notes": ["no reconstructed plan"]}
    ideas = _idea_index(source_map)
    topics = _topic_index(source_map)
    chapters = list(plan.get("chapters") or [])
    assigned_total = max(1, int((plan.get("stats") or {}).get("assigned_idea_count") or 1))
    rows: list[dict[str, Any]] = []
    overloaded: list[str] = []
    tiny: list[str] = []
    previous_title = ""
    for index, chapter in enumerate(chapters):
        if not isinstance(chapter, Mapping):
            continue
        idea_refs = list(chapter.get("idea_refs") or [])
        topic_refs = list(chapter.get("topic_refs") or [])
        sections = list(chapter.get("sections") or [])
        share = len(idea_refs) / assigned_total
        unknown_topics = [ref for ref in topic_refs if ref not in topics]
        unknown_ideas = [ref for ref in idea_refs if ref not in ideas]
        leak = _manuscript_leak(str(chapter.get("purpose") or "")) or _manuscript_leak(
            str(chapter.get("summary") or "")
        )
        if share >= settings.max_chapter_idea_share_warn:
            overloaded.append(str(chapter.get("chapter_id")))
        if (
            len(chapters) >= settings.min_chapters
            and share <= settings.min_chapter_idea_share_warn
            and idea_refs
        ):
            tiny.append(str(chapter.get("chapter_id")))
        next_title = ""
        if index + 1 < len(chapters) and isinstance(chapters[index + 1], Mapping):
            next_title = str(chapters[index + 1].get("working_title") or "")
        rows.append(
            {
                "canonical_id": chapter.get("chapter_id"),
                "working_title": chapter.get("working_title"),
                "purpose": chapter.get("purpose"),
                "summary": chapter.get("summary"),
                "section_count": len(sections),
                "idea_count": len(idea_refs),
                "idea_share": round(share, 4),
                "major_topic_refs": topic_refs,
                "topic_labels": [
                    (topics[ref].label if ref in topics else ref) for ref in topic_refs
                ],
                "idea_summaries": [
                    {
                        "idea_id": ref,
                        "summary": ideas[ref].summary if ref in ideas else "",
                        "kind": ideas[ref].kind if ref in ideas else "",
                        "importance": ideas[ref].importance if ref in ideas else "",
                    }
                    for ref in idea_refs[:40]
                ],
                "unknown_topic_refs": unknown_topics,
                "unknown_idea_refs": unknown_ideas,
                "manuscript_leakage": leak,
                "boundary_previous": previous_title,
                "boundary_next": next_title,
                "semantic_coherence": "REVIEW" if leak or unknown_ideas else "PASS",
                "support_verdict": _support_verdict(
                    idea_count=len(idea_refs),
                    unknown=len(unknown_ideas),
                    empty=not sections,
                ),
            }
        )
        previous_title = str(chapter.get("working_title") or "")
    status = "PASS"
    if any(row["support_verdict"] == "FAIL" for row in rows):
        status = "FAIL"
    elif overloaded or tiny:
        status = "REVIEW"
    return {
        "status": status,
        "chapter_count": len(rows),
        "overloaded_chapters": overloaded,
        "tiny_chapters": tiny,
        "chapters": rows,
        "validator_warnings": list((contract.get("validator") or {}).get("warnings") or []),
    }


def section_review(
    plan: Mapping[str, Any] | None,
    source_map: SourceMap,
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    settings = frozen_production_settings()
    contract = dict(contract or {})
    if not isinstance(plan, Mapping):
        return {"status": "FAIL", "sections": [], "notes": ["no reconstructed plan"]}
    ideas = _idea_index(source_map)
    examples = {item.example_id: item for item in source_map.examples}
    references = {item.reference_id: item for item in source_map.references}
    uncertainties = {item.uncertainty_id: item for item in source_map.uncertainties}
    rows: list[dict[str, Any]] = []
    tiny: list[str] = []
    overloaded: list[str] = []
    leaks: list[str] = []
    unsupported: list[str] = []
    for chapter in plan.get("chapters") or []:
        if not isinstance(chapter, Mapping):
            continue
        for section in chapter.get("sections") or []:
            if not isinstance(section, Mapping):
                continue
            idea_refs = list(section.get("idea_refs") or [])
            example_refs = list(section.get("example_refs") or [])
            reference_refs = list(section.get("reference_refs") or [])
            uncertainty_refs = list(section.get("uncertainty_refs") or [])
            unknown_ideas = [ref for ref in idea_refs if ref not in ideas]
            unknown_ex = [ref for ref in example_refs if ref not in examples]
            unknown_ref = [ref for ref in reference_refs if ref not in references]
            unknown_unc = [ref for ref in uncertainty_refs if ref not in uncertainties]
            leak = _manuscript_leak(str(section.get("purpose") or ""))
            if leak:
                leaks.append(str(section.get("section_id")))
            if len(idea_refs) > settings.max_ideas_per_section_warn:
                overloaded.append(str(section.get("section_id")))
            if len(idea_refs) <= 1 and len(idea_refs) < 1:
                tiny.append(str(section.get("section_id")))
            if not idea_refs:
                tiny.append(str(section.get("section_id")))
                unsupported.append(str(section.get("section_id")))
            traceable = bool(idea_refs) and bool(section.get("source_refs"))
            rows.append(
                {
                    "canonical_id": section.get("section_id"),
                    "chapter": chapter.get("chapter_id"),
                    "working_title": section.get("working_title"),
                    "purpose": section.get("purpose"),
                    "idea_refs": idea_refs,
                    "example_refs": example_refs,
                    "reference_refs": reference_refs,
                    "uncertainty_refs": uncertainty_refs,
                    "topic_refs": list(section.get("topic_refs") or []),
                    "source_refs": list(section.get("source_refs") or []),
                    "idea_summaries": [
                        ideas[ref].summary if ref in ideas else "" for ref in idea_refs[:20]
                    ],
                    "unknown_idea_refs": unknown_ideas,
                    "unknown_example_refs": unknown_ex,
                    "unknown_reference_refs": unknown_ref,
                    "unknown_uncertainty_refs": unknown_unc,
                    "traceability": "PASS" if traceable else "FAIL",
                    "semantic_coherence": (
                        "FAIL" if unknown_ideas or not idea_refs else "PASS"
                    ),
                    "unsupported_content_verdict": (
                        "FAIL" if not idea_refs or unknown_ideas else "PASS"
                    ),
                    "manuscript_leakage": leak,
                    "overloaded": str(section.get("section_id")) in overloaded,
                }
            )
    status = "PASS"
    if any(row["unsupported_content_verdict"] == "FAIL" for row in rows):
        status = "FAIL"
    elif leaks or overloaded:
        status = "REVIEW"
    return {
        "status": status,
        "section_count": len(rows),
        "tiny_sections": sorted(set(tiny)),
        "overloaded_sections": overloaded,
        "manuscript_leakage_sections": leaks,
        "unsupported_sections": unsupported,
        "sections": rows,
        "validator_warnings": list((contract.get("validator") or {}).get("warnings") or []),
    }


__all__ = ["chapter_review", "section_review"]
