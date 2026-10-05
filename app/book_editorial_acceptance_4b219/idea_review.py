"""
Content review of the 11 proposed IDEA correspondences.

SRC overlap is recorded and is never sufficient for CONTENT_SUPPORTED.
The accepted chapter is not rewritten. paras[].e is not written.
"""

from __future__ import annotations

from typing import Any

from app.book_editorial_acceptance_4b219.chapter_io import iter_paragraphs
from app.book_editorial_acceptance_4b219.constants import (
    CHAPTER_ID,
    CLASS_CONTENT_SUPPORTED,
    CLASS_NOT_SUPPORTED,
    CLASS_PARTIALLY_SUPPORTED,
    CLASS_UNDETERMINED,
    IDEA_COUNT,
    MAPPING_TABLE_VERSION,
    PHASE,
    PLANNED_IDEA_IDS,
)
from app.book_generation.coverage import assigned_idea_ids_for_chapter, chapter_by_id
from app.book_generation.identity import load_production_inputs
from app.book_generation_4b217.constants import PROJECT_NAME

# Content markers required in the accepted prose. Shared SRC is not a marker.
CONTENT_CRITERIA: dict[str, dict[str, Any]] = {
    "IDEA179": {
        "proposed_paragraphs": ("P000001",),
        "required_all": ("bavardage", "tongues"),
        "required_any_groups": (
            ("all night", "all-night", "night"),
            ("fatigue", "fatiguing", "exhausted"),
        ),
    },
    "IDEA182": {
        "proposed_paragraphs": ("P000002",),
        "required_all": ("scripture", "tongues"),
        "required_any_groups": (("does not work", "do not do", "failure"),),
    },
    "IDEA186": {
        "proposed_paragraphs": ("P000003",),
        "required_all": ("sincere", "ignorance"),
        "required_any_groups": (("did not know", "do not know", "knowledge"),),
    },
    "IDEA180": {
        "proposed_paragraphs": ("P000004",),
        "required_all": ("isaiah 28", "1 corinthians 14"),
        "required_any_groups": (("cool", "refresh"),),
    },
    "IDEA181": {
        "proposed_paragraphs": ("P000006",),
        "required_all": ("five minutes",),
        "required_any_groups": (("fatigued", "fatigue"), ("refresh",)),
    },
    "IDEA237": {
        "proposed_paragraphs": ("P000007",),
        "required_all": ("peace",),
        "required_any_groups": (("spirit of god praying", "praying through"),),
    },
    "IDEA184": {
        "proposed_paragraphs": ("P000009",),
        "additional_supporting_paragraphs": ("P000008",),
        "required_all": ("tired",),
        "required_any_groups": (("wrong doctrine", "correction"),),
    },
    "IDEA185": {
        "proposed_paragraphs": ("P000010",),
        "required_all": ("ceiling",),
        "required_any_groups": (
            ("never come", "never gone", "not absent"),
            ("touch", "reach"),
        ),
    },
    "IDEA238": {
        "proposed_paragraphs": ("P000011",),
        "required_all": ("sincere", "rest"),
        "required_any_groups": (("not doing it well", "correction"),),
    },
    "IDEA212": {
        "proposed_paragraphs": ("P000012", "P000013"),
        "required_all": ("isaiah 44:3", "thirst"),
        "required_any_groups": (("pour",), ("beatitude", "righteousness")),
        "split_across_paragraphs": True,
    },
    "IDEA213": {
        "proposed_paragraphs": ("P000014",),
        "required_all": ("spiritual hunger", "no respecter of persons"),
        "required_any_groups": (("reveal", "discovered"),),
    },
}


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _markers_present(prose: str, markers: tuple[str, ...]) -> list[str]:
    haystack = _normalize(prose)
    return [marker for marker in markers if marker in haystack]


def _groups_present(prose: str, groups: tuple[tuple[str, ...], ...]) -> list[str]:
    found: list[str] = []
    for group in groups:
        hits = _markers_present(prose, group)
        if hits:
            found.append(hits[0])
    return found


