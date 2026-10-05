"""Phase 4B.2.29 final report."""

from __future__ import annotations

from typing import Any, Mapping


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    artifacts = dict(bundle.get("written") or {})
    decisions = [
        "Reused the existing Book 1.0 production contract instead of inventing a new schema.",
        "Extended book.json only with backward-compatible editorial, version, and provenance fields.",
        "Chapter JSON remained the structural source. The 4B.2.28 Markdown manuscript was a coherence control.",
        "Global P000001… paragraph IDs were assigned during assembly. Chapter-local IDs were kept as source_paragraph_id.",
        "The six accepted chapters kept HUMAN_EDITORIALLY_ACCEPTED. The thirteen others stayed GENERATED_STRUCTURALLY_VALID.",
        "The book-level DRAFT_FOR_PRINT_REVIEW status does not overwrite chapter statuses.",
        "Editorial observations from 4B.2.28 were linked, not treated as confirmed errors, and not corrected.",
        "Author, publisher, ISBN, copyright, preface, dedication, biography, and acknowledgements were not invented.",
        "Production book.json is the runtime canonical. The audit copy is immutable evidence, not a second runtime source.",
    ]
    limits = [
        "This is a working print-review draft, not HUMAN_EDITORIALLY_ACCEPTED at book level.",
        "Thirteen chapters remain pending human literary review of the first printed version.",
        "Semantic certification was not performed.",
        "Visual direction has not started.",
        "DOCX and PDF were not generated.",
        "No complete revision-management system was implemented; only a comparison hook was prepared.",
    ]
    lines = [
        "**PHASE 4B.2.29 — PRINT REVIEW BOOK CANONICAL**",
        "",
        f"RESULT = {header.get('result')}",
        "PROVIDER CALLS = 0",
        "ANTHROPIC HTTP = 0",
        "OPENAI HTTP = 0",
        f"BOOK TITLE = {header.get('book_title')}",
        f"BOOK STATUS = {header.get('book_status')}",
        f"BOOK VERSION = {header.get('book_version')}",
        f"BOOK CANONICAL PATH = {header.get('book_canonical_path')}",
        f"BOOK SHA-256 = {header.get('book_sha256')}",
        f"CHAPTERS = {header.get('chapters')}",
        f"SECTIONS = {header.get('sections')}",
        f"IDEA COVERAGE = {header.get('idea_coverage')}",
        f"HUMAN ACCEPTED CHAPTERS = {header.get('human_accepted_chapters')}",
        f"HUMAN REVIEW PENDING CHAPTERS = {header.get('human_review_pending_chapters')}",
        f"PARAGRAPH INTEGRITY = {header.get('paragraph_integrity')}",
        f"PROVENANCE INTEGRITY = {header.get('provenance_integrity')}",
        f"MARKDOWN COMPARISON = {header.get('markdown_comparison')}",
        f"SCHEMA VALIDATION = {header.get('schema_validation')}",
        f"WORD RENDERER READINESS = {header.get('word_renderer_readiness')}",
        f"EDITORIAL OBSERVATIONS PRESERVED = {header.get('editorial_observations_preserved')}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post')}",
        f"SOURCE CHAPTERS IMMUTABLE = {header.get('source_chapters_immutable')}",
        f"PUBLICATION ATOMIC = {header.get('publication_atomic')}",
        "DOCX = NOT GENERATED",
        "PDF = NOT GENERATED",
        "VISUAL DIRECTION = NOT STARTED",
        "SEMANTIC CERTIFICATION = NOT PERFORMED",
        f"READY_FOR_PRINT_REVIEW_PRODUCTION = {header.get('ready_for_print_review_production')}",
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
            "- Added isolated package `app/book_print_review_canonical_4b229`.",
            "- Added offline tests `app/tests/test_book_print_review_canonical_4b229.py`.",
            "- 4B.2.28 now tolerates an existing 4B.2.29 draft and still refuses to write book.json.",
            "- Did not change chapter sources, SourceMap, EditorialPlan, transcript, or the 4B.2.28 manuscript.",
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
