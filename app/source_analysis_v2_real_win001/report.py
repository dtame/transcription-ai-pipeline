"""Rapport markdown déterministe 3B.7.7A.15."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v2_real_win001.constants import NEXT_ACTION


def _dash(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return str(value)


def render_report(result: Any, *, tests: str | None = None) -> str:
    pre = result.preflight or {}
    exe = result.execution or {}
    review = result.review or {}
    window = pre.get("window") or {}
    rec = exe.get("records") or {}
    links = exe.get("links") or {}
    src = exe.get("src") or {}
    cost = exe.get("cost") or {}
    verdict = exe.get("result") or (
        "BLOCKED_PRECALL" if result.blocked_precall else result.mode
    )
    tests_line = tests or pre.get("baseline_tests") or "UNKNOWN"
    ready = exe.get("real_windows_ready") or "0 / 7"
    lines = [
        "# PHASE 3B.7.7A.15 — REAL V2 SMALL WIN001 SEMANTIC CANARY",
        "",
        "## Result",
        "",
        str(verdict),
        "",
        f"REAL PROVIDER CALLS = {result.anthropic_post_attempts}",
        "",
        f"REAL WINDOW CALLS = {1 if result.engine_generate_attempts else 0}",
        "",
        "AUTHORIZED TARGET = WIN001",
        "",
        f"WIN001 SRC RANGE = {window.get('src_range')}",
        "",
        f"OWNED SRC COUNT = {window.get('owned_src_count')}",
        "",
        f"WORD COUNT = {window.get('word_count')}",
        "",
        f"LOCAL INPUT ESTIMATE = {pre.get('local_input_estimate')}",
        "",
        f"ACTUAL PROVIDER INPUT = {_dash(exe.get('actual_provider_input') or exe.get('input_tokens'))}",
        "",
        f"INPUT RATIO = {_dash(exe.get('input_ratio'))}",
        "",
        "PROMPT = window-analysis-1.2.1",
        "",
        "TRANSPORT = semantic-transport-v2",
        "",
        "THINKING = disabled",
        "",
        f"ACTUAL THINKING TOKENS = {_dash(exe.get('thinking_tokens'))}",
        "",
        "MAX OUTPUT = 32000",
        "",
        f"ACTUAL OUTPUT = {_dash(exe.get('output_tokens'))}",
        "",
        f"FINISH REASON = {_dash(exe.get('finish_reason'))}",
        "",
        f"HTTP = {_dash(exe.get('http_status'))}",
        "",
        f"REQUEST ID = {_dash(exe.get('request_id'))}",
        "",
        f"STRUCTURED PARSE = {_dash(exe.get('structured_parse'))}",
        "",
        f"V2 DECODER = {_dash(exe.get('v2_decoder'))}",
        "",
        f"V2 VALIDATOR = {_dash(exe.get('v2_validator'))}",
        "",
        f"CAPACITY SIGNAL = {_dash(exe.get('capacity_signal'))}",
        "",
        f"TOTAL RECORDS = {_dash(rec.get('total_records'))}",
        "",
        f"TOPIC = {_dash(rec.get('TOPIC'))}",
        "",
        f"IDEA = {_dash(rec.get('IDEA'))}",
        "",
        f"RELATION = {_dash(rec.get('RELATION'))}",
        "",
        f"EXAMPLE = {_dash(rec.get('EXAMPLE'))}",
        "",
        f"REFERENCE = {_dash(rec.get('REFERENCE'))}",
        "",
        f"UNCERTAINTY = {_dash(rec.get('UNCERTAINTY'))}",
        "",
        f"SELF LINKS = {_dash(links.get('self_links'))}",
        "",
        f"INVALID LINKS = {_dash(links.get('invalid_targets'))}",
        "",
        f"DISTINCT SRC REFS = {_dash(src.get('distinct_srcs_referenced'))}",
        "",
        f"SEMANTIC SRC COVERAGE = {_dash(src.get('semantic_src_coverage_pct'))}",
        "",
        f"UNSUPPORTED CONTENT = {_dash(review.get('unsupported_content'))}",
        "",
        f"SEMANTIC QUALITY = {_dash(review.get('semantic_quality'))}",
        "",
        f"THINKING_DISABLED LOCAL EXTRACTION = {_dash(review.get('thinking_disabled_local_extraction'))}",
        "",
        f"ACTUAL COST = {_dash(cost.get('display'))}",
        "",
        f"PROVIDER ELAPSED = {_dash(exe.get('provider_elapsed_ms'))}",
        "",
        f"CACHE = {_dash(exe.get('cache') or (pre.get('cache') or {}).get('status'))}",
        "",
        f"REAL WINDOWS READY = {ready}",
        "",
        "WIN002 AUTHORIZED = NO",
        "",
        "CONSOLIDATION AUTHORIZED = NO",
        "",
        "SOURCE MAP = NOT PUBLISHED",
        "",
        "PRODUCTION DEFAULT = window-planner-v2.0",
        "",
        "PHASE 3B = INCOMPLETE",
        "",
        f"TESTS = {tests_line}",
        "",
        f"NEXT ACTION = {NEXT_ACTION}",
        "",
        "## 1. Provider calls",
        "",
        f"How many provider calls occurred? {result.anthropic_post_attempts}",
        f"Was only WIN001 called? {'YES' if result.anthropic_post_attempts <= 1 else 'NO'}",
        "Did WIN002–WIN007 occur? NO",
        "Did consolidation occur? NO",
        "Was source_map published? NO",
        "Was production default changed? NO",
        "",
        "## 2. Thinking contract",
        "",
        f"Did thinking remain disabled? type=disabled, tokens={_dash(exe.get('thinking_tokens'))}",
        f"Finish reason: {_dash(exe.get('finish_reason'))}",
        "",
        "## 3. Technical pipeline",
        "",
        f"Structured parse: {_dash(exe.get('structured_parse'))}",
        f"Decoder: {_dash(exe.get('v2_decoder'))}",
        f"Validator: {_dash(exe.get('v2_validator'))}",
        f"Links valid: {_dash(links.get('links_valid'))}",
        f"Capacity signal: {_dash(exe.get('capacity_signal'))}",
        "",
        "## 4. Semantic review",
        "",
        f"Quality: {_dash(review.get('semantic_quality'))}",
        f"Thinking-disabled local extraction: {_dash(review.get('thinking_disabled_local_extraction'))}",
        f"Unsupported content: {_dash(review.get('unsupported_content'))}",
        f"Idea grouping: {_dash(review.get('idea_grouping'))}",
        f"Reasons: {review.get('reasons')}",
        "",
        "## 5. Comparison with CALL C",
        "",
        "CALL C: input 50603 / output 32000 / thinking 21911 / finish max_tokens / parse FAIL",
        f"A.15: input {_dash(exe.get('input_tokens'))} / output {_dash(exe.get('output_tokens'))} / "
        f"thinking {_dash(exe.get('thinking_tokens'))} / finish {_dash(exe.get('finish_reason'))}",
        "Causality is not claimed beyond this one window.",
        "",
        "## 6. Next phase",
        "",
        "Do not pre-authorize WIN002–WIN007 or another canary.",
        "If PASS: human review before deciding sequential windows or another representative canary.",
        "Do not execute either.",
        "",
        f"Error: {_dash(result.error)}",
        "",
        f"NEXT ACTION = {NEXT_ACTION}",
        "",
    ]
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
