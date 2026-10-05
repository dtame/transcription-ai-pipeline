"""Final 4B.2.23 BATCH-01 report. Starts with the required phase title."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation_4b223.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_CHAPTER_IDS,
    BATCH_ID,
    BUDGET_CAP_DISPLAY,
    CANONICAL_PYTHON,
    NEXT_ACTION,
    PHASE,
    PROMPT_VERSION,
)


def _yn(value: bool | None) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return "n/a"


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    chapters = list(bundle.get("chapter_rows") or [])
    lines = [
        "**PHASE 4B.2.23 — BATCH-01 REAL GENERATION**",
        "",
        f"RESULT = {header.get('result')}",
        f"AUTHORIZATION SCOPE = {header.get('authorization_scope') or AUTHORIZATION_SCOPE}",
        f"BATCH = {header.get('batch') or BATCH_ID}",
        f"CHAPTERS AUTHORIZED = {', '.join(AUTHORIZED_CHAPTER_IDS)}",
        f"CHAPTERS ATTEMPTED = {header.get('chapters_attempted')}",
        f"CHAPTERS GENERATED = {header.get('chapters_generated')}",
        f"CHAPTERS NOT GENERATED = {header.get('chapters_not_generated')}",
        f"PROVIDER CALLS = {header.get('provider_calls')}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http')}",
        f"OPENAI HTTP = {header.get('openai_http')}",
        f"MODEL = {header.get('model')}",
        f"PROMPT = {header.get('prompt') or PROMPT_VERSION}",
        f"PROMPT HASH = {header.get('prompt_hash')}",
        f"AUTHORIZED GLOBAL CAP = {BUDGET_CAP_DISPLAY}",
        f"PREFLIGHT MAX COST = {header.get('preflight_max_cost')}",
        f"ACTUAL COST BY CHAPTER = {header.get('actual_cost_by_chapter')}",
        f"ACTUAL TOTAL COST = {header.get('actual_total_cost')}",
        f"RESERVED / UNCERTAIN COST = {header.get('reserved_or_uncertain_cost')}",
        f"REMAINING BUDGET = {header.get('remaining_budget')}",
        f"RETRIES = {header.get('retries')}",
        f"FALLBACKS = {header.get('fallbacks')}",
        f"STRUCTURAL VALIDATION BY CHAPTER = {header.get('structural_by_chapter')}",
        f"IDEA COVERAGE BY CHAPTER = {header.get('idea_coverage_by_chapter')}",
        f"SRC VALIDATION BY CHAPTER = {header.get('src_validation_by_chapter')}",
        f"EX / REF TRACEABILITY = {header.get('ex_ref_traceability')}",
        f"AUTHORIAL VOICE REVIEW = {header.get('authorial_voice_review')}",
        f"POTENTIAL SUBSTANTIVE ISSUES = {header.get('potential_substantive_issues')}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post')}",
        f"CH012 IMMUTABLE = {header.get('ch012_unchanged')}",
        f"CH018 IMMUTABLE = {header.get('ch018_unchanged')}",
        f"PRODUCTION CACHE = {header.get('production_cache')}",
        "SEMANTIC CERTIFICATION = NOT PERFORMED",
        "HUMAN EDITORIAL ACCEPTANCE = PENDING",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_HUMAN_REVIEW = {header.get('ready_for_human_review')}",
        "READY_FOR_BATCH02 = NO",
        f"NEXT ACTION = {header.get('next_action') or NEXT_ACTION}",
        "",
        "## Chapter table",
        "",
        "| Chapter | Status | Cost | Structural | IDEA missing | SRC invalid | Editorial | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    if not chapters:
        for chapter_id in AUTHORIZED_CHAPTER_IDS:
            lines.append(
                f"| {chapter_id} | NOT_GENERATED | n/a | n/a | n/a | n/a | n/a | not attempted |"
            )
    else:
        for row in chapters:
            lines.append(
                "| {chapter_id} | {status} | {cost} | {structural} | {ideas} | {src} | {editorial} | {notes} |".format(
                    chapter_id=row.get("chapter_id"),
                    status=row.get("status"),
                    cost=row.get("cost"),
                    structural=row.get("structural"),
                    ideas=row.get("ideas_missing"),
                    src=row.get("src_invalid"),
                    editorial=row.get("editorial"),
                    notes=row.get("notes") or "",
                )
            )
    lines.extend(
        [
            "",
            "A deterministic offline control does not certify semantic fidelity.",
            "Do not treat identifier coverage as content coverage.",
            "BATCH-01 chapters are not accepted until an explicit human decision.",
            "",
            f"Canonical Python = {header.get('canonical_python') or CANONICAL_PYTHON}",
            f"Phase = {PHASE}",
            f"Stop reason = {header.get('stop_reason')}",
            "",
            "## Stop",
            "",
            "STOP. Do not launch BATCH-02. Do not generate the remaining 13 chapters.",
            "Do not retry a failed chapter. Do not spend the remaining budget.",
            "No Terra call. No book.json. No DOCX/PDF.",
            "Wait for human editorial review.",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = ["render_report"]
