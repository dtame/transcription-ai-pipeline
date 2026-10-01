"""Explicit semantic review of the reconstructed production EditorialPlan."""

from __future__ import annotations

from typing import Any, Mapping

from app.editorial_planning.constants import DEFERRAL_REASONS, EXCLUSION_REASONS
from app.source_analysis.models import SourceMap

_CERTAINTY_MARKERS = (
    "definitely",
    "without doubt",
    "we now know",
    "it is certain that",
    "resolved that",
    "confirmed that",
)
_MANUSCRIPT_MARKERS = (
    "dear reader",
    "in this chapter we will write",
    "the manuscript",
)


def _blob(plan: Mapping[str, Any]) -> str:
    chapters = list(plan.get("chapters") or [])
    sections = [
        section
        for chapter in chapters
        if isinstance(chapter, Mapping)
        for section in (chapter.get("sections") or [])
        if isinstance(section, Mapping)
    ]
    parts = [
        str(plan.get("selected_title") or ""),
        str(plan.get("subtitle") or ""),
        str(plan.get("editorial_angle") or ""),
        str(plan.get("target_reader") or ""),
        str((plan.get("book_concept") or {}).get("purpose") or ""),
        str((plan.get("book_concept") or {}).get("core_subject") or ""),
        str((plan.get("book_concept") or {}).get("reader_journey") or ""),
        str((plan.get("book_concept") or {}).get("editorial_progression") or ""),
    ]
    for chapter in chapters:
        if isinstance(chapter, Mapping):
            parts.extend(
                [
                    str(chapter.get("working_title") or ""),
                    str(chapter.get("purpose") or ""),
                    str(chapter.get("summary") or ""),
                ]
            )
    for section in sections:
        parts.extend(
            [
                str(section.get("working_title") or ""),
                str(section.get("purpose") or ""),
            ]
        )
    return "\n".join(parts).lower()


def _overlap(a: str, b: str) -> float:
    tokens_a = {tok for tok in "".join(ch.lower() if ch.isalnum() else " " for ch in a).split() if len(tok) > 3}
    tokens_b = {tok for tok in "".join(ch.lower() if ch.isalnum() else " " for ch in b).split() if len(tok) > 3}
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a)


