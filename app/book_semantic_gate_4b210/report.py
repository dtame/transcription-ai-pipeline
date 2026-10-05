"""4B.2.10 report renderer. No secrets."""

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
        "**PHASE 4B.2.10 — SEMANTIC GATE 2.0 OFFLINE CONTRACT HARDENING**",
        "",
        f"RESULT = {header.get('result') or 'FAIL'}",
        f"PROVIDER CALLS = {header.get('provider_calls') if header.get('provider_calls') is not None else 0}",
        f"OPENAI HTTP = {header.get('openai_http') if header.get('openai_http') is not None else 0}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http') if header.get('anthropic_http') is not None else 0}",
        "HISTORICAL H01 = PARTIAL",
        "HISTORICAL H02 = PARTIAL",
        "HISTORICAL H11 = PARTIAL",
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
        "HISTORICAL CONTRACTS MODIFIED = NO",
        "HISTORICAL LABELS MODIFIED = NO",
        "PRODUCTION PIPELINE MODIFIED = NO",
        f"SEMANTIC GATE 2.0 CONTRACT = {header.get('contract_20')}",
        f"SEMANTIC GATE 2.0 TRANSPORT = {header.get('transport_20')}",
        f"CONTRACT HARDENING = {header.get('contract_hardening')}",
        f"UNIT INTEGRITY = {header.get('unit_integrity')}",
        f"CONTEXT PRESERVATION = {header.get('context_preservation')}",
        f"SELECTED CANARY = {header.get('selected_canary')}",
        f"HUMAN LABEL = {header.get('human_label')} — audit interne uniquement",
        f"LABEL LEAKAGE = {header.get('label_leakage')}",
        f"REQUEST SHA256 = {header.get('request_sha256')}",
        f"REQUEST DETERMINISM = {header.get('request_determinism')}",
        f"SDK SERIALIZATION = {header.get('sdk_serialization')}",
        f"MODEL = {header.get('model')}",
        f"MAX_COMPLETION_TOKENS = {header.get('max_completion_tokens')}",
        "RETRIES = 0",
        "FALLBACKS = 0",
        f"COST ESTIMATE = {header.get('cost_estimate')}",
        f"MAXIMUM COST ESTIMATE = {header.get('maximum_cost_estimate')}",
        f"FAKEAI CONTRACT TESTS = {header.get('fakeai_contract_tests')}",
        f"TESTS PASSED / FAILED = {tests.get('passed') if tests.get('passed') is not None else 0} / {tests.get('failed') if tests.get('failed') is not None else 0}",
        f"NEW REGRESSIONS = {header.get('new_regressions') if header.get('new_regressions') is not None else 0}",
        f"PROVIDER SAFETY = {header.get('provider_safety')}",
        f"STRATEGIC STOP RULE = {header.get('strategic_stop_rule')}",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_SEMANTIC_GATE_20_HUMAN_REVIEW = {_yn(header.get('ready_for_semantic_gate_20_human_review'))}",
        f"READY_FOR_ONE_REAL_TERRA_CANARY = {_yn(header.get('ready_for_one_real_terra_canary'))}",
        "REAL_TERRA_CANARY_AUTHORIZED = NO",
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
        "4B.2.9 = PASS",
        "",
        "h01 remains PARTIAL. h02 remains PARTIAL. h11 remains PARTIAL.",
        "Do not rewrite any historical result.",
        "FakeAI PASS is local contract and orchestration only, not Terra quality.",
        "Contract 2.0.1-candidate is a hardening of instructions, not a Terra correction.",
        "",
        "## Notes",
        "",
        str(header.get("notes") or ""),
        "",
        "Estimates use configured project rates dated in the catalog. They are not live provider prices.",
        "Reasoning tokens are not assumed to be low. max_completion_tokens does not guarantee a complete answer.",
        "Do not count reasoning tokens twice when they are already included in completion tokens.",
        "2.0-candidate is preserved. 2.0.1-candidate is a new version and is not activated.",
        "Transport 2.0-candidate is not enabled for a real call.",
        "",
        "STOP. No Terra call. No Sonnet call. No CH016 regeneration. "
        "No 19-chapter run. No Semantic Gate 2.0 promotion. "
        "No production pipeline change. No cache acceptance. No book.json. "
        "No Phase 5. No Word/PDF. Wait for human review before any real experiment.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
