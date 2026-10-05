"""Deterministic first remaining-chapter selection. Not automatically CH001."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_scale_up_preparation_4b220.constants import (
    ACCEPTED_CHAPTER,
    EXPECTED_FIRST_CHAPTER_ID,
    PHASE,
)
from app.book_scale_up_preparation_4b220.guard import BookScaleUpPreparation4220Error


def _int(row: Mapping[str, Any], key: str) -> int:
    try:
        return int(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def selection_score(row: Mapping[str, Any]) -> tuple[int, str]:
    """
    Higher is better. Deterministic tie-break is reverse chapter_id so CH001
    is never preferred when scores are equal.
    """
    chapter_id = str(row.get("chapter_id") or "")
    if chapter_id == ACCEPTED_CHAPTER:
        return (-10_000, chapter_id)
    sections = _int(row, "section_count")
    ideas = _int(row, "idea_count")
    examples = _int(row, "example_count")
    references = _int(row, "reference_count")
    src_words = int(
        ((row.get("estimated_source_context") or {}).get("hydrated_src_words") or 0)
    )
    testimony = "testimony" in list(row.get("example_kinds") or [])
    missing = len(list(row.get("missing_src_ids") or []))
    score = 0
    if 3 <= sections <= 5:
        score += 30
    if sections == 4:
        score += 12
    if 9 <= ideas <= 15:
        score += 30
    if ideas == 11:
        score += 10
    if examples > 0:
        score += 12
    if references > 0:
        score += 12
    if examples > 0 and references > 0:
        score += 10
    if testimony:
        score += 18
    if 200 <= src_words <= 600:
        score += 10
    if missing:
        score -= 80
    if sections <= 1:
        score -= 40
    if ideas <= 7:
        score -= 20
    if ideas >= 20 or sections >= 7:
        score -= 40
    if chapter_id == "CH001":
        score -= 8
    return (score, chapter_id)


def select_first_chapter(inventory: Mapping[str, Any]) -> dict[str, Any]:
    rows = list(inventory.get("chapters") or [])
    if not rows:
        raise BookScaleUpPreparation4220Error("Remaining chapter inventory is empty.")
    ranked = sorted(rows, key=selection_score, reverse=True)
    chosen = ranked[0]
    if chosen["chapter_id"] == "CH001" and len(ranked) > 1:
        chosen = ranked[1]
    if chosen["chapter_id"] == ACCEPTED_CHAPTER:
        raise BookScaleUpPreparation4220Error(
            f"{ACCEPTED_CHAPTER} cannot be selected for remaining-chapter generation."
        )
    scores = {
        row["chapter_id"]: selection_score(row)[0]
        for row in rows
    }
    rejected_shortest = [
        row["chapter_id"]
        for row in rows
        if _int(row, "section_count") <= 1 or _int(row, "idea_count") <= 7
    ]
    reasons = [
        (
            f"{chosen['chapter_id']} has {chosen['section_count']} sections and "
            f"{chosen['idea_count']} planned IDEA units, matching the accepted "
            f"{ACCEPTED_CHAPTER} scale without being the shortest remaining chapter."
        ),
        (
            f"The chapter carries {chosen['example_count']} EX and "
            f"{chosen['reference_count']} REF units, which lets the first real "
            "call test the evidence-handle contract."
        ),
        (
            "Example kinds include testimony."
            if "testimony" in list(chosen.get("example_kinds") or [])
            else "Narrative risk is representative of remaining authorial-voice work."
        ),
        (
            "Targeted source context is "
            f"{(chosen.get('estimated_source_context') or {}).get('hydrated_src_words')} "
            "hydrated SRC words. The 38 313-word transcript is not injected."
        ),
        "CH001 was not auto-selected. The shortest chapters were not preferred.",
    ]
    return {
        "phase": PHASE,
        "selected_chapter_id": chosen["chapter_id"],
        "working_title": chosen["working_title"],
        "book_order": chosen["book_order"],
        "section_count": chosen["section_count"],
        "section_ids": list(chosen.get("section_ids") or []),
        "idea_count": chosen["idea_count"],
        "idea_ids": list(chosen.get("idea_ids") or []),
        "example_count": chosen["example_count"],
        "reference_count": chosen["reference_count"],
        "uncertainty_count": chosen["uncertainty_count"],
        "src_count": chosen["src_count"],
        "estimated_source_context": chosen.get("estimated_source_context"),
        "estimated_output_tokens": chosen.get("estimated_output_tokens"),
        "editorial_complexity": chosen.get("editorial_complexity"),
        "coverage_risks": list(chosen.get("coverage_risks") or []),
        "narrative_attribution_risks": list(
            chosen.get("narrative_attribution_risks") or []
        ),
        "anticipated_difficulties": [
            "Prompt 1.1 has never been used in a real provider call.",
            "The 4B.2.17 failure mode — IDEA handles in section metadata but not in paras[].e — must be detected immediately.",
            "Three testimony examples require first-person vs third-person attribution discipline.",
            "No UNC is assigned to this chapter; uncertainty preservation must be re-checked on a later chapter.",
            "Semantic equivalence is not proved by structural validation.",
        ],
        "success_criteria": [
            "Valid transport JSON and reconstructed chapter candidate.",
            "Exact planned sections in EditorialPlan order.",
            "Every assigned IDEA represented by content in the prose.",
            "Justified IDEA handles in paras[].e when correspondence is clear; no invented handles.",
            "SRC, EX, and REF handles drawn only from the supplied allowed set.",
            "No post-hoc invention of paras[].e to satisfy the validator.",
            "No truncation, no publication, budget respected.",
        ],
        "stop_conditions": [
            "Invalid or truncated JSON.",
            "Missing or extra sections.",
            "Missing planned IDEA content or invented IDEA handles.",
            "IDEA handles present in metadata only, absent from paragraph evidence.",
            "Invalid SRC, EX, REF, or UNC handles.",
            "Unknown cost or theoretical maximum above the distinct future cap.",
            "Missing human authorization for this chapter.",
            "Any automatic paid retry.",
        ],
        "reasons": reasons,
        "selection_scores": scores,
        "rejected_automatic_ch001": True,
        "rejected_shortest_only": True,
        "rejected_shortest_chapter_ids": rejected_shortest,
        "not_ch012": chosen["chapter_id"] != ACCEPTED_CHAPTER,
        "expected_chapter_id": EXPECTED_FIRST_CHAPTER_ID,
        "matches_expected_on_this_corpus": (
            chosen["chapter_id"] == EXPECTED_FIRST_CHAPTER_ID
        ),
        "authorized": False,
        "generation_status": "READY" if not chosen.get("missing_src_ids") else "BLOCKED",
        "secrets_included": False,
    }


__all__ = ["select_first_chapter", "selection_score"]
