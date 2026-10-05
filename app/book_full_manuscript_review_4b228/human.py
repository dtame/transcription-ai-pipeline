"""Human review guide and checklist. Does not grant approvals."""

from __future__ import annotations

from typing import Any

from app.book_full_manuscript_review_4b228.constants import (
    HUMAN_ACCEPTANCE_STATUS,
    HUMAN_REVIEW_PENDING_STATUS,
    PENDING_CHAPTER_IDS,
    PHASE,
)


def human_review_checklist(inventory: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for chapter in inventory.get("chapters") or []:
        if chapter["chapter_id"] not in PENDING_CHAPTER_IDS:
            continue
        rows.append(
            {
                "chapter_id": chapter["chapter_id"],
                "title": chapter["title"],
                "status": HUMAN_REVIEW_PENDING_STATUS,
                "decision": "",
                "decision_allowed": [
                    "APPROVE_UNCHANGED",
                    "APPROVE_WITH_DOCUMENTED_OBSERVATIONS",
                    "REQUEST_CORRECTION",
                    "HOLD",
                ],
                "correction_note": "",
                "reviewer": "",
                "date": "",
                "prefilled_approval": False,
            }
        )
    return {
        "phase": PHASE,
        "manuscript_decision": "",
        "manuscript_decision_allowed": [
            "APPROVE_FULL_MANUSCRIPT",
            "APPROVE_ACCEPTED_CHAPTERS_ONLY",
            "HOLD_FOR_CHAPTER_CORRECTIONS",
        ],
        "accepted_chapters_already_approved": list(inventory.get("accepted_chapter_ids") or []),
        "pending_chapters": rows,
        "no_approval_attributed_by_this_phase": True,
        "secrets_included": False,
    }


def render_human_review_guide(
    *,
    inventory: dict[str, Any],
    editorial: dict[str, Any],
    integrity: dict[str, Any],
) -> str:
    pending = ", ".join(inventory.get("pending_chapter_ids") or [])
    accepted = ", ".join(inventory.get("accepted_chapter_ids") or [])
    strengthened = list(
        (editorial.get("strengthened_claims") or {}).get("observations") or []
    )
    similar = list(
        (editorial.get("references_examples") or {}).get(
            "similar_observations_in_new_chapters"
        )
        or []
    )
    continuity = list((editorial.get("continuity") or {}).get("observations") or [])
    lines = [
        "# Human review guide — Phase 4B.2.28",
        "",
        "This dossier lets you read the book without opening 19 chapter files.",
        "This phase did not approve any pending chapter.",
        "",
        "## Where to read the complete manuscript",
        "",
        "Open `audit/book_full_manuscript_review_4b228/manuscript_reading_draft.md`.",
        "That file contains the book title from the EditorialPlan, a table of contents,",
        "and the 19 chapters in canonical order. Paragraphs are unchanged.",
        "",
        f"Integrity status: {integrity.get('status')}.",
        f"Paragraph integrity: {integrity.get('paragraph_integrity')}.",
        "",
        "## Chapters already approved",
        "",
        f"{accepted}.",
        f"Recorded status: `{HUMAN_ACCEPTANCE_STATUS}`.",
        "Do not regenerate or rewrite them.",
        "",
        "- CH001: `audit/real/book_generation_4b223_batch01/chapters/CH001/`",
        "- CH002: recovered artefacts only, `audit/book_ch002_offline_recovery_4b224/`",
        "- CH003 and CH004: `audit/real/book_generation_4b225_batch01_resume/chapters/`",
        "- CH012: authorial v2 designated by the 4B.2.19 acceptance manifest",
        "- CH018: artefacts designated by the 4B.2.22 acceptance manifest",
        "",
        "## Chapters still awaiting editorial approval",
        "",
        f"{pending}.",
        f"Recorded status: `{HUMAN_REVIEW_PENDING_STATUS}`.",
        "They are generated and structurally valid. They are not approved.",
        "",
        "## Observations that deserve particular attention",
        "",
        "### Strengthened claims in the 13 new chapters",
        "",
    ]
    if not strengthened:
        lines.append("No STRENGTHENED_CLAIM observation was consolidated.")
    for item in strengthened:
        token = ""
        spans = item.get("matched_spans") or []
        if spans:
            token = spans[0].get("matched_token") or ""
        lines.append(
            f"- {item['chapter_id']} {item.get('section') or ''} "
            f"{item.get('paragraph') or ''} — `{token or 'not localized'}`. "
            "An `always` / `never` wording is not automatically an error. "
            "Keep or change it only by human decision."
        )
    lines.extend(
        [
            "",
            "### Historical reference / example notes",
            "",
            "- CH003: EX005 without an explicit handle.",
            "- CH004: REF011, REF012, REF013 without explicit handles; references present in the prose.",
            "- CH012: EX030, historically documented partial coverage.",
            "- CH018: EX046 present in the text without an explicit handle.",
            "",
            "### Similar handle-absent notes among the 13 new chapters",
            "",
        ]
    )
    if not similar:
        lines.append("None identified from the existing EX/REF reviews.")
    for item in similar:
        lines.append(
            f"- {item['chapter_id']} {item['kind']} {item['id']} — {item['category']}."
        )
    lines.extend(["", "### Continuity notes", ""])
    if not continuity:
        lines.append("No deterministic continuity observation was recorded.")
    for item in continuity:
        lines.append(
            f"- `{item.get('code')}` {item.get('chapter_from', '')} → "
            f"{item.get('chapter_to', '')}: {item.get('detail')}"
        )
    lines.extend(
        [
            "",
            "## How to signal a correction",
            "",
            "1. Open `human_review_checklist.json`.",
            "2. Set the chapter `decision` to `REQUEST_CORRECTION`.",
            "3. Write the exact passage, the chapter, the section, and the required change in `correction_note`.",
            "4. Do not edit the chapter files in place during this review.",
            "5. Do not ask this phase to rewrite the prose automatically.",
            "",
            "## How to approve one of the 13 chapters",
            "",
            "1. Read the chapter in the assembled manuscript.",
            "2. Check the observations listed above for that chapter.",
            "3. In `human_review_checklist.json`, set `decision` to `APPROVE_UNCHANGED` or `APPROVE_WITH_DOCUMENTED_OBSERVATIONS`.",
            "4. Fill `reviewer` and `date`.",
            "5. A later phase must record a formal acceptance manifest. This phase does not do that.",
            "",
            "## How to approve the whole manuscript",
            "",
            "Approve the manuscript only after the 13 pending chapters have been reviewed.",
            "Set `manuscript_decision` to `APPROVE_FULL_MANUSCRIPT` in the checklist.",
            "That decision is a human record. It is not created by this phase.",
            "Approval of the reading manuscript is not publication of `book.json`, DOCX, or PDF.",
            "",
            "## Review grid for the 13 new chapters",
            "",
            "| Chapter | Title | Voice | Strengthened claim | EX/REF notes | Continuity | Decision |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    by_id = {row["chapter_id"]: row for row in inventory.get("chapters") or []}
    strengthened_ids = {item["chapter_id"] for item in strengthened}
    similar_ids = {item["chapter_id"] for item in similar}
    voice_rows = {
        item["chapter_id"]: item
        for item in (editorial.get("voice") or {}).get("chapters") or []
    }
    continuity_ids = {
        item.get("chapter_to")
        for item in continuity
        if item.get("code") == "POSSIBLE_ABRUPT_TRANSITION"
    }
    for chapter_id in PENDING_CHAPTER_IDS:
        title = (by_id.get(chapter_id) or {}).get("title") or ""
        voice = voice_rows.get(chapter_id) or {}
        voice_mark = "frames" if voice.get("conference_report_frames") else "no frame flagged"
        claim_mark = "yes" if chapter_id in strengthened_ids else "no historical flag"
        ref_mark = "handle-absent note" if chapter_id in similar_ids else "no similar note"
        cont_mark = "abrupt-transition note" if chapter_id in continuity_ids else "—"
        lines.append(
            f"| {chapter_id} | {title} | {voice_mark} | {claim_mark} | {ref_mark} | {cont_mark} | |"
        )
    lines.extend(
        [
            "",
            "Leave the Decision column empty until a human writes it.",
            "",
            "## What this phase did not do",
            "",
            "- It did not approve the 13 candidates.",
            "- It did not rewrite any sentence.",
            "- It did not call a provider.",
            "- It did not publish `book.json`.",
            "- It did not generate DOCX or PDF.",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = ["human_review_checklist", "render_human_review_guide"]
