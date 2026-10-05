"""4B.2.7.7 human-readable report."""

from __future__ import annotations

from typing import Any, Mapping


def _dash(value: Any) -> str:
    if value is None or value == "":
        return "UNKNOWN"
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
        "**PHASE 4B.2.7.7 — ONE REAL TERRA H11 DISCRIMINATING CANARY**",
        "",
        f"RESULT = {_dash(header.get('result'))}",
        "HISTORICAL H01 = PARTIAL",
        "HISTORICAL H02 = PARTIAL",
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
        f"CASE HANDLE = {_dash(header.get('case_handle') or 'h11')}",
        f"CASE ID = {_dash(header.get('case_id') or '4b276_p4_new_implication')}",
        "HUMAN LABEL = UNSUPPORTED",
        f"LABEL LEAKAGE = {_dash(header.get('label_leakage'))}",
        "CONTRACT = book-semantic-validator-1.1.3-candidate",
        "TRANSPORT = book-semantic-validation-transport-1.1-candidate",
        f"REQUEST SHA256 = {_dash(header.get('request_sha256'))}",
        f"REQUEST DETERMINISM = {_dash(header.get('request_determinism'))}",
        f"SDK SERIALIZATION = {_dash(header.get('sdk_serialization'))}",
        f"CANONICAL HASHES PRE/POST = {hash_line}",
        "MAX_COMPLETION_TOKENS = 8192",
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
        f"SPAN VALIDITY = {_dash(header.get('span_validity'))}",
        f"EVIDENCE VALIDITY = {_dash(header.get('evidence_validity'))}",
        f"TERRA GLOBAL VERDICT = {_dash(header.get('terra_global_verdict'))}",
        f"UNIVERSAL GUARANTEE VERDICT = {_dash(header.get('universal_guarantee_verdict'))}",
        f"UNIVERSAL GUARANTEE REASON CODE = {_dash(header.get('universal_guarantee_reason_code'))}",
        f"SUPPORTED CLAIMS REVIEW = {_dash(header.get('supported_claims_review'))}",
        f"SEMANTIC REVIEW = {_dash(header.get('semantic_review'))}",
        f"DETERMINISTIC REPLAY = {_dash(header.get('deterministic_replay'))}",
        f"TESTS PASSED / FAILED = {_dash(header.get('tests_passed_failed'))}",
        f"NEW REGRESSIONS = {_dash(header.get('new_regressions'))}",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_SEMANTIC_GATE_COMPARATIVE_REVIEW = {_dash(header.get('ready_for_semantic_gate_comparative_review'))}",
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
        "",
        "h01 remains PARTIAL. h02 remains PARTIAL.",
        "Do not rewrite any historical result.",
        "",
        "## Notes",
        "",
        _dash(header.get("notes")),
        "",
        "A blocking global verdict is not a semantic PASS by itself.",
        "The human UNSUPPORTED label stayed in local evaluation data only.",
        "Contract 1.1.3-candidate is not promoted.",
        "This cost uses configured project rates and is not a provider invoice.",
        "",
        "STOP. No second Terra call. No Sonnet call. No CH016 regeneration. "
        "No 19-chapter run. No 1.1.3 promotion. No cache acceptance. "
        "No book.json. No Phase 5. Wait for human review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
