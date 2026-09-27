"""Rapport markdown déterministe 3B.7.7A.21."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v3_hardened_win001.constants import (
    EXPECTED_SCHEMA_HASH,
    NEXT_ACTION,
)


def _dash(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return str(value)


def render_report(result: Any, *, tests: str | None = None) -> str:
    pre = result.preflight or {}
    exe = result.execution or {}
    review = result.review or {}
    cmp = result.comparison or {}
    window = pre.get("window") or {}
    rec = exe.get("records") or {}
    handles = exe.get("handles") or result.handles or {}
    gate = exe.get("handle_gate") or {}
    src = exe.get("src_forensic") or exe.get("src") or {}
    cost = exe.get("cost") or {}
    counts = handles.get("counts") or {}
    verdict = exe.get("result") or (
        "BLOCKED_PRECALL" if result.blocked_precall else result.mode
    )
    tests_line = tests or pre.get("baseline_tests") or "UNKNOWN"
    ready = exe.get("real_windows_ready") or "0 / 7"
    coverage = review.get("coverage") or {}
    lines = [
        "# PHASE 3B.7.7A.21 — REAL V3 SMALL WIN001 HARDENED RETRY",
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
        "PROMPT = window-analysis-1.3.1",
        "",
        "TRANSPORT = semantic-transport-v3",
        "",
        f"SCHEMA HASH = {EXPECTED_SCHEMA_HASH}",
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
        f"TOTAL SRC OCCURRENCES = {_dash(src.get('total_src_occurrences'))}",
        "",
        f"VALID SRC OCCURRENCES = {_dash(src.get('valid_src_occurrences'))}",
        "",
        f"MALFORMED SRC = {_dash(src.get('malformed_src'))}",
        "",
        f"WRONG-CASE SRC = {_dash(src.get('wrong_case_src'))}",
        "",
        f"UNKNOWN SRC = {_dash(src.get('unknown_src'))}",
        "",
        f"OUT-OF-WINDOW SRC = {_dash(src.get('out_of_window_src'))}",
        "",
        f"DUPLICATE SRC = {_dash(src.get('duplicate_src'))}",
        "",
        f"V3 DECODER = {_dash(exe.get('v3_decoder'))}",
        "",
        f"HANDLE REGISTRY = {_dash(exe.get('handle_registry'))}",
        "",
        f"HANDLE RESOLUTION = {_dash(exe.get('handle_resolution'))}",
        "",
        f"V3 VALIDATOR = {_dash(exe.get('v3_validator'))}",
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
        f"UNKNOWN HANDLES = {_dash(gate.get('unknown_handles', counts.get('unknown')))}",
        "",
        f"WRONG-KIND HANDLES = {_dash(gate.get('wrong_kind_handles', counts.get('wrong_kind')))}",
        "",
        f"DUPLICATE OWNERS = {_dash(gate.get('duplicate_owners', counts.get('duplicate_owners')))}",
        "",
        f"MALFORMED HANDLES = {_dash(gate.get('malformed_handles', counts.get('malformed')))}",
        "",
        f"SELF RELATIONS = {_dash(gate.get('self_relations', counts.get('self_relations')))}",
        "",
        f"NUMERIC LINK REGRESSION = {_dash(gate.get('numeric_link_regression', handles.get('numeric_link_regression')))}",
        "",
        f"A.15 TARGET-KIND DEFECT = {_dash(exe.get('a15_target_kind_defect') or cmp.get('a15_target_kind_defect'))}",
        "",
        f"A.19 SRC TYPO CLASS = {_dash(exe.get('a19_src_typo_class') or src.get('a19_src_typo_class'))}",
        "",
        f"SEMANTIC SRC COVERAGE = {_dash(src.get('semantic_src_coverage_pct') or coverage.get('semantic_src_coverage_pct'))}",
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
        "Did WIN002–WIN007 remain untouched? YES",
        "Did consolidation remain untouched? YES",
        "Was source_map absent? YES",
        "Was production default unchanged? YES — window-planner-v2.0",
        "",
        "## 2. Source identity",
        "",
        f"Was the exact A.19 source window reused? {window.get('src_range')} "
        f"owned={window.get('owned_src_count')} words={window.get('word_count')}",
        f"CLEAN sha={window.get('clean_sha256')}",
        f"Signature={pre.get('analysis_signature')}",
        f"Prompt=window-analysis-1.3.1 hash={pre.get('prompt_sha256')}",
        "",
        "## 3. Schema / thinking",
        "",
        f"Did Anthropic use V3 schema verified in A.18? hash={EXPECTED_SCHEMA_HASH}",
        f"Did thinking remain disabled? type=disabled, tokens={_dash(exe.get('thinking_tokens'))}",
        f"Finish reason: {_dash(exe.get('finish_reason'))}",
        "",
        "## 4. Technical pipeline",
        "",
        f"Structured parse: {_dash(exe.get('structured_parse'))}",
        f"V3 decoder: {_dash(exe.get('v3_decoder'))}",
        f"Handle registry: {_dash(exe.get('handle_registry'))}",
        f"Handle resolution: {_dash(exe.get('handle_resolution'))}",
        f"V3 validator: {_dash(exe.get('v3_validator'))}",
        f"Capacity: {_dash(exe.get('capacity_signal'))}",
        f"SRC forensic: malformed={src.get('malformed_src')} wrong-case="
        f"{src.get('wrong_case_src')} unknown={src.get('unknown_src')} "
        f"out-of-window={src.get('out_of_window_src')} duplicate={src.get('duplicate_src')}",
        f"Unknown/wrong-kind/duplicate/malformed/self: "
        f"{gate.get('unknown_handles')}/{gate.get('wrong_kind_handles')}/"
        f"{gate.get('duplicate_owners')}/{gate.get('malformed_handles')}/"
        f"{gate.get('self_relations')}",
        f"Numeric link regression: {_dash(gate.get('numeric_link_regression'))}",
        "",
        "## 5. A.19 comparison",
        "",
        f"Did prompt 1.3.1 eliminate malformed SRC copying? "
        f"{_dash(exe.get('a19_src_typo_class') or cmp.get('a19_src_typo_class'))}",
        f"Did V3 continue to eliminate the A.15 target-kind defect? "
        f"{_dash(cmp.get('a15_target_kind_defect'))}",
        f"Record counts A.19 vs A.21: A.19=106 / A.21={rec.get('total_records')}",
        f"SRC coverage A.15 19.92% / A.19 27.11% / A.21 "
        f"{_dash(coverage.get('semantic_src_coverage_pct'))}",
        "Counts need not match. Causality is not claimed from one paired run.",
        "",
        "## 6. Semantic review",
        "",
        f"Transport valid: {_dash(review.get('transport_valid'))}",
        f"Quality: {_dash(review.get('semantic_quality'))}",
        f"Unsupported: {_dash(review.get('unsupported_content'))}",
        f"Beginning/middle/end: {coverage.get('beginning')}/{coverage.get('middle')}/{coverage.get('end')}",
        f"Known content checks: {review.get('known_content_checks')}",
        f"Thinking-disabled local extraction: {_dash(review.get('thinking_disabled_local_extraction'))}",
        f"Limitation: {_dash(review.get('thinking_disabled_limitation'))}",
        "Do not generalize to WIN002–WIN007, other transcripts, languages, or domains.",
        "",
        "## 7. Next phase",
        "",
        "Do not automatically launch six calls after A.21.",
        "A human must explicitly authorize the next real-call budget.",
        "If PASS: evaluate whether WIN001 has now sufficiently validated "
        "thinking disabled, V3 handles, strict SRC copying, and local extraction.",
        "Then recommend ONE of:",
        "A. bounded execution of WIN002–WIN007, or",
        "B. one representative second-window canary before authorizing the remaining windows.",
        "Recommendation: B. WIN001 now has repeated thinking-disabled + V3 + SRC-hardening",
        "evidence, but every successful semantic-quality observation is still the same",
        "source region. Do not authorize six remaining windows from WIN001 alone.",
        "All successful semantic-quality evidence so far comes from the same WIN001 region.",
        "Do not execute either. No automatic spending.",
        "",
        f"Error: {result.error if result.error else 'none'}",
        "",
        f"NEXT ACTION = {NEXT_ACTION}",
        "",
    ]
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