def review_semantics(
    plan: Mapping[str, Any] | None,
    source_map: SourceMap,
    *,
    contract: Mapping[str, Any] | None = None,
    chapter_audit: Mapping[str, Any] | None = None,
    section_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    notes: list[str] = []
    issues: list[str] = []
    review_flags: list[str] = []
    if not isinstance(plan, Mapping):
        return {
            "status": "FAIL",
            "primary_question": "FAIL",
            "issues": ["no reconstructed plan"],
            "notes": notes,
        }
    contract = dict(contract or {})
    chapter_audit = dict(chapter_audit or {})
    section_audit = dict(section_audit or {})
    header = source_map.source_analysis
    intent = header.author_intent.summary
    audience = header.target_audience.summary
    theme = header.main_theme
    voice = source_map.author_voice_profile
    blob = _blob(plan)
    titles = list(plan.get("title_candidates") or [])
    selected = str(plan.get("selected_title") or "")
    subtitle = str(plan.get("subtitle") or "")
    angle = str(plan.get("editorial_angle") or "")
    reader = str(plan.get("target_reader") or "")
    concept = dict(plan.get("book_concept") or {})

    title_overlap = max(
        (_overlap(selected, theme), _overlap(selected, intent), _overlap(selected, audience))
    )
    if selected and title_overlap < 0.02:
        review_flags.append("selected title has very little lexical overlap with SourceMap theme/intent")
    title_reviews = []
    for item in titles:
        if not isinstance(item, Mapping):
            continue
        title = str(item.get("title") or "")
        rationale = str(item.get("rationale") or "")
        overlap = max(_overlap(title, theme), _overlap(title, intent))
        unsupported_promise = any(
            marker in title.lower()
            for marker in ("guaranteed", "secret formula", "never before")
        )
        title_reviews.append(
            {
                "title": title,
                "rationale": rationale,
                "source_support": "PASS" if overlap >= 0.02 or theme[:20].lower() in title.lower() else "REVIEW",
                "scope": "REVIEW" if len(title) > 90 else "PASS",
                "unsupported_promise": "FAIL" if unsupported_promise else "PASS",
                "fit_with_author_intent": "PASS" if overlap >= 0.02 else "REVIEW",
            }
        )

    if any(row.get("unsupported_promise") == "FAIL" for row in title_reviews):
        issues.append("title candidate makes an unsupported promise")

    reader_overlap = _overlap(reader, audience)
    if reader and audience and reader_overlap < 0.02:
        review_flags.append("target reader weakly aligned with SourceMap audience")

    angle_overlap = max(_overlap(angle, theme), _overlap(angle, intent))
    if angle and angle_overlap < 0.02:
        review_flags.append("editorial angle weakly aligned with SourceMap intent/theme")

    concept_text = " ".join(str(concept.get(key) or "") for key in ("purpose", "core_subject", "reader_journey", "editorial_progression"))
    if concept_text and max(_overlap(concept_text, theme), _overlap(concept_text, intent)) < 0.02:
        review_flags.append("book concept weakly aligned with SourceMap")

    for marker in _CERTAINTY_MARKERS:
        if marker in blob:
            issues.append(f"possible uncertainty-to-certainty language: {marker}")
    for marker in _MANUSCRIPT_MARKERS:
        if marker in blob:
            issues.append(f"manuscript leakage marker: {marker}")

    coverage_rows = list(plan.get("idea_coverage") or [])
    ideas = {idea.idea_id: idea for idea in source_map.ideas}
    excluded = [
        row
        for row in coverage_rows
        if isinstance(row, Mapping) and row.get("disposition") == "EXCLUDED"
    ]
    deferred = [
        row
        for row in coverage_rows
        if isinstance(row, Mapping) and row.get("disposition") == "DEFERRED"
    ]
    excluded_reviews = []
    for row in excluded:
        idea_id = str(row.get("idea_id") or "")
        idea = ideas.get(idea_id)
        reason = str(row.get("reason") or "")
        summary = idea.summary if idea is not None else ""
        importance = idea.importance if idea is not None else ""
        kind = idea.kind if idea is not None else ""
        compelling = reason in EXCLUSION_REASONS
        substantive = importance in {"high", "medium"} or kind in {"claim", "explanation"}
        verdict = "PASS"
        if not compelling:
            verdict = "FAIL"
            issues.append(f"{idea_id} EXCLUDED without valid closed reason")
        elif substantive and reason in {"non_substantive", "administrative"}:
            verdict = "REVIEW_REQUIRED"
            review_flags.append(
                f"{idea_id} excluded as {reason} but SourceMap marks it {importance}/{kind}: {summary[:160]}"
            )
        excluded_reviews.append(
            {
                "idea_id": idea_id,
                "reason": reason,
                "note": row.get("note"),
                "summary": summary,
                "kind": kind,
                "importance": importance,
                "verdict": verdict,
            }
        )
    deferred_reviews = []
    for row in deferred:
        idea_id = str(row.get("idea_id") or "")
        idea = ideas.get(idea_id)
        reason = str(row.get("reason") or "")
        summary = idea.summary if idea is not None else ""
        compelling = reason in DEFERRAL_REASONS
        verdict = "PASS" if compelling else "FAIL"
        if not compelling:
            issues.append(f"{idea_id} DEFERRED without valid closed reason")
        deferred_reviews.append(
            {
                "idea_id": idea_id,
                "reason": reason,
                "note": row.get("note"),
                "summary": summary,
                "kind": idea.kind if idea is not None else "",
                "importance": idea.importance if idea is not None else "",
                "verdict": verdict,
            }
        )

    unc_handling = dict(plan.get("uncertainty_handling") or {})
    assigned_unc = list(unc_handling.get("assigned_uncertainty_refs") or [])
    unassigned_unc = list(unc_handling.get("unassigned_uncertainty_refs") or [])
    if source_map.uncertainties and not assigned_unc and not unassigned_unc:
        issues.append("UNC present in SourceMap but none listed assigned or unassigned")
    unc_ok = contract.get("uncertainty_preservation") == "PASS"
    if not unc_ok:
        issues.append("uncertainty preservation technical gate failed")

    examples_ok = int((contract.get("unknown_refs") or {}).get("unknown_example_refs") or 0) == 0
    refs_ok = int((contract.get("unknown_refs") or {}).get("unknown_reference_refs") or 0) == 0
    if not examples_ok:
        issues.append("unknown example refs")
    if not refs_ok:
        issues.append("unknown reference refs")

    coverage_complete = bool((contract.get("idea_coverage") or {}).get("coverage_complete"))
    if not coverage_complete:
        issues.append("IDEA coverage incomplete")

    invention_ok = contract.get("invention_boundary") == "PASS"
    if not invention_ok:
        issues.append("invention boundary failed")
    if chapter_audit.get("status") == "FAIL" or section_audit.get("status") == "FAIL":
        issues.append("chapter or section support failed")

    chapters = list(plan.get("chapters") or [])
    progression_ok = len(chapters) >= 2
    if not progression_ok:
        issues.append("insufficient chapters for a book organization")

    voice_conflict = False
    voice_blob = " ".join(
        [
            " ".join(voice.tone),
            voice.register,
            voice.sentence_style,
        ]
    ).lower()
    if "oral" in voice_blob and "academic monograph" in blob:
        voice_conflict = True
        review_flags.append("editorial framing may contradict observed oral voice")

    leakage = bool(section_audit.get("manuscript_leakage_sections"))
    if leakage:
        review_flags.append("possible manuscript leakage in section purposes")

    coverage_note = (
        "286/286 technical coverage does not by itself prove good editorial organization. "
        f"Chapters={len(chapters)}; assigned={(contract.get('idea_coverage') or {}).get('assigned')}; "
        f"deferred={len(deferred)}; excluded={len(excluded)}."
    )
    notes.append(coverage_note)

    primary = (
        contract.get("structured_parse") == "PASS"
        and contract.get("canonical_reconstruction") == "PASS"
        and coverage_complete
        and invention_ok
        and contract.get("traceability") == "PASS"
        and not issues
    )
    if issues:
        status = "FAIL"
    elif review_flags:
        status = "REVIEW_REQUIRED"
    elif primary:
        status = "PASS"
    else:
        status = "REVIEW_REQUIRED"

    return {
        "status": status,
        "primary_question": (
            "PASS"
            if status == "PASS"
            else ("REVIEW_REQUIRED" if status == "REVIEW_REQUIRED" else "FAIL")
        ),
        "primary_question_text": (
            "Does this plan provide a faithful and coherent organization of the "
            "validated SourceMap into a potential book WITHOUT inventing the book's "
            "substantive content?"
        ),
        "coverage": "PASS" if coverage_complete else "FAIL",
        "coverage_note": coverage_note,
        "order": "PASS" if progression_ok else "FAIL",
        "boundaries": chapter_audit.get("status") or "REVIEW",
        "repetition": (
            "REVIEW"
            if int((contract.get("idea_coverage") or {}).get("reused") or 0) > 40
            else "PASS"
        ),
        "exclusions": (
            "FAIL"
            if any(row["verdict"] == "FAIL" for row in excluded_reviews)
            else (
                "REVIEW_REQUIRED"
                if any(row["verdict"] == "REVIEW_REQUIRED" for row in excluded_reviews)
                else "PASS"
            )
        ),
        "deferred": (
            "FAIL"
            if any(row["verdict"] == "FAIL" for row in deferred_reviews)
            else "PASS"
        ),
        "uncertainty": "PASS" if unc_ok else "FAIL",
        "author_intent": "PASS" if angle_overlap >= 0.02 or not angle else "REVIEW",
        "audience": "PASS" if reader_overlap >= 0.02 or not reader else "REVIEW",
        "voice": "REVIEW" if voice_conflict else "PASS",
        "title_review": title_reviews,
        "selected_title": selected,
        "subtitle": subtitle,
        "editorial_angle": angle,
        "target_reader": reader,
        "book_concept": concept,
        "source_theme": theme,
        "source_author_intent": intent,
        "source_audience": audience,
        "source_voice": {
            "tone": list(voice.tone),
            "register": voice.register,
            "sentence_style": voice.sentence_style,
        },
        "excluded_ideas": excluded_reviews,
        "deferred_ideas": deferred_reviews,
        "assigned_uncertainty_refs": assigned_unc,
        "unassigned_uncertainty_refs": unassigned_unc,
        "issues": issues,
        "review_flags": review_flags,
        "notes": notes,
        "invention_boundary": contract.get("invention_boundary"),
        "traceability": contract.get("traceability"),
        "manuscript_leakage": "FAIL" if leakage and status == "FAIL" else ("REVIEW" if leakage else "PASS"),
    }


__all__ = ["review_semantics"]
