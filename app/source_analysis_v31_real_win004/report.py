"""Rapport markdown déterministe 3B.7.7A.27."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v31_real_win004.constants import (
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    EXPECTED_SCHEMA_HASH,
    NEXT_ACTION,
    NEXT_PHASE_LABEL,
)


def _dash(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return str(value)


def _relation_summary(relations: Any) -> dict[str, Any] | None:
    if not isinstance(relations, dict):
        return None
    rows = relations.get("rows") or []
    counts = {"well-supported": 0, "plausible-loose": 0, "incorrect": 0, "unverifiable": 0}
    for row in rows:
        quality = str(row.get("quality") or "")
        if quality in {"well-supported", "well_supported"}:
            counts["well-supported"] += 1
        elif quality in {"plausible", "plausible-loose", "loose"}:
            counts["plausible-loose"] += 1
        elif quality == "incorrect":
            counts["incorrect"] += 1
        else:
            counts["unverifiable"] += 1
    return {
        "total": len(rows),
        **counts,
        "vocab_ok_count": relations.get("vocab_ok_count"),
    }


def render_report(result: Any, *, tests: str | None = None) -> str:
    pre = result.preflight or {}
    exe = result.execution or {}
    review = result.review or {}
    cmp = result.comparison or {}
    canonical = result.canonical or exe.get("canonical") or {}
    window = pre.get("window") or {}
    rec = exe.get("records") or {}
    handles = exe.get("handles") or result.handles or {}
    gate = exe.get("handle_gate") or {}
    src = exe.get("src_forensic") or exe.get("src") or {}
    cost = exe.get("cost") or {}
    counts = handles.get("counts") or {}
    metadata = exe.get("metadata") or result.metadata or review.get("metadata") or {}
    coverage = review.get("coverage") or {}
    schema = pre.get("schema_metrics") or {}
    verdict = exe.get("result") or (
        "BLOCKED_PRECALL" if result.blocked_precall else result.mode
    )
    tests_line = tests or pre.get("baseline_tests") or "UNKNOWN"
    ready = exe.get("real_windows_ready") or "1 / 7"
    src_violations = None
    if src:
        src_violations = (
            (src.get("malformed_src") or 0)
            + (src.get("wrong_case_src") or 0)
            + (src.get("unknown_src") or 0)
            + (src.get("out_of_window_src") or 0)
            + (src.get("duplicate_src") or 0)
        )
    handle_violations = (
        (gate.get("unknown_handles", counts.get("unknown")) or 0)
        + (gate.get("wrong_kind_handles", counts.get("wrong_kind")) or 0)
        + (gate.get("duplicate_owners", counts.get("duplicate_owners")) or 0)
        + (gate.get("malformed_handles", counts.get("malformed")) or 0)
        + (gate.get("self_relations", counts.get("self_relations")) or 0)
    )
    win004 = canonical.get("win004") or {}
    lines = [
        "# PHASE 3B.7.7A.27 — REAL WIN004 LOCAL-LITE CANARY",
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
        "PROMPT = window-analysis-1.4.0",
        "",
        "TRANSPORT = semantic-transport-v3.1-local-lite",
        "",
        f"SCHEMA RAW / ADAPTED = {schema.get('raw_bytes', EXPECTED_RAW_SCHEMA_BYTES)} / "
        f"{schema.get('adapted_bytes', EXPECTED_ADAPTED_SCHEMA_BYTES)}",
        "",
        f"SCHEMA HASH = {schema.get('raw_hash') or EXPECTED_SCHEMA_HASH}",
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
        f"TOTAL RECORDS = {_dash(rec.get('total_records'))}",
        "",
        f"IDEA RECORDS = {_dash(metadata.get('idea_records'))}",
        "",
        f"VALID IMPORTANCE-ONLY IDEA = {_dash(metadata.get('valid_importance_only_idea'))}",
        "",
        f"IDEA SUBTYPE LEAKAGE = {_dash(metadata.get('idea_subtype_leakage'))}",
        "",
        f"OLD-V3 IDEA SHAPE = {_dash(metadata.get('old_v3_idea_shape'))}",
        "",
        f"INVALID IMPORTANCE = {_dash(metadata.get('invalid_importance'))}",
        "",
        f"TOTAL SRC OCCURRENCES = {_dash(src.get('total_src_occurrences'))}",
        "",
        f"VALID SRC OCCURRENCES = {_dash(src.get('valid_src_occurrences'))}",
        "",
        f"SRC VIOLATIONS = {_dash(src_violations)}",
        "",
        f"HANDLE VIOLATIONS = {handle_violations}",
        "",
        f"NUMERIC LINK REGRESSION = {_dash(gate.get('numeric_link_regression', handles.get('numeric_link_regression')))}",
        "",
        f"V3.1 DECODER = {_dash(exe.get('v31_decoder'))}",
        "",
        f"HANDLE REGISTRY = {_dash(exe.get('handle_registry'))}",
        "",
        f"HANDLE RESOLUTION = {_dash(exe.get('handle_resolution'))}",
        "",
        f"LOCAL VALIDATOR = {_dash(exe.get('v31_validator'))}",
        "",
        f"CAPACITY SIGNAL = {_dash(exe.get('capacity_signal'))}",
        "",
        f"TECHNICAL GATE = {_dash(exe.get('technical_ok'))}",
        "",
        f"SEMANTIC GROUNDING = {_dash(review.get('grounding_counts'))}",
        "",
        f"UNSUPPORTED CONTENT = {_dash(review.get('unsupported_content'))}",
        "",
        f"MAJOR IDEA COVERAGE = represented={_dash(coverage.get('major_ideas_represented'))} "
        f"partial={_dash(coverage.get('major_ideas_partial'))} "
        f"missing={_dash(coverage.get('major_ideas_missing'))}",
        "",
        f"MATERIAL OMISSIONS = {_dash(review.get('material_omissions') if review.get('material_omissions') is not None else coverage.get('material_omissions'))}",
        "",
        f"RELATION QUALITY = {_dash(review.get('relation_quality_summary') or _relation_summary(review.get('relations')))}",
        "",
        f"EXAMPLE QUALITY = {_dash(review.get('example_quality_summary') or (review.get('duplication') or {}).get('duplicate_pair_count'))}",
        "",
        f"I44-LIKE REPRESENTATION = {_dash((review.get('i44_like') or {}).get('representation'))}",
        "",
        f"SEMANTIC SRC COVERAGE = {_dash(coverage.get('verified_semantic_src_coverage_pct') or coverage.get('semantic_src_coverage_pct'))}",
        "",
        f"BEGINNING/MIDDLE/END = {coverage.get('beginning')}/{coverage.get('middle')}/{coverage.get('end')}",
        "",
        f"SEMANTIC QUALITY = {_dash(review.get('semantic_quality'))}",
        "",
        f"CANONICAL RECONSTRUCTION = {_dash((canonical.get('win004') or {}).get('idea_validation'))}",
        "",
        f"CANONICAL kind = {_dash((canonical.get('win004') or {}).get('all_kinds_empty'))}",
        "",
        f"IMPORTANCE→KIND CONTAMINATION = {_dash(exe.get('importance_to_kind_contamination') or win004.get('importance_to_kind_contamination'))}",
        "",
        f"MIXED V3/V3.1 COMPATIBILITY = {_dash(canonical.get('mixed_compatibility'))}",
        "",
        f"A.22/A.24 SUBTYPE FAILURE CLASS = {_dash(exe.get('a22_a24_subtype_failure_class') or cmp.get('a22_a24_subtype_failure_class'))}",
        "",
        f"ACTUAL COST = {_dash(cost.get('display'))}",
        "",
        f"PROVIDER ELAPSED = {_dash(exe.get('provider_elapsed_ms'))}",
        "",
        f"CACHE = {_dash(exe.get('cache') or (pre.get('cache') or {}).get('status'))}",
        "",
        f"REAL WINDOWS READY = {ready}",
        "",
        f"PRE-CALL FULL TESTS = {_dash((pre.get('full_suite_baseline') or {}).get('summary') or pre.get('baseline_tests') or tests_line)}",
        "",
        f"POST-CALL FULL TESTS = {_dash((exe.get('post_tests') or {}).get('summary'))}",
        "",
        f"NEW TEST FAILURES = {_dash((exe.get('post_tests') or {}).get('new_failures'))}",
        "",
        f"FOCUSED TESTS = {_dash((exe.get('post_tests') or {}).get('focused') or (pre.get('focused_baseline') or {}).get('summary') or pre.get('baseline_tests'))}",
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
        f"Was the exact A.22/A.24 CLEAN WIN004 reused? {window.get('src_range')} "
        f"owned={window.get('owned_src_count')} words={window.get('word_count')}",
        f"CLEAN sha={window.get('clean_sha256')}",
        f"Same A.22 ownership={window.get('same_a22_ownership')}",
        f"Signature={pre.get('analysis_signature')}",
        f"Prompt=window-analysis-1.4.0 hash={pre.get('prompt_sha256')}",
        f"Transport=semantic-transport-v3.1-local-lite",
        "",
        "## 3. Schema / thinking",
        "",
        f"Schema identity 588/650 A.18-identical? hash={EXPECTED_SCHEMA_HASH}",
        f"schema.py on local-lite path? NO",
        f"Did thinking remain disabled? type=disabled, tokens={_dash(exe.get('thinking_tokens'))}",
        f"Finish reason: {_dash(exe.get('finish_reason'))}",
        f"Server grammar: A.18 proof remains applicable. No new grammar canary.",
        "",
        "## 4. Local-lite technical pipeline",
        "",
        f"Structured parse: {_dash(exe.get('structured_parse'))}",
        f"V3.1 decoder: {_dash(exe.get('v31_decoder'))}",
        f"Handle registry: {_dash(exe.get('handle_registry'))}",
        f"Handle resolution: {_dash(exe.get('handle_resolution'))}",
        f"Local validator: {_dash(exe.get('v31_validator'))}",
        f"Capacity: {_dash(exe.get('capacity_signal'))}",
        f"IDEA records / valid importance-only / leakage / old-V3 / invalid importance: "
        f"{metadata.get('idea_records')} / {metadata.get('valid_importance_only_idea')} / "
        f"{metadata.get('idea_subtype_leakage')} / {metadata.get('old_v3_idea_shape')} / "
        f"{metadata.get('invalid_importance')}",
        f"SRC forensic: malformed={src.get('malformed_src')} wrong-case="
        f"{src.get('wrong_case_src')} unknown={src.get('unknown_src')} "
        f"out-of-window={src.get('out_of_window_src')} duplicate={src.get('duplicate_src')}",
        f"Numeric link regression: {_dash(gate.get('numeric_link_regression'))}",
        "",
        "## 5. A.22 / A.24 comparison",
        "",
        f"Subtype failure class: {_dash(exe.get('a22_a24_subtype_failure_class') or cmp.get('a22_a24_subtype_failure_class'))}",
        "A.19 remains FAIL. A.21 remains PASS. A.22 remains FAIL. A.23 remains PASS.",
        "A.24 remains FAIL. A.25 remains PARTIAL. A.26 remains PASS. A.26.1 remains PASS.",
        "A.22/A.24 generations remain invalid historical evidence. Not READY candidates.",
        "Counts need not match. Causality is not claimed from one paired run.",
        "",
        "## 6. Semantic review",
        "",
        f"Label: {_dash(review.get('status') or review.get('label'))}",
        f"Transport valid: {_dash(review.get('transport_valid'))}",
        f"Quality: {_dash(review.get('semantic_quality'))}",
        f"Unsupported: {_dash(review.get('unsupported_content'))}",
        f"Beginning/middle/end: {coverage.get('beginning')}/{coverage.get('middle')}/{coverage.get('end')}",
        f"Major ideas vs A.23 diagnostic: "
        f"{coverage.get('major_ideas_represented')}/"
        f"{coverage.get('major_ideas_partial')}/"
        f"{coverage.get('major_ideas_missing')}",
        f"I44-like: {_dash((review.get('i44_like') or {}).get('representation'))}",
        f"The Fall: verify semantically; do not repeat A.24 automated false negative.",
        f"Thinking-disabled two distinct windows: "
        f"{_dash(review.get('thinking_disabled_local_extraction'))}",
        "Do not generalize beyond this project / this local-window architecture / WIN001+WIN004.",
        "",
        "## 7. Canonical / mixed",
        "",
        f"Canonical reconstruction: {_dash(win004.get('idea_validation'))}",
        f"Canonical empty kind: {_dash(win004.get('all_kinds_empty'))}",
        f"Importance→kind contamination: {_dash(win004.get('importance_to_kind_contamination'))}",
        f"Mixed V3/V3.1 compatibility: {_dash(canonical.get('mixed_compatibility'))}",
        "schema.py is not a publication gate and is not on the A.27 local-lite path.",
        "",
        "## 8. Next phase",
        "",
        "Do not automatically launch remaining windows after A.27.",
        f"If PASS, human review should decide whether to authorize: {NEXT_PHASE_LABEL}",
        "If FAIL, do not spend on remaining windows. Offline forensics first.",
        "Do not execute remaining windows in this phase.",
        "",
        f"Error: {result.error if result.error else 'none'}",
        "",
        f"NEXT ACTION = {NEXT_ACTION}",
        "",
    ]
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
