"""Editorial integrity: paragraphs, provenance, order, IDEA coverage, Markdown."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_ch002_offline_recovery_4b224.chapter_io import load_json
from app.book_full_manuscript_review_4b228.assemble import assemble_manuscript
from app.book_full_manuscript_review_4b228.integrity import (
    _extract_assembled_chapters,
    validate_manuscript_integrity,
)
from app.book_print_review_canonical_4b229.builder import (
    book_paragraph_texts,
    collect_source_paragraphs,
)
from app.book_print_review_canonical_4b229.constants import (
    ACCEPTED_CHAPTER_IDS,
    CANONICAL_CHAPTER_IDS,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SECTION_COUNT,
    HUMAN_ACCEPTED_STATUS,
    PENDING_CHAPTER_IDS,
    PHASE,
    STRUCTURAL_STATUS,
)
from app.book_print_review_canonical_4b229.guard import BookPrintReviewCanonical4229Error
from app.book_print_review_canonical_4b229.hashes import file_sha256
from app.book_print_review_canonical_4b229.paths import manuscript_path


def _handle_kind(handle: str) -> str:
    text = str(handle)
    for prefix in ("IDEA", "SRC", "EX", "REF", "UNC"):
        if text.startswith(prefix):
            return prefix
    return "OTHER"


def _collect_handles(paragraph: dict[str, Any]) -> dict[str, list[str]]:
    buckets = {"IDEA": [], "SRC": [], "EX": [], "REF": [], "UNC": [], "OTHER": []}
    values = []
    for key in (
        "evidence_handles",
        "source_refs",
        "idea_refs",
        "example_refs",
        "reference_refs",
        "uncertainty_refs",
    ):
        values.extend(paragraph.get(key) or [])
    seen: set[str] = set()
    for handle in values:
        text = str(handle)
        if text in seen:
            continue
        seen.add(text)
        buckets[_handle_kind(text)].append(text)
    return buckets


def compare_with_markdown(
    *,
    inventory: dict[str, Any],
    payload: dict[str, Any],
    manuscript_text: str,
) -> dict[str, Any]:
    source_texts = collect_source_paragraphs(inventory)
    book_texts = book_paragraph_texts(payload)
    extracted = _extract_assembled_chapters(manuscript_text)
    markdown_texts: list[str] = []
    for chapter in extracted:
        for section in chapter.get("sections") or []:
            markdown_texts.extend(section.get("paragraphs") or [])
    added = [text for text in book_texts if text not in source_texts]
    removed = [text for text in source_texts if text not in book_texts]
    modified = [
        {"index": index, "source": source, "book": book}
        for index, (source, book) in enumerate(zip(source_texts, book_texts), start=1)
        if source != book
    ]
    markdown_mismatch = [
        {"index": index, "markdown": markdown, "book": book}
        for index, (markdown, book) in enumerate(zip(markdown_texts, book_texts), start=1)
        if markdown != book
    ]
    count_ok = (
        len(source_texts) == len(book_texts) == len(markdown_texts)
        and not added
        and not removed
        and not modified
        and not markdown_mismatch
        and source_texts == book_texts == markdown_texts
    )
    return {
        "status": "PASS" if count_ok else "FAIL",
        "source_paragraph_count": len(source_texts),
        "book_paragraph_count": len(book_texts),
        "markdown_paragraph_count": len(markdown_texts),
        "prose_added": len(added),
        "prose_removed": len(removed),
        "prose_modified": len(modified),
        "markdown_mismatches": len(markdown_mismatch),
        "binary_identity_not_required": True,
        "editorial_content_identity": count_ok,
        "punctuation_normalized": False,
        "internal_spaces_normalized": False,
        "secrets_included": False,
    }


def validate_book_integrity(
    *,
    inventory: dict[str, Any],
    payload: dict[str, Any],
    root: Path | None = None,
) -> dict[str, Any]:
    manuscript = manuscript_path(root=root).read_text(encoding="utf-8")
    assembly = assemble_manuscript(inventory)
    manuscript_integrity = validate_manuscript_integrity(
        inventory=inventory, assembly=assembly
    )
    if assembly["manuscript_text"] != manuscript:
        raise BookPrintReviewCanonical4229Error(
            "On-disk 4B.2.28 manuscript drifted from deterministic re-assembly. STOP."
        )
    comparison = compare_with_markdown(
        inventory=inventory, payload=payload, manuscript_text=manuscript
    )
    ids = [chapter["chapter_id"] for chapter in payload.get("chapters") or []]
    duplicate_chapters = sorted({item for item in ids if ids.count(item) > 1})
    missing_chapters = [item for item in CANONICAL_CHAPTER_IDS if item not in ids]
    section_ids = [
        section["section_id"]
        for chapter in payload.get("chapters") or []
        for section in chapter.get("sections") or []
    ]
    duplicate_sections = sorted(
        {item for item in section_ids if item and section_ids.count(item) > 1}
    )
    idea_ids = list(inventory.get("idea_ids") or [])
    paragraph_idea_ids: list[str] = []
    seen_paragraph_ideas: set[str] = set()
    invalid_handles: list[str] = []
    for chapter in payload.get("chapters") or []:
        for section in chapter.get("sections") or []:
            for paragraph in section.get("paragraphs") or []:
                handles = _collect_handles(paragraph)
                for idea_id in handles["IDEA"]:
                    if idea_id not in seen_paragraph_ideas:
                        seen_paragraph_ideas.add(idea_id)
                        paragraph_idea_ids.append(idea_id)
                for bucket, values in handles.items():
                    if bucket == "OTHER":
                        invalid_handles.extend(values)
    accepted = [
        chapter["chapter_id"]
        for chapter in payload.get("chapters") or []
        if chapter.get("editorial_status") == HUMAN_ACCEPTED_STATUS
    ]
    pending = [
        chapter["chapter_id"]
        for chapter in payload.get("chapters") or []
        if chapter.get("editorial_status") == STRUCTURAL_STATUS
    ]
    paragraph_ok = comparison["status"] == "PASS"
    provenance_ok = (
        not invalid_handles
        and len(idea_ids) == EXPECTED_IDEA_COUNT
        and set(paragraph_idea_ids).issubset(set(idea_ids))
    )
    order_ok = ids == list(CANONICAL_CHAPTER_IDS) and not missing_chapters
    status_ok = accepted == list(ACCEPTED_CHAPTER_IDS) and pending == list(
        PENDING_CHAPTER_IDS
    )
    ok = (
        paragraph_ok
        and provenance_ok
        and order_ok
        and status_ok
        and not duplicate_chapters
        and not duplicate_sections
        and len(section_ids) == EXPECTED_SECTION_COUNT
        and manuscript_integrity.get("status") == "PASS"
    )
    return {
        "phase": PHASE,
        "status": "PASS" if ok else "FAIL",
        "chapter_count": len(ids),
        "section_count": len(section_ids),
        "idea_coverage_count": len(idea_ids),
        "idea_ids": idea_ids,
        "paragraph_idea_handle_count": len(paragraph_idea_ids),
        "ideas_covered_by_review_without_paragraph_handle": [
            idea_id for idea_id in idea_ids if idea_id not in seen_paragraph_ideas
        ],
        "duplicate_chapter_ids": duplicate_chapters,
        "missing_chapter_ids": missing_chapters,
        "duplicate_section_ids": duplicate_sections,
        "invalid_provenance_handles": invalid_handles,
        "accepted_chapter_ids": accepted,
        "pending_chapter_ids": pending,
        "paragraph_integrity": "PASS" if paragraph_ok else "FAIL",
        "provenance_integrity": "PASS" if provenance_ok else "FAIL",
        "markdown_comparison": comparison["status"],
        "human_statuses_preserved": status_ok,
        "structural_statuses_preserved": pending == list(PENDING_CHAPTER_IDS),
        "order_matches_editorial_plan": order_ok,
        "manuscript_integrity": manuscript_integrity.get("status"),
        "comparison": comparison,
        "secrets_included": False,
    }


def chapter_source_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in inventory.get("chapters") or []:
        payload = load_json(Path(row["json_path"]))
        handle_sets = {"IDEA": [], "SRC": [], "EX": [], "REF": [], "UNC": []}
        for section in payload.get("sections") or []:
            for paragraph in section.get("paragraphs") or []:
                if not isinstance(paragraph, dict):
                    continue
                buckets = _collect_handles(paragraph)
                for key in handle_sets:
                    for handle in buckets[key]:
                        if handle not in handle_sets[key]:
                            handle_sets[key].append(handle)
        rows.append(
            {
                "chapter_id": row["chapter_id"],
                "title": row["title"],
                "order": row["book_order"],
                "json_path": row["json_path"],
                "markdown_path": row["markdown_path"],
                "json_sha256": row["json_sha256"],
                "markdown_sha256": row["markdown_sha256"],
                "structural_status": row.get("structural_status") or "",
                "human_acceptance_status": row.get("human_status_exact") or "",
                "section_count": row["section_count"],
                "paragraph_count": row["paragraph_count"],
                "idea_ids": handle_sets["IDEA"],
                "src_ids": handle_sets["SRC"],
                "ex_ids": handle_sets["EX"],
                "ref_ids": handle_sets["REF"],
                "unc_ids": handle_sets["UNC"],
                "json_bytes": file_sha256(Path(row["json_path"])).get("bytes"),
            }
        )
    return rows


__all__ = [
    "chapter_source_rows",
    "compare_with_markdown",
    "validate_book_integrity",
]
