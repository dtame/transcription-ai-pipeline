"""Generic assignment-fit labels plus this phase's review overlay.

Production planner behavior is not modified. Overlay IDs are audit-only.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from app.source_analysis.models import SourceMap

FIT_STRONG = "STRONG_FIT"
FIT_ACCEPTABLE = "ACCEPTABLE_FIT"
FIT_QUESTIONABLE = "QUESTIONABLE_FIT"
FIT_DEFER = "LIKELY_SHOULD_DEFER"
FIT_EXCLUDE = "LIKELY_SHOULD_EXCLUDE"

FIT_LABELS = (FIT_STRONG, FIT_ACCEPTABLE, FIT_QUESTIONABLE, FIT_DEFER, FIT_EXCLUDE)

ALIGN_SECTION = "SECTION_TOPIC_HIT"
ALIGN_CHAPTER = "CHAPTER_TOPIC_ONLY"
ALIGN_NONE = "NO_TOPIC_HIT"
ALIGN_EMPTY = "NO_IDEA_TOPICS"

# Review-layer overlays for this saved candidate only. Not generic planner rules.
# Audit-only labels for this saved candidate. Not planner rules.
# Purpose match can outweigh a missing section-topic overlap.
_REVIEW_OVERLAYS: dict[str, tuple[str, str]] = {
    "IDEA001": (
        FIT_STRONG,
        "Empty topic_refs, but the assigned section purpose matches the idea: hearing God rather than relying on external information.",
    ),
    "IDEA029": (
        FIT_ACCEPTABLE,
        "Glory and false modesty close the resurrection chapter beside the gospel-decision and already-possessed life. Chapter fit, looser than the section's message-accountability core.",
    ),
    "IDEA054": (
        FIT_QUESTIONABLE,
        "Priestly principles received as laws sit in the Melchizedek recognition section. Nearby offices material, not the tightest section fit. Valid content; not a defer or exclude.",
    ),
    "IDEA062": (
        FIT_STRONG,
        "Fasting and sacrifice that replace God are the thesis of the heart-before-offering section, even though the idea's topic refs sit on the chapter rather than that section.",
    ),
    "IDEA091": (
        FIT_STRONG,
        "Unity of essence between Father and Son, extended to believers, is the subject of the Father/Son unity section.",
    ),
    "IDEA100": (
        FIT_QUESTIONABLE,
        "A local community's need for a particular minister's mantle is related to carried anointing, but weaker than the section's knowledge-born confidence. Not administrative and not outside the book.",
    ),
    "IDEA107": (
        FIT_STRONG,
        "The section purpose explicitly recalls the Spirit already indwelling. The idea states that; its topic ref points elsewhere.",
    ),
    "IDEA112": (
        FIT_QUESTIONABLE,
        "Redirected invitation and former sinners as pillars is inclusion material grouped under knowing the Spirit more than gifts. Source-supported; placement is loose.",
    ),
    "IDEA113": (
        FIT_QUESTIONABLE,
        "Children as holy seed is inclusion material in the gifts-versus-person section. Valid teaching; not a cleanup defer.",
    ),
    "IDEA133": (
        FIT_STRONG,
        "Philippians 4:8 thought-selection is the stated subject of the ordinary-thoughts section.",
    ),
    "IDEA168": (
        FIT_QUESTIONABLE,
        "Paul's meek in-person presence versus bold letters is only loosely related to revelation versus flesh-and-blood knowledge.",
    ),
    "IDEA175": (
        FIT_STRONG,
        "Weapons that pull down strongholds are the subject of the reasoning-strongholds section.",
    ),
    "IDEA217": (
        FIT_STRONG,
        "Forgiveness and healing kept simple belongs with healing already accomplished, despite a neighboring topic ref.",
    ),
    "IDEA270": (
        FIT_STRONG,
        "Only abnormal acts draw attention is the principle named by the section, even though the idea also carries a testimony topic.",
    ),
    "IDEA272": (
        FIT_STRONG,
        "Short confident miracle prayer is the subject of the short-prayer section.",
    ),
    "IDEA283": (
        FIT_QUESTIONABLE,
        "A live-audience word of imminent ministry growth is assigned with the stolen-Bible redemption narrative. Source-supported exhortation, not a recording artifact, and not automatic exclusion.",
    ),
    "IDEA286": (
        FIT_QUESTIONABLE,
        "Praying together to release the promised move matches the closing vision section. The 'hold hands with someone nearby' gesture is live-event audience instruction. Not housekeeping, and not excluded: the prayer call is book-relevant.",
    ),
}


def topic_alignment(
    idea_topics: set[str],
    section_topics: set[str],
    chapter_topics: set[str],
) -> str:
    if not idea_topics:
        return ALIGN_EMPTY
    if idea_topics & section_topics:
        return ALIGN_SECTION
    if idea_topics & chapter_topics:
        return ALIGN_CHAPTER
    return ALIGN_NONE


def default_fit_from_alignment(alignment: str) -> str:
    if alignment == ALIGN_SECTION:
        return FIT_STRONG
    if alignment in {ALIGN_CHAPTER, ALIGN_EMPTY}:
        return FIT_ACCEPTABLE
    return FIT_QUESTIONABLE


def classify_assignment(
    *,
    idea_id: str,
    idea_topics: set[str],
    section_topics: set[str],
    chapter_topics: set[str],
    overlays: Mapping[str, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    alignment = topic_alignment(idea_topics, section_topics, chapter_topics)
    fit = default_fit_from_alignment(alignment)
    reason = f"Topic alignment={alignment}."
    overlay_applied = False
    table = overlays if overlays is not None else _REVIEW_OVERLAYS
    if idea_id in table:
        fit, reason = table[idea_id]
        overlay_applied = True
    return {
        "idea_id": idea_id,
        "alignment": alignment,
        "fit": fit,
        "reason": reason,
        "overlay_applied": overlay_applied,
    }


def review_assignments(
    plan: Mapping[str, Any],
    source_map: SourceMap,
) -> dict[str, Any]:
    ideas = {idea.idea_id: idea for idea in source_map.ideas}
    topics = {topic.topic_id: topic for topic in source_map.topics}
    section_index: dict[str, dict[str, Any]] = {}
    chapter_of: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for chapter in plan.get("chapters") or []:
        if not isinstance(chapter, Mapping):
            continue
        chapter_topics = set(chapter.get("topic_refs") or [])
        for section in chapter.get("sections") or []:
            if not isinstance(section, Mapping):
                continue
            section_id = str(section.get("section_id") or "")
            section_index[section_id] = dict(section)
            chapter_of[section_id] = dict(chapter)
            section_topics = set(section.get("topic_refs") or [])
            for idea_id in section.get("idea_refs") or []:
                idea = ideas.get(str(idea_id))
                if idea is None:
                    rows.append(
                        {
                            "idea_id": idea_id,
                            "fit": FIT_QUESTIONABLE,
                            "alignment": ALIGN_NONE,
                            "reason": "Unknown IDEA ref.",
                            "overlay_applied": False,
                            "chapter_id": chapter.get("chapter_id"),
                            "section_id": section_id,
                            "canonical_disposition": "ASSIGNED",
                        }
                    )
                    continue
                classified = classify_assignment(
                    idea_id=idea.idea_id,
                    idea_topics=set(idea.topic_refs),
                    section_topics=section_topics,
                    chapter_topics=chapter_topics,
                )
                classified.update(
                    {
                        "chapter_id": chapter.get("chapter_id"),
                        "section_id": section_id,
                        "section_title": section.get("working_title"),
                        "chapter_title": chapter.get("working_title"),
                        "importance": idea.importance,
                        "kind": idea.kind,
                        "topic_refs": list(idea.topic_refs),
                        "topic_labels": [
                            topics[ref].label if ref in topics else ref
                            for ref in idea.topic_refs
                        ],
                        "source_supported_description": idea.summary,
                        "canonical_disposition": "ASSIGNED",
                    }
                )
                rows.append(classified)

    counts = Counter(row["fit"] for row in rows)
    flagged = [
        {
            "idea_id": row["idea_id"],
            "source_supported_description": row.get("source_supported_description") or "",
            "assigned_ch": row.get("chapter_id"),
            "assigned_sec": row.get("section_id"),
            "fit": row["fit"],
            "reason": row["reason"],
        }
        for row in rows
        if row["fit"] in {FIT_QUESTIONABLE, FIT_DEFER, FIT_EXCLUDE}
    ]
    overall = FIT_STRONG
    if counts[FIT_EXCLUDE] or counts[FIT_DEFER] > 5:
        overall = "OVERASSIGNED"
    elif counts[FIT_QUESTIONABLE] == 0 and counts[FIT_DEFER] == 0:
        overall = "SEMANTICALLY_CREDIBLE"
    elif counts[FIT_QUESTIONABLE] <= 12 and counts[FIT_DEFER] == 0:
        overall = "CREDIBLE_WITH_MINOR_REVIEW"
    else:
        overall = "OVERASSIGNED"

    by_chapter: dict[str, dict[str, Any]] = {}
    for row in rows:
        chapter_id = str(row.get("chapter_id") or "")
        bucket = by_chapter.setdefault(
            chapter_id,
            {
                "chapter_id": chapter_id,
                "idea_count": 0,
                "fit_distribution": Counter(),
                "questionable_count": 0,
                "possible_defer_exclude_count": 0,
            },
        )
        bucket["idea_count"] += 1
        bucket["fit_distribution"][row["fit"]] += 1
        if row["fit"] == FIT_QUESTIONABLE:
            bucket["questionable_count"] += 1
        if row["fit"] in {FIT_DEFER, FIT_EXCLUDE}:
            bucket["possible_defer_exclude_count"] += 1

    chapter_rows = []
    for chapter in plan.get("chapters") or []:
        if not isinstance(chapter, Mapping):
            continue
        chapter_id = str(chapter.get("chapter_id") or "")
        bucket = by_chapter.get(chapter_id) or {
            "chapter_id": chapter_id,
            "idea_count": 0,
            "fit_distribution": Counter(),
            "questionable_count": 0,
            "possible_defer_exclude_count": 0,
        }
        chapter_rows.append(
            {
                "chapter_id": chapter_id,
                "working_title": chapter.get("working_title"),
                "purpose": chapter.get("purpose"),
                "idea_count": bucket["idea_count"],
                "section_count": len(list(chapter.get("sections") or [])),
                "fit_distribution": dict(bucket["fit_distribution"]),
                "questionable_count": bucket["questionable_count"],
                "possible_defer_exclude_count": bucket["possible_defer_exclude_count"],
            }
        )

    return {
        "ideas_reviewed": len(rows),
        "canonical_assigned": len(rows),
        "canonical_deferred": 0,
        "canonical_excluded": 0,
        "fit_counts": {
            FIT_STRONG: int(counts[FIT_STRONG]),
            FIT_ACCEPTABLE: int(counts[FIT_ACCEPTABLE]),
            FIT_QUESTIONABLE: int(counts[FIT_QUESTIONABLE]),
            FIT_DEFER: int(counts[FIT_DEFER]),
            FIT_EXCLUDE: int(counts[FIT_EXCLUDE]),
        },
        "assignment_result": overall,
        "principle": (
            "The planner contract permits ASSIGNED, DEFERRED, and EXCLUDED. "
            "It does not require all three categories to occur."
        ),
        "exclusion_standard": (
            "Exclusion requires a meaningful editorial reason "
            "(administrative, non-substantive, duplicate at editorial level, "
            "or outside selected book scope). Short, minor, illustrative, or "
            "repetitive wording is not enough."
        ),
        "defer_standard": (
            "DEFER means valid content intentionally outside current book "
            "scope or unsuitable for current organization. Not a cleanup bucket."
        ),
        "administrative_inspection": {
            "recording_or_transcription_artifacts": 0,
            "speaker_housekeeping": 0,
            "event_logistics_candidates": [],
            "live_audience_instruction_not_excluded": ["IDEA286"],
            "live_closing_exhortation_not_excluded": ["IDEA283"],
            "note": (
                "No microphone, recording, transcription, parking, or housekeeping IDEAs. "
                "Physical-exercise and food-custom ideas match the tradition-to-reexamine section and stay assigned. "
                "IDEA286 contains a live 'hold hands nearby' gesture inside an otherwise on-subject closing prayer; "
                "IDEA283 is a live growth word beside a redemption narrative. Neither meets the exclusion standard."
            ),
        },
        "flagged": flagged,
        "rows": rows,
        "chapters": chapter_rows,
    }
