"""Phase 4B.2.31 final report."""

from __future__ import annotations

from typing import Any, Mapping


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    artifacts = dict(bundle.get("written") or {})
    issues = header.get("issues") or "- None."
    lines = [
        "**PHASE 4B.2.31 — PRINT REVIEW DOCX/PDF GENERATION**",
        "",
        f"RESULT = {header.get('result')}",
        "PROVIDER CALLS = 0",
        f"BOOK TITLE = {header.get('book_title')}",
        f"BOOK VERSION = {header.get('book_version')}",
        f"BOOK STATUS = {header.get('book_status')}",
        f"BOOK SHA-256 = {header.get('book_sha256')}",
        f"PRINT FORMAT = {header.get('print_format')}",
        f"PRINT PROFILE = {header.get('print_profile')}",
        f"WORD AVAILABLE = {header.get('word_available')}",
        f"WORD FINALIZATION = {header.get('word_finalization')}",
        f"DOCX GENERATED = {header.get('docx_generated')}",
        f"DOCX PATH = {header.get('docx_path')}",
        f"DOCX SHA-256 = {header.get('docx_sha256')}",
        f"DOCX CONTENT INTEGRITY = {header.get('docx_content_integrity')}",
        f"CHAPTERS = {header.get('chapters')}",
        f"SECTIONS = {header.get('sections')}",
        f"PARAGRAPHS = {header.get('paragraphs')}",
        f"TOC UPDATED = {header.get('toc_updated')}",
        f"PAGINATION STABLE = {header.get('pagination_stable')}",
        f"PDF GENERATED = {header.get('pdf_generated')}",
        f"PDF PATH = {header.get('pdf_path')}",
        f"PDF SHA-256 = {header.get('pdf_sha256')}",
        f"PDF PAGE COUNT = {header.get('pdf_page_count')}",
        f"PDF PAGE SIZE = {header.get('pdf_page_size')}",
        f"PDF CONTENT INTEGRITY = {header.get('pdf_content_integrity')}",
        f"ODD-PAGE CHAPTER STARTS = {header.get('odd_page_chapter_starts')}",
        f"VISUAL INSPECTION = {header.get('visual_inspection')}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post')}",
        f"SOURCE CHAPTERS IMMUTABLE = {header.get('source_chapters_immutable')}",
        f"PUBLICATION STATUS = {header.get('publication_status')}",
        f"READY_FOR_PHYSICAL_PRINT_REVIEW = {header.get('ready_for_physical_print_review')}",
        f"NEXT ACTION = {header.get('next_action')}",
        "",
        "## Tests executed",
        "",
        f"- pytest: {header.get('pytest_summary')}",
        f"- offline scenarios: {header.get('scenario_summary')}",
        "",
        "## Files produced",
        "",
    ]
    for name, path in artifacts.items():
        if name == "phase":
            continue
        lines.append(f"- `{name}` = {path}")
    if not artifacts:
        lines.append("- artefacts written only when the runner is asked to persist them")
    lines.extend(
        [
            "",
            "## Problems encountered",
            "",
            issues,
            "",
            "## Word limits",
            "",
            header.get("word_limits") or "- None recorded.",
            "",
            "## Remaining human checks",
            "",
            header.get("human_checks") or "- Visual inspection of the printed copy.",
            "",
            "## Technical corrections",
            "",
            header.get("technical_corrections")
            or "- None beyond the reusable Word field-update-on-open setting and the canonical version line.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
