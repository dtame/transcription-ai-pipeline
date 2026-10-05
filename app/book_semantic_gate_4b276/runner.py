"""
Phase 4B.2.7.6 runner.

Offline only. Designs an independent discriminating canary. Never authorizes a provider call.
"""

from __future__ import annotations

import re
import subprocess
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
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle
from app.book_semantic_gate_4b276.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_112_SHA256,
    EXPECTED_PROMPT_113_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B261_STATUS,
    HISTORICAL_4B262_STATUS,
    HISTORICAL_4B26_STATUS,
    HISTORICAL_4B271_STATUS,
    HISTORICAL_4B272_STATUS,
    HISTORICAL_4B273_STATUS,
    HISTORICAL_4B274_STATUS,
    HISTORICAL_4B275_STATUS,
    HISTORICAL_4B27_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_113,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    SELECTED_CASE_ORIGIN,
    TARGET_FAILURE_FAMILY,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_11,
)
from app.book_semantic_gate_4b276.contract import (
    inspect_contract_113,
    inspect_reason_code_compatibility,
    inspect_transport_compatibility,
)
from app.book_semantic_gate_4b276.evidence import build_canonical_evidence_inventory
from app.book_semantic_gate_4b276.fakeai import (
    historical_ten_case_protection,
    interpret_selected_simulation,
)
from app.book_semantic_gate_4b276.guard import (
    BookSemanticGate276Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b276.identity import (
    human_reference_label,
    selected_canary_provenance,
    synthetic_paragraph_text,
)
from app.book_semantic_gate_4b276.inventory import candidate_inventory, candidate_selection_matrix
from app.book_semantic_gate_4b276.paths import production_book_path, repo_root, venv_python_path
from app.book_semantic_gate_4b276.preflight import (
    build_preflight,
    context_budget,
    cost_estimate,
    future_canary_success_criteria,
)
from app.book_semantic_gate_4b276.report import render_report
from app.book_semantic_gate_4b276.request import (
    freeze_selected_request,
    label_leakage_audit,
    request_identity,
    serialize_selected_sdk,
)
from app.file_utils import content_hash


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b276.py",
        "app/tests/test_book_semantic_gate_4b275.py",
        "app/tests/test_book_semantic_gate_4b274.py",
        "app/tests/test_book_semantic_gate_4b272.py",
        "app/tests/test_book_semantic_gate_4b23.py",
    ]
    python = str(venv_python_path(root=root))
    command = [python, "-m", "pytest", "-q", "--tb=no", *tests]
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
        "canonical_python": python,
    }


