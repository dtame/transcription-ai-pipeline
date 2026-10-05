"""Final 4B.2.21 report. Starts with the required phase title."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation_4b221.constants import (
    AUTHORIZATION_SCOPE,
    BUDGET_CAP_DISPLAY,
    CANONICAL_PYTHON,
    EXPECTED_IDEA_COUNT,
    PHASE,
    PROMPT_VERSION,
    TARGET_CHAPTER_ID,
)


def _yn(value: bool | None) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return "n/a"


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    editorial = dict(bundle.get("editorial_readiness_review") or {})
    idea = dict(bundle.get("idea_traceability_review") or {})
    voice = dict(editorial.get("authorial_voice") or {})
    potential = editorial.get("potential_substantive_issues") or []
    quality = header.get("quality_summary") or (
        editorial.get("readability")
        or "No chapter candidate was available for a quality summary."
    )
    lines = [
        "**PHASE 4B.2.21 — CH018 FIRST REAL CONTROLLED GENERATION**",
        "",
        f"RESULT = {header.get('result')}",
        f"AUTHORIZATION SCOPE = {header.get('authorization_scope') or AUTHORIZATION_SCOPE}",
        f"PROVIDER CALLS = {header.get('provider_calls')}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http')}",
        f"OPENAI HTTP = {header.get('openai_http')}",
        f"CHAPTER = {header.get('chapter') or TARGET_CHAPTER_ID}",
        f"MODEL = {header.get('model')}",
        f"PROMPT = {header.get('prompt') or PROMPT_VERSION}",
        f"PROMPT HASH = {header.get('prompt_hash')}",
        f"SOURCE CONTEXT HASH = {header.get('source_context_hash')}",
        f"INPUT TOKENS = {header.get('input_tokens')}",
        f"OUTPUT TOKENS = {header.get('output_tokens')}",
        f"FINISH REASON = {header.get('finish_reason')}",
        f"PREFLIGHT MAX COST = {header.get('preflight_max_cost')}",
        f"ACTUAL COST = {header.get('actual_cost')}",
        f"AUTHORIZED CAP = {BUDGET_CAP_DISPLAY}",
        f"RETRIES = {header.get('retries')}",
        f"FALLBACKS = {header.get('fallbacks')}",
        f"JSON VALID = {header.get('json_valid')}",
        f"STRUCTURAL CONTRACT = {header.get('structural_contract')}",
        f"SECTIONS PRESENT = {header.get('sections_present')}",
        f"IDEA HANDLES EXPECTED = {header.get('idea_handles_expected') or EXPECTED_IDEA_COUNT}",
        f"IDEA HANDLES FOUND = {header.get('idea_handles_found')}",
        f"IDEA HANDLES INVALID = {header.get('idea_handles_invalid')}",
        f"SRC HANDLES INVALID = {header.get('src_handles_invalid')}",
        f"AUTHORIAL VOICE REVIEW = {header.get('authorial_voice_review')}",
        f"POTENTIAL SUBSTANTIVE ISSUES = {header.get('potential_substantive_issues')}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post')}",
        f"CH012 UNCHANGED = {header.get('ch012_unchanged')}",
        f"PRODUCTION CACHE = {header.get('production_cache')}",
        "SEMANTIC CERTIFICATION = NOT PERFORMED",
        "HUMAN EDITORIAL ACCEPTANCE = PENDING",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_HUMAN_REVIEW = {header.get('ready_for_human_review')}",
        "READY_FOR_NEXT_CHAPTER = NO",
        f"NEXT ACTION = {header.get('next_action')}",
        "",
        "## Quality summary",
        "",
        quality,
        "",
        f"Authorial voice classification: {voice.get('classification', 'n/a')}.",
        f"First person observed: {voice.get('first_person_observed', 'n/a')}.",
        f"Second person observed: {voice.get('second_person_observed', 'n/a')}.",
        f"Conference-report frames: {voice.get('conference_report_frames') or 'none flagged'}.",
        f"Potential substantive issues: {len(potential)}.",
        f"IDEA handles in paras[].e: {idea.get('ideas_found_count', 'n/a')} / {EXPECTED_IDEA_COUNT}.",
        "",
        "A deterministic offline control does not certify semantic fidelity.",
        "Do not treat identifier coverage as content coverage.",
        "CH018 is not accepted until an explicit human decision.",
        "",
        f"Canonical Python = {header.get('canonical_python') or CANONICAL_PYTHON}",
        f"Phase = {PHASE}",
        f"Stop reason = {header.get('stop_reason')}",
        "",
        "## Stop",
        "",
        "STOP. No second provider call. No Terra call. No next chapter.",
        "No 18-chapter generation. No book.json. No DOCX/PDF.",
        "Wait for human editorial review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
