"""4B.2.7 human-readable report."""

from __future__ import annotations

from typing import Any, Mapping


def _dash(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    hashes = dict(header.get("source_hashes") or {})
    hash_line = (
        f"pre source={hashes.get('source_pre')} "
        f"plan={hashes.get('plan_pre')} "
        f"transcript={hashes.get('transcript_pre')}; "
        f"post source={hashes.get('source_post')} "
        f"plan={hashes.get('plan_post')} "
        f"transcript={hashes.get('transcript_post')}"
    )
    lines = [
        "**PHASE 4B.2.7 — ONE REAL TERRA COMPACT SINGLE-CASE CANARY**",
        "",
        f"RESULT = {_dash(header.get('result'))}",
        "HISTORICAL 4B.2.6 = FAIL",
        "HISTORICAL 4B.2.6.1 = PASS",
        "HISTORICAL 4B.2.6.2 = PASS",
        "AUTHORIZED REMOTE INVOCATIONS = 1",
        f"EXECUTION ATTEMPTS = {_dash(header.get('execution_attempts'))}",
        f"REMOTE INVOCATIONS = {_dash(header.get('remote_invocations'))}",
        f"HTTP REQUESTS = {_dash(header.get('http_requests'))}",
        f"PROVIDER RESPONSES = {_dash(header.get('provider_responses'))}",
        "RETRIES = 0",
        "FALLBACKS = 0",
        "SONNET CALLS = 0",
        f"CANONICAL PYTHON = {_dash(header.get('canonical_python'))}",
        f"OPENAI SDK VERSION = {_dash(header.get('openai_sdk_version'))}",
        "MODEL = gpt-5.6-terra",
        "ENDPOINT = chat.completions",
        "CONTRACT = 1.1-candidate",
        f"SELECTED CASE = {_dash(header.get('selected_case'))}",
        f"BENCHMARK IDENTITY = {_dash(header.get('benchmark_identity'))}",
        f"LABEL LEAKAGE = {_dash(header.get('label_leakage'))}",
        f"SOURCE HASHES PRE/POST = {hash_line}",
        f"REQUEST SHA256 = {_dash(header.get('request_sha256'))}",
        f"REQUEST DETERMINISM = {_dash(header.get('request_determinism'))}",
        f"SDK SERIALIZATION = {_dash(header.get('sdk_serialization'))}",
        "MAX_COMPLETION_TOKENS = 8192",
        f"JSON_OBJECT = {_dash(header.get('json_object'))}",
        f"HTTP STATUS = {_dash(header.get('http_status'))}",
        f"FINISH_REASON = {_dash(header.get('finish_reason'))}",
        f"RESPONSE CONTENT LENGTH = {_dash(header.get('response_content_length'))}",
        f"INPUT TOKENS = {_dash(header.get('input_tokens'))}",
        f"COMPLETION TOKENS = {_dash(header.get('completion_tokens'))}",
        f"REASONING TOKENS = {_dash(header.get('reasoning_tokens'))}",
        f"ACTUAL COST = {_dash(header.get('actual_cost'))}",
        f"JSON PARSE = {_dash(header.get('json_parse'))}",
        f"CONTRACT VALIDATION = {_dash(header.get('contract_validation'))}",
        f"CLAIM COVERAGE = {_dash(header.get('claim_coverage'))}",
        f"EVIDENCE/SPAN VALIDITY = {_dash(header.get('evidence_span_validity'))}",
        f"TERRA VERDICT = {_dash(header.get('terra_verdict'))}",
        "HUMAN VERDICT = SUPPORTED",
        f"SEMANTIC REVIEW = {_dash(header.get('semantic_review'))}",
        f"DETERMINISTIC REPLAY = {_dash(header.get('deterministic_replay'))}",
        f"TESTS PASSED / FAILED = {_dash(header.get('tests_passed_failed'))}",
        f"NEW REGRESSIONS = {_dash(header.get('new_regressions'))}",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_NEGATIVE_CASE_CANARY_DESIGN = {_dash(header.get('ready_for_negative_case_canary_design'))}",
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO",
        "READY_FOR_FULL_REAL_BOOK_GENERATION = NO",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Historical status",
        "",
        "4B.2.4 = FAIL",
        "4B.2.4.1 = PASS",
        "4B.2.5 = FAIL",
        "4B.2.5.1 = PASS",
        "4B.2.6 = FAIL (8 192 completion tokens, empty JSON).",
        "4B.2.6.1 = PASS",
        "4B.2.6.2 = PASS (compact single-case freeze, no provider call).",
        "",
        "Do not rewrite any historical result.",
        "",
        "## Notes",
        "",
        _dash(header.get("notes")),
        "",
        "A single-case PASS is not a ten-case validation.",
        "Contract 1.1-candidate is not promoted.",
        "Human SUPPORTED label stayed in local evaluation data only.",
        "",
        "STOP. No second Terra call. No Sonnet call. No CH016 regeneration. "
        "No 19-chapter run. No cache acceptance. No book.json. "
        "No Phase 5. Wait for human review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
