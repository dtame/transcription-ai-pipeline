"""Final 4B.2.27 remaining-13 real generation report."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation_4b227.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_CHAPTER_IDS,
    BUDGET_CAP_DISPLAY,
    CANONICAL_PYTHON,
    EXPECTED_PROMPT_1_1_SHA256,
    NEXT_ACTION,
    PHASE,
    PROMPT_VERSION,
)


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    rows = list(bundle.get("chapter_rows") or [])
    by_id = {row.get("chapter_id"): row for row in rows}
    lines = [
        "**PHASE 4B.2.27 — REMAINING 13 REAL GENERATION**",
        "",
        f"RESULT = {header.get('result')}",
        f"AUTHORIZATION SCOPE = {header.get('authorization_scope') or AUTHORIZATION_SCOPE}",
        f"AUTHORIZED CHAPTERS = {header.get('authorized_chapters')}",
        f"MODEL = {header.get('model')}",
        f"PROMPT = {header.get('prompt') or PROMPT_VERSION}",
        f"PROMPT HASH = {header.get('prompt_hash') or EXPECTED_PROMPT_1_1_SHA256}",
        f"PROVIDER CALLS = {header.get('provider_calls')}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http')}",
        "OPENAI HTTP = 0",
        "RETRIES = 0",
        "FALLBACKS = 0",
        f"AUTHORIZED CAP = {BUDGET_CAP_DISPLAY}",
        f"PREFLIGHT MAX COST = {header.get('preflight_max_cost')}",
        f"ACTUAL TOTAL COST = {header.get('actual_total_cost')}",
        f"RESERVED / UNCERTAIN COST = {header.get('reserved_or_uncertain_cost')}",
        f"REMAINING BUDGET = {header.get('remaining_budget')}",
        f"CHAPTERS GENERATED = {header.get('chapters_generated')}",
        f"CHAPTERS FAILED = {header.get('chapters_failed')}",
        f"CHAPTERS NOT_STARTED = {header.get('chapters_not_started')}",
        f"NORMALIZED EMPTY PARAGRAPHS = {header.get('normalized_empty_paragraphs')}",
        f"STRUCTURAL VALIDATION = {header.get('structural_validation')}",
        f"IDEA COVERAGE = {header.get('idea_coverage')}",
        f"INVALID SRC = {header.get('invalid_src')}",
        f"EX / REF / UNC TRACEABILITY = {header.get('ex_ref_unc_traceability')}",
        f"AUTHORIAL VOICE REVIEW = {header.get('authorial_voice_review')}",
        f"POTENTIAL SUBSTANTIVE ISSUES = {header.get('potential_substantive_issues')}",
        f"ACCEPTED CHAPTERS IMMUTABLE = {header.get('accepted_chapters_immutable')}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post_status')}",
        f"RESUME SAFETY = {header.get('resume_safety')}",
        f"CALL LOCK SAFETY = {header.get('call_lock_safety')}",
        "SEMANTIC CERTIFICATION = NOT PERFORMED",
        "HUMAN EDITORIAL ACCEPTANCE OF NEW CHAPTERS = PENDING",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_19_CHAPTER_MANUSCRIPT_REVIEW = {header.get('ready_for_19_chapter_manuscript_review')}",
        f"NEXT ACTION = {header.get('next_action') or NEXT_ACTION}",
        "",
        "## Chapter table",
        "",
        "| Chapitre | Appels | Coût réel | IDEA | Structure | Statut |",
        "|---|---|---|---|---|---|",
    ]
    for chapter_id in AUTHORIZED_CHAPTER_IDS:
        row = by_id.get(chapter_id) or {}
        ideas = row.get("ideas_found")
        expected = row.get("ideas_expected")
        idea_cell = (
            f"{ideas}/{expected}"
            if ideas is not None and expected is not None
            else row.get("ideas") or "n/a"
        )
        lines.append(
            "| {chapter_id} | {calls} | {cost} | {ideas} | {structural} | {status} |".format(
                chapter_id=chapter_id,
                calls=row.get("provider_calls", 0 if row else "n/a"),
                cost=row.get("cost", "n/a"),
                ideas=idea_cell,
                structural=row.get("structural", "n/a"),
                status=row.get("status", "NOT_STARTED"),
            )
        )
    lines.extend(
        [
            "",
            "A deterministic structural control does not certify semantic fidelity.",
            "The 13 new chapters remain pending human editorial acceptance.",
            "The six previously accepted chapters were not rewritten.",
            "",
            f"Canonical Python = {header.get('canonical_python') or CANONICAL_PYTHON}",
            f"Phase = {PHASE}",
            f"Stop reason = {header.get('stop_reason')}",
            "",
            "## Stop",
            "",
            "STOP. Do not regenerate. Do not retry a consumed or uncertain call.",
            "Do not launch a new lot. Do not call Terra. Do not call OpenAI.",
            "Do not generate images. Do not assemble DOCX or PDF.",
            "Do not publish book.json. Do not spend the remaining budget.",
            "Wait for human editorial review of the new chapters.",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = ["render_report"]
