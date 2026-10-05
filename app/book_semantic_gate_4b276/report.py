"""4B.2.7.6 report renderer. No secrets."""

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
        "PHASE 4B.2.7.6 — INDEPENDENT DISCRIMINATING CANARY OFFLINE PREFLIGHT",
        "",
        f"RESULT = {header.get('result') or 'FAIL'}",
        f"PROVIDER CALLS = {header.get('provider_calls') if header.get('provider_calls') is not None else 0}",
        f"OPENAI HTTP = {header.get('openai_http') if header.get('openai_http') is not None else 0}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http') if header.get('anthropic_http') is not None else 0}",
        f"HISTORICAL H01 = {header.get('historical_h01') or 'PARTIAL'}",
        f"HISTORICAL H02 = {header.get('historical_h02') or 'PARTIAL'}",
        f"CANONICAL PYTHON = {header.get('canonical_python') or ''}",
        f"OPENAI SDK VERSION = {header.get('openai_sdk_version') or ''}",
        f"CANONICAL HASHES PRE/POST = pre source={hashes.get('source_pre')} plan={hashes.get('plan_pre')} transcript={hashes.get('transcript_pre')}; post source={hashes.get('source_post')} plan={hashes.get('plan_post')} transcript={hashes.get('transcript_post')}",
        f"SELECTED CANARY ID = {header.get('selected_canary_id') or ''}",
        f"CANARY ORIGIN = {header.get('canary_origin') or ''}",
        f"CANARY INDEPENDENCE = {header.get('canary_independence') or ''}",
        f"TARGET FAILURE FAMILY = {header.get('target_failure_family') or ''}",
        f"HUMAN REFERENCE LABEL = {header.get('human_reference_label') or ''} — audit interne uniquement",
        f"LABEL LEAKAGE = {header.get('label_leakage') if header.get('label_leakage') is not None else 0}",
        f"CONTRACT = {header.get('contract') or 'book-semantic-validator-1.1.3-candidate'}",
        f"TRANSPORT = {header.get('transport') or 'book-semantic-validation-transport-1.1-candidate'}",
        f"REQUEST SHA256 = {header.get('request_sha256') or ''}",
        f"REQUEST DETERMINISM = {header.get('request_determinism') or ''}",
        f"SDK SERIALIZATION = {header.get('sdk_serialization') or ''}",
        "MAX_COMPLETION_TOKENS = 8192",
        f"INPUT TOKENS ESTIMATE = {header.get('input_tokens_estimate') if header.get('input_tokens_estimate') is not None else ''}",
        f"SHORT RESPONSE COST ESTIMATE = {header.get('short_response_cost_estimate') if header.get('short_response_cost_estimate') is not None else ''}",
        f"FULL BUDGET COST ESTIMATE = {header.get('full_budget_cost_estimate') if header.get('full_budget_cost_estimate') is not None else ''}",
        f"FAKEAI POSITIVES = {header.get('fakeai_positives') if header.get('fakeai_positives') is not None else ''}",
        f"FAKEAI NEGATIVES = {header.get('fakeai_negatives') if header.get('fakeai_negatives') is not None else ''}",
        f"TESTS PASSED / FAILED = {tests.get('passed') if tests.get('passed') is not None else 0} / {tests.get('failed') if tests.get('failed') is not None else 0}",
        f"NEW REGRESSIONS = {header.get('new_regressions') if header.get('new_regressions') is not None else 0}",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_ONE_REAL_CANARY_HUMAN_REVIEW = {_yn(header.get('ready_for_one_real_canary_human_review'))}",
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
        "",
        "Do not rewrite any historical result.",
        "h01 remains PARTIAL. h02 remains PARTIAL and is not a PASS.",
        "",
        "## Notes",
        "",
        str(header.get("notes") or ""),
        "",
        "Observed h01 cost remains 0.018812 USD. Observed h02 cost remains 0.066036 USD.",
        "Estimates use configured project rates dated in the catalog. They are not live provider prices.",
        "Reasoning tokens are not assumed to be low. max_completion_tokens does not guarantee a complete answer.",
        "FakeAI PASS is local contract and orchestration only, not proof that Terra will agree.",
        "1.1.3-candidate is not promoted. Frozen historical contracts are unchanged.",
        "The selected paragraph is a documented synthetic variant of 4b22_p4_supported. It is not an authentic citation.",
        "",
        "STOP. No Terra call. No Sonnet call. No CH016 regeneration. "
        "No 19-chapter run. No contract promotion. No historical benchmark change. "
        "No cache acceptance. No book.json. No Phase 5. Wait for human review "
        "and a new explicit remote authorization.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
