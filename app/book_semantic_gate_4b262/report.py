"""4B.2.6.2 report renderer. No secrets."""

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
    selection = dict(bundle.get("selection") or {})
    human = dict(selection.get("human_label_audit_only") or {})
    hashes = dict(header.get("source_hashes") or {})
    cost = dict(bundle.get("cost") or {})
    short = dict(cost.get("short_json") or {})
    detailed = dict(cost.get("detailed_json") or {})
    exhausted = dict(cost.get("if_8192_exhausted") or {})
    tests = dict(bundle.get("tests") or {})
    lines = [
        "PHASE 4B.2.6.2 — TERRA COMPACT SINGLE-CASE CANARY FREEZE",
        "",
        f"RESULT = {header.get('result') or 'FAIL'}",
        f"PROVIDER CALLS = {header.get('provider_calls') if header.get('provider_calls') is not None else 0}",
        f"OPENAI HTTP = {header.get('openai_http') if header.get('openai_http') is not None else 0}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http') if header.get('anthropic_http') is not None else 0}",
        f"CANONICAL PYTHON = {header.get('canonical_python') or ''}",
        f"OPENAI SDK VERSION = {header.get('openai_sdk_version') or ''}",
        f"HISTORICAL 4B.2.6 = {header.get('historical_4b26') or 'FAIL'}",
        f"HISTORICAL 4B.2.6.1 = {header.get('historical_4b261') or 'PASS'}",
        f"CONTRACT 1.0 = {header.get('contract_10') or 'UNCHANGED'}",
        f"CONTRACT 1.1 CANDIDATE = {header.get('contract_11') or ''}",
        f"SELECTED CASE = {header.get('selected_case') or ''}",
        f"SELECTED CASE HUMAN LABEL = {human.get('expected_class')} ({human.get('role')}) — audit interne uniquement",
        f"BENCHMARK IDENTITY = {header.get('benchmark_identity') or ''}",
        f"LABEL LEAKAGE = {header.get('label_leakage') if header.get('label_leakage') is not None else 0}",
        f"SOURCE HASHES PRE/POST = pre source={hashes.get('source_pre')} plan={hashes.get('plan_pre')} transcript={hashes.get('transcript_pre')}; post source={hashes.get('source_post')} plan={hashes.get('plan_post')} transcript={hashes.get('transcript_post')}",
        f"SDK SERIALIZATION = {header.get('sdk_serialization') or ''}",
        f"REQUEST SHA256 = {header.get('request_sha256') or ''}",
        f"REQUEST DETERMINISM = {header.get('request_determinism') or ''}",
        "MAX_COMPLETION_TOKENS = 8192",
        f"REASONING TOKEN TELEMETRY = {header.get('reasoning_token_telemetry') or ''}",
        "JSON_OBJECT SERVER CAPABILITY = UNKNOWN",
        f"CONTEXT SAFETY = {header.get('context_safety') or ''}",
        f"ESTIMATED COST = short={short.get('total_cost_usd')} detailed={detailed.get('total_cost_usd')} if_8192={exhausted.get('total_cost_usd')}",
        f"TESTS PASSED / FAILED = {tests.get('passed') if tests.get('passed') is not None else 0} / {tests.get('failed') if tests.get('failed') is not None else 0}",
        f"NEW REGRESSIONS = {header.get('new_regressions') if header.get('new_regressions') is not None else 0}",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_SINGLE_CASE_CANARY_HUMAN_REVIEW = {_yn(header.get('ready_for_single_case_canary_human_review'))}",
        "READY_FOR_NEW_REMOTE_TERRA_CALL = NO",
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO",
        "READY_FOR_FULL_REAL_BOOK_GENERATION = NO",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Notes",
        "",
        str(header.get("notes") or ""),
        "",
        "A single-case PASS later must not be read as a ten-case validation.",
        "FakeAI PASS is local orchestration only, not Terra semantic quality.",
        "0/10 in 4B.2.6 remains absence of decisions, not ten misclassifications.",
        "Contract 1.1-candidate is not promoted.",
        "",
        "STOP. No Terra call. No Sonnet call. No CH016 regeneration. "
        "No 19-chapter run. No cache acceptance. No book.json. "
        "Wait for human review and a new explicit remote authorization.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
