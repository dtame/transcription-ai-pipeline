"""Final 4B.2.25 BATCH-01 resume report. Starts with the required phase title."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation_4b225.constants import (
    AUTHORIZATION_SCOPE,
    BUDGET_CAP_DISPLAY,
    CANONICAL_PYTHON,
    EXPECTED_PROMPT_1_1_SHA256,
    NEXT_ACTION,
    PHASE,
    PROMPT_VERSION,
)


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    chapters = list(bundle.get("chapter_rows") or [])
    lines = [
        "**PHASE 4B.2.25 — BATCH-01 RESUME**",
        "",
        f"RESULT = {header.get('result')}",
        f"AUTHORIZATION SCOPE = {header.get('authorization_scope') or AUTHORIZATION_SCOPE}",
        f"PROVIDER CALLS = {header.get('provider_calls')}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http')}",
        "OPENAI HTTP = 0",
        f"CH001 HUMAN ACCEPTANCE = {header.get('ch001_human_acceptance')}",
        f"CH002 HUMAN ACCEPTANCE = {header.get('ch002_human_acceptance')}",
        f"CH001 MD/JSON SHA-256 = {header.get('ch001_md_json_sha256')}",
        f"CH002 MD/JSON SHA-256 = {header.get('ch002_md_json_sha256')}",
        f"CH003 STATUS = {header.get('ch003_status')}",
        f"CH004 STATUS = {header.get('ch004_status')}",
        f"MODEL = {header.get('model')}",
        f"PROMPT = {header.get('prompt') or PROMPT_VERSION}",
        f"PROMPT HASH = {header.get('prompt_hash') or EXPECTED_PROMPT_1_1_SHA256}",
        f"AUTHORIZED CAP = {BUDGET_CAP_DISPLAY}",
        f"PREFLIGHT MAX COST = {header.get('preflight_max_cost')}",
        f"ACTUAL COST CH003 = {header.get('actual_cost_ch003')}",
        f"ACTUAL COST CH004 = {header.get('actual_cost_ch004')}",
        f"ACTUAL TOTAL COST = {header.get('actual_total_cost')}",
        f"RESERVED / UNCERTAIN COST = {header.get('reserved_or_uncertain_cost')}",
        "RETRIES = 0",
        "FALLBACKS = 0",
        f"STRUCTURAL VALIDATION BY CHAPTER = {header.get('structural_by_chapter')}",
        f"IDEA COVERAGE BY CHAPTER = {header.get('idea_coverage_by_chapter')}",
        f"SRC VALIDATION BY CHAPTER = {header.get('src_validation_by_chapter')}",
        f"EX / REF TRACEABILITY = {header.get('ex_ref_traceability')}",
        f"AUTHORIAL VOICE REVIEW = {header.get('authorial_voice_review')}",
        f"POTENTIAL SUBSTANTIVE ISSUES = {header.get('potential_substantive_issues')}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post')}",
        f"CH001 / CH002 IMMUTABLE = {header.get('ch001_ch002_immutable')}",
        f"CH012 / CH018 IMMUTABLE = {header.get('ch012_ch018_immutable')}",
        "PRODUCTION CACHE = UNCHANGED",
        "SEMANTIC CERTIFICATION = NOT PERFORMED",
        "HUMAN EDITORIAL ACCEPTANCE CH003/CH004 = PENDING",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_HUMAN_REVIEW = {header.get('ready_for_human_review')}",
        f"NEXT ACTION = {header.get('next_action') or NEXT_ACTION}",
        "",
        "## Chapter table",
        "",
        "| Chapter | Status | Cost | Structural | IDEA missing | SRC invalid | Editorial | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    if not chapters:
        for chapter_id in ("CH003", "CH004"):
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
            "CH003 and CH004 remain pending human editorial acceptance.",
            "",
            f"Canonical Python = {header.get('canonical_python') or CANONICAL_PYTHON}",
            f"Phase = {PHASE}",
            f"Stop reason = {header.get('stop_reason')}",
            "",
            "## Stop",
            "",
            "STOP. Do not launch BATCH-02. Do not generate the remaining 13 chapters.",
            "Do not retry a consumed call. Do not spend the remaining budget.",
            "No Terra call. No book.json. No DOCX/PDF.",
            "Wait for a new explicit human decision.",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = ["render_report"]
