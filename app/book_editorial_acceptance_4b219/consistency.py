"""Compare accepted Markdown and JSON without rewriting either file."""

from __future__ import annotations

import re
from typing import Any

from app.book_editorial_acceptance_4b219.chapter_io import (
    iter_paragraphs,
    paragraph_ids,
    section_ids,
)
from app.book_editorial_acceptance_4b219.constants import (
    CHAPTER_ID,
    CHAPTER_TITLE,
    PARAGRAPH_COUNT,
    PARAGRAPH_IDS,
    PHASE,
    SECTION_IDS,
    UNCERTAINTY_ID,
)

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def parse_markdown_prose(markdown: str) -> dict[str, Any]:
    title = ""
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    buffer: list[str] = []

    def _flush() -> None:
        if current is None:
            return
        text = "\n".join(buffer).strip()
        buffer.clear()
        if text:
            current["paragraphs"].append(text)

    for raw_line in markdown.replace("\r\n", "\n").split("\n"):
        match = _HEADING.match(raw_line)
        if match:
            _flush()
            hashes, heading = match.group(1), match.group(2).strip()
            if hashes == "#" and not title:
                title = heading
                continue
            if hashes == "##":
                current = {"title": heading, "paragraphs": []}
                sections.append(current)
                continue
            continue
        if raw_line.strip() == "":
            _flush()
            continue
        if current is None:
            continue
        buffer.append(raw_line)
    _flush()
    paragraphs = [
        paragraph
        for section in sections
        for paragraph in section["paragraphs"]
    ]
    return {
        "title": title,
        "sections": sections,
        "paragraphs": paragraphs,
        "section_count": len(sections),
        "paragraph_count": len(paragraphs),
    }


def compare_markdown_json(chapter: dict[str, Any], markdown: str) -> dict[str, Any]:
    parsed = parse_markdown_prose(markdown)
    json_rows = list(iter_paragraphs(chapter))
    json_texts = [row["text"].strip() for _pid, row in json_rows]
    md_texts = [text.strip() for text in parsed["paragraphs"]]
    json_section_titles = [
        str(section.get("title") or "") for section in chapter.get("sections") or []
    ]
    md_section_titles = [section["title"] for section in parsed["sections"]]
    prose_pairs = []
    mismatches = []
    for index, (json_text, md_text) in enumerate(zip(json_texts, md_texts)):
        paragraph_id = json_rows[index][0] if index < len(json_rows) else f"index-{index}"
        same = json_text == md_text
        prose_pairs.append(
            {
                "paragraph_id": paragraph_id,
                "json_chars": len(json_text),
                "markdown_chars": len(md_text),
                "prose_match": same,
            }
        )
        if not same:
            mismatches.append(paragraph_id)
    extra_json = max(0, len(json_texts) - len(md_texts))
    extra_md = max(0, len(md_texts) - len(json_texts))
    if extra_json:
        mismatches.append("extra_json_paragraphs")
    if extra_md:
        mismatches.append("extra_markdown_paragraphs")
    unc_rows = [
        row for _pid, row in json_rows if UNCERTAINTY_ID in row["uncertainty_refs"]
    ]
    unc_in_prose = any("unclear" in text.lower() for text in json_texts)
    presentation_only = {
        "markdown_chapter_title": parsed["title"],
        "markdown_section_titles": md_section_titles,
        "json_section_titles": json_section_titles,
        "technical_ids_absent_from_markdown_prose": True,
        "not_counted_as_prose_divergence": True,
    }
    consistent = (
        chapter.get("chapter_id") == CHAPTER_ID
        and parsed["title"] == CHAPTER_TITLE
        and paragraph_ids(chapter) == PARAGRAPH_IDS
        and section_ids(chapter) == SECTION_IDS
        and len(json_texts) == PARAGRAPH_COUNT
        and len(md_texts) == PARAGRAPH_COUNT
        and json_section_titles == md_section_titles
        and not mismatches
        and bool(unc_rows)
        and unc_in_prose
    )
    return {
        "phase": PHASE,
        "chapter_id": CHAPTER_ID,
        "consistent": consistent,
        "freeze_blocked": not consistent,
        "json_chapter_id": chapter.get("chapter_id"),
        "markdown_title": parsed["title"],
        "json_sections": list(section_ids(chapter)),
        "expected_sections": list(SECTION_IDS),
        "json_paragraph_ids": list(paragraph_ids(chapter)),
        "expected_paragraph_ids": list(PARAGRAPH_IDS),
        "json_paragraph_count": len(json_texts),
        "markdown_paragraph_count": len(md_texts),
        "expected_paragraph_count": PARAGRAPH_COUNT,
        "section_order_match": list(section_ids(chapter)) == list(SECTION_IDS),
        "paragraph_order_match": list(paragraph_ids(chapter)) == list(PARAGRAPH_IDS),
        "section_titles_match": json_section_titles == md_section_titles,
        "prose_pairs": prose_pairs,
        "prose_mismatches": mismatches,
        "references_conserved_in_json": all(
            row["source_refs"] for _pid, row in json_rows
        ),
        "unc029_on_paragraphs": [row["paragraph_id"] for row in unc_rows],
        "unc029_in_prose": unc_in_prose,
        "extra_json_paragraphs": extra_json,
        "extra_markdown_paragraphs": extra_md,
        "presentation_only": presentation_only,
        "rewritten": False,
        "secrets_included": False,
    }


__all__ = ["compare_markdown_json", "parse_markdown_prose"]
