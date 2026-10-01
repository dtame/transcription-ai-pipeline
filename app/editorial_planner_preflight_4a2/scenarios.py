"""Synthetic full-scale transports for budget modelling and FakeAI stress."""

from __future__ import annotations

from typing import Any, Sequence

from app.editorial_planning.constants import DEFERRAL_REASONS, EXCLUSION_REASONS
from app.editorial_planning.settings import frozen_production_settings
from app.source_analysis.models import SourceMap

_A1_PURPOSE = (
    "Establish the preparation decisions that constrain everything later: "
    "soil condition, compost handling, and light across the plot."
)
_A1_SUMMARY = (
    "Soil testing, layered compost with an open question on drop-off hours, "
    "and sun/shade mapping of beds."
)
_A1_ANGLE = (
    "Treat the workshop as a sequence of decisions made before, during, and "
    "after the growing season, so each instruction sits where a gardener "
    "would actually need it."
)
_A1_STRATEGY = (
    "Group the material by the three source topics, but order chapters along "
    "the working calendar of the plot. Place cautionary anecdotes next to the "
    "instruction they support, keep the single compost-schedule uncertainty "
    "flagged where compost is discussed, and give the minor volunteer "
    "observation its own short section rather than diluting the harvest-sharing "
    "claim."
)


def _pad(text: str, scale: float, cap: int) -> str:
    if scale <= 1.0:
        return text[:cap]
    extra = " " + text
    target = min(cap, max(len(text), int(len(text) * scale)))
    out = text
    while len(out) < target:
        out += extra
    return out[:cap]


def _split(ids: Sequence[str], n_groups: int) -> list[list[str]]:
    if n_groups <= 0:
        return []
    groups: list[list[str]] = [[] for _ in range(n_groups)]
    if not ids:
        return groups
    for index, idea_id in enumerate(ids):
        groups[index % n_groups].append(idea_id)
    filled = [group for group in groups if group]
    while len(filled) < n_groups and ids:
        filled.append([ids[len(filled) % len(ids)]])
    return filled[:n_groups]


def disposition_row_cost() -> dict[str, Any]:
    assigned = json_len(["IDEA001"])
    assigned_item = json_len("IDEA001")
    deferred_min = json_len(
        {"id": "IDEA001", "why": "insufficient_support"}
    )
    deferred_note = json_len(
        {
            "id": "IDEA001",
            "why": "insufficient_support",
            "n": "deferred pending support",
        }
    )
    excluded_min = json_len({"id": "IDEA001", "why": "non_substantive"})
    excluded_note = json_len(
        {"id": "IDEA001", "why": "non_substantive", "n": "out of selected scope"}
    )
    return {
        "assigned_id_chars": assigned_item,
        "assigned_singleton_array_chars": assigned,
        "deferred_min_chars": deferred_min,
        "deferred_with_note_chars": deferred_note,
        "excluded_min_chars": excluded_min,
        "excluded_with_note_chars": excluded_note,
        "assigned_reason_required": False,
        "deferred_reason_required": True,
        "excluded_reason_required": True,
        "closed_deferral_reasons": list(DEFERRAL_REASONS),
        "closed_exclusion_reasons": list(EXCLUSION_REASONS),
        "note": (
            "ASSIGNED ideas appear only as canonical IDs in section i[]. "
            "DEFERRED/EXCLUDED require a closed why; n is optional."
        ),
    }


