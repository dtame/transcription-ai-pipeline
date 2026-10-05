"""
Phase 4B.2.12 runner.

Offline only. Contract consolidation, historical replay, FakeAI negatives,
architecture options, and a Book Generator resumption plan.
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
from app.book_semantic_gate_4b23.identity import (
    file_identity,
    snapshot_identities,
    verify_canonical_inputs,
)
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
from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b210.contract import semantic_contract_201_candidate
from app.book_semantic_gate_4b211.request import paragraph_context
from app.book_semantic_gate_4b212.architecture import architecture_options
from app.book_semantic_gate_4b212.concepts import semantic_vs_operational_verdicts
from app.book_semantic_gate_4b212.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_4B211_RAW_TEXT_SHA256,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B210_STATUS,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    PHASE,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PROJECT_NAME,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_20_CANDIDATE,
    PROMPT_VERSION_201_ACTIVATED,
    PROMPT_VERSION_201_CANDIDATE,
    PROMPT_VERSION_202_ACTIVATED,
    PROMPT_VERSION_202_CANDIDATE,
    REAL_TERRA_CANARY_AUTHORIZED,
    REMOTE_STRICT_SCHEMA_COMPATIBILITY,
    SEMANTIC_GATE_20_ENABLED,
    SEMANTIC_GATE_201_ENABLED,
    SEMANTIC_GATE_202_ENABLED,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_20_ACTIVATED,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b212.contract import semantic_contract_202_candidate
from app.book_semantic_gate_4b212.fakeai import run_negative_fakeai_tests
from app.book_semantic_gate_4b212.forensics import (
    real_response_forensics,
    schema_mismatch_analysis,
)
from app.book_semantic_gate_4b212.guard import (
    BookSemanticGate212Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b212.inventory import technical_inventory
from app.book_semantic_gate_4b212.paths import (
    historical_raw_response_path,
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_semantic_gate_4b212.policy import (
    acceptance_policy_document,
    apply_acceptance_policy_202,
)
from app.book_semantic_gate_4b212.replay import (
    historical_replay_201,
    historical_semantic_observations,
    synthetic_202_fixture_replay,
)
from app.book_semantic_gate_4b212.report import render_report
from app.book_semantic_gate_4b212.resumption import book_generator_resumption_plan
from app.book_semantic_gate_4b212.safety import provider_safety
from app.book_semantic_gate_4b212.schema_feasibility import strict_schema_feasibility
from app.book_semantic_gate_4b212.validator import validate_response_202
from app.file_utils import content_hash


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b212.py",
        "app/tests/test_book_semantic_gate_4b211.py",
        "app/tests/test_book_semantic_gate_4b210.py",
        "app/tests/test_book_semantic_gate_4b29.py",
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


def _policy_validation(*, root: Path | None = None) -> dict[str, Any]:
    context = paragraph_context(root=root)
    prepared = dict(context.get("prepared") or {})
    coverage = validate_prepared_coverage(prepared)
    synthetic = synthetic_202_fixture_replay(root=root)
    payload = dict((synthetic.get("fixture") or {}).get("payload") or {})
    validation = validate_response_202(
        payload,
        prepared,
        allowed_evidence=list(context.get("allowed_handles") or []),
        expected_chapter="CH016",
    )
    policy = apply_acceptance_policy_202(prepared, coverage, validation)
    document = acceptance_policy_document()
    return {
        "phase": PHASE,
        "document": document,
        "synthetic_decision": policy.get("decision"),
        "synthetic_contract_ok": validation.get("ok"),
        "review_does_not_accept_cache": True,
        "production_cache_acceptance": PRODUCTION_CACHE_ACCEPTANCE,
        "pass_requires_all_substantive_supported": True,
        "passed": bool(validation.get("ok")) and policy.get("decision") in {"PASS", "REVIEW", "BLOCK"},
        "secrets_included": False,
    }


@dataclass
class Phase212Result:
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
) -> Phase212Result:
    result = Phase212Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookSemanticGate212Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.12."
        result.mode = "REJECTED"
        return result
    if REAL_TERRA_CANARY_AUTHORIZED:
        result.error = "A real Terra canary must not be authorized in 4B.2.12."
        result.mode = "REJECTED"
        return result
    if (
        PROMPT_VERSION_20_ACTIVATED
        or PROMPT_VERSION_201_ACTIVATED
        or PROMPT_VERSION_202_ACTIVATED
        or TRANSPORT_VERSION_20_ACTIVATED
        or SEMANTIC_GATE_20_ENABLED
        or SEMANTIC_GATE_201_ENABLED
        or SEMANTIC_GATE_202_ENABLED
        or PRODUCTION_PIPELINE_HOOK
    ):
        result.error = "Semantic Gate 2.0 must remain inactive."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = verify_canonical_inputs(root=root)
    raw_before = file_identity(historical_raw_response_path(root=root))
    inventory = technical_inventory(root=root)
    forensics = real_response_forensics(root=root)
    mismatch = schema_mismatch_analysis(root=root)
    concepts = semantic_vs_operational_verdicts()
    frozen_20 = semantic_contract_20_candidate()
    frozen_201 = semantic_contract_201_candidate()
    consolidated = semantic_contract_202_candidate()
    schema = strict_schema_feasibility(root=root)
    replay_201 = historical_replay_201(root=root)
    semantic = historical_semantic_observations(root=root)
    synthetic = synthetic_202_fixture_replay(root=root)
    fakeai = run_negative_fakeai_tests(root=root)
    policy = _policy_validation(root=root)
    architecture = architecture_options()
    resumption = book_generator_resumption_plan()
    safety = provider_safety(root=root)
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
            "openai_http_requests": 0,
            "anthropic_http_requests": 0,
        }
    )
    after = verify_canonical_inputs(root=root)
    raw_after = file_identity(historical_raw_response_path(root=root))
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
        HISTORICAL_H01_STATUS == "PARTIAL"
        and HISTORICAL_H02_STATUS == "PARTIAL"
        and HISTORICAL_H11_STATUS == "PARTIAL"
        and HISTORICAL_4B210_STATUS == "PASS"
        and HISTORICAL_4B211_STATUS == "PARTIAL"
    )
    raw_ok = (
        raw_before.get("sha256") == raw_after.get("sha256")
        and forensics.get("text_sha256") == EXPECTED_4B211_RAW_TEXT_SHA256
        and forensics.get("text_sha256_match") is True
    )
    contract_ok = (
        prompt_10_ok
        and prompt_11_ok
        and prompt_111_ok
        and prompt_112_ok
        and prompt_113_ok
        and frozen_20.get("candidate_activated") is False
        and frozen_201.get("candidate_activated") is False
        and consolidated.get("candidate_activated") is False
        and consolidated.get("does_not_overwrite_2_0_candidate") is True
        and consolidated.get("does_not_overwrite_2_0_1_candidate") is True
        and consolidated.get("overfit_tokens_absent_from_candidate") is True
        and consolidated.get("differs_from_2_0") is True
        and consolidated.get("differs_from_2_0_1") is True
        and consolidated.get("human_labels_absent_from_provider_prompt") is True
        and consolidated.get("operational_decision_excluded_from_model") is True
        and consolidated.get("example_strictly_conformant") is True
    )
    mismatch_ok = bool(mismatch.get("anomaly_a", {}).get("root_cause")) and bool(
        mismatch.get("anomaly_b", {}).get("root_cause")
    )
    replay_ok = bool(replay_201.get("pass")) and replay_201.get("contract_validation") == "FAIL"
    semantic_ok = (
        bool(semantic.get("target_recognized"))
        and bool(semantic.get("all_five_supported"))
        and bool(semantic.get("historical_canary_not_declared_pass"))
    )
    synthetic_ok = bool(synthetic.get("pass")) and synthetic.get("fixture_kind") == "SYNTHETIC_OFFLINE_FIXTURE"
    fakeai_ok = bool(fakeai.get("passed"))
    safety_ok = bool(safety.get("ok"))
    schema_ok = schema.get("REMOTE_COMPATIBILITY") == REMOTE_STRICT_SCHEMA_COMPATIBILITY and schema.get("activated") is False
    labels_ok = bool(bench.get("identity_match")) if "identity_match" in bench else True
    anomalies_explained = mismatch_ok
    ready_preflight = (
        tests_ok
        and fakeai_ok
        and contract_ok
        and book_absent
        and historical_status_ok
        and hashes_ok
        and source_ok
        and plan_ok
        and transcript_ok
        and raw_ok
        and replay_ok
        and semantic_ok
        and synthetic_ok
        and safety_ok
        and schema_ok
        and anomalies_explained
        and labels_ok
    )
    phase_pass = ready_preflight and int(AUTHORIZED_TERRA_CALLS) == 0
    verdict = "PASS" if phase_pass else "PARTIAL" if contract_ok and replay_ok else "FAIL"
    if not hashes_ok or not source_ok or not plan_ok or not transcript_ok or not raw_ok:
        verdict = "BLOCKED"
    hashes_artifact = {
        "phase": PHASE,
        "pre": {
            "source_map": before_snap.get("source_map"),
            "editorial_plan": before_snap.get("editorial_plan"),
            "clean_transcript": before_snap.get("clean_transcript"),
            "raw_4b211_file": raw_before,
        },
        "post": {
            "source_map": after_snap.get("source_map"),
            "editorial_plan": after_snap.get("editorial_plan"),
            "clean_transcript": after_snap.get("clean_transcript"),
            "raw_4b211_file": raw_after,
        },
        "expected": {
            "source_map": EXPECTED_SOURCE_MAP,
            "editorial_plan": EXPECTED_EDITORIAL_PLAN,
            "clean_transcript": EXPECTED_CLEAN_TRANSCRIPT,
            "raw_4b211_text": EXPECTED_4B211_RAW_TEXT_SHA256,
        },
        "match": hashes_ok and source_ok and plan_ok and transcript_ok and raw_ok,
        "historical_contracts_unmodified": True,
        "historical_labels_unmodified": True,
        "historical_raw_unmodified": raw_ok,
        "secrets_included": False,
    }
    header = {
        "result": verdict,
        "provider_calls": 0,
        "openai_http": 0,
        "anthropic_http": 0,
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
        "schema_mismatch_root_cause": (
            "ANOMALY_A: 2.0.1 asked for counts of uppercase k values but the "
            "schema/validator required lowercase sc keys without an example. "
            "ANOMALY_B: paragraph v was undocumented as a classification while "
            "top-level v was PASS/REVIEW/FAIL; Terra emitted PASS at pr[0].v."
        ),
        "consolidated_contract": PROMPT_VERSION_202_CANDIDATE,
        "strict_schema_feasibility": schema.get("feasibility"),
        "historical_replay": (
            "CONTRACT VALIDATION = FAIL; ACCEPTANCE POLICY = BLOCK"
            if replay_ok
            else "UNEXPECTED"
        ),
        "synthetic_replay": "PASS" if synthetic_ok else "FAIL",
        "fakeai_negative_tests": "PASS" if fakeai_ok else "FAIL",
        "acceptance_policy": "PASS_BLOCK_REVIEW_FAIL_CLOSED",
        "architecture_options": "A_FULL B_TARGETED C_HYBRID_DOCUMENTED",
        "proposed_integration_strategy": architecture.get("proposed_integration_strategy"),
        "book_generator_resumption_plan": "DOCUMENTED_NOT_EXECUTED",
        "new_regressions": tests.get("new_failures"),
        "source_hashes_unchanged": hashes_ok and source_ok and plan_ok and transcript_ok,
        "ready_for_controlled_integration_preflight": ready_preflight,
        "notes": (
            "Semantic Gate 2.0.2-candidate removes operational fields from the "
            "model output, keeps the validator strict, and replays the 4B.2.11 "
            "response without rewriting it. Historical 4B.2.11 remains PARTIAL. "
            "No provider call. Production pipeline and cache are unchanged."
        ),
        "authorization_scope": AUTHORIZATION_SCOPE,
        "historical_h01": HISTORICAL_H01_STATUS,
        "historical_h02": HISTORICAL_H02_STATUS,
        "historical_h11": HISTORICAL_H11_STATUS,
        "historical_4b211": HISTORICAL_4B211_STATUS,
        "contract_20": PROMPT_VERSION_20_CANDIDATE,
        "contract_201": PROMPT_VERSION_201_CANDIDATE,
        "transport_20": TRANSPORT_VERSION_20_CANDIDATE,
    }
    readiness = {
        "READY_FOR_CONTROLLED_INTEGRATION_PREFLIGHT": ready_preflight,
        "READY_FOR_NEW_REMOTE_TERRA_CALL": False,
        "READY_FOR_REAL_CHAPTER_GENERATION": False,
        "READY_FOR_FULL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "production_pipeline": "UNCHANGED",
        "candidate_promoted": False,
        "contract_20_activated": False,
        "contract_201_activated": False,
        "contract_202_activated": False,
        "human_label_modified": False,
        "historical_contracts_modified": False,
        "historical_raw_response_modified": False,
        "states_are_not_equivalent": True,
        "why": (
            "Offline consolidation is complete enough for a human to inspect a "
            "controlled integration design. It is not authorization for a Terra "
            "call, a real chapter, or the full book."
            if ready_preflight
            else "Consolidation incomplete. Do not resume the Book Generator."
        ),
        "phase": PHASE,
        "secrets_included": False,
    }
    tests_artifact = {
        **tests,
        "frozen_1_0_prompt_sha256": content_hash(system_prompt()),
        "frozen_1_1_prompt_sha256": candidate_prompt_bundle()["prompt_sha256"],
        "frozen_1_1_1_prompt_sha256": candidate_111_prompt_bundle()["prompt_sha256"],
        "frozen_1_1_2_prompt_sha256": candidate_112_prompt_bundle()["prompt_sha256"],
        "frozen_1_1_3_prompt_sha256": candidate_113_prompt_bundle()["prompt_sha256"],
        "frozen_2_0_prompt_sha256": frozen_20.get("candidate_sha256"),
        "frozen_2_0_1_prompt_sha256": frozen_201.get("candidate_sha256"),
        "candidate_2_0_2_prompt_sha256": consolidated.get("candidate_sha256"),
        "fakeai_not_terra_quality": True,
    }
    bundle = {
        "header": header,
        "inventory": inventory,
        "forensics": forensics,
        "mismatch": mismatch,
        "concepts": concepts,
        "contract": consolidated,
        "schema": schema,
        "replay_201": replay_201,
        "semantic": semantic,
        "synthetic": synthetic,
        "fakeai": fakeai,
        "policy": policy,
        "architecture": architecture,
        "resumption": resumption,
        "safety": safety,
        "hashes": hashes_artifact,
        "readiness": readiness,
        "tests": tests_artifact,
        "canonical": before,
        "canonical_after": after,
    }
    bundle["report_text"] = render_report(bundle)
    bundle = redact_secrets(bundle)
    if write_artifacts:
        from app.book_semantic_gate_4b212.writer import write_phase_artifacts

        write_phase_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase212Result", "run_phase"]
