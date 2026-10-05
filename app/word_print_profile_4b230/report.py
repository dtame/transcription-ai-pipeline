"""Phase 4B.2.30 final report."""

from __future__ import annotations

from typing import Any, Mapping


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    artifacts = dict(bundle.get("written") or {})
    decisions = [
        "Reused python-docx, the existing 6x9 page-size key, and the classic Georgia body font.",
        "Did not replace publication_docx_engine or docx_export_service; those remain Markdown workshop exporters.",
        "Layout lives in a book-agnostic profile: app/word_renderer/profiles/print_review_6x9_v1.json.",
        "Mirror margins treat left=inside and right=outside. w:gutter is additional and is not folded into the inside margin.",
        "Chapter numbers come from chapter.order and are written on a separate line, never merged into titles.",
        "The Word TOC is a field. Page numbers are PAGE fields. Running chapter titles use STYLEREF.",
        "Author, ISBN, publisher, copyright, date, and logo are not invented. The canonical subtitle is used only because book.json already has it.",
        "Cover remains optional. Spine width is not computed.",
        "In-memory documents and a two-chapter synthetic book were used for layout tests. The full book DOCX was not published.",
    ]
    limits = [
        "python-docx cannot refresh fields or compute final page numbers.",
        "ODD_PAGE chapter starts are configured; Word materializes any blank verso pages.",
        "Roman front-matter pagination was avoided because it is not independently verifiable here.",
        "The Word Finalizer contract is prepared but not executed.",
        "Hyphenation stays disabled until a later print inspection justifies it.",
        "These 6x9 margins are a first print-review starting point and may change after the first printed copy.",
    ]
    lines = [
        "**PHASE 4B.2.30 — WORD PRINT PROFILE PREPARATION**",
        "",
        f"RESULT = {header.get('result')}",
        "PROVIDER CALLS = 0",
        f"BOOK TITLE = {header.get('book_title')}",
        f"BOOK VERSION = {header.get('book_version')}",
        f"BOOK STATUS = {header.get('book_status')}",
        f"BOOK SHA-256 = {header.get('book_sha256')}",
        f"PRINT FORMAT = {header.get('print_format')}",
        f"PROFILE = {header.get('profile')}",
        f"WORD RENDERER = {header.get('word_renderer')}",
        f"WORD FINALIZER = {header.get('word_finalizer')}",
        f"PAGE GEOMETRY = {header.get('page_geometry')}",
        f"MIRROR MARGINS = {header.get('mirror_margins')}",
        f"TYPOGRAPHY STYLES = {header.get('typography_styles')}",
        f"CHAPTER STYLES = {header.get('chapter_styles')}",
        f"SECTION STYLES = {header.get('section_styles')}",
        f"TOC PREPARATION = {header.get('toc_preparation')}",
        f"HEADERS / FOOTERS = {header.get('headers_footers')}",
        f"CHAPTER PAGE BREAKS = {header.get('chapter_page_breaks')}",
        f"COVER INTEGRATION = {header.get('cover_integration')}",
        f"BOOK CONTENT MAPPING = {header.get('book_content_mapping')}",
        f"OFFLINE TESTS PASSED / FAILED = {header.get('offline_tests')}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post')}",
        "DOCX = NOT GENERATED",
        "PDF = NOT GENERATED",
        f"READY_FOR_DOCX_PDF_GENERATION = {header.get('ready_for_docx_pdf_generation')}",
        f"NEXT ACTION = {header.get('next_action')}",
        "",
        "## Tests executed",
        "",
        f"- pytest: {header.get('pytest_summary')}",
        f"- offline scenarios: {header.get('scenario_summary')}",
        "",
        "## Artefacts",
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
            "## Technical decisions",
            "",
            *[f"- {item}" for item in decisions],
            "",
            "## Code modifications",
            "",
            "- Added reusable package `app/word_renderer` with profile, styles, geometry, headers, TOC field, mapping, and finalizer contract.",
            "- Added isolated package `app/word_print_profile_4b230`.",
            "- Added offline tests `app/tests/test_word_print_profile_4b230.py`.",
            "- Did not change book.json, chapter sources, SourceMap, EditorialPlan, or the existing Markdown Word exporters.",
            "",
            "## Known limits",
            "",
            *[f"- {item}" for item in limits],
            "",
            "## Issues",
            "",
            header.get("issues") or "- None.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
