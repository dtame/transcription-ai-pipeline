"""Deterministic manuscript integrity. Every paragraph must map to its source."""

from __future__ import annotations

from typing import Any

from app.book_full_manuscript_review_4b228.assemble import manuscript_digest
from app.book_full_manuscript_review_4b228.constants import (
    CANONICAL_CHAPTER_IDS,
    CHAPTER_SEPARATOR,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SECTION_COUNT,
    PHASE,
)
from app.book_full_manuscript_review_4b228.guard import BookFullManuscriptReview4228Error


def _extract_assembled_chapters(manuscript: str) -> list[dict[str, Any]]:
    text = manuscript.replace("\r\n", "\n")
    marker = f"\n{CHAPTER_SEPARATOR}\n"
    if "## Table of contents\n" not in text:
        raise BookFullManuscriptReview4228Error("Assembled manuscript has no table of contents.")
    after_toc = text.split("## Table of contents\n", 1)[1]
    if marker not in after_toc:
        raise BookFullManuscriptReview4228Error("Assembled manuscript has no chapter separator.")
    body = after_toc.split(marker, 1)[1]
    chunks = [chunk.strip("\n") for chunk in body.split(f"\n{CHAPTER_SEPARATOR}\n")]
    chapters: list[dict[str, Any]] = []
    for chunk in chunks:
        lines = chunk.split("\n")
        title = ""
        sections: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        buffer: list[str] = []

        def flush() -> None:
            nonlocal buffer
            if current is not None and buffer:
                current["paragraphs"].append("\n".join(buffer).strip())
            buffer = []

        for line in lines:
            if line.startswith("## ") and not line.startswith("### "):
                flush()
                title = line[3:].strip()
                continue
            if line.startswith("### "):
                flush()
                current = {"title": line[4:].strip(), "paragraphs": []}
                sections.append(current)
                continue
            if not line.strip():
                flush()
                continue
            buffer.append(line)
        flush()
        chapters.append({"title": title, "sections": sections})
    return chapters


def _toc_titles(manuscript: str) -> list[str]:
    text = manuscript.replace("\r\n", "\n")
    block = text.split("## Table of contents\n", 1)[1]
    block = block.split(f"\n{CHAPTER_SEPARATOR}\n", 1)[0]
    titles: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if ". " in stripped:
            titles.append(stripped.split(". ", 1)[1])
    return titles


