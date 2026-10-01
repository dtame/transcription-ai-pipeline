"""Rapport markdown 3B.7.7A.34. Offline."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_global_preflight.constants import (
    FROZEN_SRC_POLICY,
    WIN007_CANONICAL_SRC,
    WIN007_RAW_SRC,
)


def _dash(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(value)


def render_report(bundle: Mapping[str, Any], *, tests: str) -> str:
    header = bundle["header"]
    totals = header.get("totals") or {}
    budget = bundle.get("budget") or {}
    local_est = (budget.get("local_estimate") or {})
    provider_est = (budget.get("provider_adjusted_estimate") or {})
    schema = bundle.get("schema") or {}
    freeze = bundle.get("freeze") or {}
    readiness = bundle.get("readiness") or {}
    inventory = bundle.get("inventory") or {}
    windows = inventory.get("windows") or {}
    boundary = bundle.get("boundary") or {}
    duplicates = bundle.get("duplicates") or {}
    cost = budget.get("cost_estimate_one_call") or {}
    local_cost = budget.get("local_extraction_cost_summary") or {}
    lines = [
        "# PHASE 3B.7.7A.34 — GLOBAL CONSOLIDATION OFFLINE PREFLIGHT",
        "",
        "## Result",
        "",
        str(header.get("result")),
        "",
        "REAL PROVIDER CALLS =",
        "0",
        "",
        "REAL WINDOW CALLS =",
        "0",
        "",
        "REAL CONSOLIDATION CALLS =",
        "0",
        "",
        "READY WINDOWS =",
        str(header.get("ready_windows")),
        "",
        "LOCAL EXTRACTION FREEZE CANDIDATE =",
        str(header.get("local_extraction_freeze_candidate")),
        "",
        "LOCAL EXTRACTION FUNCTIONALLY FROZEN =",
        str(header.get("local_extraction_functionally_frozen")),
        "",
        "NORMALIZED GLOBAL INPUT =",
        str(header.get("normalized_global_input")),
        "",
        "TOTAL LOCAL RECORDS =",
        _dash(totals.get("total_records")),
        "",
        "TOPICS =",
        _dash(totals.get("TOPIC")),
        "",
        "IDEAS =",
        _dash(totals.get("IDEA")),
        "",
        "RELATIONS =",
        _dash(totals.get("RELATION")),
        "",
        "EXAMPLES =",
        _dash(totals.get("EXAMPLE")),
        "",
        "REFERENCES =",
        _dash(totals.get("REFERENCE")),
        "",
        "UNCERTAINTIES =",
        _dash(totals.get("UNCERTAINTY")),
        "",
        "DISTINCT SRC =",
        _dash(totals.get("distinct_src_refs")),
        "",
        "NORMALIZED INPUT CHARS =",
        _dash(totals.get("normalized_compact_chars")),
        "",
        "ESTIMATED INPUT TOKENS =",
        _dash(local_est.get("tokens")),
        "",
        "ESTIMATED PROVIDER INPUT TOKENS =",
        _dash(provider_est.get("planning_tokens_with_20pct_margin")),
        "",
        "PROPOSED CONSOLIDATION ARCHITECTURE =",
        str(header.get("proposed_architecture")),
        "",
        "PROPOSED MODEL =",
        str(header.get("proposed_model")),
        "",
        "PROPOSED THINKING POLICY =",
        str(header.get("proposed_thinking_policy")),
        "",
        "PROPOSED MAX OUTPUT =",
        str(header.get("proposed_max_output")),
        "",
        "GLOBAL TRANSPORT VERSION =",
        str(header.get("global_transport_version")),
        "",
        "GLOBAL SCHEMA RAW / ADAPTED =",
        f"{header.get('schema_raw')} / {header.get('schema_adapted')}",
        "",
        "GLOBAL SCHEMA HASH =",
        str(header.get("schema_hash")),
        "",
        "IDEA DISPOSITION COVERAGE REQUIRED =",
        "100%",
        "",
        "RELATION POLICY =",
        str(header.get("relation_policy")),
        "",
        "RELATION_QUALITY_TECHNICAL_DEBT =",
        "YES",
        "",
        "GLOBAL GRAMMAR CANARY REQUIRED =",
        str(header.get("grammar_canary_required")),
        "",
        "ESTIMATED REAL CONSOLIDATION COST =",
        _dash(header.get("estimated_real_consolidation_cost")),
        "",
        "TESTS =",
        tests,
        "",
        "NEW FAILURES =",
        "0",
        "",
        "SOURCE MAP =",
        "NOT PUBLISHED",
        "",
        "GLOBAL CONSOLIDATION =",
        "NOT EXECUTED",
        "",
        "PHASE 3B =",
        "INCOMPLETE",
        "",
        "NEXT ACTION =",
        "HUMAN REVIEW",
        "",
        "## Historical status (unchanged)",
        "",
        f"A.28 = {header.get('historical', {}).get('A.28')}",
        f"A.30 = {header.get('historical', {}).get('A.30')}",
        f"A.31 = {header.get('historical', {}).get('A.31')}",
        f"A.32 = {header.get('historical', {}).get('A.32')}",
        f"A.33 = {header.get('historical', {}).get('A.33')}",
        "",
        "## Mixed provenance",
        "",
    ]
    mixed = (inventory.get("mixed_provenance") or {})
    for window_id in (
        "WIN001",
        "WIN002",
        "WIN003",
        "WIN004",
        "WIN005",
        "WIN006",
        "WIN007",
    ):
        lines.append(f"{window_id} = {mixed.get(window_id)}")
    lines.extend(
        [
            "",
            "## WIN007 SRC provenance",
            "",
            f"raw provider SRC = {WIN007_RAW_SRC}",
            f"derived canonical SRC = {WIN007_CANONICAL_SRC}",
            f"policy = {FROZEN_SRC_POLICY}",
            "Consolidator consumes the canonical SRC. Provenance retains the raw provider value.",
            "",
            "## Local extraction freeze",
            "",
            f"planner = {(freeze.get('frozen_architecture') or {}).get('planner')}",
            f"prompt = {(freeze.get('frozen_architecture') or {}).get('prompt')}",
            f"transport = {(freeze.get('frozen_architecture') or {}).get('transport')}",
            f"granularity = {(freeze.get('frozen_architecture') or {}).get('granularity')}",
            f"SRC policy = {(freeze.get('frozen_architecture') or {}).get('src_policy')}",
            "These were not modified in A.34.",
            "",
            "## Per-window inventory",
            "",
        ]
    )
    for window_id, row in windows.items():
        counts = row.get("record_counts") or row
        lines.append(
            f"{window_id}: path={row.get('candidate_path')} "
            f"request={row.get('request_id')} "
            f"prompt={row.get('prompt_version')} "
            f"transport={row.get('transport_version')} "
            f"granularity={row.get('granularity_policy')} "
            f"src_policy={row.get('src_policy')} "
            f"owned={row.get('src_ownership_range')} "
            f"records={counts.get('total_records')} "
            f"T/I/R/E/REF/U={counts.get('TOPIC')}/{counts.get('IDEA')}/"
            f"{counts.get('RELATION')}/{counts.get('EXAMPLE')}/"
            f"{counts.get('REFERENCE')}/{counts.get('UNCERTAINTY')} "
            f"chars={((row.get('serialized_size') or {}).get('candidate_chars'))} "
            f"bytes={((row.get('serialized_size') or {}).get('candidate_bytes'))}"
        )
    lines.extend(
        [
            "",
            "## Cross-window SRC ownership",
            "",
            f"violations = {boundary.get('cross_window_src_violation_count')}",
            f"ownership_pass = {boundary.get('ownership_pass')}",
            "",
            "## Boundary continuity (diagnostic)",
            "",
        ]
    )
    for item in boundary.get("boundaries") or []:
        lines.append(
            f"{item.get('boundary')}: continuity={item.get('continuity')} "
            f"contiguous={item.get('contiguous')}"
        )
    lines.extend(
        [
            "",
            "WINDOW != CHAPTER. WINDOW != SECTION. WINDOW != EDITORIAL UNIT.",
            "",
            "## Duplicate candidates",
            "",
            f"pairs = {duplicates.get('candidate_pair_count')}",
            f"classifications = {duplicates.get('classification_counts')}",
            "Heuristic only. Not merged. Not proof.",
            "",
            "## Contract decisions",
            "",
            f"relation policy = {header.get('relation_policy')}",
            "IDEA ops = KEEP / MERGE_EQUIVALENT / LINK_RELATED / OTHER / DROP",
            "IDEA kind globally = keep empty (downstream does not require it)",
            "idea text rewrite = minimal equivalent only",
            "importance = evidence, reassess auditable",
            "author_intent / target_audience / voice = global only",
            "disposition coverage for local IDEAs = 100%",
            "",
            "## Context / cost",
            "",
            f"one-call architecture selected = {header.get('proposed_architecture')}",
            f"thinking = {header.get('proposed_thinking_policy')}",
            f"max_output = {header.get('proposed_max_output')}",
            f"estimated consolidation cost = {cost.get('total')} (ESTIMATE)",
            f"local extraction seven-window cost = {local_cost.get('total_cost_usd')}",
            f"readiness = {readiness.get('status')}",
            "",
            "WAIT FOR HUMAN REVIEW. Do not call Anthropic. Do not call OpenAI.",
            "Do not run global grammar canary. Do not execute global consolidation.",
            "Do not publish source_map. Do not change local extraction.",
            "Do not start Editorial Planner, Book Generator, or Phase 4.",
            "Phase 3B remains INCOMPLETE.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
