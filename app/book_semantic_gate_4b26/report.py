"""4B.2.6 human-readable report."""

from __future__ import annotations

from typing import Any, Mapping


def _dash(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    lines = [
        "# PHASE 4B.2.6 — ONE REAL TERRA SEMANTIC-GATE CANARY",
        "",
        f"RESULT = {_dash(header.get('result'))}",
        "HISTORICAL 4B.2.5 = FAIL",
        "4B.2.5.1 = PASS",
        "AUTHORIZED REMOTE INVOCATIONS = 1",
        f"EXECUTION ATTEMPTS = {_dash(header.get('execution_attempts'))}",
        f"REMOTE INVOCATIONS = {_dash(header.get('remote_invocations'))}",
        f"HTTP REQUESTS = {_dash(header.get('http_requests'))}",
        f"PROVIDER RESPONSES = {_dash(header.get('provider_responses'))}",
        "SONNET CALLS = 0",
        "RETRIES = 0",
        "FALLBACKS = 0",
        f"PYTHON EXECUTABLE = {_dash(header.get('python_executable'))}",
        f"OPENAI SDK VERSION = {_dash(header.get('openai_sdk_version'))}",
        f"MODEL/ENDPOINT = {_dash(header.get('model_endpoint'))}",
        f"PROVIDER READINESS = {_dash(header.get('provider_readiness'))}",
        f"CANONICAL HASHES PRE/POST = {_dash(header.get('canonical_hashes'))}",
        f"BENCHMARK IDENTITY = {_dash(header.get('benchmark_identity'))}",
        f"REQUEST SHA256 = {_dash(header.get('request_sha256'))}",
        f"REQUEST DETERMINISM = {_dash(header.get('request_determinism'))}",
        "TOKEN FIELD = max_completion_tokens",
        "TOKEN BUDGET = 8192",
        f"JSON_OBJECT = {_dash(header.get('json_object'))}",
        f"SERVER-ONLY UNKNOWNS = {_dash(header.get('server_only_unknowns'))}",
        f"LABEL LEAKAGE = {_dash(header.get('label_leakage'))}",
        f"CONTEXT SAFETY = {_dash(header.get('context_safety'))}",
        f"ESTIMATED COST = {_dash(header.get('estimated_cost'))}",
        f"HTTP/FINISH = {_dash(header.get('http_finish'))}",
        f"REQUEST ID = {_dash(header.get('request_id'))}",
        f"INPUT TOKENS = {_dash(header.get('input_tokens'))}",
        f"OUTPUT TOKENS = {_dash(header.get('output_tokens'))}",
        f"REASONING TOKENS = {_dash(header.get('reasoning_tokens'))}",
        f"ACTUAL COST = {_dash(header.get('actual_cost'))}",
        f"JSON PARSE = {_dash(header.get('json_parse'))}",
        f"TRANSPORT = {_dash(header.get('transport_decode'))}",
        f"CASE COVERAGE = {_dash(header.get('case_coverage'))}",
        f"CLAIM/SPAN COVERAGE = {_dash(header.get('span_claim_coverage'))}",
        f"POSITIVES ACCEPTED = {_dash(header.get('positive_accepted'))}",
        f"POSITIVE FALSE REJECTIONS = {_dash(header.get('positive_false_rejections'))}",
        f"NEGATIVES BLOCKED = {_dash(header.get('negative_blocked'))}",
        f"NEGATIVE FALSE NEGATIVES = {_dash(header.get('negative_false_negatives'))}",
        f"FUNERAL = {_dash(header.get('funeral_case'))}",
        f"CONNECTIVE = {_dash(header.get('connective_case'))}",
        f"P3 = {_dash(header.get('p3_case'))}",
        f"P8 = {_dash(header.get('p8_case'))}",
        f"EXTERNAL-KNOWLEDGE RESISTANCE = {_dash(header.get('external_knowledge_resistance'))}",
        f"REASON-CODE COMPATIBILITY = {_dash(header.get('reason_code_compatible'))}",
        f"DETERMINISTIC REPLAY = {_dash(header.get('deterministic_replay'))}",
        f"TESTS = {_dash(header.get('tests'))}",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT = {_dash(header.get('ready_for_book_generator_production_preflight'))}",
        "READY_FOR_FULL_REAL_BOOK_GENERATION = NO",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Historical status",
        "",
        "4B.2 = FAIL",
        "4B.2.1 = PASS",
        "4B.2.2 = PARTIAL",
        "4B.2.3 = PASS",
        "4B.2.4 = FAIL",
        "4B.2.4.1 = PASS",
        "4B.2.5 = FAIL",
        "4B.2.5.1 = PASS",
        "",
        "Do not rewrite any historical result.",
        "",
        "## Server-only uncertainties documented before the call",
        "",
        _dash(header.get("server_only_unknowns_detail") or header.get("server_only_unknowns")),
        "",
        "UNKNOWN is not PASS. No separate live probe was authorized.",
        "",
        "## Notes",
        "",
        _dash(header.get("notes")),
        "",
        "10 cases are an engineering canary, not a statistical model-quality benchmark.",
        "",
        "book-generator-1.0.1 remains SUFFICIENT_WITH_SEMANTIC_GATE unless new evidence materially requires reassessment.",
        "",
        "Wait for human review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
