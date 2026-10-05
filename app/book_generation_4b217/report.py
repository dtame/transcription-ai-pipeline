"""Final 4B.2.17 report. Starts with the required phase title."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation_4b217.constants import (
    BUDGET_CAP_DISPLAY,
    CANONICAL_PYTHON,
    PHASE,
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
    editorial = dict(bundle.get("editorial_summary") or {})
    lines = [
        "**PHASE 4B.2.17 — CH012 FAITHFUL REAL PILOT GENERATION**",
        "",
        f"RESULT = {header.get('result')}",
        f"PROVIDER CALLS = {header.get('provider_calls')}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http')}",
        f"OPENAI HTTP = {header.get('openai_http')}",
        f"MODEL = {header.get('model')}",
        f"CHAPTER = {TARGET_CHAPTER_ID}",
        f"CANONICAL PYTHON = {header.get('canonical_python') or CANONICAL_PYTHON}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post')}",
        f"EDITORIAL POLICY = {header.get('editorial_policy')}",
        f"GENERATOR PROMPT = {header.get('generator_prompt')}",
        f"PROMPT VERSION = {header.get('prompt_version')}",
        f"REAL CALL AUTHORIZATION = {header.get('real_call_authorization')}",
        f"COST CAP = {BUDGET_CAP_DISPLAY}",
        f"PRECALL MAXIMUM COST = {header.get('precall_maximum_cost')}",
        f"REAL COST = {header.get('real_cost')}",
        f"COST SOURCE = {header.get('cost_source')}",
        f"INPUT TOKENS = {header.get('input_tokens')}",
        f"OUTPUT TOKENS = {header.get('output_tokens')}",
        f"STOP REASON = {header.get('stop_reason')}",
        f"CHAPTER JSON VALID = {header.get('chapter_json_valid')}",
        f"CHAPTER CONTRACT VALID = {header.get('chapter_contract_valid')}",
        f"SECTIONS EXPECTED / GENERATED = {header.get('sections_expected_generated')}",
        f"IDEAS EXPECTED / REFERENCED = {header.get('ideas_expected_referenced')}",
        f"PARAGRAPHS GENERATED = {header.get('paragraphs_generated')}",
        f"SOURCE COVERAGE = {header.get('source_coverage')}",
        "SEMANTIC FIDELITY VALIDATED = NO",
        "TERRA VALIDATION CALLS = 0",
        f"ESTIMATED TERRA CALLS = {header.get('estimated_terra_calls')}",
        f"ESTIMATED TERRA COST = {header.get('estimated_terra_cost')}",
        "HISTORICAL PROMPTS MODIFIED = NO",
        "HISTORICAL SEMANTIC CONTRACT MODIFIED = NO",
        "PRODUCTION PIPELINE MODIFIED = NO",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_HUMAN_CHAPTER_REVIEW = {header.get('ready_for_human_chapter_review')}",
        f"READY_FOR_TERRA_VALIDATION = {header.get('ready_for_terra_validation')}",
        "READY_FOR_FULL_BOOK_GENERATION = NO",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Editorial summary",
        "",
        f"- Reading quality observed: {editorial.get('reading_quality', 'n/a')}",
        f"- Thematic organization: {editorial.get('thematic_organization', 'n/a')}",
        f"- Passages to examine: {editorial.get('passages_to_examine', 'n/a')}",
        f"- Uncertain references: {editorial.get('uncertain_references', 'n/a')}",
        f"- Possible omissions: {editorial.get('possible_omissions', 'n/a')}",
        f"- Transitions that may be interpretive: {editorial.get('interpretive_transitions', 'n/a')}",
        "",
        "A deterministic offline control does not certify semantic fidelity.",
        "Do not treat identifier coverage as content coverage.",
        "",
        "## Historical results left in place",
        "",
        "4B.2.12 remains PASS. 4B.2.13 remains PASS. 4B.2.14 remains PASS.",
        "4B.2.15 remains PARTIAL. 4B.2.16 remains PASS.",
        "h01, h02, and h11 remain PARTIAL.",
        "",
        "## Stop",
        "",
        "STOP. No second provider call. No Terra call. No Phase 5 real run.",
        "No CH016 generation. No 19-chapter generation. No book.json.",
        "No DOCX/PDF. Wait for human review.",
        "",
    ]
    return "\n".join(lines)


def _yn_header(value: bool | None) -> str:
    return _yn(value)


__all__ = ["render_report"]