def json_len(value: Any) -> int:
    import json

    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def build_scenario_transport(
    source_map: SourceMap,
    *,
    name: str,
    chapter_count: int,
    section_count: int,
    title_count: int,
    deferred_count: int,
    excluded_count: int,
    reuse_count: int,
    reuse_extra: int,
    field_scale: float,
    include_notes: bool,
    attach_support: bool,
) -> dict[str, Any]:
    settings = frozen_production_settings()
    chapter_count = max(settings.min_chapters, min(chapter_count, settings.max_chapters))
    section_count = max(chapter_count, min(section_count, settings.max_total_sections))
    title_count = max(1, min(title_count, settings.max_title_candidates))
    idea_ids = [idea.idea_id for idea in source_map.ideas]
    excluded_count = max(0, min(excluded_count, max(0, len(idea_ids) - section_count)))
    remaining = len(idea_ids) - excluded_count
    deferred_count = max(0, min(deferred_count, max(0, remaining - section_count)))
    excluded_ids = tuple(idea_ids[-excluded_count:]) if excluded_count else ()
    usable = [idea_id for idea_id in idea_ids if idea_id not in excluded_ids]
    deferred_ids = tuple(usable[-deferred_count:]) if deferred_count else ()
    assigned_ids = [idea_id for idea_id in usable if idea_id not in deferred_ids]
    if len(assigned_ids) < section_count:
        section_count = max(chapter_count, len(assigned_ids))
    sections_per_chapter = [0] * chapter_count
    for index in range(section_count):
        sections_per_chapter[index % chapter_count] += 1
    section_buckets = _split(assigned_ids, section_count)
    examples = [item.example_id for item in source_map.examples]
    references = [item.reference_id for item in source_map.references]
    uncertainties = [item.uncertainty_id for item in source_map.uncertainties]
    repetitions = [item.repetition_id for item in source_map.repetitions]
    topics = [topic.topic_id for topic in source_map.topics]
    purpose_cap = 240 if field_scale >= 1.5 else 180
    title_cap = 80 if field_scale >= 1.5 else 50
    sum_cap = 200 if field_scale >= 1.5 else 140
    meta_cap = 400 if field_scale >= 1.5 else 280
    chapters = []
    section_index = 0
    all_sections: list[dict[str, Any]] = []
    for c_index, n_sections in enumerate(sections_per_chapter, start=1):
        sections = []
        for s_index in range(1, n_sections + 1):
            bucket = section_buckets[section_index] if section_index < len(section_buckets) else assigned_ids[:1]
            section_index += 1
            section = {
                "h": f"c{c_index}s{s_index}",
                "t": _pad(f"Working section {c_index}.{s_index} cluster", field_scale, title_cap),
                "p": _pad(_A1_PURPOSE, field_scale, purpose_cap),
                "i": list(bucket),
                "x": [],
                "ref": [],
                "u": [],
                "rep": [],
                "top": [],
                "act": [{"k": "GROUP", "n": _pad("group related ideas", field_scale, 80)}],
            }
            if attach_support and c_index == 1 and s_index == 1:
                section["x"] = examples
                section["ref"] = references
                section["u"] = uncertainties
                section["rep"] = repetitions
                if topics:
                    section["top"] = [topics[0]]
            sections.append(section)
            all_sections.append(section)
        chapters.append(
            {
                "h": f"c{c_index}",
                "t": _pad(f"Working chapter {c_index} title", field_scale, title_cap),
                "p": _pad(_A1_PURPOSE, field_scale, purpose_cap),
                "sum": _pad(_A1_SUMMARY, field_scale, sum_cap),
                "top": [topics[min(c_index - 1, len(topics) - 1)]] if topics else [],
                "act": [{"k": "REORDER", "n": _pad("editorial order", field_scale, 80)}],
                "sections": sections,
            }
        )
    reuse_ids = assigned_ids[:reuse_count]
    if reuse_ids and all_sections:
        for idea_id in reuse_ids:
            targets = all_sections[1 : 1 + reuse_extra] if len(all_sections) > 1 else all_sections
            if not targets:
                targets = all_sections[-1:]
            for section in targets:
                if idea_id not in section["i"]:
                    section["i"].append(idea_id)
    titles = [
        {
            "t": _pad(f"Working Title {index}", field_scale, title_cap),
            "why": _pad("Editorial construct grounded in source clusters", field_scale, 120),
        }
        for index in range(1, title_count + 1)
    ]
    note = "fixture note" if include_notes else ""
    return {
        "scenario": name,
        "concept": {
            "promise": _pad(
                "Organize the validated source into a readable book",
                field_scale,
                160,
            ),
            "subject": (source_map.source_analysis.main_theme or "subject")[:180],
            "journey": _pad(
                "From foundation through development to application",
                field_scale,
                160,
            ),
            "progression": "foundation-development-application",
        },
        "titles": titles,
        "pick": 0,
        "subtitle": _pad("A source-grounded working subtitle", field_scale, 120),
        "angle": _pad(_A1_ANGLE, field_scale, meta_cap),
        "reader": (source_map.source_analysis.target_audience.summary or "reader")[:180],
        "strategy": _pad(_A1_STRATEGY, field_scale, meta_cap),
        "chapters": chapters,
        "deferred": [
            {
                "id": idea_id,
                "why": "insufficient_support",
                **({"n": note} if include_notes else {}),
            }
            for idea_id in deferred_ids
        ],
        "excluded": [
            {
                "id": idea_id,
                "why": "non_substantive",
                **({"n": note} if include_notes else {}),
            }
            for idea_id in excluded_ids
        ],
        "_meta": {
            "name": name,
            "chapter_count": len(chapters),
            "section_count": section_count,
            "title_count": title_count,
            "assigned_count": len(assigned_ids),
            "deferred_count": len(deferred_ids),
            "excluded_count": len(excluded_ids),
            "reuse_count": len(reuse_ids),
            "reuse_extra": reuse_extra,
            "field_scale": field_scale,
            "budget_modelling_only": True,
        },
    }


