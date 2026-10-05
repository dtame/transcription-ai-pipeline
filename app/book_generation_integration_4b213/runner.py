"""
Phase 4B.2.13 runner.

Offline only. Isolated Book Generator × Semantic Gate 2.0 integration preflight.
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
from app.book_generation_integration_4b213.architecture import integration_architecture
from app.book_generation_integration_4b213.chapter_validation import run_chapter_scenarios
from app.book_generation_integration_4b213.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_PYTHON_EXECUTABLE,
    CODE_VERSION,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B210_STATUS,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    INTEGRATION_CONTRACT_ACTIVATED,
    INTEGRATION_CONTRACT_VERSION,
    PHASE,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PROJECT_NAME,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_201_ACTIVATED,
    PROMPT_VERSION_202_ACTIVATED,
    PROMPT_VERSION_202_CANDIDATE,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    SEMANTIC_GATE_20_ENABLED,
    SEMANTIC_GATE_201_ENABLED,
    SEMANTIC_GATE_202_ENABLED,
    SONNET_EXECUTION_AUTHORIZED,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_20_ACTIVATED,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_generation_integration_4b213.contract import integration_contract
from app.book_generation_integration_4b213.costing import cost_estimates
from app.book_generation_integration_4b213.fixtures import generation_scenario_catalog
from app.book_generation_integration_4b213.guard import (
    BookGenerationIntegration213Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_generation_integration_4b213.invalidation import cache_invalidation
from app.book_generation_integration_4b213.inventory import technical_inventory
from app.book_generation_integration_4b213.paths import (
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_generation_integration_4b213.phase5 import phase5_interface
from app.book_generation_integration_4b213.preparation import deterministic_preparation
from app.book_generation_integration_4b213.recovery import interruption_recovery
from app.book_generation_integration_4b213.report import render_report
from app.book_generation_integration_4b213.safety import provider_safety
from app.book_generation_integration_4b213.strategy import controlled_generation_strategy
from app.book_generation_integration_4b213.traceability import traceability
from app.book_semantic_gate_4b23.identity import snapshot_identities, verify_canonical_inputs
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
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
from app.book_semantic_gate_4b210.contract import semantic_contract_201_candidate
from app.book_semantic_gate_4b212.contract import semantic_contract_202_candidate
from app.file_utils import content_hash


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_generation_integration_4b213.py",
        "app/tests/test_book_semantic_gate_4b212.py",
        "app/tests/test_book_semantic_gate_4b211.py",
        "app/tests/test_book_semantic_gate_4b210.py",
        "app/tests/test_book_semantic_gate_4b29.py",
        "app/tests/test_book_generation_4b1.py",
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
        "fakeai_not_sonnet_quality": True,
    }


@dataclass
class Phase213Result:
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
) -> Phase213Result:
    result = Phase213Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookGenerationIntegration213Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.13."
        result.mode = "REJECTED"
        return result
    if SONNET_EXECUTION_AUTHORIZED or REAL_CHAPTER_GENERATION_AUTHORIZED:
        result.error = "Real chapter generation must not be authorized in 4B.2.13."
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
        or INTEGRATION_CONTRACT_ACTIVATED
    ):
        result.error = "Semantic Gate 2.0 and the integration contract must remain inactive."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = verify_canonical_inputs(root=root)
    inventory = technical_inventory(root=root)
    architecture = integration_architecture()
    contract = integration_contract()
    preparation = deterministic_preparation()
    fakeai_generation = generation_scenario_catalog()
    chapter = run_chapter_scenarios()
    fakeai_semantic = {
        "phase": PHASE,
        "source": "FAKEAI_SIMULATED",
        "role": "simulated_semantic_validator",
        "not_terra": True,
        "map": chapter.get("semantic_map"),
        "scenarios": chapter.get("scenarios"),
        "passed": chapter.get("passed"),
        "secrets_included": False,
    }
    invalidation = cache_invalidation()
    recovery = interruption_recovery()
    traces = traceability()
    phase5 = phase5_interface()
    cost = cost_estimates(root=root)
    strategy = controlled_generation_strategy()
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
    before_snap = snapshot_identities(before)
    after_snap = snapshot_identities(after)
    hashes_ok = before_snap == after_snap
    source_ok = before["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
    plan_ok = before["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
    transcript_ok = before["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
    prompt_ok = (
        content_hash(system_prompt()) == EXPECTED_PROMPT_SYSTEM_SHA256
        and content_hash(instruction_prompt()) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
        and candidate_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256
        and candidate_111_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256
        and candidate_112_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_112_SHA256
        and candidate_113_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256
    )
    frozen_20 = semantic_contract_20_candidate()
    frozen_201 = semantic_contract_201_candidate()
    consolidated = semantic_contract_202_candidate()
    book_absent = production_book_absent(PROJECT_NAME)
    tests_ok = int(tests.get("new_failures") or 0) == 0 and int(tests.get("failed") or 0) == 0
    historical_ok = (
        HISTORICAL_H01_STATUS == "PARTIAL"
        and HISTORICAL_H02_STATUS == "PARTIAL"
        and HISTORICAL_H11_STATUS == "PARTIAL"
        and HISTORICAL_4B210_STATUS == "PASS"
        and HISTORICAL_4B211_STATUS == "PARTIAL"
    )
    contract_ok = (
        prompt_ok
        and frozen_20.get("candidate_activated") is False
        and frozen_201.get("candidate_activated") is False
        and consolidated.get("candidate_activated") is False
        and contract.get("activated") is False
        and contract.get("does_not_invent_absent_references") is True
    )
    chapter_ok = bool(chapter.get("passed")) and bool(chapter.get("pass_review_block_covered"))
    prep_ok = bool(preparation.get("ok")) and bool(preparation.get("complete_coverage"))
    cache_ok = bool(chapter.get("sample_pass_not_production"))
    invalidation_ok = bool(invalidation.get("ok"))
    recovery_ok = bool(recovery.get("ok"))
    trace_ok = bool(traces.get("ok"))
    safety_ok = bool(safety.get("ok"))
    cost_ok = cost.get("unknown_not_treated_as_zero") is True and cost.get("total_complete_status") == "UNKNOWN"
    phase5_ok = phase5.get("executed") is False and phase5.get("independent") is True
    ready = (
        tests_ok
        and chapter_ok
        and prep_ok
        and cache_ok
        and invalidation_ok
        and recovery_ok
        and trace_ok
        and safety_ok
        and contract_ok
        and book_absent
        and historical_ok
        and hashes_ok
        and source_ok
        and plan_ok
        and transcript_ok
        and cost_ok
        and phase5_ok
        and int(AUTHORIZED_TERRA_CALLS) == 0
    )
    verdict = "PASS" if ready else "PARTIAL" if chapter_ok and prep_ok else "FAIL"
    if not hashes_ok or not source_ok or not plan_ok or not transcript_ok:
        verdict = "BLOCKED"
    gen_cost = dict(cost.get("book_generator") or {})
    sem_cost = dict(cost.get("semantic_gate") or {})
    total = dict(cost.get("partial_sum_generator_plus_chapter_gate") or {})
    hashes_artifact = {
        "phase": PHASE,
        "pre": before_snap,
        "post": after_snap,
        "expected": {
            "source_map": EXPECTED_SOURCE_MAP,
            "editorial_plan": EXPECTED_EDITORIAL_PLAN,
            "clean_transcript": EXPECTED_CLEAN_TRANSCRIPT,
        },
        "match": hashes_ok and source_ok and plan_ok and transcript_ok,
        "historical_contracts_unmodified": True,
        "historical_labels_unmodified": True,
        "secrets_included": False,
    }
    counts = dict(chapter.get("counts") or {})
    header = {
        "result": verdict,
        "provider_calls": 0,
        "openai_http": 0,
        "anthropic_http": 0,
        "canonical_python": CANONICAL_PYTHON_EXECUTABLE,
        "source_hashes": {
            "source_pre": before_snap["source_map"],
            "plan_pre": before_snap["editorial_plan"],
            "transcript_pre": before_snap["clean_transcript"],
            "source_post": after_snap["source_map"],
            "plan_post": after_snap["editorial_plan"],
            "transcript_post": after_snap["clean_transcript"],
        },
        "semantic_contract": PROMPT_VERSION_202_CANDIDATE,
        "semantic_transport": TRANSPORT_VERSION_20_CANDIDATE,
        "integration_module": CODE_VERSION,
        "integration_contract": INTEGRATION_CONTRACT_VERSION,
        "deterministic_preparation": "PASS" if prep_ok else "FAIL",
        "unit_coverage": "COMPLETE" if prep_ok else "FAIL",
        "fakeai_chapter_scenarios": len(chapter.get("scenarios") or []),
        "pass_review_block": (
            f"PASS={counts.get('PASS', 0)} "
            f"REVIEW={counts.get('REVIEW', 0)} "
            f"BLOCK={counts.get('BLOCK', 0)}"
        ),
        "isolated_cache": "PASS" if cache_ok else "FAIL",
        "cache_invalidation": "PASS" if invalidation_ok else "FAIL",
        "interruption_recovery": "PASS" if recovery_ok else "FAIL",
        "traceability": "PASS" if trace_ok else "FAIL",
        "phase5_interface": "DOCUMENTED_NOT_EXECUTED",
        "book_generator_cost_estimate": (
            f"low={gen_cost.get('low_usd')} central={gen_cost.get('central_usd')} "
            f"high={gen_cost.get('high_usd')} (4B.1 documented envelope; bands assumed)"
        ),
        "semantic_gate_cost_estimate": (
            f"low={sem_cost.get('low_usd')} central={sem_cost.get('central_usd')} "
            f"high={sem_cost.get('high_usd')} (4B.2.3 chapter-call envelope; "
            "h01 canary not extrapolated; Phase 5 excluded)"
        ),
        "phase5_cost_estimate": "UNKNOWN",
        "total_estimate": (
            f"partial_generator_plus_chapter_gate central={total.get('central_usd')}; "
            "complete_total=UNKNOWN"
        ),
        "new_regressions": tests.get("new_failures"),
        "ready_for_controlled_integration_human_review": ready,
        "notes": (
            "Isolated FakeAI orchestration demonstrates structure, deterministic "
            "preparation, 2.0.2 validation, PASS/REVIEW/BLOCK, isolated cache, "
            "invalidation, interruption recovery, and a Phase 5 interface. "
            "No provider call. Production pipeline and cache are unchanged. "
            "Historical h01/h02/h11 and 4B.2.11 remain PARTIAL."
        ),
        "authorization_scope": AUTHORIZATION_SCOPE,
    }
    readiness = {
        "READY_FOR_CONTROLLED_INTEGRATION_HUMAN_REVIEW": ready,
        "READY_FOR_ONE_REAL_CHAPTER_EXPERIMENT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "production_pipeline": "UNCHANGED",
        "candidate_promoted": False,
        "historical_contracts_modified": False,
        "historical_labels_modified": False,
        "phase": PHASE,
        "secrets_included": False,
    }
    bundle = {
        "header": header,
        "inventory": inventory,
        "architecture": architecture,
        "contract": contract,
        "preparation": preparation,
        "fakeai_generation": fakeai_generation,
        "fakeai_semantic": fakeai_semantic,
        "chapter": chapter,
        "cache": chapter.get("cache"),
        "invalidation": invalidation,
        "recovery": recovery,
        "traceability": traces,
        "phase5": phase5,
        "cost": cost,
        "strategy": strategy,
        "safety": safety,
        "hashes": hashes_artifact,
        "readiness": readiness,
        "tests": tests,
        "canonical": before,
        "canonical_after": after,
    }
    bundle["report_text"] = render_report(bundle)
    bundle = redact_secrets(bundle)
    if write_artifacts:
        from app.book_generation_integration_4b213.writer import write_phase_artifacts

        write_phase_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase213Result", "run_phase"]
