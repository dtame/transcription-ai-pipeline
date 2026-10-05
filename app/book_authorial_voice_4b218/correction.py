"""Minimum necessary CH012 voice corrections. Original chapter stays intact."""

from __future__ import annotations

import copy
from typing import Any

from app.book_authorial_voice_4b218.chapter_io import (
    iter_paragraphs,
    paragraph_ids,
    render_chapter_markdown,
    section_ids,
)
from app.book_authorial_voice_4b218.constants import (
    CLASS_ATTRIBUTION_UNCERTAIN,
    CLASS_EXTERNAL_CONFIRMED,
    EXPECTED_UNCERTAINTY_ID,
    PHASE,
    STATUS_APPLIED,
    STATUS_ATTRIBUTION_UNCERTAIN,
    STATUS_REQUIRES_HUMAN_REVIEW,
    STATUS_UNCHANGED,
    TARGET_CHAPTER_ID,
)

P000003_ORIGINAL = (
    "Those who prayed this way were sincere, even very sincere. But sincerity "
    "was not the issue. The real problem was that they did not know — their "
    "manner of praying rested on ignorance rather than on correct knowledge "
    "of what the practice was for."
)
P000003_CORRECTED = (
    "We were sincere, even very sincere. But sincerity was not the issue. "
    "The real problem was that we did not know — our manner of praying "
    "rested on ignorance rather than on correct knowledge of what the "
    "practice was for."
)
P000004_ORIGINAL = (
    "One of the primary purposes of praying in tongues, as taught here, is "
    "to cool or refresh oneself. This is grounded in Isaiah 28 and in "
    "1 Corinthians 14. The speaker also referred to an earlier passage, "
    "Isaiah chapter 26, locating a related statement in verse 3, though the "
    "connection between chapter 26 and chapter 28 at this point in the "
    "teaching remained unclear in the delivery."
)
P000004_CORRECTED = (
    "One of the primary purposes of praying in tongues is to cool or refresh "
    "oneself. This is grounded in Isaiah 28 and in 1 Corinthians 14. An "
    "earlier passage, Isaiah chapter 26, locating a related statement in "
    "verse 3, though the connection between chapter 26 and chapter 28 at "
    "this point in the teaching remained unclear."
)
P000008_ORIGINAL = (
    "The speaker recounted a personal experience of this correction. He had "
    "prayed so intensely that he ended up on the ground, his voice broken "
    "from the effort. Someone saw the manner in which he had prayed."
)
P000008_CORRECTED = (
    "I had prayed so intensely that I ended up on the ground, my voice "
    "broken from the effort. Someone saw the manner in which I had prayed."
)
P000009_ORIGINAL = (
    "In that state, God spoke to him directly, calling him \"my son\" and "
    "telling him he was tired. God further said that if He left him in that "
    "condition without correction, he would go on to preach a wrong doctrine."
)
P000009_CORRECTED = (
    "In that state, God spoke to me directly, calling me \"my son\" and "
    "telling me I was tired. God further said that if He left me in that "
    "condition without correction, I would go on to preach a wrong doctrine."
)
P000001_ORIGINAL = (
    "Praying all night in tongues, by itself, is not proof of effective "
    "prayer. It can become mere bavardage — fatiguing talk without "
    "discernment — rather than prayer that accomplishes anything. One "
    "speaker was told plainly: \"You just exercised bavardage,\" after a "
    "night spent praying in tongues that left him and others simply exhausted."
)
P000001_PROPOSED = (
    "Praying all night in tongues, by itself, is not proof of effective "
    "prayer. It can become mere bavardage — fatiguing talk without "
    "discernment — rather than prayer that accomplishes anything. The words "
    "were spoken plainly: \"You just exercised bavardage,\" after a night "
    "spent praying in tongues that left us simply exhausted."
)


