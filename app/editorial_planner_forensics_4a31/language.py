"""Measure editorial-plan language. IDs and inherited refs are not plan language."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping

from app.language_cleanup.language_detector import classify_text
from app.language_cleanup.models import LANGUAGE_EN, LANGUAGE_FR, LANGUAGE_MIXED, LANGUAGE_UNKNOWN

_ID_RE = re.compile(
    r"\b(?:IDEA|TOP|EX|REF|UNC|REP|SRC|CH|SEC)\d+\b",
    re.IGNORECASE,
)

_PROSE_FIELDS = (
    "selected_title",
    "subtitle",
    "editorial_angle",
    "target_reader",
    "editorial_strategy",
)


def strip_inherited_ids(text: str) -> str:
    return _ID_RE.sub(" ", text or "")


def classify_editorial_prose(text: str) -> dict[str, Any]:
    cleaned = strip_inherited_ids(text or "").strip()
    if not cleaned:
        return {"language": LANGUAGE_UNKNOWN, "confidence": 0.0, "reason": "empty"}
    result = classify_text(cleaned)
    return {
        "language": result.language,
        "confidence": result.confidence,
        "reason": result.reason,
        "chars": len(cleaned),
    }


def _join(parts: list[str]) -> str:
    return "\n".join(part for part in parts if part and str(part).strip())


def collect_plan_prose(plan: Mapping[str, Any]) -> dict[str, str]:
    concept = plan.get("book_concept") if isinstance(plan.get("book_concept"), Mapping) else {}
    titles = [
        str(item.get("title") or "")
        for item in (plan.get("title_candidates") or [])
        if isinstance(item, Mapping)
    ]
    chapters = [ch for ch in (plan.get("chapters") or []) if isinstance(ch, Mapping)]
    sections = [
        section
        for chapter in chapters
        for section in (chapter.get("sections") or [])
        if isinstance(section, Mapping)
    ]
    actions = []
    for chapter in chapters:
        for action in chapter.get("editorial_actions") or []:
            if isinstance(action, Mapping):
                actions.append(str(action.get("note") or ""))
        for section in chapter.get("sections") or []:
            if not isinstance(section, Mapping):
                continue
            for action in section.get("editorial_actions") or []:
                if isinstance(action, Mapping):
                    actions.append(str(action.get("note") or ""))
    for action in plan.get("editorial_actions") or []:
        if isinstance(action, Mapping):
            actions.append(str(action.get("note") or ""))
    return {
        "book_concept": _join(
            [
                str(concept.get("purpose") or ""),
                str(concept.get("core_subject") or ""),
                str(concept.get("reader_journey") or ""),
                str(concept.get("editorial_progression") or ""),
            ]
        ),
        "title_candidates": _join(titles),
        "selected_title": str(plan.get("selected_title") or ""),
        "subtitle": str(plan.get("subtitle") or ""),
        "editorial_angle": str(plan.get("editorial_angle") or ""),
        "target_reader": str(plan.get("target_reader") or ""),
        "editorial_strategy": str(plan.get("editorial_strategy") or ""),
        "chapter_titles": _join(str(ch.get("working_title") or "") for ch in chapters),
        "chapter_purposes": _join(
            str(ch.get("purpose") or "") + "\n" + str(ch.get("summary") or "")
            for ch in chapters
        ),
        "section_titles": _join(str(sec.get("working_title") or "") for sec in sections),
        "section_purposes": _join(str(sec.get("purpose") or "") for sec in sections),
        "editorial_actions": _join(actions),
    }


def dominant_language(counts: Mapping[str, int]) -> str:
    fr = int(counts.get(LANGUAGE_FR, 0))
    en = int(counts.get(LANGUAGE_EN, 0))
    mixed = int(counts.get(LANGUAGE_MIXED, 0))
    if fr == 0 and en == 0 and mixed == 0:
        return "UNKNOWN"
    if mixed and mixed >= max(fr, en):
        return "mixed"
    if fr > 0 and en == 0:
        return "predominantly French"
    if en > 0 and fr == 0:
        return "predominantly English"
    if fr >= max(2, 3 * en):
        return "predominantly French"
    if en >= max(2, 3 * fr):
        return "predominantly English"
    return "mixed"


def measure_plan_language(plan: Mapping[str, Any]) -> dict[str, Any]:
    blobs = collect_plan_prose(plan)
    fields: dict[str, Any] = {}
    counts: Counter[str] = Counter()
    for name, text in blobs.items():
        row = classify_editorial_prose(text)
        fields[name] = row
        if row["language"] in {LANGUAGE_FR, LANGUAGE_EN, LANGUAGE_MIXED}:
            counts[row["language"]] += 1
    combined = classify_editorial_prose("\n".join(blobs.values()))
    if combined["language"] in {LANGUAGE_FR, LANGUAGE_EN, LANGUAGE_MIXED}:
        counts[combined["language"]] += 2
    return {
        "fields": fields,
        "combined": combined,
        "counts": dict(counts),
        "editorial_plan_language": dominant_language(counts),
        "note": (
            "Inherited IDEA/TOP/EX/REF/UNC/SRC/CH/SEC identifiers were stripped "
            "before classification. Source quotations are not treated as "
            "provider editorial language unless they appear in plan prose."
        ),
    }