def classify_content(*, missing_required: list[str], missing_groups: int, required_groups: int) -> str:
    if not missing_required and missing_groups == 0:
        return CLASS_CONTENT_SUPPORTED
    if missing_required and missing_groups == required_groups:
        return CLASS_NOT_SUPPORTED
    if missing_required or missing_groups:
        return CLASS_PARTIALLY_SUPPORTED
    return CLASS_UNDETERMINED


def src_overlap_alone_is_not_support() -> bool:
    return True


def review_idea_mappings(
    chapter: dict[str, Any],
    *,
    source_map=None,
    plan=None,
) -> dict[str, Any]:
    if source_map is None or plan is None:
        inputs = load_production_inputs(PROJECT_NAME)
        source_map = source_map or inputs.source_map
        plan = plan or inputs.plan
    editorial = chapter_by_id(plan, CHAPTER_ID)
    planned = list(assigned_idea_ids_for_chapter(editorial))
    idea_index = {item.idea_id: item for item in source_map.ideas}
    paragraphs = {pid: row for pid, row in iter_paragraphs(chapter)}
    rows = []
    counts = {
        CLASS_CONTENT_SUPPORTED: 0,
        CLASS_PARTIALLY_SUPPORTED: 0,
        CLASS_NOT_SUPPORTED: 0,
        CLASS_UNDETERMINED: 0,
    }
    for idea_id in planned:
        idea = idea_index.get(idea_id)
        criteria = CONTENT_CRITERIA.get(idea_id) or {}
        proposed = list(criteria.get("proposed_paragraphs") or ())
        additional = list(criteria.get("additional_supporting_paragraphs") or ())
        idea_src = list(getattr(idea, "source_refs", ()) or [])
        paragraph_reviews = []
        combined_texts = []
        for paragraph_id in proposed:
            row = paragraphs.get(paragraph_id) or {}
            text = str(row.get("text") or "")
            combined_texts.append(text)
            shared = sorted(set(idea_src).intersection(set(row.get("source_refs") or [])))
            paragraph_reviews.append(
                {
                    "paragraph_id": paragraph_id,
                    "section_id": row.get("section_id") or "",
                    "shared_src": shared,
                    "src_overlap_alone_is_not_support": True,
                    "accepted_text": text,
                }
            )
        combined = "\n".join(combined_texts)
        required_all = tuple(criteria.get("required_all") or ())
        required_groups = tuple(criteria.get("required_any_groups") or ())
        present_required = _markers_present(combined, required_all)
        present_groups = _groups_present(combined, required_groups)
        missing_required = [item for item in required_all if item not in present_required]
        missing_group_count = len(required_groups) - len(present_groups)
        status = classify_content(
            missing_required=missing_required,
            missing_groups=missing_group_count,
            required_groups=len(required_groups),
        )
        if not required_all and not required_groups:
            status = CLASS_UNDETERMINED
        counts[status] += 1
        editorial_section = next(
            (
                section.section_id
                for section in editorial.sections
                if idea_id in section.idea_refs
            ),
            "",
        )
        rows.append(
            {
                "idea_id": idea_id,
                "source_map_summary": getattr(idea, "summary", ""),
                "source_map_src": idea_src,
                "editorial_section": editorial_section,
                "proposed_paragraphs": proposed,
                "additional_supporting_paragraphs": additional,
                "split_across_paragraphs": bool(criteria.get("split_across_paragraphs")),
                "status": status,
                "content_markers_present": present_required + present_groups,
                "content_markers_missing": missing_required,
                "src_overlap_recorded": any(item["shared_src"] for item in paragraph_reviews),
                "confirmed_on_src_overlap_alone": False,
                "applied_to_accepted_chapter": False,
                "written_into_paragraph_evidence": False,
                "semantic_certificate": False,
                "paragraphs": paragraph_reviews,
                "justification": _justification(idea_id, status, present_required, present_groups),
            }
        )
    return {
        "phase": PHASE,
        "table_version": MAPPING_TABLE_VERSION,
        "chapter_id": CHAPTER_ID,
        "ideas_planned": planned,
        "ideas_expected": IDEA_COUNT,
        "planned_ids_match": planned == list(PLANNED_IDEA_IDS),
        "counts": counts,
        "content_supported": [
            row["idea_id"] for row in rows if row["status"] == CLASS_CONTENT_SUPPORTED
        ],
        "partially_supported": [
            row["idea_id"] for row in rows if row["status"] == CLASS_PARTIALLY_SUPPORTED
        ],
        "not_supported": [
            row["idea_id"] for row in rows if row["status"] == CLASS_NOT_SUPPORTED
        ],
        "undetermined": [
            row["idea_id"] for row in rows if row["status"] == CLASS_UNDETERMINED
        ],
        "mappings": rows,
        "many_to_many_preserved": True,
        "src_overlap_alone_rejected": src_overlap_alone_is_not_support(),
        "written_into_paragraph_evidence": False,
        "accepted_chapter_modified": False,
        "not_a_semantic_certificate": True,
        "future_production_projection_must_keep_this_table": True,
        "secrets_included": False,
    }


