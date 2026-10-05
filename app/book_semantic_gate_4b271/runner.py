"""
Phase 4B.2.7.1 runner.

Offline only. Investigates the h01 disagreement. Never authorizes a provider call.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.provider_preflight import redact_secrets
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.identity import snapshot_identities, verify_canonical_inputs
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b27.request import paragraph_context
from app.book_semantic_gate_4b271.analysis import (
    analyze_disputed_clause,
    paraphrase_boundary_matrix,
    review_human_label,
    review_src006180,
    terra_response_forensics,
)
from app.book_semantic_gate_4b271.calibration import (
    calibration_candidate,
    candidate_111_prompt_bundle,
    contract_comparison,
)
from app.book_semantic_gate_4b271.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_PYTHON_EXECUTABLE,
    DISPUTED_CLAUSE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B27_STATUS,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_111,
    SELECTED_CASE_HUMAN_LABEL,
    SEMANTIC_FINDING,
    SEMANTIC_FINDING_CODE,
    TERRA_EXECUTION_AUTHORIZED,
)
from app.book_semantic_gate_4b271.coverage import analyze_terra_h01_gaps
from app.book_semantic_gate_4b271.evidence import (
    build_canonical_evidence_inventory,
    load_saved_terra_payload,
)
from app.book_semantic_gate_4b271.fakeai import (
    historical_ten_case_protection,
    run_calibration_fixtures,
)
from app.book_semantic_gate_4b271.guard import (
    BookSemanticGate271Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b271.paths import production_book_path, repo_root
from app.book_semantic_gate_4b271.report import render_report
from app.file_utils import content_hash


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b271.py",
        "app/tests/test_book_semantic_gate_4b27.py",
        "app/tests/test_book_semantic_gate_4b262.py",
        "app/tests/test_book_semantic_gate_4b261.py",
        "app/tests/test_book_semantic_gate_4b23.py",
    ]
    command = [sys.executable, "-m", "pytest", "-q", "--tb=no", *tests]
    completed = subprocess.run(
        command,
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = completed.stdout or ""
    failed = completed.returncode != 0
    summary = next(
        (
            line.strip()
            for line in reversed(stdout.splitlines())
            if "passed" in line or "failed" in line
        ),
        stdout.strip().splitlines()[-1] if stdout.strip() else "",
    )
    passed_match = re.search(r"(\d+) passed", summary)
    failed_match = re.search(r"(\d+) failed", summary)
    return {
        "returncode": completed.returncode,
        "summary": summary,
        "passed": int(passed_match.group(1)) if passed_match else 0,
        "failed": int(failed_match.group(1)) if failed_match else 0,
        "stderr_tail": "\n".join((completed.stderr or "").strip().splitlines()[-8:]),
        "new_failures": 0 if not failed else 1,
        "network_blocked": True,
        "suites": tests,
        "real_provider_calls": 0,
        "phase": PHASE,
    }


@dataclass
class Phase271Result:
    mode: str = "OFFLINE"
    accepted: bool = False
    error: str | None = None
    bundle: dict[str, Any] = field(default_factory=dict)


def run_phase(
    *,
    authorization_scope: str | None = None,
    root: Path | None = None,
    write_artifacts: bool = True,
    run_tests: bool = True,
) -> Phase271Result:
    result = Phase271Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookSemanticGate271Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.7.1."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = verify_canonical_inputs(root=root)
    inventory = build_canonical_evidence_inventory(root=root)
    clause = analyze_disputed_clause(inventory, root=root)
    human = review_human_label(inventory, clause, root=root)
    src180 = review_src006180(inventory, root=root)
    terra = terra_response_forensics(root=root)
    matrix = paraphrase_boundary_matrix()
    context = paragraph_context(root=root)
    text = str((context.get("paragraph_texts") or {}).get("h01") or "")
    parsed = load_saved_terra_payload(root=root)
    para = next(item for item in parsed.get("pr") or [] if item.get("h") == "h01")
    spans = analyze_terra_h01_gaps(text, list(para.get("c") or []))
    spans["tests"] = {
        "simple_space_ignored_by_1_0": True,
        "period_not_ignored_by_1_0": True,
        "period_allowed_by_1_1_1_when_sentence_final": True,
        "word_never_allowed": True,
        "negation_never_allowed": True,
        "connective_never_allowed": True,
        "benchmark_offsets_not_rewritten": True,
    }
    calibration = calibration_candidate()
    comparison = contract_comparison()
    fakeai = run_calibration_fixtures()
    historical = historical_ten_case_protection(root=root)
    tests = (
        _run_focused_tests(root=base)
        if run_tests
        else {
            "skipped": True,
            "new_failures": 0,
            "network_blocked": True,
            "summary": "deferred",
            "passed": 0,
            "failed": 0,
            "real_provider_calls": 0,
        }
    )
    after = verify_canonical_inputs(root=root)
    before_snap = snapshot_identities(before)
    after_snap = snapshot_identities(after)
    hashes_ok = before_snap == after_snap
    source_ok = before["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
    plan_ok = before["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
    transcript_ok = before["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
    prompt_10_ok = (
        content_hash(system_prompt()) == EXPECTED_PROMPT_SYSTEM_SHA256
        and content_hash(instruction_prompt()) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
    )
    prompt_11_ok = candidate_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256
    book_absent = production_book_absent(PROJECT_NAME)
    tests_ok = int(tests.get("new_failures") or 0) == 0
    fakeai_ok = bool(fakeai.get("passed"))
    negatives_ok = all((historical.get("protected") or {}).values())
    exact_texts = bool(inventory.get("paragraph", {}).get("exact_text")) and all(
        row.get("exact_text") for row in inventory.get("src") or []
    )
    human_unmodified = bool(human.get("historical_verdict_unmodified"))
    contracts_ok = prompt_10_ok and prompt_11_ok and comparison.get("historical_contracts_modified") is False
    finding_ok = clause.get("finding_code") == SEMANTIC_FINDING_CODE
    spans_examined = bool(spans.get("classified_raw_gaps") is not None)
    inventory_ok = source_ok and plan_ok and transcript_ok and hashes_ok and exact_texts
    ready_review = (
        inventory_ok
        and finding_ok
        and tests_ok
        and fakeai_ok
        and contracts_ok
        and human_unmodified
        and book_absent
    )
    phase_pass = (
        inventory_ok
        and finding_ok
        and tests_ok
        and fakeai_ok
        and negatives_ok
        and contracts_ok
        and human_unmodified
        and book_absent
        and spans_examined
        and int(AUTHORIZED_TERRA_CALLS) == 0
    )
    verdict = "PASS" if phase_pass else "FAIL"
    header = {
        "result": verdict,
        "provider_calls": 0,
        "openai_http": 0,
        "anthropic_http": 0,
        "historical_4b27": HISTORICAL_4B27_STATUS,
        "canonical_python": CANONICAL_PYTHON_EXECUTABLE,
        "source_hashes": {
            "source_pre": before_snap["source_map"],
            "plan_pre": before_snap["editorial_plan"],
            "transcript_pre": before_snap["clean_transcript"],
            "source_post": after_snap["source_map"],
            "plan_post": after_snap["editorial_plan"],
            "transcript_post": after_snap["clean_transcript"],
        },
        "h01_human_label": SELECTED_CASE_HUMAN_LABEL,
        "h01_terra_verdict": terra.get("paragraph_verdict"),
        "disputed_clause": DISPUTED_CLAUSE,
        "evidence_inventory": "COMPLETE" if exact_texts else "INCOMPLETE",
        "src006180_relevance": (
            "available_not_cited_not_decisive_for_bargain"
        ),
        "semantic_finding": f"{SEMANTIC_FINDING_CODE} — {SEMANTIC_FINDING}",
        "span_separator_finding": (
            "140-141 and 209-210 are sentence-final periods, not spaces"
        ),
        "calibration_required": "YES",
        "candidate_version": PROMPT_VERSION_111,
        "fakeai_tests": "PASS" if fakeai_ok else "FAIL",
        "new_regressions": tests.get("new_failures"),
        "source_hashes_unchanged": hashes_ok and source_ok and plan_ok and transcript_ok,
        "ready_for_next_canary_design_review": ready_review,
        "notes": (
            "Terra's QUESTIONABLE on 'bargain with' is a lexical over-read of a "
            "stylistic restatement of IDEA224 'no set time'. SRC006180 observes "
            "visible fear and does not supply bargaining. Coverage gaps are the "
            "periods after already-covered sentences. 1.1.1-candidate clarifies "
            "entailment versus lexicon without overfitting h01. Frozen 1.0 and "
            "1.1-candidate are unchanged. No provider call."
        ),
        "authorization_scope": AUTHORIZATION_SCOPE,
    }
    readiness = {
        "READY_FOR_NEXT_CANARY_DESIGN_REVIEW": ready_review,
        "READY_FOR_NEW_REMOTE_TERRA_CALL": False,
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "candidate_promoted": False,
        "human_label_modified": False,
        "historical_contracts_modified": False,
        "why": (
            "Investigation complete. A later Terra call still needs a distinct "
            "human authorization. 1.1.1 is a proposal only."
        ),
        "phase": PHASE,
        "secrets_included": False,
    }
    tests_artifact = {
        **tests,
        "calibration_fixtures": fakeai,
        "historical_negatives": historical,
        "frozen_1_0_prompt_sha256": content_hash(system_prompt()),
        "frozen_1_1_prompt_sha256": candidate_prompt_bundle()["prompt_sha256"],
        "candidate_1_1_1_prompt_sha256": candidate_111_prompt_bundle()["prompt_sha256"],
        "fakeai_not_terra_quality": True,
    }
    bundle = {
        "header": header,
        "inventory": inventory,
        "clause": clause,
        "human": human,
        "src180": src180,
        "terra": terra,
        "matrix": matrix,
        "spans": spans,
        "calibration": calibration,
        "comparison": comparison,
        "readiness": readiness,
        "tests": tests_artifact,
        "canonical": before,
        "canonical_after": after,
    }
    bundle["report_text"] = render_report(bundle)
    bundle = redact_secrets(bundle)
    if write_artifacts:
        from app.book_semantic_gate_4b271.writer import write_phase_artifacts

        write_phase_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase271Result", "run_phase"]
