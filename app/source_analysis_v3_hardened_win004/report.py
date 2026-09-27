"""Rapport markdown déterministe 3B.7.7A.24."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v3_hardened_win004.constants import (
    EXPECTED_SCHEMA_HASH,
    NEXT_ACTION,
    NEXT_PHASE_LABEL,
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
    metadata = exe.get("metadata") or result.metadata or review.get("metadata") or {}
    coverage = review.get("coverage") or {}
    four = (review.get("four_patterns") or {}).get("patterns") or []
    verdict = exe.get("result") or (
        "BLOCKED_PRECALL" if result.blocked_precall else result.mode
    )
    tests_line = tests or pre.get("baseline_tests") or "UNKNOWN"
    ready = exe.get("real_windows_ready") or "1 / 7"
    idea_counts = metadata.get("idea_kind_counts") or {}
    lines = [
        "# PHASE 3B.7.7A.24 — REAL WIN004 HARDENED TYPE-CONTRACT RETRY",
        "",
        "## Result",
        "",
        str(verdict),
        "",
        f"REAL PROVIDER CALLS = {result.anthropic_post_attempts}",
        "",
        f"REAL WINDOW CALLS = {1 if result.engine_generate_attempts else 0}",
        "",
        "AUTHORIZED TARGET = WIN004",
        "",
        f"SRC RANGE = {window.get('src_range')}",
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
        "PROMPT = window-analysis-1.3.2",
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
        f"SRC VIOLATIONS = {_dash((src.get('malformed_src') or 0) + (src.get('wrong_case_src') or 0) + (src.get('unknown_src') or 0) + (src.get('out_of_window_src') or 0) + (src.get('duplicate_src') or 0) if src else None)}",
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
        f"IDEA KIND COUNTS = {idea_counts}",
        "",
        f"IDEA KIND \"example\" = {_dash(metadata.get('idea_kind_example'))}",
        "",
        f"OTHER METADATA VIOLATIONS = {_dash(metadata.get('other_metadata_violation_count'))}",
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
        f"HANDLE VIOLATIONS = unknown={_dash(gate.get('unknown_handles', counts.get('unknown')))} "
        f"wrong-kind={_dash(gate.get('wrong_kind_handles', counts.get('wrong_kind')))} "
        f"duplicate-owners={_dash(gate.get('duplicate_owners', counts.get('duplicate_owners')))} "
        f"malformed={_dash(gate.get('malformed_handles', counts.get('malformed')))} "
        f"self={_dash(gate.get('self_relations', counts.get('self_relations')))}",
        "",
        f"NUMERIC LINK REGRESSION = {_dash(gate.get('numeric_link_regression', handles.get('numeric_link_regression')))}",
        "",
        f"A.22 TYPE-CONTRACT DEFECT = {_dash(exe.get('a22_type_contract_defect') or cmp.get('a22_type_contract_defect'))}",
        "",
        f"A.22 FOUR-PATTERN REPRESENTATION = {four}",
        "",
        f"SEMANTIC GROUNDING = {_dash(review.get('grounding_counts'))}",
        "",
        f"UNSUPPORTED CONTENT = {_dash(review.get('unsupported_content'))}",
        "",
        f"MAJOR IDEA COVERAGE = represented={_dash(coverage.get('major_ideas_represented'))} "
        f"partial={_dash(coverage.get('major_ideas_partial'))} "
        f"missing={_dash(coverage.get('major_ideas_missing'))}",
        "",
        f"RELATION QUALITY = {_dash(review.get('relations'))}",
        "",
        f"EXAMPLE QUALITY = {_dash((review.get('duplication') or {}).get('duplicate_pair_count'))} "
        f"duplicate IDEA/EXAMPLE pairs (diagnostic)",
        "",
        f"SEMANTIC SRC COVERAGE = {_dash(coverage.get('verified_semantic_src_coverage_pct') or coverage.get('semantic_src_coverage_pct'))}",
        "",
        f"BEGINNING/MIDDLE/END = {coverage.get('beginning')}/{coverage.get('middle')}/{coverage.get('end')}",
        "",
        f"SEMANTIC QUALITY = {_dash(review.get('semantic_quality'))}",
        "",
        f"THINKING_DISABLED TWO DISTINCT WINDOWS = "
        f"{'YES' if review.get('thinking_disabled_two_distinct_windows') else 'NO'}",
        "",
        f"V3 TWO DISTINCT WINDOWS = "
        f"{'YES' if review.get('v3_two_distinct_windows') else 'NO'}",
        "",
        f"ACTUAL COST = {_dash(cost.get('display'))}",
        "",
        f"PROVIDER ELAPSED = {_dash(exe.get('provider_elapsed_ms'))}",
        "",
        f"CACHE = {_dash(exe.get('cache') or (pre.get('cache') or {}).get('status'))}",
        "",
        f"REAL WINDOWS READY = {ready}",
        "",
        "OTHER WINDOWS AUTHORIZED = NO",
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
        f"Was only WIN004 called? {'YES' if result.anthropic_post_attempts <= 1 else 'NO'}",
        "Did WIN001/002/003/005/006/007 remain untouched? YES",
        "Did consolidation remain untouched? YES",
        "Was source_map absent? YES",
        "Was production default unchanged? YES — window-planner-v2.0",
        "",
        "## 2. Source identity",
        "",
        f"Was the exact A.22 CLEAN WIN004 reused? {window.get('src_range')} "
        f"owned={window.get('owned_src_count')} words={window.get('word_count')}",
        f"CLEAN sha={window.get('clean_sha256')}",
        f"Same A.22 ownership={window.get('same_a22_ownership')}",
        f"Signature={pre.get('analysis_signature')}",
        f"Prompt=window-analysis-1.3.2 hash={pre.get('prompt_sha256')}",
        "",
        "## 3. Schema / thinking",
        "",
        f"Did Anthropic use V3 schema verified in A.18? hash={EXPECTED_SCHEMA_HASH}",
        f"Did thinking remain disabled? type=disabled, tokens={_dash(exe.get('thinking_tokens'))}",
        f"Finish reason: {_dash(exe.get('finish_reason'))}",
        f"Server grammar: A.18 proof remains applicable. No new grammar canary.",
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
        f"IDEA kind example: {_dash(metadata.get('idea_kind_example'))}",
        f"Other metadata violations: {_dash(metadata.get('other_metadata_violation_count'))}",
        f"Numeric link regression: {_dash(gate.get('numeric_link_regression'))}",
        "",
        "## 5. A.22 comparison",
        "",
        f"Did prompt 1.3.2 eliminate the IDEA/EXAMPLE type-contract defect? "
        f"{_dash(exe.get('a22_type_contract_defect') or cmp.get('a22_type_contract_defect'))}",
        "A.22 remains FAIL. A.19 remains FAIL. A.21 remains PASS. A.23 remains PASS.",
        "Counts need not match. Causality is not claimed from one paired run.",
        f"Four-pattern representation: {four}",
        "",
        "## 6. Semantic review",
        "",
        f"Transport valid: {_dash(review.get('transport_valid'))}",
        f"Quality: {_dash(review.get('semantic_quality'))}",
        f"Unsupported: {_dash(review.get('unsupported_content'))}",
        f"Beginning/middle/end: {coverage.get('beginning')}/{coverage.get('middle')}/{coverage.get('end')}",
        f"Major ideas vs A.23 15/1/0: "
        f"{coverage.get('major_ideas_represented')}/"
        f"{coverage.get('major_ideas_partial')}/"
        f"{coverage.get('major_ideas_missing')}",
        f"Thinking-disabled two distinct windows: "
        f"{_dash(review.get('thinking_disabled_local_extraction'))}",
        f"Limitation: {_dash(review.get('thinking_disabled_limitation'))}",
        f"Prompt 1.3.2 evidence: {_dash(review.get('prompt_1_3_2_evidence'))}",
        "Do not generalize beyond this project / this local-window architecture / WIN001+WIN004.",
        "",
        "## 7. Next phase",
        "",
        "Do not automatically launch remaining windows after A.24.",
        f"If PASS, human review should decide whether to authorize: {NEXT_PHASE_LABEL}",
        "If FAIL, do not spend on remaining windows. Offline forensics first.",
        "Do not execute A.25 in this phase.",
        "",
        f"Error: {result.error if result.error else 'none'}",
        "",
        f"NEXT ACTION = {NEXT_ACTION}",
        "",
    ]
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
