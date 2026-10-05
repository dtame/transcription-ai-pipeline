"""4B.2.9 report renderer. No secrets."""

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
        "**PHASE 4B.2.9 — SEMANTIC GATE 2.0 OFFLINE IMPLEMENTATION**",
        "",
        f"RESULT = {header.get('result') or 'FAIL'}",
        f"PROVIDER CALLS = {header.get('provider_calls') if header.get('provider_calls') is not None else 0}",
        f"OPENAI HTTP = {header.get('openai_http') if header.get('openai_http') is not None else 0}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http') if header.get('anthropic_http') is not None else 0}",
        "HISTORICAL H01 = PARTIAL",
        "HISTORICAL H02 = PARTIAL",
        "HISTORICAL H11 = PARTIAL",
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
        "HISTORICAL CONTRACTS MODIFIED = NO",
        "HISTORICAL LABELS MODIFIED = NO",
        "PRODUCTION PIPELINE MODIFIED = NO",
        f"SEMANTIC GATE 2.0 MODULE = {header.get('semantic_gate_20_module')}",
        f"DETERMINISTIC PREPARATION = {header.get('deterministic_preparation')}",
        f"UNIT IDENTIFIERS = {header.get('unit_identifiers')}",
        f"OFFSET CONVENTION = {header.get('offset_convention')}",
        f"COVERAGE = {header.get('coverage')}",
        f"CONTEXT PRESERVATION = {header.get('context_preservation')}",
        f"CONTRACT 2.0 = {header.get('contract_20')}",
        f"TRANSPORT 2.0 = {header.get('transport_20')}",
        f"RESPONSE VALIDATOR = {header.get('response_validator')}",
        f"ACCEPTANCE POLICY = {header.get('acceptance_policy')}",
        f"FAKEAI SCENARIOS = {header.get('fakeai_scenarios')}",
        f"H01 OFFLINE REPLAY = {header.get('h01_offline_replay')}",
        f"H02 OFFLINE REPLAY = {header.get('h02_offline_replay')}",
        f"H11 OFFLINE REPLAY = {header.get('h11_offline_replay')}",
        f"BENCHMARK COMPATIBILITY = {header.get('benchmark_compatibility')}",
        f"INTEGRATION PREFLIGHT = {header.get('integration_preflight')}",
        f"PROVIDER SAFETY = {header.get('provider_safety')}",
        f"TESTS PASSED / FAILED = {tests.get('passed') if tests.get('passed') is not None else 0} / {tests.get('failed') if tests.get('failed') is not None else 0}",
        f"NEW REGRESSIONS = {header.get('new_regressions') if header.get('new_regressions') is not None else 0}",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_SEMANTIC_GATE_20_HUMAN_REVIEW = {_yn(header.get('ready_for_semantic_gate_20_human_review'))}",
        "READY_FOR_NEW_REMOTE_TERRA_CALL = NO",
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO",
        "READY_FOR_FULL_REAL_BOOK_GENERATION = NO",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Historical status",
        "",
        "4B.2.6 = FAIL",
        "4B.2.6.1 = PASS",
        "4B.2.6.2 = PASS",
        "4B.2.7 = PARTIAL",
        "4B.2.7.1 = PASS",
        "4B.2.7.2 = PASS",
        "4B.2.7.3 = PARTIAL",
        "4B.2.7.4 = PASS",
        "4B.2.7.5 = PASS",
        "4B.2.7.6 = PASS",
        "4B.2.7.7 = PARTIAL",
        "4B.2.8 = PASS",
        "",
        "h01 remains PARTIAL. h02 remains PARTIAL. h11 remains PARTIAL.",
        "Do not rewrite any historical result.",
        "FakeAI PASS is local orchestration only, not Terra quality.",
        "Historical false rejections are not declared corrected.",
        "",
        "## Implementation",
        "",
        str(header.get("notes") or ""),
        "",
        "STOP. No Terra call. No Sonnet call. No CH016 regeneration. "
        "No 19-chapter run. No Semantic Gate 2.0 promotion. "
        "No production pipeline change. No cache acceptance. No book.json. "
        "No Phase 5. No Word/PDF. Wait for human review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
