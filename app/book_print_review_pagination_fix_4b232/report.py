"""Phase 4B.2.32 final report."""

from __future__ import annotations

from typing import Any, Mapping


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    artifacts = dict(bundle.get("written") or {})
    issues = header.get("issues") or "- None."
    lines = [
        "**PHASE 4B.2.32 — INTERCHAPTER BLANK PAGE REMOVAL**",
        "",
        f"RESULT = {header.get('result')}",
        "PROVIDER CALLS = 0",
        f"BOOK TITLE = {header.get('book_title')}",
        f"BOOK CANONICAL SHA-256 = {header.get('book_canonical_sha256')}",
        f"SOURCE VERSION = {header.get('source_version')}",
        f"OUTPUT VERSION = {header.get('output_version')}",
        f"PAGE FORMAT = {header.get('page_format')}",
        f"CHAPTER BREAK POLICY = {header.get('chapter_break_policy')}",
        f"FRONT MATTER UNCHANGED = {header.get('front_matter_unchanged')}",
        f"CHAPTERS = {header.get('chapters')}",
        f"SECTIONS = {header.get('sections')}",
        f"PARAGRAPHS = {header.get('paragraphs')}",
        f"CHAPTER TRANSITIONS CHECKED = {header.get('chapter_transitions_checked')}",
        f"UNNECESSARY INTERCHAPTER BLANK PAGES = {header.get('unnecessary_interchapter_blank_pages')}",
        f"TOC UPDATED = {header.get('toc_updated')}",
        f"PAGINATION STABLE = {header.get('pagination_stable')}",
        f"ORIGINAL PDF PAGE COUNT = {header.get('original_pdf_page_count')}",
        f"NEW PDF PAGE COUNT = {header.get('new_pdf_page_count')}",
        f"DOCX INTEGRITY = {header.get('docx_integrity')}",
        f"PDF INTEGRITY = {header.get('pdf_integrity')}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post')}",
        f"ORIGINAL FILES PRESERVED = {header.get('original_files_preserved')}",
        f"READY_FOR_PRINT_REVIEW = {header.get('ready_for_print_review')}",
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
            "## Next action",
            "",
            header.get("next_action") or "- STOP.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