def _justification(
    idea_id: str,
    status: str,
    present_required: list[str],
    present_groups: list[str],
) -> str:
    notes = {
        "IDEA179": (
            "P000001 restates all-night tongues as bavardage and fatigue "
            "rather than effective prayer. Classification uses those claims, "
            "not the shared SRC004846/850/851 identifiers."
        ),
        "IDEA182": (
            "P000002 restates that tongues do not work because believers do "
            "not do what Scripture instructs. The extra gloss that the "
            "failure was not in the gift itself is a fidelity note, not the "
            "basis of the correspondence."
        ),
        "IDEA186": (
            "P000003 restates sincerity, ignorance, and the lack of correct "
            "knowledge. First-person we is the accepted 4B.2.18 voice, not a "
            "new idea."
        ),
        "IDEA180": (
            "P000004 states cooling/refreshing as a primary purpose and names "
            "Isaiah 28 and 1 Corinthians 14. UNC029 sits on the same paragraph "
            "and does not remove that support."
        ),
        "IDEA181": (
            "P000006 states the five-minute counsel when fatigued and contrasts "
            "it with all-night fatigue."
        ),
        "IDEA237": (
            "P000007 states that praying in tongues brings peace and that this "
            "is the Spirit of God praying through the believer."
        ),
        "IDEA184": (
            "P000009 states that God said the speaker was tired and that "
            "continuing without correction would lead to a wrong doctrine. "
            "P000008 is adjacent testimony (EX030), not required for this idea."
        ),
        "IDEA185": (
            "P000010 keeps God as never having come or gone elsewhere and "
            "keeps the ceiling / touch-or-reach question. The gloss "
            "'meaning He was not absent' is a fidelity note."
        ),
        "IDEA238": (
            "P000011 quotes sincerity, 'not doing it well', correction, and "
            "true rest. The 4B.2.16 heuristic called this IDENTIFIER_ONLY "
            "because summary tokens such as spiritual/practices/incorrectly "
            "are absent. This review uses the accepted claims, not SRC006452."
        ),
        "IDEA212": (
            "The SourceMap idea already joins Isaiah 44:3 with the beatitude. "
            "P000012 carries the pouring on the thirsty; P000013 carries the "
            "beatitude. Split coverage is allowed and is not SRC-only."
        ),
        "IDEA213": (
            "P000014 states spiritual hunger as the single condition, that "
            "God is no respecter of persons, and that He wants to be discovered "
            "by those who hunger."
        ),
    }
    prefix = f"{status}. Markers={present_required + present_groups}. "
    return prefix + notes.get(idea_id, "Content markers evaluated against accepted prose.")


__all__ = [
    "CONTENT_CRITERIA",
    "classify_content",
    "review_idea_mappings",
    "src_overlap_alone_is_not_support",
]
