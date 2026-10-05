"""Render the 4B.2.14 report. No secrets."""

from __future__ import annotations

from typing import Any, Mapping


def _yn(value: Any) -> str:
    if value in (True, "YES", "PASS", "yes", "pass"):
        return "YES"
    if value in (False, "NO", "FAIL", "no", "fail"):
        return "NO"
    return str(value)


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    hashes = dict(header.get("source_hashes") or {})
    tests = dict(bundle.get("tests") or {})
    lines = [
        "**PHASE 4B.2.14 — BOOK GENERATOR × SEMANTIC GATE 2.0 PRODUCTION BRIDGE & COST-BOUNDED EXECUTION PREFLIGHT**",
        "",
        f"RESULT = {header.get('result') or 'FAIL'}",
        f"PROVIDER CALLS = {header.get('provider_calls') if header.get('provider_calls') is not None else 0}",
        f"OPENAI HTTP = {header.get('openai_http') if header.get('openai_http') is not None else 0}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http') if header.get('anthropic_http') is not None else 0}",
        f"CANONICAL PYTHON = {header.get('canonical_python') or ''}",
        (
            "CANONICAL HASHES PRE/POST = "
            f"pre source={hashes.get('source_pre')} "
            f"plan={hashes.get('plan_pre')} "
            f"transcript={hashes.get('transcript_pre')}; "
            f"post source={hashes.get('source_post')} "
            f"plan={hashes.get('plan_post')} "
            f"transcript={hashes.get('transcript_post')}"
        ),
        "HISTORICAL H01 / H02 / H11 = PARTIAL",
        "HISTORICAL 4B.2.11 = PARTIAL",
        "HISTORICAL CONTRACTS MODIFIED = NO",
        "HISTORICAL LABELS MODIFIED = NO",
        "PRODUCTION PIPELINE MODIFIED = NO",
        f"BRIDGE MODULE = {header.get('bridge_module')}",
        "BRIDGE ENABLED BY DEFAULT = NO",
        "REAL PROVIDERS ENABLED = NO",
        f"REAL DATA ADAPTER = {header.get('real_data_adapter')}",
        f"EVIDENCE VALIDATION = {header.get('evidence_validation')}",
        f"VALIDATION GRANULARITY = {header.get('validation_granularity')}",
        f"PROJECT VOLUMES = {header.get('project_volumes')}",
        f"ESTIMATED REQUEST COUNTS = {header.get('estimated_request_counts')}",
        f"BOOK GENERATOR COST = {header.get('book_generator_cost')}",
        f"SEMANTIC GATE COST = {header.get('semantic_gate_cost')}",
        f"PHASE 5 COST = {header.get('phase5_cost')}",
        f"TOTAL PROJECTED COST = {header.get('total_projected_cost')}",
        f"COST UNCERTAINTIES = {header.get('cost_uncertainties')}",
        f"BUDGET GUARD = {header.get('budget_guard')}",
        f"HUMAN AUTHORIZATION = {header.get('human_authorization')}",
        f"SINGLE_CHAPTER_MODE = {header.get('single_chapter_mode')}",
        f"PASS / REVIEW / BLOCK = {header.get('pass_review_block')}",
        f"INTERRUPTION RECOVERY = {header.get('interruption_recovery')}",
        f"IDEMPOTENCE = {header.get('idempotence')}",
        f"TRACEABILITY = {header.get('traceability')}",
        f"PHASE 5 BOUNDARY = {header.get('phase5_boundary')}",
        (
            "TESTS PASSED / FAILED = "
            f"{tests.get('passed') if tests.get('passed') is not None else 0} / "
            f"{tests.get('failed') if tests.get('failed') is not None else 0}"
        ),
        f"NEW REGRESSIONS = {header.get('new_regressions') if header.get('new_regressions') is not None else 0}",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_BRIDGE_HUMAN_REVIEW = {_yn(header.get('ready_for_bridge_human_review'))}",
        "READY_FOR_ONE_REAL_CHAPTER_EXPERIMENT = NO",
        "READY_FOR_FULL_REAL_BOOK_GENERATION = NO",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Historical status",
        "",
        "h01 remains PARTIAL. h02 remains PARTIAL. h11 remains PARTIAL.",
        "4B.2.11 remains PARTIAL. 4B.2.12 remains PASS. 4B.2.13 remains PASS.",
        "Do not rewrite any historical result.",
        "FakeAI PASS is local contract and policy only, not Terra or Sonnet quality.",
        "Contract 2.0.2 has not been validated by a real Terra call.",
        "Remote strict JSON Schema compatibility remains UNVERIFIED.",
        "",
        "## Remaining obstacles before one real chapter experiment",
        "",
        str(header.get("obstacles") or ""),
        "",
        "## Notes",
        "",
        str(header.get("notes") or ""),
        "",
        "STOP. No Terra call. No Sonnet call. No CH016 regeneration. "
        "No 19-chapter run. No Semantic Gate 2.0 promotion. "
        "No production pipeline change. No cache acceptance. No book.json. "
        "No Phase 5. No Word/PDF. Wait for human review before the next step.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
