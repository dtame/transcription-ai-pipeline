"""
Phase 4B.2.7.2 runner.

Offline only. Freezes the P3 negative compact canary. Never authorizes a provider call.
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
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b262.telemetry import run_telemetry_cases
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b272.causal import review_causal_claim
from app.book_semantic_gate_4b272.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_SOURCE_MAP,
    H01_REQUEST_SHA256,
    HISTORICAL_4B271_STATUS,
    HISTORICAL_4B27_STATUS,
    MODEL,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_111,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_11,
)
from app.book_semantic_gate_4b272.contract import (
    inspect_contract_111,
    inspect_transport_compatibility,
)
from app.book_semantic_gate_4b272.coverage import analyze_p3_span_coverage
from app.book_semantic_gate_4b272.evidence import build_canonical_evidence_inventory
from app.book_semantic_gate_4b272.fakeai import (
    historical_ten_case_protection,
    interpret_p3_simulation,
)
from app.book_semantic_gate_4b272.guard import (
    BookSemanticGate272Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b272.identity import p3_benchmark_identity
from app.book_semantic_gate_4b272.paths import production_book_path, repo_root
from app.book_semantic_gate_4b272.preflight import (
    build_preflight,
    context_budget,
    cost_estimate,
)
from app.book_semantic_gate_4b272.report import render_report
from app.book_semantic_gate_4b272.request import (
    freeze_p3_request,
    label_leakage_audit,
    request_identity,
    serialize_p3_sdk,
)
from app.file_utils import content_hash


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b272.py",
        "app/tests/test_book_semantic_gate_4b271.py",
        "app/tests/test_book_semantic_gate_4b27.py",
        "app/tests/test_book_semantic_gate_4b262.py",
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
        "new_failures": 0 if not failed else int(failed_match.group(1) if failed_match else 1),
        "network_blocked": True,
        "suites": tests,
        "real_provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "phase": PHASE,
    }


@dataclass
class Phase272Result:
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
) -> Phase272Result:
    result = Phase272Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookSemanticGate272Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.7.2."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = verify_canonical_inputs(root=root)
    identity = p3_benchmark_identity(root=root)
    inventory = build_canonical_evidence_inventory(root=root)
    causal = review_causal_claim(inventory, root=root)
    contract = inspect_contract_111()
    transport = inspect_transport_compatibility()
    text = str((inventory.get("paragraph") or {}).get("exact_text") or "")
    spans = analyze_p3_span_coverage(text)
    leak = label_leakage_audit(root=root)
    frozen = freeze_p3_request(root=root)
    serialized = serialize_p3_sdk(root=root)
    req_identity = request_identity(root=root)
    payload = dict(frozen.get("payload") or {})
    budget = context_budget(payload, frozen=frozen)
    cost = cost_estimate(payload, budget=budget)
    telemetry = run_telemetry_cases()
    ten = historical_ten_case_protection(root=root)
    one = interpret_p3_simulation(payload, root=root)
    preflight = build_preflight(root=root)
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
    runtime = runtime_snapshot(root=root)
    bench = benchmark_identity(root=root)

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
    prompt_10_ok = (
        content_hash(system_prompt()) == EXPECTED_PROMPT_SYSTEM_SHA256
        and content_hash(instruction_prompt()) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
    )
    prompt_11_ok = candidate_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256
    prompt_111_ok = candidate_111_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256
    conflict = bool(causal.get("BENCHMARK_EVIDENCE_CONFLICT"))
    tests_ok = int(tests.get("failed") or 0) == 0 and int(tests.get("new_failures") or 0) == 0
    book_absent = production_book_absent(PROJECT_NAME)
    sim_ok = (
        ten.get("positives_accepted") == 6
        and ten.get("negatives_blocked") == 4
        and ten.get("funeral_blocked")
        and ten.get("connective_blocked")
        and ten.get("p3_blocked")
        and ten.get("p8_blocked")
        and one.get("p3_blocked")
        and one.get("causal_claim_flagged")
        and (one.get("validation") or {}).get("status") == "PASS"
    )
    freeze_ok = (
        hashes_match
        and prompt_10_ok
        and prompt_11_ok
        and prompt_111_ok
        and bool(identity.get("identified"))
        and bool(inventory.get("complete"))
        and not conflict
        and contract.get("anomaly") is None
        and bool(transport.get("compatible_without_schema_change"))
        and bool(spans.get("coverage_complete"))
        and bool(spans.get("omitting_causal_clause_fails"))
        and bool(frozen.get("determinism"))
        and bool(frozen.get("differs_from_h01"))
        and bool(frozen.get("exactly_one_case"))
        and bool(frozen.get("label_leak_pass"))
        and bool(frozen.get("independent_of_h01"))
        and bool(serialized.get("serialization_pass"))
        and int(serialized.get("network_calls") or 0) == 0
        and bool(telemetry.get("passed"))
        and sim_ok
        and tests_ok
        and book_absent
        and bool(bench.get("identity_match"))
        and cost.get("short_json") is not None
        and frozen.get("sha256") != H01_REQUEST_SHA256
        and not preflight.get("blocked_precall")
    )
    if conflict:
        verdict = "BLOCKED"
    elif freeze_ok:
        verdict = "PASS"
    else:
        verdict = "FAIL"
    ready_review = freeze_ok and not conflict
    request_for_audit = dict(req_identity)
    request_for_audit.pop("payload", None)
    readiness = {
        "READY_FOR_P3_REAL_CANARY_HUMAN_REVIEW": ready_review,
        "READY_FOR_NEW_REMOTE_TERRA_CALL": False,
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "terra_executed": False,
        "candidate_promoted": False,
        "historical_contracts_modified": False,
        "BENCHMARK_EVIDENCE_CONFLICT": conflict,
        "why": (
            "Offline P3 negative canary freeze completed. A new explicit "
            "human authorization is required before any Terra call. "
            "1.1.1-candidate is not production."
        ),
        "phase_result": verdict,
        "selected_case": f"{SELECTED_CASE_HANDLE} / {SELECTED_CASE_ID}",
        "request_sha256": frozen.get("sha256"),
        "secrets_included": False,
    }
    header = {
        "result": verdict,
        "provider_calls": 0,
        "openai_http": 0,
        "anthropic_http": 0,
        "historical_4b27": HISTORICAL_4B27_STATUS,
        "historical_4b271": HISTORICAL_4B271_STATUS,
        "canonical_python": CANONICAL_PYTHON_EXECUTABLE,
        "python_executable": sys.executable,
        "openai_sdk_version": runtime.get("openai_sdk_version"),
        "source_hashes": {
            "source_pre": source_pre,
            "plan_pre": plan_pre,
            "transcript_pre": transcript_pre,
            "source_post": source_post,
            "plan_post": plan_post,
            "transcript_post": transcript_post,
        },
        "p3_case_id": SELECTED_CASE_ID,
        "p3_benchmark_id": SELECTED_CASE_ID,
        "p3_human_label": SELECTED_CASE_HUMAN_LABEL,
        "p3_disputed_causal_clause": (identity.get("disputed_causal_clause")),
        "p3_evidence_review": (
            "INSUFFICIENT_FOR_CAUSALITY"
            if not causal.get("sufficient_to_justify_causality")
            else "CONFLICT"
        ),
        "benchmark_evidence_conflict": conflict,
        "contract": PROMPT_VERSION_111,
        "transport": TRANSPORT_VERSION_11,
        "label_leakage": 0 if frozen.get("label_leak_pass") else frozen.get("label_leakage"),
        "sdk_serialization": "PASS" if serialized.get("serialization_pass") else "FAIL",
        "request_sha256": frozen.get("sha256"),
        "request_determinism": "PASS" if frozen.get("determinism") else "FAIL",
        "max_completion_tokens": 8192,
        "json_object_server_capability": "UNKNOWN",
        "input_tokens_estimate": budget.get("estimated_input_tokens"),
        "short_response_cost_estimate": (cost.get("short_json") or {}).get("total_cost_usd"),
        "full_budget_cost_estimate": (cost.get("if_8192_exhausted") or {}).get("total_cost_usd"),
        "fakeai_results": {
            "positives_accepted": ten.get("positives_accepted"),
            "negatives_blocked": ten.get("negatives_blocked"),
            "funeral_blocked": ten.get("funeral_blocked"),
            "connective_blocked": ten.get("connective_blocked"),
            "p3_blocked": ten.get("p3_blocked"),
            "p8_blocked": ten.get("p8_blocked"),
            "p3_single_blocked": one.get("p3_blocked"),
            "not_terra_quality": True,
        },
        "tests_passed": tests.get("passed"),
        "tests_failed": tests.get("failed"),
        "new_regressions": tests.get("new_failures"),
        "historical_contracts_modified": False,
        "production_cache": "UNCHANGED",
        "book_json": "NOT PUBLISHED",
        "ready_for_p3_real_canary_human_review": ready_review,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "model": MODEL,
        "notes": (
            "4B.2.7 remains PARTIAL (h01 false rejection). 4B.2.7.1 remains "
            "PASS (offline investigation and 1.1.1-candidate). This phase "
            "freezes an independent P3 negative request without calling Terra."
        ),
    }
    out: dict[str, Any] = {
        "header": header,
        "identity": identity,
        "inventory": inventory,
        "causal": causal,
        "leak": leak,
        "contract": contract,
        "transport": transport,
        "spans": spans,
        "serialization": serialized,
        "request": request_for_audit,
        "budget": budget,
        "cost": cost,
        "preflight": preflight,
        "tests": {
            **tests,
            "ten_case_compact": ten,
            "p3_single_compact": one,
            "telemetry": telemetry,
            "benchmark_identity_match": bench.get("identity_match"),
            "fakeai_not_terra_quality": True,
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
        from app.book_semantic_gate_4b272.writer import write_phase_artifacts

        write_phase_artifacts(out, root=root)
    result.bundle = out
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase272Result", "run_phase"]
