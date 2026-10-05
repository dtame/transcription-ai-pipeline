"""Final 4B.2.24 report. Starts with the required phase title."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_ch002_offline_recovery_4b224.constants import CANONICAL_PYTHON, NEXT_ACTION


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    forensic = dict(bundle.get("ch002_empty_paragraph_forensic_review") or {})
    recovery = dict(bundle.get("recovery_manifest") or {})
    validation = dict(bundle.get("recovery_validation") or {})
    prevention = dict(bundle.get("prevention") or {})
    review = dict(bundle.get("ch001_human_editorial_review_packet") or {})
    resume = dict(bundle.get("batch01_resume_plan") or {})
    where = dict(prevention.get("where_introduced") or {})
    lines = [
        "**PHASE 4B.2.24 — CH002 OFFLINE RECOVERY & CH001 EDITORIAL REVIEW**",
        "",
        f"RESULT = {header.get('result')}",
        "PROVIDER CALLS = 0",
        "ANTHROPIC HTTP = 0",
        "OPENAI HTTP = 0",
        f"CH001 STATUS = {header.get('ch001_status')}",
        "CH001 EDITORIAL REVIEW = PENDING",
        "CH002 ORIGINAL STATUS = FAILED",
        f"CH002 RECOVERY = {header.get('ch002_recovery')}",
        f"CH002 RECOVERED STRUCTURAL CONTRACT = {header.get('ch002_recovered_contract')}",
        f"CH002 IDEA COVERAGE = {header.get('ch002_idea_coverage')}",
        f"CH002 EMPTY PARAGRAPH = {header.get('ch002_empty_paragraph')}",
        f"CH002 ADDITIONAL DEFECTS = {header.get('ch002_additional_defects')}",
        f"CH002 ORIGINAL IMMUTABLE = {header.get('ch002_original_immutable')}",
        f"CH002 CALL LOCK CONSUMED = {header.get('ch002_lock_consumed')}",
        "CH003 STATUS = NOT_STARTED",
        "CH004 STATUS = NOT_STARTED",
        "BATCH-01 HISTORICAL COST = 0.075284 USD",
        "ADDITIONAL COST = 0 USD",
        "AUTHORIZED SPEND = 0 USD",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post')}",
        f"CH012 IMMUTABLE = {header.get('ch012_immutable')}",
        f"CH018 IMMUTABLE = {header.get('ch018_immutable')}",
        f"OFFLINE TESTS PASSED / FAILED = {header.get('offline_tests')}",
        "PRODUCTION PIPELINE MODIFIED = NO",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_CH001_HUMAN_REVIEW = {header.get('ready_for_ch001_human_review')}",
        f"READY_FOR_CH002_HUMAN_REVIEW = {header.get('ready_for_ch002_human_review')}",
        f"READY_FOR_CH003_CH004_AUTHORIZATION = {header.get('ready_for_ch003_ch004_authorization')}",
        f"NEXT ACTION = {header.get('next_action') or NEXT_ACTION}",
        "",
        "## Recovery synthesis",
        "",
        str(header.get("recovery_notes") or ""),
        "",
        f"Removed paragraph: {recovery.get('removed_paragraph_id')}",
        f"Justification: {recovery.get('justification')}",
        f"Exact modifications: {recovery.get('exact_modifications')}",
        f"Recovered validation status: {(validation.get('status') or recovery.get('validation_status'))}",
        f"Human acceptance: {recovery.get('human_acceptance')}",
        "",
        "## Forensic finding",
        "",
        str((forensic.get("introduction") or {}).get("rationale") or ""),
        f"Additional defects: {header.get('ch002_additional_defects')}",
        "",
        "## Prevention proposed",
        "",
        str(where.get("evidence") or header.get("prevention_notes") or ""),
        "",
        "A future authorized phase may strip strictly empty, provenance-less "
        "paragraphs before the existing validator runs. This phase does not "
        "install that rule in production. The raw Anthropic response stays immutable.",
        "",
        "## CH001 review",
        "",
        f"Title: {review.get('title')}",
        f"Paragraphs: {review.get('paragraph_count')}",
        f"IDEA: {review.get('ideas_traced_count')} / {review.get('ideas_expected_count')}",
        "The sentence \"You only did not accept it there.\" is awkward and may be "
        "an oral residue. Reformulations were proposed and not applied.",
        "",
        "## Resume plan",
        "",
        f"Resume chapters: {', '.join(resume.get('resume_chapters') or [])}",
        "CH003 and CH004 remain NOT_STARTED. Their locks were not consumed.",
        "The 4B.2.23 remaining budget is not a new authorization.",
        "This plan was not executed.",
        "",
        f"Canonical Python = {CANONICAL_PYTHON}",
        "Phase = 4B.2.24",
        "",
        "## Stop",
        "",
        "STOP. Do not call Anthropic. Do not relaunch CH002.",
        "Do not generate CH003 or CH004. Do not launch BATCH-02.",
        "Wait for human editorial review and a new explicit paid-generation authorization.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
