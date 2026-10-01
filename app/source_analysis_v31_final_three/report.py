"""Rapport markdown déterministe 3B.7.7A.31."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v31_final_three.constants import (
    EXECUTION_ORDER,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    EXPECTED_SCHEMA_HASH,
    GRANULARITY_POLICY,
    NEXT_ACTION,
    NEXT_PHASE_LABEL,
    READY_BEFORE,
    RELATION_QUALITY_TECHNICAL_DEBT,
)
from app.source_analysis_v31_final_three.relations import build_relation_cross


def _dash(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return str(value)


def _window_status(result: Any, window_id: str) -> str:
    item = (result.windows or {}).get(window_id)
    if not item:
        return "NOT_RUN"
    return str(item.get("result") or (item.get("execution") or {}).get("result") or "NOT_RUN")


def _sum_int(result: Any, *keys: str) -> int:
    total = 0
    for item in (result.windows or {}).values():
        execution = item.get("execution") or {}
        cursor: Any = execution
        for key in keys:
            if not isinstance(cursor, dict):
                cursor = 0
                break
            cursor = cursor.get(key)
        total += int(cursor or 0)
    return total


def _table(result: Any) -> list[str]:
    lines = [
        "| Window | SRC range | Owned SRC | Words | Local estimate | Provider input | Output | Records | Ideas | Max theme | Max IDEA | Max EXAMPLE | SRC coverage | Semantic quality | Relations W/P/I/U | Cost | Elapsed | Technical | Canonical | READY |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for window_id in EXECUTION_ORDER:
        item = (result.windows or {}).get(window_id) or {}
        exe = item.get("execution") or {}
        pre = ((result.preflight or {}).get("windows") or {}).get(window_id) or {}
        rec = exe.get("records") or {}
        src = exe.get("src") or exe.get("src_forensic") or {}
        rel = exe.get("relation_quality_summary") or {}
        cost = (exe.get("cost") or {}).get("display")
        ready = "YES" if exe.get("ready") else "NO"
        if not item:
            lines.append(
                f"| {window_id} | {pre.get('src_range', '')} | {pre.get('owned_src_count', '')} | "
                f"{pre.get('word_count', '')} | {pre.get('local_input_estimate', '')} | "
                "NOT_RUN | NOT_RUN |  |  |  |  |  |  |  |  |  |  |  |  | NO |"
            )
            continue
        rel_cell = (
            f"{rel.get('well-supported', 0)}/{rel.get('plausible-loose', 0)}/"
            f"{rel.get('incorrect', 0)}/{rel.get('unverifiable', 0)}"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    window_id,
                    str(exe.get("src_range") or pre.get("src_range") or ""),
                    str(exe.get("owned_src_count") or pre.get("owned_src_count") or ""),
                    str(exe.get("word_count") or pre.get("word_count") or ""),
                    str(exe.get("local_input_estimate") or pre.get("local_input_estimate") or ""),
                    _dash(exe.get("actual_provider_input") or exe.get("input_tokens")),
                    _dash(exe.get("output_tokens")),
                    _dash(rec.get("total_records")),
                    _dash((exe.get("metadata") or {}).get("idea_records")),
                    _dash(exe.get("max_theme_length")),
                    _dash(exe.get("max_idea_length")),
                    _dash(exe.get("max_example_length")),
                    _dash(src.get("semantic_src_coverage_pct")),
                    _dash(exe.get("semantic_quality")),
                    rel_cell,
                    _dash(cost),
                    _dash(exe.get("provider_elapsed_ms")),
                    _dash(exe.get("technical_ok")),
                    _dash((exe.get("canonical") or {}).get("mixed_compatibility")
                          or ((item.get("canonical") or {}).get("local") or {}).get("idea_validation")),
                    ready,
                ]
            )
            + " |"
        )
    return lines


def render_report(result: Any, *, tests: str | None = None) -> str:
    pre = result.preflight or {}
    schema = pre.get("schema_metrics") or {}
    cross = result.relation_cross or build_relation_cross(result)
    new_rel = cross.get("totals_new_a31_windows") or {}
    verdict = result.phase_result or (
        "BLOCKED_PRECALL" if result.blocked_precall else result.mode
    )
    order = "WIN005 → WIN006 → WIN007"
    thinking_total = _sum_int(result, "thinking_tokens")
    leakage_total = _sum_int(result, "idea_subtype_leakage")
    length_violations = 0
    src_violations = 0
    handle_violations = 0
    numeric = "NO"
    unsupported = 0
    omissions = 0
    input_tokens = 0
    output_tokens = 0
    elapsed = 0
    cost_total = 0.0
    cost_unknown = False
    canonical_all = []
    mixed_all = []
    for item in (result.windows or {}).values():
        exe = item.get("execution") or {}
        src = exe.get("src_forensic") or {}
        gate = exe.get("handle_gate") or {}
        counts = (exe.get("handles") or {}).get("counts") or {}
        length = exe.get("length_audit") or item.get("length_audit") or {}
        length_violations += int(length.get("violation_count") or 0)
        src_violations += (
            int(src.get("malformed_src") or 0)
            + int(src.get("wrong_case_src") or 0)
            + int(src.get("unknown_src") or 0)
            + int(src.get("out_of_window_src") or 0)
            + int(src.get("duplicate_src") or 0)
        )
        handle_violations += (
            int(gate.get("unknown_handles", counts.get("unknown")) or 0)
            + int(gate.get("wrong_kind_handles", counts.get("wrong_kind")) or 0)
            + int(gate.get("duplicate_owners", counts.get("duplicate_owners")) or 0)
            + int(gate.get("malformed_handles", counts.get("malformed")) or 0)
            + int(gate.get("self_relations", counts.get("self_relations")) or 0)
        )
        if gate.get("numeric_link_regression") == "YES":
            numeric = "YES"
        unsupported += int(exe.get("unsupported_content") or 0)
        omissions += int(exe.get("material_omissions") or 0)
        input_tokens += int(exe.get("input_tokens") or 0)
        output_tokens += int(exe.get("output_tokens") or 0)
        elapsed += int(exe.get("provider_elapsed_ms") or 0)
        cost = exe.get("cost") or {}
        if cost.get("amount") is None:
            cost_unknown = True
        else:
            cost_total += float(cost.get("amount") or 0.0)
        canonical_all.append(((item.get("canonical") or {}).get("local") or {}).get("idea_validation"))
        mixed_all.append((item.get("canonical") or {}).get("mixed_compatibility"))
    cost_display = "UNKNOWN" if cost_unknown and not cost_total else f"{cost_total:.7f} USD"
    attempted = list(result.windows or {})
    unspent = max(0, 3 - int(result.anthropic_post_attempts or 0))
    successful = sum(
        1 for item in (result.windows or {}).values() if item.get("result") == "PASS"
    )
    failed = sum(
        1 for item in (result.windows or {}).values() if item.get("result") == "FAIL"
    )
    tests_line = tests or pre.get("baseline_tests") or "UNKNOWN"
    delta = result.test_delta or {}
    lines = [
        "# PHASE 3B.7.7A.31 — FINAL THREE REAL LOCAL-LITE WINDOWS",
        "",
        "## Result",
        "",
        str(verdict),
        "",
        "AUTHORIZED MAX CALLS =",
        "3",
        "",
        "ACTUAL PROVIDER CALLS =",
        str(result.anthropic_post_attempts),
        "",
        "ACTUAL WINDOW CALLS =",
        str(result.engine_generate_attempts),
        "",
        "EXECUTION ORDER =",
        order,
        "",
        "STOPPED AT =",
        _dash(result.stopped_at),
        "",
        "STOP REASON =",
        _dash(result.stop_reason),
        "",
        "WIN005 =",
        _window_status(result, "WIN005"),
        "",
        "WIN006 =",
        _window_status(result, "WIN006"),
        "",
        "WIN007 =",
        _window_status(result, "WIN007"),
        "",
        "READY BEFORE =",
        READY_BEFORE,
        "",
        "READY AFTER =",
        f"{result.ready_after_count} / 7",
        "",
        "LOCAL_EXTRACTION_FREEZE_CANDIDATE =",
        result.freeze_candidate,
        "",
        "PROMPT =",
        "window-analysis-1.4.0",
        "",
        "TRANSPORT =",
        "semantic-transport-v3.1-local-lite",
        "",
        "GRANULARITY =",
        GRANULARITY_POLICY,
        "",
        "SCHEMA RAW / ADAPTED =",
        f"{schema.get('raw_bytes', EXPECTED_RAW_SCHEMA_BYTES)} / "
        f"{schema.get('adapted_bytes', EXPECTED_ADAPTED_SCHEMA_BYTES)}",
        "",
        "SCHEMA HASH =",
        str(schema.get("raw_hash") or EXPECTED_SCHEMA_HASH),
        "",
        "THINKING =",
        "disabled",
        "",
        "TOTAL THINKING TOKENS =",
        str(thinking_total),
        "",
        "LENGTH POLICY VIOLATIONS =",
        str(length_violations),
        "",
        "IDEA SUBTYPE LEAKAGE =",
        str(leakage_total),
        "",
        "SRC VIOLATIONS =",
        str(src_violations),
        "",
        "HANDLE VIOLATIONS =",
        str(handle_violations),
        "",
        "NUMERIC REGRESSION =",
        numeric,
        "",
        "UNSUPPORTED MATERIAL CONTENT =",
        str(unsupported),
        "",
        "MATERIAL OMISSIONS =",
        str(omissions),
        "",
        "RELATION QUALITY NEW WINDOWS =",
        (
            f"well-supported {new_rel.get('well-supported', 0)} / "
            f"plausible-loose {new_rel.get('plausible-loose', 0)} / "
            f"incorrect {new_rel.get('incorrect', 0)} / "
            f"unverifiable {new_rel.get('unverifiable', 0)}"
        ),
        "",
        "RELATION_QUALITY_TECHNICAL_DEBT =",
        RELATION_QUALITY_TECHNICAL_DEBT,
        "",
        "TOTAL INPUT TOKENS =",
        str(input_tokens),
        "",
        "TOTAL OUTPUT TOKENS =",
        str(output_tokens),
        "",
        "TOTAL COST =",
        cost_display,
        "",
        "TOTAL PROVIDER ELAPSED =",
        str(elapsed),
        "",
        "CANONICAL RECONSTRUCTION =",
        _dash("PASS" if canonical_all and all(item == "PASS" for item in canonical_all) else (canonical_all or None)),
        "",
        "MIXED COMPATIBILITY =",
        _dash("PASS" if mixed_all and all(item == "PASS" for item in mixed_all) else (mixed_all or None)),
        "",
        "PRE TESTS =",
        _dash((pre.get("full_suite_baseline") or {}).get("summary") or tests_line),
        "",
        "POST TESTS =",
        _dash((delta.get("post_call_full") or {}).get("summary") or tests),
        "",
        "NEW TEST FAILURES =",
        _dash(delta.get("new_failure_count") if delta else "UNKNOWN"),
        "",
        "CONSOLIDATION AUTHORIZED =",
        "NO",
        "",
        "SOURCE MAP =",
        "NOT PUBLISHED",
        "",
        "PRODUCTION DEFAULT =",
        "window-planner-v2.0",
        "",
        "PHASE 3B =",
        "INCOMPLETE",
        "",
        "NEXT ACTION =",
        NEXT_ACTION,
        "",
        "## Per-window table",
        "",
        *_table(result),
        "",
        "## Call budget",
        "",
        "Authorized maximum = 3",
        f"Actual calls = {result.anthropic_post_attempts}",
        f"Successful calls = {successful}",
        f"Failed calls = {failed}",
        f"Unspent authorized calls after STOP = {unspent}",
        "Authorized windows = WIN005, WIN006, WIN007",
        "WIN001 authorized = NO",
        "WIN002 authorized = NO",
        "WIN003 authorized = NO",
        "WIN004 authorized = NO",
        "",
        "## Next",
        "",
        (
            "OFFLINE FORENSICS OF WIN007 SRC TYPO (SRec007337). "
            "No retry. No later window. No consolidation."
            if str(verdict) == "FAIL"
            else NEXT_PHASE_LABEL
        ),
        "",
        "WAIT FOR HUMAN REVIEW. Do not retry automatically. Do not run consolidation.",
        "",
    ]
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