def correction_catalog() -> list[dict[str, Any]]:
    return [
        {
            "paragraph_id": "P000001",
            "section_id": "SEC047",
            "classification": CLASS_ATTRIBUTION_UNCERTAIN,
            "case": 3,
            "status": STATUS_ATTRIBUTION_UNCERTAIN,
            "applied": False,
            "original": P000001_ORIGINAL,
            "proposed": P000001_PROPOSED,
            "corrected": None,
            "src_proof": [
                "SRC004846 Tu viens juste d'exercer le bavardage.",
                "SRC004850 Nous sommes tellement fatigués.",
                "SRC004851 Nous prions toute la nuit en langue.",
            ],
            "justification": (
                "The source uses tu and nous. It is not proven whether the "
                "author received or delivered 'Tu viens juste d'exercer le "
                "bavardage'. 'I was told' would invent an attribution. "
                "The original text is kept."
            ),
        },
        {
            "paragraph_id": "P000003",
            "section_id": "SEC047",
            "classification": CLASS_EXTERNAL_CONFIRMED,
            "case": 1,
            "status": STATUS_APPLIED,
            "applied": True,
            "original": P000003_ORIGINAL,
            "proposed": P000003_CORRECTED,
            "corrected": P000003_CORRECTED,
            "src_proof": [
                "SRC004918 Nous étions sincères,",
                "SRC004920 nous étions très sincères.",
                "SRC004921 C'est parce que nous ne savions pas.",
                "SRC004923 nous ne connaissons pas.",
            ],
            "justification": (
                "The teaching voice said we were sincere and did not know. "
                "Those/they/their converted that inclusive we into an "
                "external group. Restored we/our. No new autobiographical "
                "detail was added."
            ),
        },
        {
            "paragraph_id": "P000004",
            "section_id": "SEC048",
            "classification": CLASS_EXTERNAL_CONFIRMED,
            "case": 1,
            "status": STATUS_APPLIED,
            "applied": True,
            "original": P000004_ORIGINAL,
            "proposed": P000004_CORRECTED,
            "corrected": P000004_CORRECTED,
            "src_proof": [
                "SRC004854 C'est de refroidir",
                "SRC004856 Isaiah 28 est dans votre Bible.",
                "SRC004879 dans 1 Corinthiens 14.",
                "SRC006457 before chapter 28, chapter 26",
                "SRC006459 he says in verse 3",
            ],
            "justification": (
                "Removed the conference-report frames 'as taught here', "
                "'The speaker also referred', and 'in the delivery'. "
                "Did not write 'I referred', because SRC006459 'he says' "
                "is Isaiah. UNC029 content is kept as unclear."
            ),
        },
        {
            "paragraph_id": "P000008",
            "section_id": "SEC049",
            "classification": CLASS_EXTERNAL_CONFIRMED,
            "case": 1,
            "status": STATUS_APPLIED,
            "applied": True,
            "original": P000008_ORIGINAL,
            "proposed": P000008_CORRECTED,
            "corrected": P000008_CORRECTED,
            "src_proof": [
                "SRC004891 Il a vu comment j'ai prié,",
                "SRC004893 J'étais au sol,",
                "SRC004895 Ma voix était cassée.",
            ],
            "justification": (
                "The cited SRC are first-person testimony. EX030 and the "
                "section title treat this as the author's experience. "
                "Removed 'The speaker recounted'. Restored I/my. Kept "
                "Someone as the witness ('Il a vu'). Did not add intensity "
                "or emotion beyond wording already present in the candidate."
            ),
        },
        {
            "paragraph_id": "P000009",
            "section_id": "SEC049",
            "classification": CLASS_EXTERNAL_CONFIRMED,
            "case": 1,
            "status": STATUS_APPLIED,
            "applied": True,
            "original": P000009_ORIGINAL,
            "proposed": P000009_CORRECTED,
            "corrected": P000009_CORRECTED,
            "src_proof": [
                "SRC004898 il m'a dit mon fils,",
                "SRC004899 tu es fatigué.",
                "SRC004905 Parce que si je te laisse ainsi,",
                "SRC004906 tu vas prêcher une mauvaise doctrine.",
            ],
            "justification": (
                "The recipient of God's speech is first person in the source "
                "('il m'a dit'). God remains he/He. The author becomes me/I. "
                "No new memory or emotion was added."
            ),
        },
    ]


def apply_corrections(chapter: dict[str, Any]) -> dict[str, Any]:
    revised = copy.deepcopy(chapter)
    catalog = {row["paragraph_id"]: row for row in correction_catalog() if row["applied"]}
    for section in revised.get("sections") or []:
        for paragraph in section.get("paragraphs") or []:
            paragraph_id = str(paragraph.get("paragraph_id") or "")
            item = catalog.get(paragraph_id)
            if item is None:
                continue
            if str(paragraph.get("text") or "") != item["original"]:
                raise ValueError(
                    f"{paragraph_id} original text does not match the frozen correction source"
                )
            paragraph["text"] = item["corrected"]
    return revised


