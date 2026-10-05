"""4B.2.8 report renderer. No secrets."""

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
    h11 = dict(bundle.get("h11") or {})
    replay = dict(bundle.get("replay") or {})
    lines = [
        "**PHASE 4B.2.8 — SEMANTIC GATE COMPARATIVE FORENSICS & ARCHITECTURE DESIGN**",
        "",
        f"RESULT = {header.get('result') or 'FAIL'}",
        f"PROVIDER CALLS = {header.get('provider_calls') if header.get('provider_calls') is not None else 0}",
        f"OPENAI HTTP = {header.get('openai_http') if header.get('openai_http') is not None else 0}",
        f"ANTHROPIC HTTP = {header.get('anthropic_http') if header.get('anthropic_http') is not None else 0}",
        "HISTORICAL H01 = PARTIAL",
        "HISTORICAL H02 = PARTIAL",
        "HISTORICAL H11 = PARTIAL",
        f"CANONICAL PYTHON = {header.get('canonical_python') or ''}",
        (
            "CANONICAL HASHES PRE/POST = "
            f"pre source={hashes.get('source_pre')} "
            f"plan={hashes.get('plan_pre')} "
            f"transcript={hashes.get('transcript_pre')}; "
            f"post source={hashes.get('source_post')} "
            f"plan={hashes.get('plan_post')} "
            f"transcript={hashes.get('transcript_post')}"
        ),
        f"RAW RESPONSES PRESERVED = {_yn(header.get('raw_responses_preserved'))}",
        f"HISTORICAL LABELS PRESERVED = {_yn(header.get('historical_labels_preserved'))}",
        f"HISTORICAL CONTRACTS PRESERVED = {_yn(header.get('historical_contracts_preserved'))}",
        f"H01 FALSE REJECTION ANALYSIS = {header.get('h01_false_rejection_analysis')}",
        f"H02 FALSE REJECTION ANALYSIS = {header.get('h02_false_rejection_analysis')}",
        f"H11 FALSE REJECTION ANALYSIS = {header.get('h11_false_rejection_analysis')}",
        f"H11 COVERAGE GAPS CLASSIFICATION = {h11.get('coverage_gaps_classification')}",
        f"FAILURE TAXONOMY = {header.get('failure_taxonomy')}",
        f"ARCHITECTURE A = {header.get('architecture_a')}",
        f"ARCHITECTURE B = {header.get('architecture_b')}",
        f"ARCHITECTURE C = {header.get('architecture_c')}",
        f"DETERMINISTIC SEGMENTATION FEASIBILITY = {header.get('segmentation_feasibility')}",
        f"SEGMENTATION PROTOTYPE = {header.get('segmentation_prototype')}",
        f"SEGMENTATION COVERAGE = {header.get('segmentation_coverage')}",
        f"NEGATION/CAUSALITY PRESERVATION = {header.get('negation_causality_preservation')}",
        f"CONTRACT 2.0 PROPOSAL = {header.get('contract_20_proposal')}",
        f"TRANSPORT CHANGES REQUIRED = {header.get('transport_changes_required')}",
        f"COST ANALYSIS = {header.get('cost_analysis')}",
        f"ARCHITECTURE COMPARISON = {header.get('architecture_comparison')}",
        f"PROPOSED TARGET ARCHITECTURE = {header.get('proposed_target_architecture')}",
        f"EVIDENCE LEVEL = {header.get('evidence_level')}",
        f"MIGRATION PLAN = {header.get('migration_plan')}",
        f"FAKEAI POSITIVES = {header.get('fakeai_positives')}",
        f"FAKEAI NEGATIVES = {header.get('fakeai_negatives')}",
        f"TESTS PASSED / FAILED = {tests.get('passed') if tests.get('passed') is not None else 0} / {tests.get('failed') if tests.get('failed') is not None else 0}",
        f"NEW REGRESSIONS = {header.get('new_regressions') if header.get('new_regressions') is not None else 0}",
        "PRODUCTION PIPELINE = UNCHANGED",
        "PRODUCTION CACHE = UNCHANGED",
        "book.json = NOT PUBLISHED",
        f"READY_FOR_ARCHITECTURE_HUMAN_REVIEW = {_yn(header.get('ready_for_architecture_human_review'))}",
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
        "4B.2.7.7 = PARTIAL",
        "",
        "h01 remains PARTIAL. h02 remains PARTIAL. h11 remains PARTIAL.",
        "Do not rewrite any historical result.",
        "FakeAI PASS is local orchestration only, not Terra quality.",
        "",
        "## Investigation",
        "",
        str(header.get("notes") or ""),
        "",
        f"h01 replay units = {(replay.get('h01') or {}).get('unit_count')}",
        f"h02 replay units = {(replay.get('h02') or {}).get('unit_count')}",
        f"h11 replay units = {(replay.get('h11') or {}).get('unit_count')}",
        "Offline replay does not produce new Terra verdicts.",
        "",
        "STOP. No Terra call. No Sonnet call. No CH016 regeneration. "
        "No 19-chapter run. No contract promotion. No transport replacement. "
        "No cache acceptance. No book.json. No Phase 5. Wait for human review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