def expected_transport(source_map: SourceMap) -> dict[str, Any]:
    return build_scenario_transport(
        source_map,
        name="EXPECTED",
        chapter_count=12,
        section_count=36,
        title_count=4,
        deferred_count=8,
        excluded_count=6,
        reuse_count=14,
        reuse_extra=1,
        field_scale=1.0,
        include_notes=False,
        attach_support=True,
    )


def conservative_transport(source_map: SourceMap) -> dict[str, Any]:
    return build_scenario_transport(
        source_map,
        name="CONSERVATIVE",
        chapter_count=16,
        section_count=64,
        title_count=6,
        deferred_count=20,
        excluded_count=16,
        reuse_count=25,
        reuse_extra=1,
        field_scale=1.6,
        include_notes=True,
        attach_support=True,
    )


def hard_transport(source_map: SourceMap) -> dict[str, Any]:
    settings = frozen_production_settings()
    return build_scenario_transport(
        source_map,
        name="HARD",
        chapter_count=settings.max_chapters,
        section_count=settings.max_total_sections,
        title_count=settings.max_title_candidates,
        deferred_count=50,
        excluded_count=36,
        reuse_count=int(286 * settings.max_reused_idea_ratio_warn),
        reuse_extra=settings.max_idea_reuse_count_warn - 1,
        # Prompt requires short editorial fields. 2x padding of every purpose
        # is unbounded-adjacent, not a permitted maximum.
        field_scale=1.0,
        include_notes=True,
        attach_support=True,
    )


def all_assigned_transport(source_map: SourceMap) -> dict[str, Any]:
    return build_scenario_transport(
        source_map,
        name="ALL_ASSIGNED",
        chapter_count=12,
        section_count=36,
        title_count=4,
        deferred_count=0,
        excluded_count=0,
        reuse_count=0,
        reuse_extra=0,
        field_scale=1.0,
        include_notes=False,
        attach_support=True,
    )


def mixed_transport(source_map: SourceMap) -> dict[str, Any]:
    return expected_transport(source_map)


def reuse_transport(source_map: SourceMap) -> dict[str, Any]:
    settings = frozen_production_settings()
    return build_scenario_transport(
        source_map,
        name="REUSE_MAX_WARN",
        chapter_count=12,
        section_count=36,
        title_count=4,
        deferred_count=0,
        excluded_count=0,
        reuse_count=int(len(source_map.ideas) * settings.max_reused_idea_ratio_warn),
        reuse_extra=settings.max_idea_reuse_count_warn - 1,
        field_scale=1.0,
        include_notes=False,
        attach_support=True,
    )


def max_structure_transport(source_map: SourceMap) -> dict[str, Any]:
    return hard_transport(source_map)


def strip_meta(transport: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(transport)
    cleaned.pop("_meta", None)
    cleaned.pop("scenario", None)
    return cleaned


__all__ = [
    "all_assigned_transport",
    "build_scenario_transport",
    "conservative_transport",
    "disposition_row_cost",
    "expected_transport",
    "hard_transport",
    "max_structure_transport",
    "mixed_transport",
    "reuse_transport",
    "strip_meta",
]
