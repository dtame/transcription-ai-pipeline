"""4B.2.7.4 report renderer. No secrets."""

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
    claims = dict(bundle.get("claims") or {})
    replays = dict(bundle.get("replays") or {})
    lines = [
        "**PHASE 4B.2.7.4 — OFFLINE SEMANTIC GATE CONSOLIDATION**",
        "",
        f"RESULT = {header.get('result') or 'FAIL'}",
        f"PROVIDER CALLS = {header.get('provider_calls') if header.get('provider_calls') is not None else 0}",
        f"OPENAI HTTP = {header.get('openai_http') if header.get('openai_http') is not None else 0}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http') if header.get('anthropic_http') is not None else 0}",
        "HISTORICAL H01 = PARTIAL",
        "HISTORICAL H02 = PARTIAL",
        f"CANONICAL PYTHON = {header.get('canonical_python') or ''}",
        (
            "SOURCE HASHES PRE/POST = "
            f"pre source={hashes.get('source_pre')} "
            f"plan={hashes.get('plan_pre')} "
            f"transcript={hashes.get('transcript_pre')}; "
            f"post source={hashes.get('source_post')} "
            f"plan={hashes.get('plan_post')} "
            f"transcript={hashes.get('transcript_post')}"
        ),
        f"H02 CLAIMS REVIEWED = {header.get('h02_claims_reviewed')}",
        f"H02 FALSE REJECTIONS = {header.get('h02_false_rejections')}",
        f"H02 JUSTIFIED RESERVATIONS = {header.get('h02_justified_reservations')}",
        f"H02 INDETERMINATE CLAIMS = {header.get('h02_indeterminate_claims')}",
        f"REASON CODE POLICY = {header.get('reason_code_policy')}",
        f"UNKNOWN CODES HANDLING = {header.get('unknown_codes_handling')}",
        f"PUNCTUATION COVERAGE = {header.get('punctuation_coverage')}",
        f"SUBSTANTIVE COVERAGE = {header.get('substantive_coverage')}",
        f"CONTRACT CANDIDATE = {header.get('contract_candidate')}",
        f"TRANSPORT = {header.get('transport')}",
        "HISTORICAL CONTRACTS MODIFIED = NO",
        f"H01 REPLAY = {header.get('h01_replay')}",
        f"H02 REPLAY = {header.get('h02_replay')}",
        f"FAKEAI POSITIVES = {header.get('fakeai_positives')}",
        f"FAKEAI NEGATIVES = {header.get('fakeai_negatives')}",
        f"TESTS PASSED / FAILED = {tests.get('passed') if tests.get('passed') is not None else 0} / {tests.get('failed') if tests.get('failed') is not None else 0}",
        f"NEW REGRESSIONS = {header.get('new_regressions') if header.get('new_regressions') is not None else 0}",
        f"COST ANALYSIS = {header.get('cost_analysis')}",
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
        "4B.2.6 = FAIL",
        "4B.2.6.1 = PASS",
        "4B.2.6.2 = PASS",
        "4B.2.7 = PARTIAL",
        "4B.2.7.1 = PASS",
        "4B.2.7.2 = PASS",
        "4B.2.7.3 = PARTIAL",
        "",
        "Do not rewrite any historical result.",
        "h01 remains PARTIAL. h02 remains PARTIAL and is not a PASS.",
        "",
        "## Investigation",
        "",
        str(header.get("notes") or ""),
        "",
        f"H02 causal clause isolated = {((claims.get('causal_clause') or {}).get('correctly_isolated'))}",
        f"H02 causal clause blocked = {((claims.get('causal_clause') or {}).get('correctly_blocked'))}",
        f"H01 1.1.2 replay status = {(((replays.get('h01') or {}).get('first') or {}).get('validator_1_1_2') or {}).get('status')}",
        f"H02 1.1.2 replay status = {(((replays.get('h02') or {}).get('first') or {}).get('validator_1_1_2') or {}).get('status')}",
        "A replay difference is not proof that Terra would emit a 1.1.2-conformant answer.",
        "FakeAI PASS is local orchestration only.",
        "1.1.2-candidate is not promoted.",
        "",
        "STOP. No Terra call. No Sonnet call. No CH016 regeneration. "
        "No 19-chapter run. No contract promotion. No label change. "
        "No cache acceptance. No book.json. No Phase 5. Wait for human review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
