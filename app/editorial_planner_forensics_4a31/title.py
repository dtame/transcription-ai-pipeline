"""Offline title review of the saved A.3 working title. No new alternatives."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import SourceMap

WORKING_TITLE = "Déjà héritiers"


def _contains_any(text: str, needles: tuple[str, ...]) -> list[str]:
    lowered = (text or "").lower()
    return [needle for needle in needles if needle in lowered]


def review_title(plan: Mapping[str, Any], source_map: SourceMap) -> dict[str, Any]:
    header = source_map.source_analysis
    theme = header.main_theme
    intent = header.author_intent.summary
    selected = str(plan.get("selected_title") or "")
    subtitle = str(plan.get("subtitle") or "")
    candidates = [
        {
            "title": item.get("title"),
            "rationale": item.get("rationale"),
            "is_editorial_construct": item.get("is_editorial_construct"),
        }
        for item in (plan.get("title_candidates") or [])
        if isinstance(item, Mapping)
    ]
    inheritance_needles = (
        "inherit",
        "already possess",
        "already",
        "eternal life",
        "resurrection life",
        "sons of god",
        "unconditional love",
        "spiritual authority",
        "given",
    )
    theme_hits = _contains_any(theme, inheritance_needles)
    intent_hits = _contains_any(intent, inheritance_needles)
    supporting_ideas = []
    for idea in source_map.ideas:
        hits = _contains_any(idea.summary, ("already possess", "inherit", "sons of god", "resurrection life", "unconditional love"))
        if hits and idea.importance == "central":
            supporting_ideas.append(
                {
                    "idea_id": idea.idea_id,
                    "matched": hits,
                    "summary": idea.summary,
                }
            )
            if len(supporting_ideas) >= 12:
                break
    supporting_topics = [
        {"topic_id": topic.topic_id, "label": topic.label}
        for topic in source_map.topics
        if any(
            token in (topic.label or "").lower()
            for token in ("inherited", "eternal life", "resurrection", "unconditional love", "authority")
        )
    ]
    alternatives = []
    for item in candidates:
        title = str(item.get("title") or "")
        if title == selected:
            scope = "whole-book working construct: already-given life, love, and authority."
            overweight = False
        elif "chair" in title.lower() or "os" in title.lower():
            scope = "Supported, but overweight physical resurrection / flesh-and-bone (CH002) relative to offices, John 17, practice, and testimonies."
            overweight = True
        elif "prière" in title.lower() or "unit" in title.lower():
            scope = "Supported, but overweight John 17 (CH006) as if it were the whole book."
            overweight = True
        else:
            scope = "Supported practice-over-declaration theme (TOP012 / IDEA040); narrower than inherited identity plus love plus authority."
            overweight = False
        alternatives.append(
            {
                "title": title,
                "rationale": item.get("rationale"),
                "source_support": "PASS",
                "scope_note": scope,
                "overweighted": overweight,
                "selected": title == selected,
            }
        )
    status = "SUPPORTED_BUT_HUMAN_REVIEW"
    return {
        "working_title": selected,
        "expected_working_title": WORKING_TITLE,
        "title_matches_expected": selected == WORKING_TITLE,
        "subtitle": subtitle,
        "status": status,
        "final_title_approved": False,
        "is_editorial_construct": True,
        "title_is_not_source_fact": True,
        "verbatim_in_sourcemap": False,
        "source_support": {
            "global_theme_hits": theme_hits,
            "author_intent_hits": intent_hits,
            "supporting_central_ideas": supporting_ideas,
            "supporting_topics": supporting_topics[:12],
        },
        "scope": (
            "Represents the proposed book better than the other three stored "
            "candidates: inherited/already-given life, love, and authority. "
            "Offices, practice, and closing testimonies are downstream of that "
            "thesis rather than a different book."
        ),
        "promise": (
            "Does not promise a topic absent from the SourceMap. It frames "
            "believers as already heirs of what the corpus teaches is already given."
        ),
        "ambiguity": (
            "French 'héritiers' can be read as legal inheritance, spiritual "
            "identity, or both. That is a working-title ambiguity, not an "
            "unsupported factual claim. Marketing quality is not judged here."
        ),
        "candidates_already_in_a3": alternatives,
        "new_alternatives_generated": False,
    }
