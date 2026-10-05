"""Render the 4B.2.13 report. No secrets."""

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
    cost = dict(bundle.get("cost") or {})
    generator = dict(cost.get("book_generator") or {})
    semantic = dict(cost.get("semantic_gate") or {})
    phase5 = dict(cost.get("phase5") or {})
    total = dict(cost.get("partial_sum_generator_plus_chapter_gate") or {})
    lines = [
        "**PHASE 4B.2.13 — BOOK GENERATOR × SEMANTIC GATE 2.0 CONTROLLED INTEGRATION PREFLIGHT**",
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
        f"SEMANTIC CONTRACT = {header.get('semantic_contract')}",
        f"SEMANTIC TRANSPORT = {header.get('semantic_transport')}",
        f"INTEGRATION MODULE = {header.get('integration_module')}",
        f"INTEGRATION CONTRACT = {header.get('integration_contract')}",
        f"DETERMINISTIC PREPARATION = {header.get('deterministic_preparation')}",
        f"UNIT COVERAGE = {header.get('unit_coverage')}",
        f"FAKEAI CHAPTER SCENARIOS = {header.get('fakeai_chapter_scenarios')}",
        f"PASS / REVIEW / BLOCK = {header.get('pass_review_block')}",
        f"ISOLATED CACHE = {header.get('isolated_cache')}",
        f"CACHE INVALIDATION = {header.get('cache_invalidation')}",
        f"INTERRUPTION RECOVERY = {header.get('interruption_recovery')}",
        f"TRACEABILITY = {header.get('traceability')}",
        f"PHASE 5 INTERFACE = {header.get('phase5_interface')}",
        f"BOOK GENERATOR COST ESTIMATE = {header.get('book_generator_cost_estimate')}",
        f"SEMANTIC GATE COST ESTIMATE = {header.get('semantic_gate_cost_estimate')}",
        f"PHASE 5 COST ESTIMATE = {header.get('phase5_cost_estimate')}",
        f"TOTAL ESTIMATE = {header.get('total_estimate')}",
        f"TESTS PASSED / FAILED = {tests.get('passed') if tests.get('passed') is not None else 0} / {tests.get('failed') if tests.get('failed') is not None else 0}",
        f"NEW REGRESSIONS = {header.get('new_regressions') if header.get('new_regressions') is not None else 0}",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_CONTROLLED_INTEGRATION_HUMAN_REVIEW = {_yn(header.get('ready_for_controlled_integration_human_review'))}",
        "READY_FOR_ONE_REAL_CHAPTER_EXPERIMENT = NO",
        "READY_FOR_FULL_REAL_BOOK_GENERATION = NO",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Historical status",
        "",
        "h01 remains PARTIAL. h02 remains PARTIAL. h11 remains PARTIAL.",
        "4B.2.11 remains PARTIAL. 4B.2.12 remains PASS. Do not rewrite any historical result.",
        "FakeAI PASS is local contract and policy only, not Terra or Sonnet quality.",
        "",
        "## Cost notes",
        "",
        (
            "Book Generator central figure is the documented 4B.1 19-chapter envelope "
            f"({generator.get('central_usd')}). Semantic Gate central figure is the "
            f"documented 4B.2.3 chapter-call envelope ({semantic.get('central_usd')}), "
            "status base_estimate. Phase 5 remains UNKNOWN and is not treated as zero. "
            f"Partial generator+gate sum central={total.get('central_usd')}; complete total is UNKNOWN."
        ),
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