def validate_manuscript_integrity(
    *,
    inventory: dict[str, Any],
    assembly: dict[str, Any],
) -> dict[str, Any]:
    manuscript = str(assembly.get("manuscript_text") or "")
    chapters = list(inventory.get("chapters") or [])
    assembled = _extract_assembled_chapters(manuscript)
    toc = _toc_titles(manuscript)
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    add("nineteen_chapters_present", len(chapters) == 19 and len(assembled) == 19)
    ids = [row["chapter_id"] for row in chapters]
    add("no_duplicate_chapters", len(ids) == len(set(ids)))
    add("no_missing_chapters", ids == list(CANONICAL_CHAPTER_IDS))
    add("order_matches_editorial_plan", bool(inventory.get("order_matches_editorial_plan")))
    add(
        "seventy_two_sections",
        int(inventory.get("section_count") or 0) == EXPECTED_SECTION_COUNT
        and int(assembly.get("section_count") or 0) == EXPECTED_SECTION_COUNT,
    )
    add(
        "two_hundred_eighty_six_ideas",
        int(inventory.get("idea_coverage_count") or 0) == EXPECTED_IDEA_COUNT,
    )
    add("toc_has_nineteen_titles", toc == [row["title"] for row in chapters])
    add("ch002_recovered_used", bool(inventory.get("ch002_recovered_used")))
    add("ch012_authorial_v2_used", bool(inventory.get("ch012_authorial_v2_used")))
    add("ch018_accepted_used", bool(inventory.get("ch018_accepted_used")))
    add(
        "no_invented_chapter_titles",
        all(row["title"] == row["working_title"] for row in chapters),
    )

    unmatched: list[dict[str, Any]] = []
    added = 0
    removed = 0
    rewritten = 0
    empty_sections = 0
    for source, assembled_chapter in zip(chapters, assembled):
        if assembled_chapter["title"] != source["title"]:
            rewritten += 1
            unmatched.append(
                {
                    "chapter_id": source["chapter_id"],
                    "reason": "chapter_title_mismatch",
                    "source": source["title"],
                    "assembled": assembled_chapter["title"],
                }
            )
        source_sections = source["section_titles"]
        assembled_sections = [section["title"] for section in assembled_chapter["sections"]]
        if assembled_sections != source_sections:
            rewritten += 1
            unmatched.append(
                {
                    "chapter_id": source["chapter_id"],
                    "reason": "section_title_mismatch",
                    "source": source_sections,
                    "assembled": assembled_sections,
                }
            )
        source_texts = [paragraph["text"] for paragraph in source["paragraphs"]]
        assembled_texts: list[str] = []
        for section in assembled_chapter["sections"]:
            if not section["paragraphs"]:
                empty_sections += 1
            assembled_texts.extend(section["paragraphs"])
        if len(assembled_texts) > len(source_texts):
            added += len(assembled_texts) - len(source_texts)
        if len(assembled_texts) < len(source_texts):
            removed += len(source_texts) - len(assembled_texts)
        for index, source_text in enumerate(source_texts):
            assembled_text = assembled_texts[index] if index < len(assembled_texts) else ""
            if assembled_text != source_text:
                rewritten += 1
                unmatched.append(
                    {
                        "chapter_id": source["chapter_id"],
                        "paragraph_id": source["paragraphs"][index]["paragraph_id"],
                        "reason": "paragraph_text_mismatch",
                    }
                )

    paragraph_rows = list(assembly.get("paragraphs") or [])
    for row in paragraph_rows:
        if not row.get("text") or not row.get("source_json_path"):
            unmatched.append(
                {
                    "chapter_id": row.get("chapter_id"),
                    "paragraph_id": row.get("paragraph_id"),
                    "reason": "untraceable_paragraph",
                }
            )

    add("no_empty_unplanned_section", empty_sections == 0)
    add("no_paragraph_added", added == 0)
    add("no_paragraph_removed", removed == 0)
    add("no_paragraph_rewritten", rewritten == 0)
    add("every_paragraph_traced", not any(
        item.get("reason") == "untraceable_paragraph" for item in unmatched
    ))
    add("no_wrong_historical_version", not any(
        row.get("forbidden_historical_version_used") for row in chapters
    ))

    paragraph_integrity = added == 0 and removed == 0 and rewritten == 0 and not unmatched
    provenance_integrity = all(
        row.get("source_json_sha256") and row.get("source_markdown_sha256")
        for row in paragraph_rows
    )
    add("paragraph_integrity", paragraph_integrity)
    add("provenance_integrity", provenance_integrity)

    failed = [row["name"] for row in checks if not row["ok"]]
    if failed:
        status = "FAIL"
    else:
        status = "PASS"
    if unmatched and paragraph_integrity is False:
        # Keep FAIL. Do not declare PASS when a paragraph cannot be linked.
        status = "FAIL"

    digest = manuscript_digest(manuscript)
    return {
        "phase": PHASE,
        "status": status,
        "paragraph_integrity": "PASS" if paragraph_integrity else "FAIL",
        "provenance_integrity": "PASS" if provenance_integrity else "FAIL",
        "chapters_assembled": f"{len(assembled)} / 19",
        "sections_assembled": f"{inventory.get('section_count')} / {EXPECTED_SECTION_COUNT}",
        "idea_coverage": f"{inventory.get('idea_coverage_count')} / {EXPECTED_IDEA_COUNT}",
        "checks": checks,
        "failed_checks": failed,
        "unmatched_paragraphs": unmatched,
        "toc_titles": toc,
        "allowed_differences": [
            "book_title_and_subtitle_from_editorial_plan",
            "technical_assembly_note",
            "table_of_contents",
            "heading_level_adjustment",
            "chapter_separators",
        ],
        "manuscript_sha256": digest,
        "manuscript_word_count": assembly.get("manuscript_word_count"),
        "chapter_prose_word_count": assembly.get("chapter_prose_word_count"),
        "reproducible_proof": {
            "source_paragraph_count": sum(row["paragraph_count"] for row in chapters),
            "assembled_paragraph_count": len(paragraph_rows),
            "all_paragraphs_linked": paragraph_integrity,
        },
        "secrets_included": False,
    }


__all__ = ["validate_manuscript_integrity"]
