"""Assemble the reading manuscript. Hierarchy only. No prose rewrite."""

from __future__ import annotations

from typing import Any

from app.book_full_manuscript_review_4b228.constants import (
    CHAPTER_SEPARATOR,
    MANIFEST_VERSION,
    MANUSCRIPT_NOTE,
    PHASE,
    TECHNICAL_TITLE_FALLBACK,
)
from app.book_full_manuscript_review_4b228.guard import BookFullManuscriptReview4228Error


def _word_count(text: str) -> int:
    return len([token for token in text.split() if token])


def resolve_book_title(inventory: dict[str, Any]) -> dict[str, Any]:
    selected = str(inventory.get("selected_title") or "").strip()
    subtitle = str(inventory.get("subtitle") or "").strip()
    if selected:
        return {
            "title": selected,
            "subtitle": subtitle,
            "provisional": False,
            "technical_designation": False,
            "source": "EditorialPlan.selected_title",
            "invented_by_this_phase": False,
        }
    return {
        "title": TECHNICAL_TITLE_FALLBACK,
        "subtitle": "",
        "provisional": True,
        "technical_designation": True,
        "source": "phase_technical_fallback",
        "invented_by_this_phase": False,
    }


def assemble_manuscript(inventory: dict[str, Any]) -> dict[str, Any]:
    title_info = resolve_book_title(inventory)
    chapters = list(inventory.get("chapters") or [])
    if len(chapters) != 19:
        raise BookFullManuscriptReview4228Error(
            f"Assembly requires 19 chapters, received {len(chapters)}. STOP."
        )
    toc_lines = [f"{row['book_order']}. {row['title']}" for row in chapters]
    parts: list[str] = [f"# {title_info['title']}", ""]
    if title_info["subtitle"]:
        parts.extend([f"*{title_info['subtitle']}*", ""])
    parts.extend(
        [
            f"*{MANUSCRIPT_NOTE}*",
            "",
            "## Table of contents",
            "",
            *toc_lines,
        ]
    )
    provenance_chapters: list[dict[str, Any]] = []
    paragraph_rows: list[dict[str, Any]] = []
    manuscript_index = 0
    for row in chapters:
        parts.extend(["", CHAPTER_SEPARATOR, "", f"## {row['title']}", ""])
        section_spans: list[dict[str, Any]] = []
        current_section = ""
        section_paragraph_ids: list[str] = []
        for paragraph in row["paragraphs"]:
            section_title = paragraph["section_title"]
            if section_title != current_section:
                if current_section:
                    section_spans.append(
                        {
                            "title": current_section,
                            "paragraph_ids": list(section_paragraph_ids),
                        }
                    )
                current_section = section_title
                section_paragraph_ids = []
                parts.extend([f"### {section_title}", ""])
            parts.append(paragraph["text"])
            parts.append("")
            manuscript_index += 1
            section_paragraph_ids.append(paragraph["paragraph_id"])
            paragraph_rows.append(
                {
                    "manuscript_paragraph_index": manuscript_index,
                    "chapter_id": row["chapter_id"],
                    "chapter_title": row["title"],
                    "section_id": paragraph["section_id"],
                    "section_title": section_title,
                    "paragraph_id": paragraph["paragraph_id"],
                    "text": paragraph["text"],
                    "source_markdown_path": row["markdown_path"],
                    "source_json_path": row["json_path"],
                    "source_markdown_sha256": row["markdown_sha256"],
                    "source_json_sha256": row["json_sha256"],
                    "editorial_status": row["human_status_exact"],
                    "evidence_handles": paragraph["evidence_handles"],
                }
            )
        if current_section:
            section_spans.append(
                {
                    "title": current_section,
                    "paragraph_ids": list(section_paragraph_ids),
                }
            )
        provenance_chapters.append(
            {
                "chapter_id": row["chapter_id"],
                "book_order": row["book_order"],
                "title": row["title"],
                "source_markdown_path": row["markdown_path"],
                "source_json_path": row["json_path"],
                "source_markdown_sha256": row["markdown_sha256"],
                "source_json_sha256": row["json_sha256"],
                "manifest_path": row.get("manifest_path") or "",
                "approved_version": row["approved_version"],
                "editorial_status": row["human_status_exact"],
                "structural_status": row["structural_status"],
                "section_ids": row["section_ids"],
                "section_titles": row["section_titles"],
                "sections": section_spans,
                "paragraph_count": row["paragraph_count"],
                "idea_expected_count": row["idea_expected_count"],
                "idea_covered_count": row["idea_covered_count"],
                "provenance_ids": {
                    "chapter_id": row["chapter_id"],
                    "section_ids": row["section_ids"],
                    "idea_ids": row["covered_idea_ids"],
                },
            }
        )
    manuscript = "\n".join(parts).rstrip() + "\n"
    prose_words = _word_count(
        "\n".join(item["text"] for item in paragraph_rows)
    )
    return {
        "phase": PHASE,
        "title_info": title_info,
        "manuscript_text": manuscript,
        "table_of_contents": toc_lines,
        "chapter_count": len(chapters),
        "section_count": sum(len(row["section_ids"]) for row in chapters),
        "paragraph_count": len(paragraph_rows),
        "manuscript_word_count": _word_count(manuscript),
        "chapter_prose_word_count": prose_words,
        "paragraphs": paragraph_rows,
        "provenance": {
            "phase": PHASE,
            "manifest_version": MANIFEST_VERSION,
            "book_title": title_info["title"],
            "book_title_source": title_info["source"],
            "book_title_invented": False,
            "chapters": provenance_chapters,
            "reproducible": True,
            "prose_modified": False,
            "secrets_included": False,
        },
        "assembly_spec": {
            "phase": PHASE,
            "allowed_markdown_adjustments": [
                "book_title_heading",
                "editorial_plan_subtitle",
                "technical_assembly_note",
                "table_of_contents",
                "chapter_heading_level_h2",
                "section_heading_level_h3",
                "chapter_separators",
            ],
            "forbidden": [
                "rewrite_prose",
                "add_preface",
                "add_conclusion",
                "add_transition",
                "insert_idea_src_handles_in_body",
                "invent_book_title",
                "change_chapter_titles",
            ],
            "separator": CHAPTER_SEPARATOR,
            "secrets_included": False,
        },
    }


def manuscript_digest(text: str) -> str:
    from hashlib import sha256

    return sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "assemble_manuscript",
    "manuscript_digest",
    "resolve_book_title",
]
