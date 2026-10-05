"""4B.2.15 human-readable report."""

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
        "**PHASE 4B.2.15 — ONE REAL TERRA SEMANTIC GATE 2.0.2 H11 NEGATIVE CANARY**",
        "",
        f"RESULT = {_dash(header.get('result'))}",
        "AUTHORIZED REMOTE CALLS = 1",
        f"ACTUAL REMOTE CALLS = {_dash(header.get('remote_invocations'))}",
        "RETRIES = 0",
        "FALLBACKS = 0",
        "SONNET CALLS = 0",
        f"CANONICAL PYTHON = {_dash(header.get('canonical_python'))}",
        f"OPENAI SDK VERSION = {_dash(header.get('openai_sdk_version'))}",
        "MODEL = gpt-5.6-terra",
        "CASE ID = 4b276_p4_new_implication",
        "CONTRACT = book-semantic-validator-2.0.2-candidate",
        f"TRANSPORT = {_dash(header.get('transport'))}",
        f"REQUEST SHA256 = {_dash(header.get('request_sha256'))}",
        f"LABEL LEAKAGE = {_dash(header.get('label_leakage'))}",
        f"MAX_COMPLETION_TOKENS = {_dash(header.get('max_completion_tokens'))}",
        "BUDGET CAP = 0.10 USD",
        f"PRECALL MAX COST = {_dash(header.get('precall_max_cost'))}",
        f"ACTUAL CALCULATED COST = {_dash(header.get('actual_cost'))}",
        f"HTTP STATUS = {_dash(header.get('http_status'))}",
        f"FINISH_REASON = {_dash(header.get('finish_reason'))}",
        f"INPUT TOKENS = {_dash(header.get('input_tokens'))}",
        f"COMPLETION TOKENS = {_dash(header.get('completion_tokens'))}",
        f"REASONING TOKENS = {_dash(header.get('reasoning_tokens'))}",
        f"JSON PARSE = {_dash(header.get('json_parse'))}",
        f"CONTRACT VALIDATION = {_dash(header.get('contract_validation'))}",
        f"UNIT COVERAGE = {_dash(header.get('unit_coverage'))}",
        f"EVIDENCE VALIDITY = {_dash(header.get('evidence_validity'))}",
        f"UNIVERSAL GUARANTEE CLASSIFICATION = {_dash(header.get('universal_guarantee_classification'))}",
        f"SUPPORTED CLAIMS REVIEW = {_dash(header.get('supported_claims_review'))}",
        f"PYTHON ACCEPTANCE POLICY = {_dash(header.get('acceptance_policy_result'))}",
        f"HUMAN SEMANTIC REVIEW = {_dash(header.get('semantic_human_review'))}",
        f"DETERMINISTIC REPLAY = {_dash(header.get('deterministic_replay'))}",
        f"TESTS PASSED / FAILED = {_dash(header.get('tests_passed_failed'))}",
        f"NEW REGRESSIONS = {_dash(header.get('new_regressions'))}",
        f"CANONICAL HASHES PRE/POST = {hash_line}",
        "HISTORICAL H01 / H02 / H11 = PARTIAL",
        "HISTORICAL 4B.2.11 = PARTIAL",
        "PRODUCTION PIPELINE = UNCHANGED",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_ONE_REAL_CHAPTER_EXPERIMENT = {_dash(header.get('ready_for_one_real_chapter_experiment'))}",
        "READY_FOR_FULL_REAL_BOOK_GENERATION = NO",
        "NEXT ACTION = HUMAN REVIEW",
        "",
        "## Historical status",
        "",
        "h01 remains PARTIAL. h02 remains PARTIAL. h11 remains PARTIAL.",
        "4B.2.11 remains PARTIAL. 4B.2.12 remains PASS. 4B.2.13 remains PASS.",
        "4B.2.14 remains PASS. 4B.2.7.7 remains PARTIAL.",
        "Do not rewrite any historical result.",
        "",
        "## Notes",
        "",
        _dash(header.get("notes")),
        "",
        "The human UNSUPPORTED label stayed in local evaluation data only.",
        "Contract 2.0.2-candidate is not promoted.",
        "The 4B.2.14 production bridge remains disabled.",
        "This cost uses configured project rates dated 2026-09-18 and is not a provider invoice.",
        "",
        "STOP. No second Terra call. No Sonnet call. No CH016 regeneration. "
        "No other canary. No 19-chapter run. No Semantic Gate 2.0 promotion. "
        "No bridge activation. No cache acceptance. No book.json. No Phase 5. "
        "Wait for human review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
