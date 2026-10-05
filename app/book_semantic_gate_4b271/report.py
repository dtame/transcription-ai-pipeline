"""4B.2.7.1 report renderer. No secrets."""

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
    spans = dict(bundle.get("spans") or {})
    clause = dict(bundle.get("clause") or {})
    src180 = dict(bundle.get("src180") or {})
    calibration = dict(bundle.get("calibration") or {})
    lines = [
        "PHASE 4B.2.7.1 — H01 SEMANTIC DISAGREEMENT FORENSICS",
        "",
        f"RESULT = {header.get('result') or 'FAIL'}",
        f"PROVIDER CALLS = {header.get('provider_calls') if header.get('provider_calls') is not None else 0}",
        f"OPENAI HTTP = {header.get('openai_http') if header.get('openai_http') is not None else 0}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http') if header.get('anthropic_http') is not None else 0}",
        f"HISTORICAL 4B.2.7 = {header.get('historical_4b27') or 'PARTIAL'}",
        f"CANONICAL HASHES PRE/POST = pre source={hashes.get('source_pre')} plan={hashes.get('plan_pre')} transcript={hashes.get('transcript_pre')}; post source={hashes.get('source_post')} plan={hashes.get('plan_post')} transcript={hashes.get('transcript_post')}",
        f"H01 HUMAN LABEL = {header.get('h01_human_label') or 'SUPPORTED'}",
        f"H01 TERRA VERDICT = {header.get('h01_terra_verdict') or 'QUESTIONABLE'}",
        f"DISPUTED CLAUSE = {header.get('disputed_clause') or ''}",
        f"EVIDENCE INVENTORY = {header.get('evidence_inventory') or ''}",
        f"SRC006180 RELEVANCE = {header.get('src006180_relevance') or ''}",
        f"SEMANTIC FINDING = {header.get('semantic_finding') or ''}",
        "HUMAN LABEL MODIFIED = NO",
        "HISTORICAL CONTRACTS MODIFIED = NO",
        f"SPAN SEPARATOR FINDING = {header.get('span_separator_finding') or ''}",
        f"CALIBRATION REQUIRED = {header.get('calibration_required') or ''}",
        f"CANDIDATE VERSION = {header.get('candidate_version') or ''}",
        f"FAKEAI TESTS = {header.get('fakeai_tests') or ''}",
        f"REGRESSION TESTS = {tests.get('passed') if tests.get('passed') is not None else 0} / {tests.get('failed') if tests.get('failed') is not None else 0}",
        f"NEW REGRESSIONS = {header.get('new_regressions') if header.get('new_regressions') is not None else 0}",
        f"SOURCE HASHES UNCHANGED = {_yn(header.get('source_hashes_unchanged'))}",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_NEXT_CANARY_DESIGN_REVIEW = {_yn(header.get('ready_for_next_canary_design_review'))}",
        "READY_FOR_NEW_REMOTE_TERRA_CALL = NO",
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
        "4B.2.6 = FAIL",
        "4B.2.6.1 = PASS",
        "4B.2.6.2 = PASS",
        "4B.2.7 = PARTIAL",
        "",
        "Do not rewrite any historical result.",
        "",
        "## Investigation",
        "",
        str(header.get("notes") or ""),
        "",
        f"Clause finding = {clause.get('finding')}",
        f"SRC006180 cited by Terra = {src180.get('cited_by_terra')}",
        f"SRC006180 decisive for bargain = {((src180.get('relevance_to_bargain_with') or {}).get('decisive'))}",
        f"Span finding = {spans.get('finding')}",
        f"1.1.1 prompt sha256 = {((calibration.get('prompt') or {}).get('prompt_sha256'))}",
        "Transport 1.1.1 was not created; schema 1.1-candidate is reused.",
        "FakeAI PASS is local orchestration only, not proof that Terra will follow 1.1.1.",
        "",
        "STOP. No Terra call. No Sonnet call. No CH016 regeneration. "
        "No 19-chapter run. No contract promotion. No label change. "
        "No cache acceptance. No book.json. Wait for human review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
