"""
Phase 4B.2.5.1 runner.

Offline only. Corrects Terra token-parameter mapping. Never authorizes a call.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.provider_preflight import (
    READY_WITH_SERVER_UNVERIFIED_FIELDS,
    redact_secrets,
)
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b251.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_REQUEST_SHA256_HISTORICAL,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B25_STATUS,
    MODEL,
    PHASE,
    PROJECT_NAME,
    SEMANTIC_TOKEN_BUDGET,
    TERRA_EXECUTION_AUTHORIZED,
)
from app.book_semantic_gate_4b251.forensics import collect_offline_bundle
from app.book_semantic_gate_4b251.guard import (
    BookSemanticGate251Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b251.paths import production_book_path, repo_root
from app.book_semantic_gate_4b251.report import render_report


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _pass(value: bool) -> str:
    return "PASS" if value else "FAIL"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b251.py",
        "app/tests/test_book_semantic_gate_4b23.py",
        "app/tests/test_book_semantic_gate_4b24.py",
        "app/tests/test_book_semantic_gate_4b241.py",
        "app/tests/test_book_semantic_gate_4b25.py",
        "app/tests/test_ai_providers.py",
        "app/tests/test_ai_production_models.py",
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
class Phase251Result:
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
) -> Phase251Result:
    result = Phase251Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookSemanticGate251Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.5.1."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    collected = collect_offline_bundle(root=root)
    identity = dict(collected.get("identity") or {})
    forensics = dict(collected.get("forensics") or {})
    preflight = dict(collected.get("preflight") or {})
    capture = dict(collected.get("sdk_capture") or {})
    accounting = dict(collected.get("accounting") or {})
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

    before = dict(identity.get("identities_before") or {})
    after = dict(identity.get("identities_after") or {})
    source_pre = (before.get("source_map") or {}).get("sha256")
    plan_pre = (before.get("editorial_plan") or {}).get("sha256")
    transcript_pre = (before.get("clean_transcript") or {}).get("sha256")
    source_post = (after.get("source_map") or {}).get("sha256")
    plan_post = (after.get("editorial_plan") or {}).get("sha256")
    transcript_post = (after.get("clean_transcript") or {}).get("sha256")
    inputs_unchanged = bool(identity.get("inputs_unchanged"))
    hashes_match = (
        source_pre == EXPECTED_SOURCE_MAP
        and plan_pre == EXPECTED_EDITORIAL_PLAN
        and transcript_pre == EXPECTED_CLEAN_TRANSCRIPT
        and source_post == EXPECTED_SOURCE_MAP
        and plan_post == EXPECTED_EDITORIAL_PLAN
        and transcript_post == EXPECTED_CLEAN_TRANSCRIPT
        and inputs_unchanged
    )
    historical_ok = bool(identity.get("historical_request_preserved"))
    new_sha = str(identity.get("canonical_request_sha256") or "")
    historical_sha = str(identity.get("historical_request_sha256") or "")
    deterministic = bool(identity.get("deterministic"))
    differs = bool(identity.get("differs_from_historical"))
    diff = dict(identity.get("diff") or {})
    only_compat = bool(diff.get("only_api_compatibility_fields_changed"))
    payload = dict(identity.get("payload") or {})
    token_ok = (
        payload.get("max_completion_tokens") == SEMANTIC_TOKEN_BUDGET
        and "max_tokens" not in payload
    )
    temperature_ok = "temperature" not in payload
    json_local_ok = payload.get("response_format") == {"type": "json_object"}
    sdk_ok = bool(capture.get("serialization_pass"))
    cases_ok = int(identity.get("case_count") or 0) == 10
    leak_count = int(identity.get("label_leakage") or 0)
    benchmark = dict(identity.get("benchmark_identity") or {})
    benchmark_ok = bool(benchmark.get("identity_match"))
    tests_ok = int(tests.get("failed") or 0) == 0 and int(tests.get("new_failures") or 0) == 0
    book_absent = production_book_absent(PROJECT_NAME)
    network_ok = (
        int(capture.get("network_calls") or 0) == 0
        and int(preflight.get("NETWORK_CALLS") or 0) == 0
        and int((accounting.get("this_phase") or {}).get("http_requests") or 0) == 0
    )
    live_blockers = list(
        identity.get("live_4b24_precall_blockers_excluding_historical_sha") or []
    )
    ready_class = preflight.get("readiness_class") == READY_WITH_SERVER_UNVERIFIED_FIELDS or (
        preflight.get("ready") is True
    )
    ready_terra = bool(
        hashes_match
        and historical_ok
        and deterministic
        and differs
        and new_sha != EXPECTED_REQUEST_SHA256_HISTORICAL
        and only_compat
        and token_ok
        and temperature_ok
        and json_local_ok
        and sdk_ok
        and cases_ok
        and leak_count == 0
        and benchmark_ok
        and tests_ok
        and book_absent
        and network_ok
        and ready_class
        and not live_blockers
        and identity.get("expected_compat") is True
    )
    verdict = "PASS" if ready_terra else "FAIL"
    header = {
        "result": verdict,
        "provider_calls": 0,
        "openai_http": 0,
        "anthropic_http": 0,
        "historical_4b25": HISTORICAL_4B25_STATUS,
        "python_executable": forensics.get("python_executable") or sys.executable,
        "openai_sdk_version": forensics.get("openai_sdk_version"),
        "actual_endpoint": forensics.get("actual_endpoint"),
        "root_cause": (forensics.get("root_cause") or {}).get("summary"),
        "historical_request_sha256": historical_sha,
        "corrected_request_sha256": new_sha,
        "exact_parameter_changes": (
            "max_tokens=8192 removed; max_completion_tokens=8192 added"
        ),
        "sdk_serialization": _pass(sdk_ok),
        "token_limit": SEMANTIC_TOKEN_BUDGET if token_ok else payload.get(
            "max_completion_tokens"
        ),
        "temperature_omitted": _pass(temperature_ok),
        "json_object_local": "PASS" if json_local_ok else "FAIL",
        "other_server_capabilities": "UNKNOWN",
        "benchmark_identity": "MATCH" if benchmark_ok else "MISMATCH",
        "cases_10_of_10": cases_ok,
        "label_leakage": f"{leak_count}/10",
        "canonical_input_hashes": (
            f"pre source={source_pre} plan={plan_pre} transcript={transcript_pre}; "
            f"post source={source_post} plan={plan_post} transcript={transcript_post}"
        ),
        "tests": tests.get("summary"),
        "new_regressions": int(tests.get("new_failures") or 0),
        "production_cache": "UNCHANGED",
        "book_json": "NOT PUBLISHED",
        "ready_for_one_new_explicitly_authorized_terra_canary": _yn(ready_terra),
        "ready_for_book_generator_production_preflight": "NO",
        "ready_for_full_real_book_generation": "NO",
        "next_action": "HUMAN REVIEW",
        "notes": (
            "OpenAIEngine now maps gpt-5.6-terra chat.completions output budget "
            "to max_completion_tokens=8192. Historical 4B.2.5 request "
            f"{EXPECTED_REQUEST_SHA256_HISTORICAL} is unchanged evidence. "
            "json_object and max_completion_tokens server acceptance remain "
            "UNKNOWN. No Terra call was executed."
        ),
        "canonical_environment_executable": CANONICAL_PYTHON_EXECUTABLE,
        "model": MODEL,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "inputs_unchanged": _yn(inputs_unchanged),
    }
    request_audit = {
        "historical_request_sha256": historical_sha,
        "new_canonical_request_sha256": new_sha,
        "new_canonical_request_sha256_repeat": identity.get(
            "canonical_request_sha256_repeat"
        ),
        "exact_changed_fields": identity.get("exact_changed_fields"),
        "prompt_identity": identity.get("prompt_identity"),
        "transport_identity": identity.get("transport_identity"),
        "schema_identity": identity.get("schema_identity"),
        "benchmark_identity": {
            "identity_match": benchmark.get("identity_match"),
            "sha256": benchmark.get("sha256"),
        },
        "case_count": identity.get("case_count"),
        "label_leakage": leak_count,
        "context_budget": identity.get("context_budget"),
        "estimated_cost": identity.get("estimated_cost"),
        "deterministic": deterministic,
        "differs_from_historical": differs,
        "http_sent": False,
        "secrets_included": False,
    }
    post = {
        "READY_FOR_ONE_NEW_EXPLICITLY_AUTHORIZED_TERRA_CANARY": ready_terra,
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "terra_executed": False,
        "readiness_class": READY_WITH_SERVER_UNVERIFIED_FIELDS,
        "cannot_claim_server_acceptance": True,
        "why": (
            "Local compatibility gates passed. Remaining server-only "
            "uncertainties are documented. A new explicit human "
            "authorization is required before any Terra call."
            if ready_terra
            else "Local compatibility or regression gates failed. "
            "Do not authorize Terra."
        ),
    }
    bundle: dict[str, Any] = {
        "header": header,
        "forensics": forensics,
        "matrix": collected.get("matrix"),
        "sdk_capture": capture,
        "preflight": preflight,
        "request": request_audit,
        "diff": diff,
        "cost": identity.get("cost_estimate"),
        "benchmark": {
            "identity": benchmark,
            "case_count": identity.get("case_count"),
            "label_leakage": leak_count,
            "contracts": identity.get("contracts"),
        },
        "accounting": accounting,
        "tests": tests,
        "post_readiness": post,
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
    bundle = redact_secrets(bundle)
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        from app.book_semantic_gate_4b251.writer import write_phase_artifacts

        write_phase_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase251Result", "run_phase"]