def build_diff(original: dict[str, Any], revised: dict[str, Any]) -> str:
    lines = [
        "# CH012 authorial-voice diff",
        "",
        "Only paragraphs with a justified, applied correction are listed.",
        "Uncertain attribution is not applied.",
        "",
    ]
    catalog = {row["paragraph_id"]: row for row in correction_catalog()}
    original_map = {pid: row for pid, row in iter_paragraphs(original)}
    revised_map = {pid: row for pid, row in iter_paragraphs(revised)}
    for paragraph_id in original_map:
        before = original_map[paragraph_id]["text"]
        after = revised_map[paragraph_id]["text"]
        if before == after:
            continue
        item = catalog.get(paragraph_id) or {}
        lines.extend(
            [
                f"## {paragraph_id} — {item.get('status') or STATUS_APPLIED}",
                "",
                f"Section: {original_map[paragraph_id]['section_id']}",
                f"SRC: {', '.join(original_map[paragraph_id]['source_refs'])}",
                "",
                "### Before",
                "",
                before,
                "",
                "### After",
                "",
                after,
                "",
                "### Justification",
                "",
                str(item.get("justification") or ""),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def targeted_corrections_document(
    original: dict[str, Any],
    revised: dict[str, Any],
) -> dict[str, Any]:
    catalog = correction_catalog()
    changed = [
        pid
        for pid, before in iter_paragraphs(original)
        if before["text"] != dict(iter_paragraphs(revised))[pid]["text"]
    ]
    revised_lookup = {pid: row for pid, row in iter_paragraphs(revised)}
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "minimum_necessary_change": True,
        "global_rewrite": False,
        "new_autobiographical_details_added": False,
        "new_emotions_added": False,
        "invented_memories": False,
        "corrections": catalog,
        "applied_ids": [row["paragraph_id"] for row in catalog if row["applied"]],
        "human_review_ids": [
            row["paragraph_id"]
            for row in catalog
            if row["status"] in {STATUS_REQUIRES_HUMAN_REVIEW, STATUS_ATTRIBUTION_UNCERTAIN}
        ],
        "unchanged_paragraph_ids": [
            pid
            for pid, _row in iter_paragraphs(original)
            if pid not in {row["paragraph_id"] for row in catalog if row["applied"]}
        ],
        "changed_paragraph_ids": changed,
        "paragraph_ids_preserved": paragraph_ids(original) == paragraph_ids(revised),
        "section_ids_preserved": section_ids(original) == section_ids(revised),
        "unc029_preserved": any(
            EXPECTED_UNCERTAINTY_ID in row["uncertainty_refs"]
            or EXPECTED_UNCERTAINTY_ID in row["text"]
            or "unclear" in row["text"].lower()
            for row in revised_lookup.values()
        ),
        "secrets_included": False,
    }


def human_review_document() -> dict[str, Any]:
    catalog = correction_catalog()
    items = [
        {
            "id": row["paragraph_id"],
            "status": row["status"],
            "classification": row["classification"],
            "original": row["original"],
            "proposed": row.get("proposed"),
            "applied": row["applied"],
            "src_proof": row["src_proof"],
            "justification": row["justification"],
            "decision_required": not row["applied"],
        }
        for row in catalog
        if not row["applied"]
    ]
    items.append(
        {
            "id": "IDEA_PARAGRAPH_MAPPINGS",
            "status": STATUS_REQUIRES_HUMAN_REVIEW,
            "classification": "TRACEABILITY",
            "applied": False,
            "decision_required": True,
            "justification": (
                "SRC-overlap IDEA mappings are proposed only. They are not "
                "written into paragraph evidence fields and do not rewrite "
                "the provider response."
            ),
        }
    )
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "items": items,
        "publication_authorized": False,
        "terra_validation_authorized": False,
        "full_book_generation_authorized": False,
        "secrets_included": False,
    }


def unchanged_status() -> str:
    return STATUS_UNCHANGED


def render_revised_markdown(revised: dict[str, Any]) -> str:
    return render_chapter_markdown(revised)


__all__ = [
    "P000001_ORIGINAL",
    "P000001_PROPOSED",
    "P000003_CORRECTED",
    "P000004_CORRECTED",
    "P000008_CORRECTED",
    "P000009_CORRECTED",
    "apply_corrections",
    "build_diff",
    "correction_catalog",
    "human_review_document",
    "render_revised_markdown",
    "targeted_corrections_document",
]
