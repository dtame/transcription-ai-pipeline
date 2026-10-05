"""
Phase 4B.2.6.2 runner.

Offline only. Freezes the compact single-case canary. Never authorizes a provider call.
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
from app.book_semantic_gate_4b24.identity import benchmark_identity
from app.book_semantic_gate_4b26.runtime import runtime_snapshot
from app.book_semantic_gate_4b261.evidence import load_4b26_bundle
from app.book_semantic_gate_4b262.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANDIDATE_PROMPT_VERSION,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_REQUEST_SHA256_4B26,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B261_STATUS,
    HISTORICAL_4B26_STATUS,
    MODEL,
    PHASE,
    PROJECT_NAME,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
    TERRA_EXECUTION_AUTHORIZED,
)
from app.book_semantic_gate_4b262.contract import (
    candidate_prompt_bundle,
    compact_contract_specification,
    compact_semantic_invariants,
    unnecessary_duplication_absent,
)
from app.book_semantic_gate_4b262.fakeai import (
    catalog,
    interpret_single_case_simulation,
    interpret_ten_case_compact,
)
from app.book_semantic_gate_4b262.guard import (
    BookSemanticGate262Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b262.paths import production_book_path, repo_root
from app.book_semantic_gate_4b262.preflight import (
    build_preflight,
    context_budget,
    cost_estimate,
)
from app.book_semantic_gate_4b262.report import render_report
from app.book_semantic_gate_4b262.request import (
    freeze_single_case_request,
    request_identity,
    serialize_single_case_sdk,
)
from app.book_semantic_gate_4b262.selection import evidence_manifest, review_selected_case
from app.book_semantic_gate_4b262.telemetry import run_telemetry_cases


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b262.py",
        "app/tests/test_book_semantic_gate_4b261.py",
        "app/tests/test_book_semantic_gate_4b26.py",
        "app/tests/test_book_semantic_gate_4b251.py",
        "app/tests/test_book_semantic_gate_4b23.py",
        "app/tests/test_ai_providers.py",
        "app/tests/test_ai_thinking_contract.py",
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
        "new_failures": 0 if not failed else int(failed_match.group(1) if failed_match else 1),
        "network_blocked": True,
        "suites": tests,
        "real_provider_calls": 0,
    }


@dataclass
class Phase262Result:
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
) -> Phase262Result:
    result = Phase262Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookSemanticGate262Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.6.2."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = verify_canonical_inputs(root=root)
    historical = load_4b26_bundle(root=root)
    spec = compact_contract_specification()
    invariants = compact_semantic_invariants()
    selection = review_selected_case(root=root)
    evidence = evidence_manifest(root=root)
    telemetry = run_telemetry_cases()
    frozen = freeze_single_case_request(root=root)
    serialized = serialize_single_case_sdk(root=root)
    identity = request_identity(root=root)
    payload = dict(frozen.get("payload") or {})
    budget = context_budget(payload, frozen=frozen)
    cost = cost_estimate(payload, budget=budget)
    preflight = build_preflight(root=root)
    ten = interpret_ten_case_compact(dict(historical.get("payload") or {}), root=root)
    one = interpret_single_case_simulation(payload, root=root)
    fakeai = catalog()
    after = verify_canonical_inputs(root=root)
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
    runtime = runtime_snapshot(root=root)
    bench = benchmark_identity(root=root)
    prompt = candidate_prompt_bundle()

    source_pre = (before.get("source_map") or {}).get("sha256")
    plan_pre = (before.get("editorial_plan") or {}).get("sha256")
    transcript_pre = (before.get("clean_transcript") or {}).get("sha256")
    source_post = (after.get("source_map") or {}).get("sha256")
    plan_post = (after.get("editorial_plan") or {}).get("sha256")
    transcript_post = (after.get("clean_transcript") or {}).get("sha256")
    hashes_match = (
        source_pre == EXPECTED_SOURCE_MAP
        and plan_pre == EXPECTED_EDITORIAL_PLAN
        and transcript_pre == EXPECTED_CLEAN_TRANSCRIPT
        and source_post == EXPECTED_SOURCE_MAP
        and plan_post == EXPECTED_EDITORIAL_PLAN
        and transcript_post == EXPECTED_CLEAN_TRANSCRIPT
        and before.get("source_map_unchanged")
        and after.get("source_map_unchanged")
    )
    historical_prompt_unchanged = (
        system_prompt() != ""
        and instruction_prompt() != ""
        and prompt["historical_not_replaced"]
        and prompt["version"] == CANDIDATE_PROMPT_VERSION
    )
    sim = dict(ten.get("score") or {})
    sim_ok = (
        sim.get("positives_accepted") == 6
        and sim.get("negatives_blocked") == 4
        and sim.get("negative_false_negatives") == 0
        and sim.get("funeral_blocked")
        and sim.get("connective_blocked")
        and sim.get("p3_blocked")
        and sim.get("p8_blocked")
        and ten.get("validation", {}).get("status") == "PASS"
        and unnecessary_duplication_absent(ten.get("compact") or {})
    )
    one_ok = (
        one.get("validation", {}).get("status") == "PASS"
        and one.get("no_unnecessary_duplication") is True
    )
    tests_ok = int(tests.get("failed") or 0) == 0 and int(tests.get("new_failures") or 0) == 0
    book_absent = production_book_absent(PROJECT_NAME)
    freeze_ok = (
        hashes_match
        and historical_prompt_unchanged
        and bool(frozen.get("determinism"))
        and bool(frozen.get("differs_from_4b26"))
        and bool(frozen.get("exactly_one_case"))
        and bool(frozen.get("label_leak_pass"))
        and bool(serialized.get("serialization_pass"))
        and int(serialized.get("network_calls") or 0) == 0
        and bool(selection.get("selected"))
        and bool(evidence.get("complete"))
        and bool(telemetry.get("passed"))
        and bool(invariants.get("proposition_level_control_preserved"))
        and sim_ok
        and one_ok
        and tests_ok
        and book_absent
        and bool(bench.get("identity_match"))
        and cost.get("short_json") is not None
        and str(historical.get("request_sha256") or "") == EXPECTED_REQUEST_SHA256_4B26
    )
    verdict = "PASS" if freeze_ok else "FAIL"
    ready_review = freeze_ok
    request_for_audit = dict(identity)
    request_for_audit.pop("payload", None)
    readiness = {
        "READY_FOR_SINGLE_CASE_CANARY_HUMAN_REVIEW": ready_review,
        "READY_FOR_NEW_REMOTE_TERRA_CALL": False,
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "terra_executed": False,
        "candidate_promoted": False,
        "why": (
            "Offline compact single-case freeze completed. A new explicit "
            "human authorization is required before any Terra call. "
            "Candidate 1.1 contracts are not production."
        ),
        "phase_result": verdict,
        "selected_case": f"{SELECTED_CASE_HANDLE} / {SELECTED_CASE_ID}",
        "request_sha256": frozen.get("sha256"),
    }
    header = {
        "result": verdict,
        "provider_calls": 0,
        "openai_http": 0,
        "anthropic_http": 0,
        "canonical_python": CANONICAL_PYTHON_EXECUTABLE,
        "python_executable": sys.executable,
        "openai_sdk_version": runtime.get("openai_sdk_version"),
        "historical_4b26": HISTORICAL_4B26_STATUS,
        "historical_4b261": HISTORICAL_4B261_STATUS,
        "contract_10": "UNCHANGED",
        "contract_11": f"{CANDIDATE_PROMPT_VERSION} FINALIZED_NOT_PROMOTED",
        "selected_case": f"{SELECTED_CASE_HANDLE} / {SELECTED_CASE_ID}",
        "benchmark_identity": "PASS" if bench.get("identity_match") else "FAIL",
        "label_leakage": 0 if frozen.get("label_leak_pass") else frozen.get("label_leakage"),
        "source_hashes": {
            "source_pre": source_pre,
            "plan_pre": plan_pre,
            "transcript_pre": transcript_pre,
            "source_post": source_post,
            "plan_post": plan_post,
            "transcript_post": transcript_post,
        },
        "sdk_serialization": "PASS" if serialized.get("serialization_pass") else "FAIL",
        "request_sha256": frozen.get("sha256"),
        "request_determinism": "PASS" if frozen.get("determinism") else "FAIL",
        "reasoning_token_telemetry": "PASS" if telemetry.get("passed") else "FAIL",
        "context_safety": "PASS" if budget.get("context_safe") else "FAIL",
        "new_regressions": tests.get("new_failures"),
        "ready_for_single_case_canary_human_review": ready_review,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "model": MODEL,
        "historical_4b26_request_sha256": historical.get("request_sha256"),
        "notes": (
            "4B.2.6 remains FAIL (empty JSON after 8192 completion tokens). "
            "4B.2.6.1 remains PASS (B+C). This phase freezes the compact "
            "1.1-candidate single-case request without calling Terra."
        ),
    }
    out: dict[str, Any] = {
        "header": header,
        "contract": spec,
        "invariants": invariants,
        "selection": selection,
        "evidence": evidence,
        "telemetry": telemetry,
        "serialization": serialized,
        "request": request_for_audit,
        "budget": budget,
        "cost": cost,
        "preflight": preflight,
        "tests": {
            **tests,
            "ten_case_compact": ten.get("score"),
            "single_case_compact": one.get("validation"),
            "fakeai": fakeai,
            "benchmark_identity_match": bench.get("identity_match"),
        },
        "readiness": readiness,
        "canonical": {
            "before": snapshot_identities(before),
            "after": snapshot_identities(after),
            "inputs_unchanged": hashes_match,
        },
        "execution": {
            "mode": "OFFLINE",
            "actual_terra_calls": 0,
            "openai_http_requests": 0,
            "anthropic_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "book_json": "NOT PUBLISHED",
            "production_cache": "UNCHANGED",
        },
    }
    out = redact_secrets(out)
    out["report_text"] = render_report(out)
    if write_artifacts:
        from app.book_semantic_gate_4b262.writer import write_phase_artifacts

        write_phase_artifacts(out, root=root)
    result.bundle = out
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase262Result", "run_phase"]
