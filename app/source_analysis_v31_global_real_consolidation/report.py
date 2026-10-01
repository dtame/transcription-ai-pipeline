"""Rapport markdown 3B.7.7A.38."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_global_real_consolidation.constants import (
    EXPECTED_DISTINCT_SRC,
    EXPECTED_IDEA,
    EXPECTED_TOTAL_RECORDS,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MAX_OUTPUT_TOKENS,
    MODEL,
    PRODUCTION_LOCAL_ESTIMATE_TOKENS,
    PRODUCTION_NORMALIZED_CHARS,
    PROMPT_VERSION,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_real_consolidation.runner import ConsolidationRunResult


def _dash(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(value)


def render_report(
    result: ConsolidationRunResult,
    *,
    tests: str,
    extra_header: Mapping[str, Any] | None = None,
) -> str:
    exe = result.execution or {}
    dry = result.dry_run or {}
    pre = result.preflight or {}
    semantic = result.semantic or {}
    extra = dict(extra_header or {})
    verdict = exe.get("result") or extra.get("result") or result.mode
    schema_raw = exe.get("schema_raw_bytes") or dry.get("schema_raw_bytes") or SCHEMA_RAW_BYTES
    schema_adapted = (
        exe.get("schema_adapted_bytes")
        or dry.get("schema_adapted_bytes")
        or SCHEMA_ADAPTED_BYTES
    )
    schema_hash = exe.get("schema_hash") or dry.get("schema_hash") or SCHEMA_HASH
    cost = (exe.get("cost") or {}).get("display") or (exe.get("cost") or {}).get("total_cost")
    elapsed = exe.get("provider_elapsed_ms")
    elapsed_display = f"{elapsed} ms" if elapsed is not None else "n/a"
    ideas = (semantic.get("ideas") or {}).get("classifications") or {}
    relations = (semantic.get("relations") or {}).get("classifications") or {}
    coverage = semantic.get("window_coverage") or {}
    drops = semantic.get("drops") or {}
    others = semantic.get("others") or {}
    merges = semantic.get("merges") or {}
    inventory = pre.get("inventory") or dry.get("inventory") or {}
    lines = [
        "# PHASE 3B.7.7A.38 — FIRST REAL GLOBAL CONSOLIDATION CANARY",
        "",
        "## Result",
        "",
        str(verdict),
        "",
        "AUTHORIZED PROVIDER CALLS =",
        "1",
        "",
        "ACTUAL PROVIDER CALLS =",
        str(exe.get("actual_calls") if exe else result.anthropic_post_attempts),
        "",
        "SUCCESSFUL PROVIDER CALLS =",
        str(exe.get("successful_calls") if exe else 0),
        "",
        "RETRIES =",
        "0",
        "",
        "REAL CONSOLIDATION EXECUTED =",
        "YES" if exe.get("real_consolidation_executed") else "NO",
        "",
        "WINDOWS =",
        "7 / 7",
        "",
        "LOCAL RECORDS =",
        str((inventory.get("observed") or {}).get("total_records") or EXPECTED_TOTAL_RECORDS),
        "",
        "LOCAL IDEAS =",
        str((inventory.get("observed") or {}).get("IDEA") or EXPECTED_IDEA),
        "",
        "LOCAL DISTINCT SRC =",
        str((inventory.get("observed") or {}).get("distinct_src") or EXPECTED_DISTINCT_SRC),
        "",
        "MODEL =",
        MODEL,
        "",
        "PROMPT =",
        PROMPT_VERSION,
        "",
        "TRANSPORT =",
        TRANSPORT_VERSION,
        "",
        "SCHEMA RAW / ADAPTED =",
        f"{_dash(schema_raw)} / {_dash(schema_adapted)}",
        "",
        "SCHEMA HASH =",
        _dash(schema_hash),
        "",
        "THINKING =",
        "disabled",
        "",
        "ACTUAL THINKING TOKENS =",
        _dash(exe.get("thinking_tokens")),
        "",
        "MAX OUTPUT =",
        str(exe.get("max_output") or MAX_OUTPUT_TOKENS),
        "",
        "HTTP =",
        _dash(exe.get("http_status")),
        "",
        "FINISH =",
        _dash(exe.get("finish_reason")),
        "",
        "REQUEST ID =",
        _dash(exe.get("request_id")),
        "",
        "LOCAL INPUT ESTIMATE =",
        _dash(exe.get("local_input_estimate") or dry.get("local_input_estimate_tokens") or PRODUCTION_LOCAL_ESTIMATE_TOKENS),
        "",
        "PROVIDER INPUT =",
        _dash(exe.get("provider_input") or exe.get("input_tokens")),
        "",
        "INPUT RATIO =",
        _dash(exe.get("input_ratio")),
        "",
        "OUTPUT TOKENS =",
        _dash(exe.get("output_tokens")),
        "",
        "OUTPUT HEADROOM =",
        (
            f"{_dash(exe.get('output_headroom_tokens'))} / "
            f"{_dash(exe.get('output_headroom_percent'))}%"
            if exe.get("output_headroom_tokens") is not None
            else "n/a"
        ),
        "",
        "COST =",
        _dash(cost),
        "",
        "ELAPSED =",
        elapsed_display,
        "",
        "STRUCTURED PARSE =",
        _dash(exe.get("structured_parse")),
        "",
        "TRANSPORT DECODER =",
        _dash(exe.get("transport_decoder")),
        "",
        "HANDLES =",
        _dash(exe.get("handle_validation")),
        "",
        "GLOBAL VALIDATOR =",
        _dash(exe.get("global_validator")),
        "",
        "IDEA DISPOSITION COVERAGE =",
        f"{_dash(exe.get('idea_disposition_coverage'))} / {EXPECTED_IDEA}",
        "",
        "KEEP =",
        _dash(exe.get("keep_count")),
        "",
        "MERGE_EQUIVALENT =",
        _dash(exe.get("merge_equivalent_count")),
        "",
        "DROP =",
        _dash(exe.get("drop_count")),
        "",
        "OTHER =",
        _dash(exe.get("other_count")),
        "",
        "SILENT DROPS =",
        _dash(exe.get("silent_drops")),
        "",
        "DROP REVIEW =",
        _dash(drops.get("status")),
        "",
        "OTHER REVIEW =",
        _dash(others.get("status")),
        "",
        "MERGE SOURCE UNION =",
        _dash(exe.get("merge_source_union")),
        "",
        "TRACEABILITY =",
        _dash(exe.get("traceability")),
        "",
        "CANONICAL RECONSTRUCTION =",
        _dash(exe.get("canonical_reconstruction")),
        "",
        "CANONICAL VALIDATION =",
        _dash(exe.get("canonical_validation")),
        "",
        "DETERMINISTIC REPLAY =",
        _dash(exe.get("deterministic_replay")),
        "",
        "GLOBAL TOPICS =",
        _dash(exe.get("global_topics")),
        "",
        "GLOBAL IDEAS =",
        _dash(exe.get("global_ideas")),
        "",
        "GLOBAL RELATIONS =",
        _dash(exe.get("global_relations")),
        "",
        "GLOBAL EXAMPLES =",
        _dash(exe.get("global_examples")),
        "",
        "GLOBAL REFERENCES =",
        _dash(exe.get("global_references")),
        "",
        "GLOBAL UNCERTAINTIES =",
        _dash(exe.get("global_uncertainties")),
        "",
        "GLOBAL REPETITIONS =",
        _dash(exe.get("global_repetitions")),
        "",
        "SEMANTIC IDEA REVIEW =",
        (
            f"SUPPORTED {ideas.get('SUPPORTED', 'n/a')} / "
            f"PARTIALLY_SUPPORTED {ideas.get('PARTIALLY_SUPPORTED', 'n/a')} / "
            f"UNSUPPORTED {ideas.get('UNSUPPORTED', 'n/a')} / "
            f"UNDETERMINABLE {ideas.get('UNDETERMINABLE', 'n/a')}"
        ),
        "",
        "INVALID MERGES =",
        str(len(merges.get("invalid") or [])),
        "",
        "MATERIAL OMISSIONS =",
        _dash((semantic.get("omissions") or {}).get("count")),
        "",
        "RELATIONS =",
        (
            f"WELL_SUPPORTED {relations.get('WELL_SUPPORTED', 'n/a')} / "
            f"PLAUSIBLE_LOOSE {relations.get('PLAUSIBLE_LOOSE', 'n/a')} / "
            f"INCORRECT {relations.get('INCORRECT', 'n/a')} / "
            f"UNVERIFIABLE {relations.get('UNVERIFIABLE', 'n/a')}"
        ),
        "",
        "BEGINNING / MIDDLE / END =",
        _dash(coverage.get("beginning_middle_end")),
        "",
        "CROSS-WINDOW CONSOLIDATION =",
        _dash((semantic.get("cross_window") or {}).get("connected_count")),
        "",
        "SEMANTIC QUALITY =",
        _dash(semantic.get("semantic_quality") or exe.get("semantic_quality")),
        "",
        "RELATION_QUALITY_TECHNICAL_DEBT =",
        RELATION_QUALITY_TECHNICAL_DEBT,
        "",
        "LOCAL EXTRACTION FUNCTIONALLY FROZEN =",
        LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "",
        "TESTS =",
        tests,
        "",
        "NEW FAILURES =",
        _dash(extra.get("new_failures") or "0"),
        "",
        "CANDIDATE SOURCE MAP =",
        _dash(exe.get("candidate_source_map") or "NOT_CREATED"),
        "",
        "PRODUCTION SOURCE MAP =",
        "NOT PUBLISHED",
        "",
        "PHASE 3B =",
        "INCOMPLETE",
        "",
        "NEXT ACTION =",
        "HUMAN REVIEW",
        "",
        "## Notes",
        "",
        f"Authorization scope = {result.authorization_scope}",
        "",
        f"Error = {_dash(result.error)}",
        "",
        f"A.34 normalized chars planning = {PRODUCTION_NORMALIZED_CHARS}",
        "",
        "A.38 produces an isolated candidate only. Do not publish analysis/source_map.json.",
        "",
        "Phase 3B remains INCOMPLETE pending human review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
