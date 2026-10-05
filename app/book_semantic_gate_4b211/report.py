"""4B.2.11 human-readable report."""

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
        "**PHASE 4B.2.11 — ONE REAL TERRA SEMANTIC GATE 2.0 H01 CANARY**",
        "",
        f"RESULT = {_dash(header.get('result'))}",
        "HISTORICAL H01 = PARTIAL",
        "HISTORICAL H02 = PARTIAL",
        "HISTORICAL H11 = PARTIAL",
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
        "CASE ID = 4b210_h01",
        "HUMAN LABEL = SUPPORTED",
        f"LABEL LEAKAGE = {_dash(header.get('label_leakage'))}",
        "CONTRACT = book-semantic-validator-2.0.1-candidate",
        "TRANSPORT = book-semantic-validation-transport-2.0-candidate",
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
        f"UNIT COVERAGE = {_dash(header.get('unit_coverage'))}",
        f"EVIDENCE VALIDITY = {_dash(header.get('evidence_validity'))}",
        f"TERRA GLOBAL VERDICT = {_dash(header.get('terra_global_verdict'))}",
        f"TARGET PARAPHRASE VERDICT = {_dash(header.get('target_paraphrase_verdict'))}",
        f"SUPPORTED CLAIMS REVIEW = {_dash(header.get('supported_claims_review'))}",
        f"SEMANTIC HUMAN REVIEW = {_dash(header.get('semantic_human_review'))}",
        f"ACCEPTANCE POLICY RESULT = {_dash(header.get('acceptance_policy_result'))}",
        f"DETERMINISTIC REPLAY = {_dash(header.get('deterministic_replay'))}",
        f"TESTS PASSED / FAILED = {_dash(header.get('tests_passed_failed'))}",
        f"NEW REGRESSIONS = {_dash(header.get('new_regressions'))}",
        "PRODUCTION PIPELINE = UNCHANGED",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_SEMANTIC_GATE_20_COMPARATIVE_REVIEW = {_dash(header.get('ready_for_semantic_gate_20_comparative_review'))}",
        "READY_FOR_NEW_REMOTE_TERRA_CALL = NO",
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = NO",
        "READY_FOR_FULL_REAL_BOOK_GENERATION = NO",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Historical status",
        "",
        "h01 remains PARTIAL. h02 remains PARTIAL. h11 remains PARTIAL.",
        "4B.2.10 remains PASS. Do not rewrite any historical result.",
        "",
        "## Notes",
        "",
        _dash(header.get("notes")),
        "",
        "The human SUPPORTED label stayed in local evaluation data only.",
        "Contract 2.0.1-candidate is not promoted.",
        "Semantic Gate 2.0 is not activated in production.",
        "This cost uses configured project rates and is not a provider invoice.",
        "",
        "STOP. No second Terra call. No Sonnet call. No CH016 regeneration. "
        "No other canary. No 19-chapter run. No Semantic Gate 2.0 promotion. "
        "No cache acceptance. No book.json. No Phase 5. Wait for human review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
