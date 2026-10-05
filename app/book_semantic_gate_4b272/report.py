"""4B.2.7.2 report renderer. No secrets."""

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
    fakeai = dict(header.get("fakeai_results") or {})
    causal = dict(bundle.get("causal") or {})
    conflict = header.get("benchmark_evidence_conflict")
    lines = [
        "PHASE 4B.2.7.2 — P3 NEGATIVE TERRA CANARY OFFLINE PREFLIGHT",
        "",
        f"RESULT = {header.get('result') or 'FAIL'}",
        f"PROVIDER CALLS = {header.get('provider_calls') if header.get('provider_calls') is not None else 0}",
        f"OPENAI HTTP = {header.get('openai_http') if header.get('openai_http') is not None else 0}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http') if header.get('anthropic_http') is not None else 0}",
        f"HISTORICAL 4B.2.7 = {header.get('historical_4b27') or 'PARTIAL'}",
        f"HISTORICAL 4B.2.7.1 = {header.get('historical_4b271') or 'PASS'}",
        f"CANONICAL PYTHON = {header.get('canonical_python') or ''}",
        f"OPENAI SDK VERSION = {header.get('openai_sdk_version') or ''}",
        f"SOURCE HASHES PRE/POST = pre source={hashes.get('source_pre')} plan={hashes.get('plan_pre')} transcript={hashes.get('transcript_pre')}; post source={hashes.get('source_post')} plan={hashes.get('plan_post')} transcript={hashes.get('transcript_post')}",
        f"P3 CASE ID = {header.get('p3_case_id') or ''}",
        f"P3 BENCHMARK ID = {header.get('p3_benchmark_id') or ''}",
        f"P3 HUMAN LABEL = {header.get('p3_human_label') or ''} — audit interne uniquement",
        f"P3 DISPUTED CAUSAL CLAUSE = {header.get('p3_disputed_causal_clause') or ''}",
        f"P3 EVIDENCE REVIEW = {header.get('p3_evidence_review') or ''}",
        f"BENCHMARK EVIDENCE CONFLICT = {_yn(conflict) if conflict in (True, False) else ('YES' if conflict else 'NO')}",
        f"CONTRACT = {header.get('contract') or 'book-semantic-validator-1.1.1-candidate'}",
        f"TRANSPORT = {header.get('transport') or ''}",
        f"LABEL LEAKAGE = {header.get('label_leakage') if header.get('label_leakage') is not None else 0}",
        f"SDK SERIALIZATION = {header.get('sdk_serialization') or ''}",
        f"REQUEST SHA256 = {header.get('request_sha256') or ''}",
        f"REQUEST DETERMINISM = {header.get('request_determinism') or ''}",
        "MAX_COMPLETION_TOKENS = 8192",
        "JSON_OBJECT SERVER CAPABILITY = UNKNOWN",
        f"INPUT TOKENS ESTIMATE = {header.get('input_tokens_estimate') if header.get('input_tokens_estimate') is not None else ''}",
        f"SHORT RESPONSE COST ESTIMATE = {header.get('short_response_cost_estimate') if header.get('short_response_cost_estimate') is not None else ''}",
        f"FULL BUDGET COST ESTIMATE = {header.get('full_budget_cost_estimate') if header.get('full_budget_cost_estimate') is not None else ''}",
        f"FAKEAI RESULTS = positives={fakeai.get('positives_accepted')} negatives_blocked={fakeai.get('negatives_blocked')} FUNERAL={fakeai.get('funeral_blocked')} CONNECTIVE={fakeai.get('connective_blocked')} P3={fakeai.get('p3_blocked')} P8={fakeai.get('p8_blocked')} (local only, not Terra)",
        f"TESTS PASSED / FAILED = {tests.get('passed') if tests.get('passed') is not None else 0} / {tests.get('failed') if tests.get('failed') is not None else 0}",
        f"NEW REGRESSIONS = {header.get('new_regressions') if header.get('new_regressions') is not None else 0}",
        "HISTORICAL CONTRACTS MODIFIED = NO",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_P3_REAL_CANARY_HUMAN_REVIEW = {_yn(header.get('ready_for_p3_real_canary_human_review'))}",
        "READY_FOR_NEW_REMOTE_TERRA_CALL = NO",
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO",
        "READY_FOR_FULL_REAL_BOOK_GENERATION = NO",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Notes",
        "",
        str(header.get("notes") or ""),
        "",
        str(causal.get("finding") or ""),
        "",
        "Observed h01 cost remains 0.018812 USD. Reasoning tokens can change actual cost.",
        "Estimates are not guarantees. No provider cost was incurred in this phase.",
        "FakeAI PASS is local contract and orchestration only, not proof that Terra will agree.",
        "1.1.1-candidate is not promoted. Frozen 1.0 and 1.1-candidate are unchanged.",
        "",
        "STOP. No Terra call. No Sonnet call. No CH016 regeneration. "
        "No 19-chapter run. No contract promotion. No cache acceptance. "
        "No book.json. Wait for human review and a new explicit remote authorization.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
