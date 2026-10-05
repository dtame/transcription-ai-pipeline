"""Phase 4B.2.18 report."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_authorial_voice_4b218.constants import CANONICAL_PYTHON, TARGET_CHAPTER_ID


def _yn(value: bool | None) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return "n/a"


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    table = header.get("paragraph_table") or []
    table_lines = [
        "| Paragraph ID | Problème | Correction | Preuve SRC | Statut |",
        "|---|---|---|---|---|",
    ]
    for row in table:
        table_lines.append(
            "| {paragraph_id} | {problem} | {correction} | {src} | {status} |".format(
                paragraph_id=row.get("paragraph_id", ""),
                problem=row.get("problem", ""),
                correction=row.get("correction", ""),
                src=row.get("src", ""),
                status=row.get("status", ""),
            )
        )
    lines = [
        "**PHASE 4B.2.18 — AUTHORIAL VOICE PRESERVATION & CH012 TARGETED CORRECTION**",
        "",
        f"RESULT = {header.get('result')}",
        "PROVIDER CALLS = 0",
        "ANTHROPIC HTTP = 0",
        "OPENAI HTTP = 0",
        f"CANONICAL PYTHON = {header.get('canonical_python') or CANONICAL_PYTHON}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post')}",
        f"CHAPTER = {header.get('chapter') or TARGET_CHAPTER_ID}",
        f"PARAGRAPHS AUDITED = {header.get('paragraphs_audited')}",
        f"EXTERNAL NARRATOR ISSUES = {header.get('external_narrator_issues')}",
        f"CORRECTIONS APPLIED = {header.get('corrections_applied')}",
        f"CORRECTIONS REQUIRING HUMAN REVIEW = {header.get('corrections_requiring_human_review')}",
        f"ATTRIBUTION UNCERTAIN = {header.get('attribution_uncertain')}",
        f"ORIGINAL CHAPTER HASH PRE/POST = {header.get('original_chapter_hash_pre_post')}",
        f"AUTHORIAL VOICE POLICY = {header.get('authorial_voice_policy')}",
        f"GENERATOR PROMPT 1.1 = {header.get('generator_prompt_1_1')}",
        "HISTORICAL PROMPTS MODIFIED = NO",
        f"IDEA TRACEABILITY DIAGNOSIS = {header.get('idea_traceability_diagnosis')}",
        f"IDEA MAPPINGS CONFIRMED = {header.get('idea_mappings_confirmed')}",
        f"IDEA MAPPINGS PROPOSED = {header.get('idea_mappings_proposed')}",
        f"IDEA MAPPINGS UNRESOLVED = {header.get('idea_mappings_unresolved')}",
        f"SOURCE COVERAGE STATUS = {header.get('source_coverage_status')}",
        f"UNC029 PRESERVED = {header.get('unc029_preserved')}",
        f"OFFLINE TESTS PASSED / FAILED = {header.get('tests_passed')} / {header.get('tests_failed')}",
        f"NEW REGRESSIONS = {header.get('new_regressions')}",
        "PRODUCTION PIPELINE MODIFIED = NO",
        "PRODUCTION CACHE = UNCHANGED",
        "SEMANTIC GATE PROMOTED = NO",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_HUMAN_REVIEW = {header.get('ready_for_human_review')}",
        f"READY_FOR_TERRA_VALIDATION = {header.get('ready_for_terra_validation')}",
        "READY_FOR_FULL_BOOK_GENERATION = NO",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Paragraph decisions",
        "",
        *table_lines,
        "",
        "## Why this result",
        "",
        str(header.get("notes") or ""),
        "",
        "## Historical results left in place",
        "",
        "4B.2.12 remains PASS. 4B.2.13 remains PASS. 4B.2.14 remains PASS.",
        "4B.2.15 remains PARTIAL. 4B.2.16 remains PASS. 4B.2.17 remains PARTIAL.",
        "h01, h02, and h11 remain PARTIAL.",
        "",
        "## Stop",
        "",
        "STOP. No Sonnet call. No Terra call. No CH012 regeneration.",
        "No CH016 generation. No 19-chapter generation.",
        "No Semantic Gate promotion. No production-pipeline activation.",
        "No book.json. No DOCX/PDF. Wait for human review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