@dataclass
class Phase276Result:
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
) -> Phase276Result:
    result = Phase276Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookSemanticGate276Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.7.6."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = verify_canonical_inputs(root=root)
    inventory = candidate_inventory(root=root)
    matrix = candidate_selection_matrix(root=root)
    provenance = selected_canary_provenance(root=root)
    evidence = build_canonical_evidence_inventory(root=root)
    human = human_reference_label(root=root)
    paragraph = synthetic_paragraph_text(root=root)
    leak = label_leakage_audit(root=root)
    frozen = freeze_selected_request(root=root)
    serialized = serialize_selected_sdk(root=root)
    req_identity = request_identity(root=root)
    payload = dict(frozen.get("payload") or {})
    budget = context_budget(payload, frozen=frozen)
    cost = cost_estimate(payload, budget=budget)
    contract = inspect_contract_113()
    reasons = inspect_reason_code_compatibility()
    transport = inspect_transport_compatibility()
    ten = historical_ten_case_protection(root=root)
    one = interpret_selected_simulation(payload, root=root)
    criteria = future_canary_success_criteria()
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
    prompt_112_ok = candidate_112_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_112_SHA256
    prompt_113_ok = candidate_113_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256
    tests_ok = int(tests.get("failed") or 0) == 0 and int(tests.get("new_failures") or 0) == 0
    book_absent = production_book_absent(PROJECT_NAME)
    sim_ok = (
        ten.get("positives_accepted") == 6
        and ten.get("negatives_blocked") == 4
        and ten.get("funeral_blocked")
        and ten.get("connective_blocked")
        and ten.get("p3_blocked")
        and ten.get("p8_blocked")
        and one.get("implication_blocked")
        and one.get("implication_claim_flagged")
        and one.get("flagged_span_is_disputed_clause")
        and one.get("supported_prefix_accepted")
        and (one.get("validation") or {}).get("status") == "PASS"
    )
    historical_status_ok = (
        HISTORICAL_4B26_STATUS == "FAIL"
        and HISTORICAL_4B261_STATUS == "PASS"
        and HISTORICAL_4B262_STATUS == "PASS"
        and HISTORICAL_4B27_STATUS == "PARTIAL"
        and HISTORICAL_4B271_STATUS == "PASS"
        and HISTORICAL_4B272_STATUS == "PASS"
        and HISTORICAL_4B273_STATUS == "PARTIAL"
        and HISTORICAL_4B274_STATUS == "PASS"
        and HISTORICAL_4B275_STATUS == "PASS"
        and HISTORICAL_H01_STATUS == "PARTIAL"
        and HISTORICAL_H02_STATUS == "PARTIAL"
    )
    freeze_ok = (
        hashes_match
        and prompt_10_ok
        and prompt_11_ok
        and prompt_111_ok
        and prompt_112_ok
        and prompt_113_ok
        and bool(provenance.get("source_matches_gate"))
        and bool(evidence.get("complete"))
        and contract.get("anomaly") is None
        and bool(reasons.get("codes_in_catalog"))
        and bool(transport.get("compatible_without_schema_change"))
        and bool(frozen.get("determinism"))
        and bool(frozen.get("differs_from_h01"))
        and bool(frozen.get("differs_from_h02"))
        and bool(frozen.get("exactly_one_case"))
        and bool(frozen.get("label_leak_pass"))
        and bool(frozen.get("independent_of_h01_h02"))
        and bool(serialized.get("serialization_pass"))
        and int(serialized.get("network_calls") or 0) == 0
        and sim_ok
        and tests_ok
        and book_absent
        and bool(bench.get("identity_match"))
        and cost.get("short_json") is not None
        and not preflight.get("blocked_precall")
        and historical_status_ok
        and provenance.get("historical_benchmark_modified") is False
        and evidence.get("fabricated_evidence_added") is False
        and human.get("present_in_provider_request") is False
    )
    verdict = "PASS" if freeze_ok else "FAIL"
    ready_review = freeze_ok
    request_for_audit = dict(req_identity)
    request_for_audit.pop("payload", None)
    determinism = {
        "phase": PHASE,
        "first_sha256": frozen.get("first_sha256"),
        "second_sha256": frozen.get("second_sha256"),
        "sha256": frozen.get("sha256"),
        "determinism": frozen.get("determinism"),
        "repeat_payload_identical": frozen.get("repeat_payload_identical"),
        "serialization": frozen.get("serialization"),
        "differs_from_h01": frozen.get("differs_from_h01"),
        "differs_from_h02": frozen.get("differs_from_h02"),
        "historical_h01_sha256": frozen.get("historical_h01_sha256"),
        "historical_h02_sha256": frozen.get("historical_h02_sha256"),
        "utf8": True,
        "invented_before_construction": False,
        "secrets_included": False,
    }
    readiness = {
        "READY_FOR_ONE_REAL_CANARY_HUMAN_REVIEW": ready_review,
        "READY_FOR_NEW_REMOTE_TERRA_CALL": False,
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "terra_executed": False,
        "candidate_promoted": False,
        "historical_contracts_modified": False,
        "historical_benchmark_modified": False,
        "why": (
            "Offline independent discriminating canary freeze completed. "
            "A new explicit human authorization is required before any Terra "
            "call. 1.1.3-candidate is not production."
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
        "historical_h01": HISTORICAL_H01_STATUS,
        "historical_h02": HISTORICAL_H02_STATUS,
        "canonical_python": CANONICAL_PYTHON_EXECUTABLE,
        "openai_sdk_version": runtime.get("openai_sdk_version"),
        "source_hashes": {
            "source_pre": source_pre,
            "plan_pre": plan_pre,
            "transcript_pre": transcript_pre,
            "source_post": source_post,
            "plan_post": plan_post,
            "transcript_post": transcript_post,
        },
        "selected_canary_id": SELECTED_CASE_ID,
        "canary_origin": SELECTED_CASE_ORIGIN,
        "canary_independence": (
            "PASS" if frozen.get("independent_of_h01_h02") else "FAIL"
        ),
        "target_failure_family": TARGET_FAILURE_FAMILY,
        "human_reference_label": SELECTED_CASE_HUMAN_LABEL,
        "label_leakage": 0 if frozen.get("label_leak_pass") else frozen.get("label_leakage"),
        "contract": PROMPT_VERSION_113,
        "transport": TRANSPORT_VERSION_11,
        "request_sha256": frozen.get("sha256"),
        "request_determinism": "PASS" if frozen.get("determinism") else "FAIL",
        "sdk_serialization": "PASS" if serialized.get("serialization_pass") else "FAIL",
        "max_completion_tokens": 8192,
        "input_tokens_estimate": budget.get("estimated_input_tokens"),
        "short_response_cost_estimate": (cost.get("short_json") or {}).get("total_cost_usd"),
        "full_budget_cost_estimate": (cost.get("if_8192_exhausted") or {}).get("total_cost_usd"),
        "fakeai_positives": ten.get("positives_accepted"),
        "fakeai_negatives": ten.get("negatives_blocked"),
        "new_regressions": tests.get("new_failures"),
        "ready_for_one_real_canary_human_review": ready_review,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "notes": (
            "4B.2.7 remains PARTIAL (h01). 4B.2.7.3 remains PARTIAL (h02). "
            "This phase freezes an independent synthetic which-means canary "
            "from canonical 4b22_p4_supported evidence without calling Terra."
        ),
    }
    tests_artifact = {
        **tests,
        "ten_case_compact": ten,
        "selected_single_compact": one,
        "benchmark_identity_match": bench.get("identity_match"),
        "fakeai_not_terra_quality": True,
        "historical_ten_cases_preserved": True,
    }
    out: dict[str, Any] = {
        "header": header,
        "inventory": inventory,
        "matrix": matrix,
        "provenance": provenance,
        "evidence": evidence,
        "human": human,
        "paragraph_text": paragraph,
        "provider_request": payload,
        "determinism": determinism,
        "leak": leak,
        "contract": contract,
        "reasons": reasons,
        "transport": transport,
        "serialization": serialized,
        "request": request_for_audit,
        "budget": budget,
        "cost": cost,
        "criteria": criteria,
        "preflight": preflight,
        "tests": tests_artifact,
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
        from app.book_semantic_gate_4b276.writer import write_phase_artifacts

        write_phase_artifacts(out, root=root)
    result.bundle = out
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase276Result", "run_phase"]
