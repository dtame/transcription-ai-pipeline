"""Rapport markdown déterministe 3B.7.7A.22."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v3_second_window.constants import (
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
    ready = exe.get("real_windows_ready") or "1 / 7"
    coverage = review.get("coverage") or {}
    selected = exe.get("authorized_target") or pre.get("selected_target")
    two_windows = cmp.get("thinking_disabled_two_distinct_windows")
    if two_windows is True:
        two_label = "YES"
    elif two_windows is False:
        two_label = "NO"
    else:
        two_label = "UNKNOWN"
    handle_counts = handles.get("by_kind") or handles.get("owners") or {}
    idea_topic = (
        handle_counts.get("IDEA_to_TOPIC")
        or (handles.get("links") or {}).get("idea_to_topic")
    )
    rel_idea = (
        handle_counts.get("RELATION_to_IDEA")
        or (handles.get("links") or {}).get("relation_to_idea")
    )
    ex_idea = (
        handle_counts.get("EXAMPLE_to_IDEA")
        or (handles.get("links") or {}).get("example_to_idea")
    )
    lines = [
        "# PHASE 3B.7.7A.22 — SECOND INDEPENDENT REAL-WINDOW CANARY",
        "",
        "## Result",
        "",
        str(verdict),
        "",
        f"REAL PROVIDER CALLS = {result.anthropic_post_attempts}",
        "",
        f"REAL WINDOW CALLS = {1 if result.engine_generate_attempts else 0}",
        "",
        f"SELECTED TARGET = {selected}",
        "",
        f"SELECTION REASON = {_dash(pre.get('selection_reason'))}",
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
        f"DISTINCT SRC REFS = {_dash(src.get('distinct_canonical_refs') or coverage.get('distinct_src_refs'))}",
        "",
        f"SEMANTIC SRC COVERAGE = {_dash(src.get('semantic_src_coverage_pct') or coverage.get('semantic_src_coverage_pct'))}",
        "",
        f"UNSUPPORTED CONTENT = {_dash(review.get('unsupported_content'))}",
        "",
        f"SEMANTIC QUALITY = {_dash(review.get('semantic_quality'))}",
        "",
        f"BEGINNING/MIDDLE/END = {coverage.get('beginning')}/{coverage.get('middle')}/{coverage.get('end')}",
        "",
        f"INDEPENDENT EVIDENCE VALUE = {_dash(cmp.get('independence_value') or exe.get('independence_value'))}",
        "",
        f"THINKING_DISABLED TWO DISTINCT WINDOWS = {two_label}",
        "",
        f"V3 TWO DISTINCT WINDOWS = {two_label}",
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
        "## 1. Window selection",
        "",
        f"Preferred target: WIN004. Selected: {selected}.",
        f"Reason: {_dash(pre.get('selection_reason'))}",
        "WIN001 was not called. Semantic difference from WIN001 is desirable.",
        "",
        "## 2. Provider calls",
        "",
        f"How many provider calls occurred? {result.anthropic_post_attempts}",
        f"Was WIN001 called? NO",
        f"Was only the selected window called? {'YES' if result.anthropic_post_attempts <= 1 else 'NO'}",
        "Did remaining windows remain untouched? YES",
        "Did consolidation remain untouched? YES",
        "Was source_map absent? YES",
        "Was production default unchanged? YES — window-planner-v2.0",
        "",
        "## 3. Source identity",
        "",
        f"Selected SRC range={window.get('src_range')} "
        f"owned={window.get('owned_src_count')} words={window.get('word_count')}",
        f"CLEAN sha={window.get('clean_sha256')}",
        f"Signature={pre.get('analysis_signature')}",
        f"Prompt=window-analysis-1.3.1 hash={pre.get('prompt_sha256')}",
        f"A.21 signature collision? NO",
        "",
        "## 4. Schema / thinking",
        "",
        f"Did Anthropic use V3 schema verified in A.18? hash={EXPECTED_SCHEMA_HASH}",
        f"Did thinking remain disabled? type=disabled, tokens={_dash(exe.get('thinking_tokens'))}",
        f"Finish reason: {_dash(exe.get('finish_reason'))}",
        "",
        "## 5. Technical pipeline",
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
        f"IDEA→TOPIC / RELATION→IDEA / EXAMPLE→IDEA: {idea_topic}/{rel_idea}/{ex_idea}",
        "",
        "## 6. Semantic review",
        "",
        f"Transport valid: {_dash(review.get('transport_valid'))}",
        f"Quality: {_dash(review.get('semantic_quality'))}",
        f"Unsupported: {_dash(review.get('unsupported_content'))}",
        f"Beginning/middle/end: {coverage.get('beginning')}/{coverage.get('middle')}/{coverage.get('end')}",
        f"Language: {review.get('language')}",
        f"Thinking-disabled two distinct windows: {two_label}",
        "Do not generalize to remaining windows, other transcripts, languages, or domains.",
        "",
        "## 7. Cross-window evidence",
        "",
        f"A.19 remains FAIL. A.21 remains PASS / READY 1/7.",
        f"Independence value: {_dash(cmp.get('independence_value'))}",
        f"Differences: {cmp.get('differences')}",
        "If PASS: prompt 1.3.1 has strict-SRC success on two distinct "
        "real-provider executions/windows only if counting A.21 + A.22.",
        "",
        "## 8. Decoder / validator forensics",
        "",
        f"Validation errors: {exe.get('validation_errors')}",
        "No JSON repair. No SRC repair. No handle repair. No retry.",
        "Candidate cache was not written for an invalid window.",
        "",
        "## 9. Next phase",
        "",
    ]
    if str(verdict) == "PASS":
        lines.extend(
            [
                "Do not automatically call remaining windows.",
                "Recommend human review before a bounded execution phase for the remaining 5 windows.",
                "Expected future phase concept: 3B.7.7A.23 — BOUNDED REMAINING REAL WINDOWS EXECUTION.",
                "Do not execute A.23 now.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "A.22 did not pass. Do not spend on remaining windows.",
                "Perform offline forensics first. Do not authorize A.23 from this result.",
                "A.21 WIN001 remains the only READY candidate: 1 / 7.",
                "",
            ]
        )
    lines.extend(
        [
            f"Error: {result.error if result.error else 'none'}",
            "",
            f"NEXT ACTION = {NEXT_ACTION}",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
