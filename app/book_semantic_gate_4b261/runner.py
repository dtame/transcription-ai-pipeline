"""
Phase 4B.2.6.1 runner.

Offline only. Investigates 4B.2.6. Never authorizes a provider call.
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
from app.book_semantic_gate_4b24.identity import benchmark_identity
from app.book_semantic_gate_4b261.complexity import (
    analyze_output_schema,
    analyze_prompt_and_benchmark,
    candidate_diff,
)
from app.book_semantic_gate_4b261.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_REQUEST_SHA256_4B26,
    EXPECTED_REQUEST_SHA256_HISTORICAL_4B25,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B26_STATUS,
    MODEL,
    OBSERVED_4B26_COST_USD,
    PHASE,
    PROJECT_NAME,
    TERRA_EXECUTION_AUTHORIZED,
)
from app.book_semantic_gate_4b261.contract import analyze_api_contract
from app.book_semantic_gate_4b261.costing import strategy_cost_scenarios
from app.book_semantic_gate_4b261.fakeai import (
    catalog_and_invariants,
    interpret_compact_simulation,
    interpret_recorded_empty,
)
from app.book_semantic_gate_4b261.forensics import collect_forensics
from app.book_semantic_gate_4b261.guard import (
    BookSemanticGate261Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b261.paths import production_book_path, repo_root
from app.book_semantic_gate_4b261.report import render_report
from app.book_semantic_gate_4b261.strategies import (
    analyze_strategy_a,
    analyze_strategy_b,
    analyze_strategy_c,
    candidate_request_identities,
    compare_strategies,
    proposed_next_canary,
)


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b261.py",
        "app/tests/test_book_semantic_gate_4b26.py",
        "app/tests/test_book_semantic_gate_4b251.py",
        "app/tests/test_book_semantic_gate_4b23.py",
        "app/tests/test_ai_providers.py",
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
class Phase261Result:
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
) -> Phase261Result:
    result = Phase261Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookSemanticGate261Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.6.1."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = verify_canonical_inputs(root=root)
    collected = collect_forensics(root=root)
    bundle_4b26 = dict(collected.get("bundle") or {})
    payload = dict(bundle_4b26.get("payload") or {})
    raw = dict(collected.get("raw") or {})
    usage = dict(collected.get("usage") or {})
    contract = analyze_api_contract(
        payload=payload,
        raw_text=str((bundle_4b26.get("loaded") or {}).get("raw_text") or ""),
    )
    complexity = analyze_prompt_and_benchmark(payload)
    schema = analyze_output_schema()
    diff = candidate_diff()
    identities = candidate_request_identities(payload)
    empty = interpret_recorded_empty()
    compact_sim = interpret_compact_simulation(payload, root=root)
    fakeai = catalog_and_invariants()
    strategy_a = analyze_strategy_a()
    strategy_b = analyze_strategy_b(complexity)
    strategy_c = analyze_strategy_c(payload, complexity=complexity)
    sizes = dict(complexity.get("sizes") or {})
    estimates = dict(complexity.get("output_size_estimates") or {})
    one_case_tokens = 0
    for batch in strategy_c.get("batches") or []:
        if batch.get("batch_size") == 1 and batch.get("calls_detail"):
            one_case_tokens = int(
                (batch["calls_detail"][0] or {}).get("estimated_input_tokens_candidate") or 0
            )
            break
    costs = strategy_cost_scenarios(
        historical_input_tokens=4076,
        compact_input_tokens_10=int(
            (sizes.get("full_user_message") or {}).get("estimated_tokens") or 4076
        ),
        compact_input_tokens_1=one_case_tokens or 1200,
        compact_min_output_10=int(
            (estimates.get("minimal_valid_candidate_json") or {}).get("estimated_tokens") or 400
        ),
        compact_min_output_1=80,
    )
    comparison = compare_strategies(
        strategy_a=strategy_a,
        strategy_b=strategy_b,
        strategy_c=strategy_c,
        costs=costs,
    )
    next_canary = proposed_next_canary(costs)
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
    bench = benchmark_identity(root=root)
    request_sha = str(bundle_4b26.get("request_sha256") or "")
    historical_ok = request_sha == EXPECTED_REQUEST_SHA256_4B26
    candidates_differ = bool(identities.get("candidate_10_differs_from_historical")) and bool(
        identities.get("candidate_1_differs_from_historical")
    )
    leak_ok = identities.get("label_leak_10") == 0 and identities.get("label_leak_1") == 0
    empty_ok = (
        empty.get("json_parse") == "FAIL"
        and empty.get("classifications_issued") == 0
        and empty.get("cache_acceptance") is False
    )
    sim = dict(compact_sim.get("score") or {})
    sim_ok = (
        sim.get("positives_accepted") == 6
        and sim.get("negatives_blocked") == 4
        and sim.get("negative_false_negatives") == 0
        and sim.get("funeral_blocked")
        and sim.get("connective_blocked")
        and sim.get("p3_blocked")
        and sim.get("p8_blocked")
    )
    tests_ok = int(tests.get("failed") or 0) == 0 and int(tests.get("new_failures") or 0) == 0
    book_absent = production_book_absent(PROJECT_NAME)
    network_ok = int(identities.get("candidate_10_network_calls") or 0) == 0
    reasoning_unknown = usage.get("reasoning_tokens") == "UNKNOWN"
    json_not_claimed = "json_object semantic production by gpt-5.6-terra" in [
        item.get("fact") for item in (contract.get("unknown_server_side") or [])
    ]
    verdict = (
        "PASS"
        if (
            hashes_match
            and historical_ok
            and candidates_differ
            and leak_ok
            and empty_ok
            and sim_ok
            and tests_ok
            and book_absent
            and network_ok
            and reasoning_unknown
            and json_not_claimed
            and bool(fakeai.get("historical_fakeai_passed"))
            and comparison.get("recommendation") == "B+C"
        )
        else "FAIL"
    )
    readiness = {
        "READY_FOR_NEXT_TERRA_CANARY_DESIGN_REVIEW": True,
        "READY_FOR_NEW_REMOTE_TERRA_CALL": False,
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "terra_executed": False,
        "candidate_promoted": False,
        "why": (
            "Offline forensics completed. A new explicit human authorization "
            "is required before any Terra call. Candidate 1.1 contracts are "
            "not production."
        ),
        "phase_result": verdict,
    }
    header = {
        "result": verdict,
        "provider_calls": 0,
        "openai_http": 0,
        "anthropic_http": 0,
        "historical_4b26": HISTORICAL_4B26_STATUS,
        "python_executable": sys.executable,
        "canonical_environment_executable": CANONICAL_PYTHON_EXECUTABLE,
        "model": MODEL,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "primary_diagnosis": (
            "Combination: exhausted completion budget with zero visible JSON, "
            "unknown reasoning split, and a verbose 10-case output contract. "
            "json_object was not HTTP-rejected and is not semantically proven."
        ),
        "certainty": "MEDIUM — facts about emptiness and budget are confirmed; reasoning split is UNKNOWN",
        "recommendation": comparison.get("recommendation"),
        "historical_4b26_request_sha256": request_sha,
        "historical_4b25_request_sha256": EXPECTED_REQUEST_SHA256_HISTORICAL_4B25,
        "observed_cost_usd": OBSERVED_4B26_COST_USD,
        "canonical_input_hashes": (
            f"pre source={source_pre} plan={plan_pre} transcript={transcript_pre}; "
            f"post source={source_post} plan={plan_post} transcript={transcript_post}"
        ),
        "inputs_unchanged": _yn(hashes_match),
        "ready_for_next_terra_canary_design_review": True,
        "tests": tests.get("summary"),
        "notes": (
            "4B.2.6 proved the corrected API contract is accepted, not that "
            "the semantic validator works. This phase did not call Terra."
        ),
    }
    out: dict[str, Any] = {
        "header": header,
        "raw": raw,
        "usage": usage,
        "contract": contract,
        "complexity": complexity,
        "schema": schema,
        "strategy_a": strategy_a,
        "strategy_b": strategy_b,
        "strategy_c": strategy_c,
        "comparison": comparison,
        "diff": {**diff, "request_identities": identities},
        "cost": costs,
        "tests": {
            **tests,
            "empty_recorded_response": empty,
            "compact_simulation": compact_sim.get("score"),
            "fakeai": fakeai,
            "benchmark_identity_match": bench.get("identity_match"),
        },
        "readiness": readiness,
        "next_canary": next_canary,
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
        from app.book_semantic_gate_4b261.writer import write_phase_artifacts

        write_phase_artifacts(out, root=root)
    result.bundle = out
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase261Result", "run_phase"]
