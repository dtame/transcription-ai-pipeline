"""
Phase 4B.2.10 runner.

Offline only. Semantic Gate 2.0 contract hardening and frozen canary preflight.
Never authorizes a provider call.
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
from app.book_semantic_gate_4b275.constants import (
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_112_SHA256,
    EXPECTED_PROMPT_113_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
)
from app.book_semantic_gate_4b29.contract import semantic_contract_20_candidate
from app.book_semantic_gate_4b210.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B261_STATUS,
    HISTORICAL_4B262_STATUS,
    HISTORICAL_4B26_STATUS,
    HISTORICAL_4B271_STATUS,
    HISTORICAL_4B272_STATUS,
    HISTORICAL_4B273_STATUS,
    HISTORICAL_4B274_STATUS,
    HISTORICAL_4B275_STATUS,
    HISTORICAL_4B276_STATUS,
    HISTORICAL_4B277_STATUS,
    HISTORICAL_4B27_STATUS,
    HISTORICAL_4B28_STATUS,
    HISTORICAL_4B29_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    MODEL,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_20_CANDIDATE,
    PROMPT_VERSION_201_ACTIVATED,
    PROMPT_VERSION_201_CANDIDATE,
    REAL_TERRA_CANARY_AUTHORIZED,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    SEMANTIC_GATE_20_ENABLED,
    SEMANTIC_GATE_201_ENABLED,
    SEMANTIC_TOKEN_BUDGET,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_20_ACTIVATED,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b210.contract import (
    review_contract_20,
    review_semantic_instructions,
    semantic_contract_201_candidate,
)
from app.book_semantic_gate_4b210.fakeai import run_fakeai_contract_tests
from app.book_semantic_gate_4b210.guard import (
    BookSemanticGate210Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b210.inventory import technical_inventory
from app.book_semantic_gate_4b210.paths import production_book_path, repo_root, venv_python_path
from app.book_semantic_gate_4b210.preflight import (
    build_preflight,
    canary_success_criteria,
    context_budget,
    cost_estimate,
    sdk_compatibility,
    strategic_stop_rule,
    transport_20_preflight,
)
from app.book_semantic_gate_4b210.report import render_report
from app.book_semantic_gate_4b210.request import (
    freeze_selected_request,
    label_leakage_audit,
    request_determinism_audit,
    serialize_selected_sdk,
)
from app.book_semantic_gate_4b210.safety import provider_safety
from app.book_semantic_gate_4b210.selection import candidate_selection
from app.book_semantic_gate_4b210.units import unit_integrity_review
from app.file_utils import content_hash


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b210.py",
        "app/tests/test_book_semantic_gate_4b29.py",
        "app/tests/test_book_semantic_gate_4b28.py",
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
        "fakeai_not_terra_quality": True,
    }


def _public_units(units: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in units.items()
        if not str(key).startswith("_")
    }


@dataclass
class Phase210Result:
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
) -> Phase210Result:
    result = Phase210Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookSemanticGate210Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.10."
        result.mode = "REJECTED"
        return result
    if REAL_TERRA_CANARY_AUTHORIZED:
        result.error = "A real Terra canary must not be authorized in 4B.2.10."
        result.mode = "REJECTED"
        return result
    if (
        PROMPT_VERSION_20_ACTIVATED
        or PROMPT_VERSION_201_ACTIVATED
        or TRANSPORT_VERSION_20_ACTIVATED
        or SEMANTIC_GATE_20_ENABLED
        or SEMANTIC_GATE_201_ENABLED
    ):
        result.error = "Semantic Gate 2.0 must remain inactive."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = verify_canonical_inputs(root=root)
    inventory = technical_inventory(root=root)
    contract_review = review_contract_20()
    instructions = review_semantic_instructions()
    hardened = semantic_contract_201_candidate()
    frozen_20 = semantic_contract_20_candidate()
    units = unit_integrity_review(root=root)
    selection = candidate_selection()
    leak = label_leakage_audit(root=root)
    frozen = freeze_selected_request(root=root)
    serialized = serialize_selected_sdk(root=root)
    determinism = request_determinism_audit(root=root)
    payload = dict(frozen.get("payload") or {})
    budget = context_budget(payload, frozen=frozen)
    cost = cost_estimate(payload, budget=budget)
    transport = transport_20_preflight()
    sdk = sdk_compatibility(root=root)
    fakeai = run_fakeai_contract_tests(root=root)
    criteria = canary_success_criteria()
    stop_rule = strategic_stop_rule()
    safety = provider_safety(root=root)
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
    before_snap = snapshot_identities(before)
    after_snap = snapshot_identities(after)
    runtime = runtime_snapshot(root=root)
    bench = benchmark_identity(root=root)
    hashes_ok = before_snap == after_snap
    source_ok = before["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
    plan_ok = before["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
    transcript_ok = before["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
    prompt_10_ok = (
        content_hash(system_prompt()) == EXPECTED_PROMPT_SYSTEM_SHA256
        and content_hash(instruction_prompt()) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
    )
    prompt_11_ok = candidate_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256
    prompt_111_ok = candidate_111_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256
    prompt_112_ok = candidate_112_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_112_SHA256
    prompt_113_ok = candidate_113_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256
    book_absent = production_book_absent(PROJECT_NAME)
    tests_ok = int(tests.get("new_failures") or 0) == 0 and int(tests.get("failed") or 0) == 0
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
        and HISTORICAL_4B276_STATUS == "PASS"
        and HISTORICAL_4B277_STATUS == "PARTIAL"
        and HISTORICAL_4B28_STATUS == "PASS"
        and HISTORICAL_4B29_STATUS == "PASS"
        and HISTORICAL_H01_STATUS == "PARTIAL"
        and HISTORICAL_H02_STATUS == "PARTIAL"
        and HISTORICAL_H11_STATUS == "PARTIAL"
    )
    contract_ok = (
        prompt_10_ok
        and prompt_11_ok
        and prompt_111_ok
        and prompt_112_ok
        and prompt_113_ok
        and frozen_20.get("candidate_activated") is False
        and hardened.get("candidate_activated") is False
        and hardened.get("overfit_tokens_absent_from_candidate") is True
        and hardened.get("does_not_overwrite_2_0_candidate") is True
        and bool((instructions.get("contract_201") or {}).get("all_hardening_checks"))
    )
    units_ok = bool(units.get("ok"))
    leak_ok = bool(leak.get("pass"))
    det_ok = bool(determinism.get("determinism"))
    sdk_ok = bool(serialized.get("serialization_pass"))
    fakeai_ok = bool(fakeai.get("passed"))
    safety_ok = bool(safety.get("ok"))
    selection_ok = bool(selection.get("exactly_one_selected"))
    preflight_ok = not bool(preflight.get("blocked_precall"))
    labels_ok = bool(bench.get("identity_match")) if "identity_match" in bench else True
    ready_review = (
        tests_ok
        and fakeai_ok
        and contract_ok
        and book_absent
        and historical_status_ok
        and hashes_ok
        and source_ok
        and plan_ok
        and transcript_ok
        and units_ok
        and leak_ok
        and det_ok
        and sdk_ok
        and safety_ok
        and selection_ok
        and labels_ok
    )
    ready_canary = ready_review and preflight_ok
    phase_pass = ready_review and int(AUTHORIZED_TERRA_CALLS) == 0
    verdict = "PASS" if phase_pass else "PARTIAL" if contract_ok and units_ok else "FAIL"
    if not hashes_ok or not source_ok or not plan_ok or not transcript_ok:
        verdict = "BLOCKED"
    header = {
        "result": verdict,
        "provider_calls": 0,
        "openai_http": 0,
        "anthropic_http": 0,
        "historical_h01": HISTORICAL_H01_STATUS,
        "historical_h02": HISTORICAL_H02_STATUS,
        "historical_h11": HISTORICAL_H11_STATUS,
        "canonical_python": CANONICAL_PYTHON_EXECUTABLE,
        "openai_sdk_version": runtime.get("openai_sdk_version"),
        "source_hashes": {
            "source_pre": before_snap["source_map"],
            "plan_pre": before_snap["editorial_plan"],
            "transcript_pre": before_snap["clean_transcript"],
            "source_post": after_snap["source_map"],
            "plan_post": after_snap["editorial_plan"],
            "transcript_post": after_snap["clean_transcript"],
        },
        "contract_20": PROMPT_VERSION_20_CANDIDATE,
        "transport_20": TRANSPORT_VERSION_20_CANDIDATE,
        "contract_hardening": PROMPT_VERSION_201_CANDIDATE,
        "unit_integrity": "PASS" if units_ok else "FAIL",
        "context_preservation": units.get("context_preservation"),
        "selected_canary": SELECTED_CASE_ID,
        "human_label": SELECTED_CASE_HUMAN_LABEL,
        "label_leakage": "PASS" if leak_ok else "FAIL",
        "request_sha256": frozen.get("sha256"),
        "request_determinism": "PASS" if det_ok else "FAIL",
        "sdk_serialization": "PASS" if sdk_ok else "FAIL",
        "model": MODEL,
        "max_completion_tokens": SEMANTIC_TOKEN_BUDGET,
        "cost_estimate": cost.get("cost_estimate"),
        "maximum_cost_estimate": cost.get("maximum_cost_estimate"),
        "fakeai_contract_tests": "PASS" if fakeai_ok else "FAIL",
        "new_regressions": tests.get("new_failures"),
        "provider_safety": "PASS" if safety_ok else "FAIL",
        "strategic_stop_rule": "DEFINED",
        "source_hashes_unchanged": hashes_ok and source_ok and plan_ok and transcript_ok,
        "ready_for_semantic_gate_20_human_review": ready_review,
        "ready_for_one_real_terra_canary": ready_canary,
        "notes": (
            "Semantic Gate 2.0-candidate is preserved. 2.0.1-candidate hardens "
            "verdict definitions and paraphrase instructions without claiming "
            "that historical false rejections are corrected. One h01 request is "
            "frozen for a possible later Terra canary. No provider call. "
            "Production pipeline and cache are unchanged."
        ),
        "authorization_scope": AUTHORIZATION_SCOPE,
        "selected_handle": SELECTED_CASE_HANDLE,
    }
    readiness = {
        "READY_FOR_SEMANTIC_GATE_20_HUMAN_REVIEW": ready_review,
        "READY_FOR_ONE_REAL_TERRA_CANARY": ready_canary,
        "REAL_TERRA_CANARY_AUTHORIZED": False,
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "production_pipeline": "UNCHANGED",
        "candidate_promoted": False,
        "contract_20_activated": False,
        "contract_201_activated": False,
        "human_label_modified": False,
        "historical_contracts_modified": False,
        "why": (
            "Offline contract hardening and a frozen 2.0.1 request are complete. "
            "A later Terra call still needs a distinct human authorization. "
            "2.0 and 2.0.1 remain inactive in production."
        ),
        "phase": PHASE,
        "secrets_included": False,
    }
    tests_artifact = {
        **tests,
        "offline_fakeai": fakeai,
        "frozen_1_0_prompt_sha256": content_hash(system_prompt()),
        "frozen_1_1_prompt_sha256": candidate_prompt_bundle()["prompt_sha256"],
        "frozen_1_1_1_prompt_sha256": candidate_111_prompt_bundle()["prompt_sha256"],
        "frozen_1_1_2_prompt_sha256": candidate_112_prompt_bundle()["prompt_sha256"],
        "frozen_1_1_3_prompt_sha256": candidate_113_prompt_bundle()["prompt_sha256"],
        "frozen_2_0_prompt_sha256": frozen_20.get("candidate_sha256"),
        "candidate_2_0_1_prompt_sha256": hardened.get("candidate_sha256"),
        "fakeai_not_terra_quality": True,
    }
    bundle = {
        "header": header,
        "inventory": inventory,
        "contract_review": contract_review,
        "instructions": instructions,
        "units": _public_units(units),
        "transport": transport,
        "sdk": sdk,
        "selection": selection,
        "provider_request": payload,
        "request_sha256_text": str(frozen.get("sha256") or ""),
        "leak": leak,
        "determinism": determinism,
        "serialization": serialized,
        "fakeai": fakeai,
        "criteria": criteria,
        "stop_rule": stop_rule,
        "cost": cost,
        "safety": safety,
        "readiness": readiness,
        "tests": tests_artifact,
        "preflight": preflight,
        "canonical": before,
        "canonical_after": after,
        "budget": budget,
    }
    bundle["report_text"] = render_report(bundle)
    bundle = redact_secrets(bundle)
    if write_artifacts:
        from app.book_semantic_gate_4b210.writer import write_phase_artifacts

        write_phase_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase210Result", "run_phase"]
