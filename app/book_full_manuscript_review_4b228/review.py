"""Deterministic offline editorial consolidation. No external model calls."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.book_generation_4b223.editorial import (
    _EXTERNAL_FRAME,
    _FIRST_PERSON,
    _SECOND_PERSON,
    _STRENGTHENED,
)
from app.book_full_manuscript_review_4b228.constants import (
    HISTORICAL_EX_REF_OBSERVATIONS,
    HUMAN_ACCEPTANCE_STATUS,
    HUMAN_REVIEW_PENDING_STATUS,
    PENDING_CHAPTER_IDS,
    PHASE,
    REVIEW_NO_ISSUE,
    REVIEW_POTENTIAL,
    REVIEW_UNDETERMINED,
    STRENGTHENED_CLAIM_CHAPTER_IDS,
)
from app.book_generation.coverage import chapter_by_id
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus

_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "that",
        "this",
        "with",
        "from",
        "have",
        "has",
        "had",
        "was",
        "were",
        "are",
        "for",
        "not",
        "but",
        "you",
        "your",
        "they",
        "them",
        "their",
        "his",
        "her",
        "she",
        "him",
        "who",
        "what",
        "when",
        "into",
        "onto",
        "than",
        "then",
        "there",
        "here",
        "will",
        "would",
        "could",
        "should",
        "about",
        "been",
        "being",
        "over",
        "after",
        "before",
        "because",
    }
)
_THIRD_PERSON = re.compile(r"\b(he|she|they|him|her|them|his|their)\b", re.IGNORECASE)
_IMPERSONAL = re.compile(
    r"\b(one must|it is said|it was said|people were told|believers are)\b",
    re.IGNORECASE,
)


def _load_json(path: str) -> dict[str, Any] | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.is_file():
        return None
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z']{4,}", text.lower())
    return {word for word in words if word not in _STOPWORDS}


def review_strengthened_claims(inventory: dict[str, Any]) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    by_id = {row["chapter_id"]: row for row in inventory.get("chapters") or []}
    for chapter_id in STRENGTHENED_CLAIM_CHAPTER_IDS:
        row = by_id[chapter_id]
        editorial = _load_json(row.get("editorial_review_path") or "")
        flagged = []
        if editorial:
            flagged = [
                item
                for item in (editorial.get("potential_substantive_issues") or [])
                if item.get("code") == "STRENGTHENED_CLAIM"
            ]
        matches: list[dict[str, Any]] = []
        for paragraph in row["paragraphs"]:
            for match in _STRENGTHENED.finditer(paragraph["text"]):
                src = [
                    handle
                    for handle in paragraph["evidence_handles"]
                    if str(handle).startswith("SRC")
                ]
                matches.append(
                    {
                        "section_id": paragraph["section_id"],
                        "section_title": paragraph["section_title"],
                        "paragraph_id": paragraph["paragraph_id"],
                        "exact_formulation": paragraph["text"],
                        "matched_token": match.group(0),
                        "src_handles": src,
                    }
                )
        observations.append(
            {
                "chapter_id": chapter_id,
                "section": matches[0]["section_id"] if matches else "",
                "paragraph": matches[0]["paragraph_id"] if matches else "",
                "exact_formulation": matches[0]["exact_formulation"] if matches else "",
                "matched_spans": matches,
                "src_associated": matches[0]["src_handles"] if matches else [],
                "reason": (
                    (flagged[0].get("detail") if flagged else "")
                    or "Absolute wording may strengthen a source claim."
                ),
                "historical_review_present": bool(flagged),
                "confidence": "high_lexical_match"
                if matches
                else "review_flag_without_localized_span",
                "always_or_never_is_not_automatic_error": True,
                "decision_required": (
                    "HUMAN_REVIEW — keep or revise the formulation. "
                    "No automatic replacement."
                ),
                "automatic_rewrite_forbidden": True,
            }
        )
    return {
        "phase": PHASE,
        "observation_count": len(observations),
        "chapters": list(STRENGTHENED_CLAIM_CHAPTER_IDS),
        "observations": observations,
        "semantic_certification": "NOT PERFORMED",
        "automatic_correction": False,
        "secrets_included": False,
    }


def _classify_ex_ref_item(
    *,
    chapter_id: str,
    item: dict[str, Any],
    prose: str,
    historical_note: str = "",
) -> dict[str, Any]:
    item_id = str(item.get("id") or "")
    kind = str(item.get("kind") or "")
    status = str(item.get("status") or "")
    traced = bool(item.get("traced"))
    handle_in_prose = bool(item_id) and item_id in prose
    if traced and status == "present_and_traced":
        category = "reference_traceable_in_metadata"
    elif handle_in_prose:
        category = "reference_present_in_text"
    elif status == "undetermined_handle_absent_is_not_omission":
        category = "correspondence_uncertain"
    else:
        category = "reference_potentially_omitted"
    return {
        "chapter_id": chapter_id,
        "kind": kind,
        "id": item_id,
        "status": status or "not_in_existing_review",
        "traced_in_metadata": traced,
        "handle_present_in_prose": handle_in_prose,
        "category": category,
        "historical_note": historical_note,
        "correspondence_invented": False,
        "automatic_omission": False,
    }


def review_references_examples(inventory: dict[str, Any]) -> dict[str, Any]:
    by_id = {row["chapter_id"]: row for row in inventory.get("chapters") or []}
    historical: list[dict[str, Any]] = []
    for spec in HISTORICAL_EX_REF_OBSERVATIONS:
        row = by_id[spec["chapter_id"]]
        review = _load_json(row.get("ex_ref_review_path") or "")
        items = list((review or {}).get("items") or [])
        match = next(
            (
                item
                for item in items
                if item.get("kind") == spec["kind"] and item.get("id") == spec["id"]
            ),
            {"kind": spec["kind"], "id": spec["id"], "status": "not_in_existing_review"},
        )
        prose = "\n".join(paragraph["text"] for paragraph in row["paragraphs"])
        historical.append(
            _classify_ex_ref_item(
                chapter_id=spec["chapter_id"],
                item=match,
                prose=prose,
                historical_note=spec["historical_note"],
            )
        )
    similar: list[dict[str, Any]] = []
    for chapter_id in PENDING_CHAPTER_IDS:
        row = by_id[chapter_id]
        review = _load_json(row.get("ex_ref_review_path") or "")
        prose = "\n".join(paragraph["text"] for paragraph in row["paragraphs"])
        for item in (review or {}).get("items") or []:
            if item.get("kind") not in {"EX", "REF"}:
                continue
            if item.get("status") != "undetermined_handle_absent_is_not_omission":
                continue
            similar.append(
                _classify_ex_ref_item(
                    chapter_id=chapter_id,
                    item=item,
                    prose=prose,
                    historical_note="Similar handle-absent observation among the 13 new chapters.",
                )
            )
    return {
        "phase": PHASE,
        "historical_observations": historical,
        "similar_observations_in_new_chapters": similar,
        "similar_observation_count": len(similar),
        "categories_used": [
            "reference_present_in_text",
            "reference_traceable_in_metadata",
            "reference_potentially_omitted",
            "correspondence_uncertain",
        ],
        "no_correspondence_invented": True,
        "handle_absence_is_not_automatic_omission": True,
        "semantic_certification": "NOT PERFORMED",
        "secrets_included": False,
    }


def review_continuity(inventory: dict[str, Any]) -> dict[str, Any]:
    chapters = list(inventory.get("chapters") or [])
    observations: list[dict[str, Any]] = []
    succession: list[dict[str, Any]] = []
    for index, row in enumerate(chapters):
        succession.append(
            {
                "book_order": row["book_order"],
                "chapter_id": row["chapter_id"],
                "title": row["title"],
                "purpose": row.get("purpose") or "",
                "summary": row.get("summary") or "",
            }
        )
        if index == 0:
            continue
        previous = chapters[index - 1]
        prev_last = previous["paragraphs"][-1]["text"] if previous["paragraphs"] else ""
        next_first = row["paragraphs"][0]["text"] if row["paragraphs"] else ""
        overlap = _content_words(prev_last) & _content_words(next_first)
        if not overlap:
            observations.append(
                {
                    "code": "POSSIBLE_ABRUPT_TRANSITION",
                    "chapter_from": previous["chapter_id"],
                    "chapter_to": row["chapter_id"],
                    "from_title": previous["title"],
                    "to_title": row["title"],
                    "detail": (
                        "No shared content word of length ≥ 4 between the last "
                        "paragraph of the previous chapter and the first "
                        "paragraph of the next chapter."
                    ),
                    "automatic_correction": False,
                }
            )
        prev_ideas = set(previous.get("covered_idea_ids") or [])
        next_ideas = set(row.get("covered_idea_ids") or [])
        shared_ideas = sorted(prev_ideas & next_ideas)
        if shared_ideas:
            observations.append(
                {
                    "code": "SHARED_IDEA_HANDLES",
                    "chapter_from": previous["chapter_id"],
                    "chapter_to": row["chapter_id"],
                    "handles": shared_ideas,
                    "detail": "Consecutive chapters share one or more IDEA handles.",
                    "automatic_correction": False,
                }
            )
        title_overlap = _content_words(previous["title"]) & _content_words(row["title"])
        if title_overlap:
            observations.append(
                {
                    "code": "VISIBLE_TITLE_LEXICAL_OVERLAP",
                    "chapter_from": previous["chapter_id"],
                    "chapter_to": row["chapter_id"],
                    "tokens": sorted(title_overlap),
                    "detail": "Consecutive chapter titles share visible lexical tokens.",
                    "automatic_correction": False,
                }
            )
    return {
        "phase": PHASE,
        "order": [row["chapter_id"] for row in chapters],
        "titles": [row["title"] for row in chapters],
        "theme_succession": succession,
        "observations": observations,
        "observation_count": len(observations),
        "semantic_certification": "NOT PERFORMED",
        "automatic_correction": False,
        "secrets_included": False,
    }


def review_voice(inventory: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for chapter in inventory.get("chapters") or []:
        text = "\n".join(paragraph["text"] for paragraph in chapter["paragraphs"])
        frames = sorted({match.group(0) for match in _EXTERNAL_FRAME.finditer(text)})
        first_person = bool(_FIRST_PERSON.search(text))
        second_person = bool(_SECOND_PERSON.search(text))
        third_person = bool(_THIRD_PERSON.search(text))
        impersonal = sorted({match.group(0) for match in _IMPERSONAL.finditer(text)})
        editorial = _load_json(chapter.get("editorial_review_path") or "")
        historical_frames = list(
            ((editorial or {}).get("authorial_voice") or {}).get("conference_report_frames")
            or []
        )
        rows.append(
            {
                "chapter_id": chapter["chapter_id"],
                "first_person_observed": first_person,
                "second_person_observed": second_person,
                "third_person_observed": third_person,
                "conference_report_frames": frames or historical_frames,
                "impersonal_formulations": impersonal,
                "third_person_is_not_automatic_voice_error": True,
                "classification": (
                    "REVIEW_RECOMMENDED"
                    if frames or impersonal
                    else REVIEW_NO_ISSUE
                ),
            }
        )
    return {
        "phase": PHASE,
        "chapters": rows,
        "note": (
            "Third-person narration is not treated as a voice error by itself. "
            "These are deterministic lexical cues only."
        ),
        "semantic_certification": "NOT PERFORMED",
        "automatic_correction": False,
        "secrets_included": False,
    }


def review_possible_omissions(
    inventory: dict[str, Any],
    *,
    corpus: CanonicalCorpus,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for chapter in inventory.get("chapters") or []:
        planned = chapter_by_id(corpus.plan, chapter["chapter_id"])
        expected_ex: set[str] = set()
        expected_ref: set[str] = set()
        expected_unc: set[str] = set()
        for section in planned.sections:
            expected_ex.update(str(item) for item in section.example_refs)
            expected_ref.update(str(item) for item in section.reference_refs)
            expected_unc.update(str(item) for item in section.uncertainty_refs)
        declared_ex = {
            handle
            for paragraph in chapter["paragraphs"]
            for handle in paragraph.get("example_refs") or []
            if str(handle).startswith("EX")
        }
        declared_ref = {
            handle
            for paragraph in chapter["paragraphs"]
            for handle in paragraph.get("reference_refs") or []
            if str(handle).startswith("REF")
        }
        declared_unc = {
            handle
            for paragraph in chapter["paragraphs"]
            for handle in paragraph.get("uncertainty_refs") or []
            if str(handle).startswith("UNC")
        }
        rows.append(
            {
                "chapter_id": chapter["chapter_id"],
                "ideas_expected": chapter["idea_expected_count"],
                "ideas_declared": chapter["idea_covered_count"],
                "ex_expected": sorted(expected_ex),
                "ex_declared": sorted(declared_ex),
                "ex_absent_from_handles": sorted(expected_ex - declared_ex),
                "ref_expected": sorted(expected_ref),
                "ref_declared": sorted(declared_ref),
                "ref_absent_from_handles": sorted(expected_ref - declared_ref),
                "unc_expected": sorted(expected_unc),
                "unc_declared": sorted(declared_unc),
                "unc_absent_from_handles": sorted(expected_unc - declared_unc),
                "declared_idea_is_not_semantic_proof": True,
            }
        )
    return {
        "phase": PHASE,
        "chapters": rows,
        "limits": [
            "A declared IDEA handle is not proof of faithful restatement.",
            "A missing EX/REF handle is not treated as a content omission.",
            "This review is structural and lexical only.",
            "No external semantic model was called.",
        ],
        "semantic_certification": "NOT PERFORMED",
        "automatic_correction": False,
        "secrets_included": False,
    }


def render_editorial_markdown(
    *,
    continuity: dict[str, Any],
    voice: dict[str, Any],
    strengthened: dict[str, Any],
    references: dict[str, Any],
    omissions: dict[str, Any],
    inventory: dict[str, Any],
) -> str:
    lines = [
        "# Editorial global review — Phase 4B.2.28",
        "",
        "Offline deterministic consolidation only. No external model was called. "
        "No chapter was rewritten.",
        "",
        "## Continuity",
        "",
        "Canonical order: " + ", ".join(continuity.get("order") or []) + ".",
        "",
    ]
    for item in continuity.get("theme_succession") or []:
        lines.append(
            f"- {item['chapter_id']} — {item['title']}: {item.get('summary') or item.get('purpose')}"
        )
    lines.extend(["", "### Continuity observations", ""])
    if not continuity.get("observations"):
        lines.append("No deterministic continuity observation was recorded.")
    for item in continuity.get("observations") or []:
        lines.append(
            f"- `{item.get('code')}` {item.get('chapter_from', '')} → "
            f"{item.get('chapter_to', '')}: {item.get('detail')}"
        )
    lines.extend(["", "## Authorial voice", "",])
    for item in voice.get("chapters") or []:
        lines.append(
            f"- {item['chapter_id']}: first_person={item['first_person_observed']}, "
            f"second_person={item['second_person_observed']}, "
            f"third_person={item['third_person_observed']}, "
            f"frames={item['conference_report_frames'] or 'none'}, "
            f"impersonal={item['impersonal_formulations'] or 'none'}. "
            "Third person is not an automatic voice error."
        )
    lines.extend(["", "## Strengthened claims", ""])
    for item in strengthened.get("observations") or []:
        span = item.get("matched_spans") or []
        token = span[0]["matched_token"] if span else "not localized"
        lines.append(
            f"- {item['chapter_id']} {item.get('section') or ''} "
            f"{item.get('paragraph') or ''}: token `{token}`; "
            f"confidence={item['confidence']}; decision={item['decision_required']}"
        )
    lines.extend(["", "## References and examples", "", "### Historical", ""])
    for item in references.get("historical_observations") or []:
        lines.append(
            f"- {item['chapter_id']} {item['kind']} {item['id']}: "
            f"{item['category']} — {item['historical_note']}"
        )
    lines.extend(["", "### Similar observations in the 13 new chapters", ""])
    similar = list(references.get("similar_observations_in_new_chapters") or [])
    if not similar:
        lines.append("No similar handle-absent EX/REF observation was found.")
    for item in similar:
        lines.append(
            f"- {item['chapter_id']} {item['kind']} {item['id']}: {item['category']}"
        )
    lines.extend(["", "## Possible omissions", ""])
    for item in omissions.get("chapters") or []:
        lines.append(
            f"- {item['chapter_id']}: IDEA {item['ideas_declared']}/{item['ideas_expected']}; "
            f"EX handles absent {item['ex_absent_from_handles'] or 'none'}; "
            f"REF handles absent {item['ref_absent_from_handles'] or 'none'}; "
            f"UNC handles absent {item['unc_absent_from_handles'] or 'none'}."
        )
    lines.extend(
        [
            "",
            "## Limits",
            "",
            "A declared IDEA is not a complete semantic-fidelity proof.",
            "This review does not certify meaning.",
            "",
            "## Human status",
            "",
            "Accepted: " + ", ".join(inventory.get("accepted_chapter_ids") or []) + ".",
            "Still pending: " + ", ".join(inventory.get("pending_chapter_ids") or []) + ".",
            f"Accepted status remains `{HUMAN_ACCEPTANCE_STATUS}`.",
            f"Pending status remains `{HUMAN_REVIEW_PENDING_STATUS}`.",
            "",
        ]
    )
    return "\n".join(lines)


def editorial_global_review(
    *,
    inventory: dict[str, Any],
    corpus: CanonicalCorpus,
) -> dict[str, Any]:
    continuity = review_continuity(inventory)
    voice = review_voice(inventory)
    strengthened = review_strengthened_claims(inventory)
    references = review_references_examples(inventory)
    omissions = review_possible_omissions(inventory, corpus=corpus)
    markdown = render_editorial_markdown(
        continuity=continuity,
        voice=voice,
        strengthened=strengthened,
        references=references,
        omissions=omissions,
        inventory=inventory,
    )
    return {
        "phase": PHASE,
        "continuity": continuity,
        "voice": voice,
        "strengthened_claims": strengthened,
        "references_examples": references,
        "possible_omissions": omissions,
        "markdown": markdown,
        "payload": {
            "phase": PHASE,
            "continuity_observation_count": continuity["observation_count"],
            "strengthened_claim_observation_count": strengthened["observation_count"],
            "reference_example_historical_count": len(
                references["historical_observations"]
            ),
            "reference_example_similar_count": references["similar_observation_count"],
            "semantic_certification": "NOT PERFORMED",
            "external_model_called": False,
            "automatic_correction": False,
            "accepted_chapters_unchanged": True,
            "pending_chapters_not_approved": True,
            "secrets_included": False,
        },
        "semantic_certification": "NOT PERFORMED",
        "external_model_called": False,
        "secrets_included": False,
    }


__all__ = [
    "editorial_global_review",
    "review_continuity",
    "review_possible_omissions",
    "review_references_examples",
    "review_strengthened_claims",
    "review_voice",
]
