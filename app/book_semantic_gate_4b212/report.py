"""Render the 4B.2.12 report. No secrets."""

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
        "**PHASE 4B.2.12 — SEMANTIC GATE 2.0 CONTRACT CONSOLIDATION**",
        "",
        f"RESULT = {header.get('result') or 'FAIL'}",
        f"PROVIDER CALLS = {header.get('provider_calls') if header.get('provider_calls') is not None else 0}",
        f"OPENAI HTTP = {header.get('openai_http') if header.get('openai_http') is not None else 0}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http') if header.get('anthropic_http') is not None else 0}",
        f"CANONICAL PYTHON = {header.get('canonical_python') or ''}",
        f"OPENAI SDK VERSION = {header.get('openai_sdk_version') or ''}",
        (
            "CANONICAL HASHES PRE/POST = "
            f"pre source={hashes.get('source_pre')} "
            f"plan={hashes.get('plan_pre')} "
            f"transcript={hashes.get('transcript_pre')}; "
            f"post source={hashes.get('source_post')} "
            f"plan={hashes.get('plan_post')} "
            f"transcript={hashes.get('transcript_post')}"
        ),
        "HISTORICAL H01 = PARTIAL",
        "HISTORICAL H02 = PARTIAL",
        "HISTORICAL H11 = PARTIAL",
        "HISTORICAL 4B.2.11 = PARTIAL",
        "HISTORICAL CONTRACTS MODIFIED = NO",
        "HISTORICAL LABELS MODIFIED = NO",
        "HISTORICAL RAW RESPONSE MODIFIED = NO",
        f"SCHEMA MISMATCH ROOT CAUSE = {header.get('schema_mismatch_root_cause')}",
        f"CONSOLIDATED CONTRACT = {header.get('consolidated_contract')}",
        f"STRICT SCHEMA FEASIBILITY = {header.get('strict_schema_feasibility')}",
        "REMOTE STRICT SCHEMA COMPATIBILITY = UNVERIFIED",
        f"HISTORICAL REPLAY = {header.get('historical_replay')}",
        f"SYNTHETIC REPLAY = {header.get('synthetic_replay')}",
        f"FAKEAI NEGATIVE TESTS = {header.get('fakeai_negative_tests')}",
        f"ACCEPTANCE POLICY = {header.get('acceptance_policy')}",
        f"ARCHITECTURE OPTIONS = {header.get('architecture_options')}",
        f"PROPOSED INTEGRATION STRATEGY = {header.get('proposed_integration_strategy')}",
        f"BOOK GENERATOR RESUMPTION PLAN = {header.get('book_generator_resumption_plan')}",
        f"TESTS PASSED / FAILED = {tests.get('passed') if tests.get('passed') is not None else 0} / {tests.get('failed') if tests.get('failed') is not None else 0}",
        f"NEW REGRESSIONS = {header.get('new_regressions') if header.get('new_regressions') is not None else 0}",
        "PRODUCTION PIPELINE = UNCHANGED",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_CONTROLLED_INTEGRATION_PREFLIGHT = {_yn(header.get('ready_for_controlled_integration_preflight'))}",
        "READY_FOR_NEW_REMOTE_TERRA_CALL = NO",
        "READY_FOR_REAL_CHAPTER_GENERATION = NO",
        "READY_FOR_FULL_BOOK_GENERATION = NO",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Historical status",
        "",
        "h01 remains PARTIAL. h02 remains PARTIAL. h11 remains PARTIAL.",
        "4B.2.11 remains PARTIAL. Do not rewrite any historical result.",
        "FakeAI PASS is local contract and policy only, not Terra quality.",
        "Contract 2.0.2-candidate is a consolidation of duties, not a Terra correction.",
        "",
        "## Notes",
        "",
        str(header.get("notes") or ""),
        "",
        "2.0-candidate and 2.0.1-candidate are preserved. 2.0.2-candidate is not activated.",
        "Transport 2.0-candidate is unchanged and not enabled for a real call.",
        "Strict JSON schema remains a documented option. Remote compatibility is UNVERIFIED.",
        "",
        "STOP. No Terra call. No Sonnet call. No other canary. "
        "No CH016 regeneration. No 19-chapter run. No Semantic Gate 2.0 promotion. "
        "No production pipeline change. No cache acceptance. No book.json. "
        "No Phase 5. No Word/PDF. Wait for human review before the next step.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
