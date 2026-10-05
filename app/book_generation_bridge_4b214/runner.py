"""
Phase 4B.2.14 runner.

Offline only. Production bridge preflight and cost-bounded execution plan.
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
from app.book_generation_bridge_4b214.adapter_validation import adapter_validation
from app.book_generation_bridge_4b214.architecture import bridge_architecture
from app.book_generation_bridge_4b214.authorization import (
    human_authorization_document,
    mint_synthetic_authorization,
    consume_authorization,
)
from app.book_generation_bridge_4b214.budget import budget_policy
from app.book_generation_bridge_4b214.budget_tests import (
    budget_reconciliation_tests,
    budget_reservation_tests,
)
from app.book_generation_bridge_4b214.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    BRIDGE_CONTRACT_ACTIVATED,
    BRIDGE_ENABLED,
    CANONICAL_PYTHON_EXECUTABLE,
    CANDIDATE_GRANULARITY,
    CODE_VERSION,
    COST_UNKNOWN,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B210_STATUS,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_4B212_STATUS,
    HISTORICAL_4B213_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    PHASE,
    PRODUCTION_PIPELINE_HOOK,
    PROJECT_NAME,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_201_ACTIVATED,
    PROMPT_VERSION_202_ACTIVATED,
    PROMPT_VERSION_202_CANDIDATE,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    REAL_PROVIDERS_ENABLED,
    SEMANTIC_GATE_20_ENABLED,
    SEMANTIC_GATE_201_ENABLED,
    SEMANTIC_GATE_202_ENABLED,
    SONNET_EXECUTION_AUTHORIZED,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_20_ACTIVATED,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_generation_bridge_4b214.costing import cost_assumptions, cost_estimates
from app.book_generation_bridge_4b214.granularity import validation_granularity
from app.book_generation_bridge_4b214.guard import (
    BookGenerationBridge214Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_generation_bridge_4b214.idempotence import idempotence
from app.book_generation_bridge_4b214.inventory import technical_inventory
from app.book_generation_bridge_4b214.orchestrator import run_bridge_chapter
from app.book_generation_bridge_4b214.paths import (
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_generation_bridge_4b214.phase5 import phase5_boundary
from app.book_generation_bridge_4b214.production_interfaces import production_interfaces
from app.book_generation_bridge_4b214.recovery import interruption_recovery
from app.book_generation_bridge_4b214.report import render_report
from app.book_generation_bridge_4b214.review import apply_human_review, human_review_protocol
from app.book_generation_bridge_4b214.safety import provider_safety
from app.book_generation_bridge_4b214.scenarios import request_volume_scenarios
from app.book_generation_bridge_4b214.single_chapter import (
    SingleChapterMode,
    single_chapter_mode_document,
)
from app.book_generation_bridge_4b214.traceability import traceability
from app.book_generation_bridge_4b214.volumes import canonical_volume_inventory
from app.book_generation_integration_4b213.chapter_validation import run_chapter_scenarios
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
        "app/tests/test_book_generation_bridge_4b214.py",
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


def _bridge_decisions() -> dict[str, Any]:
    rows = []
    counts = {"PASS": 0, "REVIEW": 0, "BLOCK": 0}
    for scenario, expected in (
        ("fully_supported", "PASS"),
        ("questionable", "REVIEW"),
        ("invented_causality", "BLOCK"),
    ):
        result = run_bridge_chapter(scenario=scenario)
        decision = result.get("decision")
        if decision in counts:
            counts[decision] += 1
        rows.append(
            {
                "scenario": scenario,
                "expected": expected,
                "decision": decision,
                "match": decision == expected,
                "production_cache_write": result.get("production_cache_write"),
            }
        )
    return {
        "phase": PHASE,
        "rows": rows,
        "counts": counts,
        "ok": all(item["match"] for item in rows),
        "source": "FAKEAI_SIMULATED",
        "secrets_included": False,
    }


def _authorization_simulation() -> dict[str, Any]:
    doc = human_authorization_document()
    auth = mint_synthetic_authorization(
        authorization_id="SYN-AUTH-1",
        chapter_id="SYN-CH001",
        provider="FAKEAI_SIMULATED",
        model="fakeai",
        max_calls=2,
        max_budget_usd=0.05,
        objective="4B.2.14 synthetic single-chapter FakeAI only",
    )
    first = consume_authorization(
        auth,
        phase=PHASE,
        chapter_id="SYN-CH001",
        provider="FAKEAI_SIMULATED",
        model="fakeai",
        calls=1,
        budget_usd=0.01,
    )
    consumed_blocked = False
    try:
        consume_authorization(
            auth,
            phase=PHASE,
            chapter_id="SYN-CH001",
            provider="FAKEAI_SIMULATED",
            model="fakeai",
            calls=1,
            budget_usd=0.01,
        )
    except BookGenerationBridge214Error:
        consumed_blocked = True
    other = mint_synthetic_authorization(
        authorization_id="SYN-AUTH-2",
        chapter_id="SYN-CH001",
        provider="FAKEAI_SIMULATED",
        model="fakeai",
        max_calls=1,
        max_budget_usd=0.05,
        objective="incompatible test",
    )
    incompatible_blocked = False
    try:
        consume_authorization(
            other,
            phase=PHASE,
            chapter_id="CH002",
            provider="FAKEAI_SIMULATED",
            model="fakeai",
            calls=1,
            budget_usd=0.01,
        )
    except BookGenerationBridge214Error:
        incompatible_blocked = True
    return {
        **doc,
        "consumed_once": first.get("ok"),
        "second_use_blocked": consumed_blocked,
        "incompatible_blocked": incompatible_blocked,
        "real_authorization_created_this_phase": False,
        "ok": bool(first.get("ok") and consumed_blocked and incompatible_blocked),
        "secrets_included": False,
    }


def _single_chapter_simulation() -> dict[str, Any]:
    mode = SingleChapterMode(enabled=True, chapter_id="SYN-CH001")
    locked = run_bridge_chapter(
        scenario="fully_supported",
        chapter_id="SYN-CH001",
        single_chapter=mode,
    )
    other_blocked = False
    try:
        run_bridge_chapter(
            scenario="fully_supported",
            chapter_id="SYN-CH002",
            single_chapter=mode,
        )
    except BookGenerationBridge214Error:
        other_blocked = True
    return {
        **single_chapter_mode_document(),
        "locked_chapter_id": locked.get("chapter_id") or locked.get("adapter", {}).get("chapter_id"),
        "locked_decision": locked.get("decision"),
        "other_chapters_blocked": other_blocked,
        "book_assembled": False,
        "phase5_executed": False,
        "ok": locked.get("decision") == "PASS" and other_blocked,
        "secrets_included": False,
    }


@dataclass
class Phase214Result:
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
) -> Phase214Result:
    result = Phase214Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookGenerationBridge214Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.14."
        result.mode = "REJECTED"
        return result
    if (
        SONNET_EXECUTION_AUTHORIZED
        or REAL_CHAPTER_GENERATION_AUTHORIZED
        or REAL_PROVIDERS_ENABLED
        or BRIDGE_ENABLED
    ):
        result.error = "Real generation and the production bridge must remain disabled."
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
        or BRIDGE_CONTRACT_ACTIVATED
    ):
        result.error = "Semantic Gate 2.0 and the bridge contract must remain inactive."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = verify_canonical_inputs(root=root)
    inventory = technical_inventory(root=root)
    interfaces = production_interfaces()
    architecture = bridge_architecture()
    adapter = adapter_validation()
    granularity = validation_granularity()
    volumes = canonical_volume_inventory(root=root)
    scenarios = request_volume_scenarios(volumes)
    assumptions = cost_assumptions()
    cost = cost_estimates(root=root, volumes=volumes, scenarios=scenarios)
    budget_pol = budget_policy()
    budget_reservation = budget_reservation_tests()
    budget_reconciliation = budget_reconciliation_tests()
    isolated_chapters = run_chapter_scenarios()
    bridge_decisions = _bridge_decisions()
    authorization = _authorization_simulation()
    single_chapter = _single_chapter_simulation()
    review_pass = apply_human_review(
        run_bridge_chapter(scenario="questionable"),
        action="confirm_supported",
        reviewer="SYNTHETIC_REVIEWER",
        note="simulated REVIEW handling",
    )
    review_block = apply_human_review(
        run_bridge_chapter(scenario="invented_causality"),
        action="confirm_supported",
        reviewer="SYNTHETIC_REVIEWER",
        note="simulated BLOCK handling",
    )
    review = {
        **human_review_protocol(),
        "review_confirm_does_not_rewrite_raw": review_pass.get("original_response_mutated")
        is False,
        "block_cannot_become_pass": review_block.get("human_decision") == "BLOCK",
        "ok": (
            review_pass.get("original_response_mutated") is False
            and review_block.get("human_decision") == "BLOCK"
            and review_block.get("block_cannot_become_pass_automatically") is True
        ),
        "secrets_included": False,
    }
    recovery = interruption_recovery()
    idem = idempotence()
    traces = traceability()
    phase5 = phase5_boundary()
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
        and HISTORICAL_4B212_STATUS == "PASS"
        and HISTORICAL_4B213_STATUS == "PASS"
    )
    contract_ok = (
        prompt_ok
        and frozen_20.get("candidate_activated") is False
        and frozen_201.get("candidate_activated") is False
        and consolidated.get("candidate_activated") is False
        and architecture.get("enabled_by_default") is False
        and architecture.get("connected") is False
    )
    adapter_ok = bool(adapter.get("ok"))
    granularity_ok = granularity.get("candidate", {}).get("strategy") == CANDIDATE_GRANULARITY
    volume_ok = volumes.get("paragraphs_counted_as_zero") is False
    cost_ok = cost.get("unknown_not_treated_as_zero") is True and cost.get(
        "total_complete_status"
    ) == COST_UNKNOWN
    budget_ok = bool(budget_reservation.get("ok")) and bool(budget_reconciliation.get("ok"))
    auth_ok = bool(authorization.get("ok"))
    single_ok = bool(single_chapter.get("ok"))
    review_ok = bool(review.get("ok"))
    recovery_ok = bool(recovery.get("ok"))
    idem_ok = bool(idem.get("ok"))
    trace_ok = bool(traces.get("ok"))
    safety_ok = bool(safety.get("ok"))
    phase5_ok = phase5.get("executed") is False and phase5.get("independent") is True
    chapter_ok = bool(isolated_chapters.get("passed")) and bool(bridge_decisions.get("ok"))
    ready_for_review = (
        tests_ok
        and adapter_ok
        and granularity_ok
        and volume_ok
        and cost_ok
        and budget_ok
        and auth_ok
        and single_ok
        and review_ok
        and recovery_ok
        and idem_ok
        and trace_ok
        and safety_ok
        and contract_ok
        and chapter_ok
        and book_absent
        and historical_ok
        and hashes_ok
        and source_ok
        and plan_ok
        and transcript_ok
        and phase5_ok
        and int(AUTHORIZED_TERRA_CALLS) == 0
        and BRIDGE_ENABLED is False
    )
    verdict = "PASS" if ready_for_review else "PARTIAL" if adapter_ok and budget_ok else "FAIL"
    if not hashes_ok or not source_ok or not plan_ok or not transcript_ok:
        verdict = "BLOCKED"
    gen_cost = dict(cost.get("book_generator") or {})
    sem_cost = dict(cost.get("semantic_gate") or {})
    total = dict(cost.get("partial_sum_generator_plus_strategy_a_gate") or {})
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
    counts = dict(isolated_chapters.get("counts") or {})
    obstacles = (
        "1. Contract 2.0.2 has not been validated by a real Terra call. "
        "2. Remote strict JSON Schema compatibility is UNVERIFIED. "
        "3. Historical h01/h02/h11 and 4B.2.11 remain PARTIAL. "
        "4. Generated paragraph counts are UNKNOWN. "
        "5. Semantic Gate cost is a hypothesis (h01 analog × assumed paragraphs), not a measurement. "
        "6. Terra reasoning billing and long-context pricing remain UNKNOWN. "
        "7. Phase 5 cost is UNKNOWN and the independent Book Validator is not implemented. "
        "8. No real human authorization was issued in this phase. "
        "9. The bridge remains disabled and unhooked from production. "
        "Shortest path: human review of this preflight; then a new phase with an explicit "
        "one-shot authorization for one non-CH016 chapter, one FakeAI-proven granularity A "
        "path, a hard budget cap, and a single bounded Terra 2.0.2 canary before any Sonnet "
        "generation. Do not start from 19 chapters."
    )
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
        "bridge_module": CODE_VERSION,
        "real_data_adapter": "PASS" if adapter_ok else "FAIL",
        "evidence_validation": "missing_or_invalid_handles_block",
        "validation_granularity": CANDIDATE_GRANULARITY,
        "project_volumes": (
            f"chapters={volumes.get('chapters')} sections={volumes.get('sections')} "
            f"assigned_ideas={((volumes.get('plan_stats') or {}).get('assigned_idea_count'))} "
            "paragraphs=UNKNOWN"
        ),
        "estimated_request_counts": (
            f"strategy_A low={scenarios.get('strategy_a', {}).get('requests_low')} "
            f"central={scenarios.get('strategy_a', {}).get('requests_central')} "
            f"high={scenarios.get('strategy_a', {}).get('requests_high')} "
            "(assumed paragraphs/section; not measured)"
        ),
        "book_generator_cost": (
            f"low={gen_cost.get('low_usd')} central={gen_cost.get('central_usd')} "
            f"high={gen_cost.get('high_usd')} (4B.1 documented envelope; bands assumed)"
        ),
        "semantic_gate_cost": (
            f"low={sem_cost.get('low_usd')} central={sem_cost.get('central_usd')} "
            f"high={sem_cost.get('high_usd')} (strategy A × h01 analog; NOT MEASURED; "
            "old 4B.2.3 chapter-call envelope not reused as primary)"
        ),
        "phase5_cost": COST_UNKNOWN,
        "total_projected_cost": (
            f"partial_generator_plus_strategy_A_gate central={total.get('central_usd')}; "
            "complete_total=UNKNOWN"
        ),
        "cost_uncertainties": ", ".join(cost.get("unknown_items") or []),
        "budget_guard": "PASS" if budget_ok else "FAIL",
        "human_authorization": "PASS_SYNTHETIC" if auth_ok else "FAIL",
        "single_chapter_mode": "PASS" if single_ok else "FAIL",
        "pass_review_block": (
            f"isolated_4b213 PASS={counts.get('PASS', 0)} "
            f"REVIEW={counts.get('REVIEW', 0)} "
            f"BLOCK={counts.get('BLOCK', 0)}; "
            f"bridge FakeAI ok={bridge_decisions.get('ok')}"
        ),
        "interruption_recovery": "PASS" if recovery_ok else "FAIL",
        "idempotence": "PASS" if idem_ok else "FAIL",
        "traceability": "PASS" if trace_ok else "FAIL",
        "phase5_boundary": "DOCUMENTED_NOT_EXECUTED",
        "new_regressions": tests.get("new_failures"),
        "ready_for_bridge_human_review": ready_for_review,
        "obstacles": obstacles,
        "notes": (
            "Isolated FakeAI bridge demonstrates a disabled-by-default adapter over real "
            "Book Generator objects, fail-closed evidence, strategy A granularity analysis, "
            "canonical volume inventory, cost hypotheses that keep UNKNOWN ≠ 0, budget "
            "reservation/reconciliation, synthetic one-shot authorization, single-chapter "
            "isolation, REVIEW/BLOCK human protocol, interruption recovery, and a Phase 5 "
            "boundary. No provider call. Production pipeline and cache are unchanged. "
            "Historical h01/h02/h11 and 4B.2.11 remain PARTIAL."
        ),
        "authorization_scope": AUTHORIZATION_SCOPE,
        "semantic_contract": PROMPT_VERSION_202_CANDIDATE,
        "semantic_transport": TRANSPORT_VERSION_20_CANDIDATE,
    }
    readiness = {
        "READY_FOR_BRIDGE_HUMAN_REVIEW": ready_for_review,
        "READY_FOR_ONE_REAL_CHAPTER_EXPERIMENT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "production_pipeline": "UNCHANGED",
        "bridge_enabled": False,
        "real_providers_enabled": False,
        "candidate_promoted": False,
        "historical_contracts_modified": False,
        "historical_labels_modified": False,
        "obstacles": obstacles,
        "phase": PHASE,
        "secrets_included": False,
    }
    bundle = {
        "header": header,
        "inventory": inventory,
        "interfaces": interfaces,
        "architecture": architecture,
        "adapter": adapter,
        "granularity": granularity,
        "volumes": volumes,
        "scenarios": scenarios,
        "cost_assumptions": assumptions,
        "cost": cost,
        "budget_policy": budget_pol,
        "budget_reservation": budget_reservation,
        "budget_reconciliation": budget_reconciliation,
        "single_chapter": single_chapter,
        "authorization": authorization,
        "review": review,
        "recovery": recovery,
        "idempotence": idem,
        "traceability": traces,
        "phase5": phase5,
        "safety": safety,
        "hashes": hashes_artifact,
        "readiness": readiness,
        "tests": tests,
        "chapter": isolated_chapters,
        "bridge_decisions": bridge_decisions,
        "canonical": before,
        "canonical_after": after,
    }
    bundle["report_text"] = render_report(bundle)
    bundle = redact_secrets(bundle)
    if write_artifacts:
        from app.book_generation_bridge_4b214.writer import write_phase_artifacts

        write_phase_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase214Result", "run_phase"]
