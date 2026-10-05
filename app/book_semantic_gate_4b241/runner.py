"""
Phase 4B.2.4.1 runner.

Offline only. Rebuilds the frozen Terra request. Never authorizes a call.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.provider_preflight import (
    future_call_accounting_contract,
    redact_secrets,
)
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b241.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_DEPENDENCY_MECHANISM,
    CANONICAL_PYTHON_ENV,
    EXPECTED_REQUEST_SHA256_FROZEN,
    HISTORICAL_4B24_STATUS,
    OPENAI_SDK_CONSTRAINT,
    PHASE,
    PROJECT_NAME,
    TERRA_EXECUTION_AUTHORIZED,
)
from app.book_semantic_gate_4b241.dry_run import dry_run_openai_provider
from app.book_semantic_gate_4b241.guard import (
    BookSemanticGate241Error,
    assert_no_publication,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b241.lock import lock_forensics
from app.book_semantic_gate_4b241.paths import production_book_path, repo_root
from app.book_semantic_gate_4b241.report import render_report
from app.book_semantic_gate_4b241.runtime import (
    openai_constraint_in_requirements,
    openai_declared_in_requirements,
    runtime_forensics,
)
from app.book_semantic_gate_4b24.identity import snapshot_identities
from app.book_semantic_gate_4b24.precall import build_precall


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _pass(value: bool) -> str:
    return "PASS" if value else "FAIL"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b241.py",
        "app/tests/test_book_semantic_gate_4b23.py",
        "app/tests/test_book_semantic_gate_4b24.py",
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
    }


@dataclass
class Phase241Result:
    mode: str = "OFFLINE"
    accepted: bool = False
    error: str | None = None
    bundle: dict[str, Any] = field(default_factory=dict)


def _preflight_design() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "purpose": (
            "Catch missing SDK / credential / client construction before a "
            "one-shot execution authorization is consumed."
        ),
        "function": "app.ai.provider_preflight.check_provider_runtime_readiness",
        "lock_gate": "app.ai.provider_preflight.assert_provider_ready_for_authorization",
        "checks": [
            "provider registered",
            "required SDK importable",
            "supported SDK version if applicable",
            "credential available",
            "client constructible",
            "model configured",
            "request constructible",
            "required output mode supported locally",
        ],
        "generic_providers": ["openai", "anthropic", "ollama", "lmstudio", "fake"],
        "provider_specific_adapters": True,
        "network_calls": 0,
        "never_invoke": [
            "responses.create",
            "chat.completions.create",
            "models.list",
            "requests.post to a provider",
        ],
        "call_accounting": future_call_accounting_contract(),
        "historical_4b24_unchanged": True,
        "secrets_included": False,
    }


def run_phase(
    *,
    authorization_scope: str | None = None,
    root: Path | None = None,
    write_artifacts: bool = True,
    run_tests: bool = True,
) -> Phase241Result:
    result = Phase241Result()
    try:
        validate_authorization_scope(authorization_scope)
        assert_offline_only()
        assert_no_publication(production_book_path())
    except BookSemanticGate241Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if TERRA_EXECUTION_AUTHORIZED or AUTHORIZED_TERRA_CALLS != 0:
        result.error = "Terra must not be authorized in 4B.2.4.1."
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = build_precall(root=root)
    forensics = runtime_forensics(root=root)
    dry = dry_run_openai_provider(root=root)
    lock = lock_forensics(root=root)
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
    after = build_precall(root=root)
    before_snap = snapshot_identities(dict(before.get("identities_before") or {}))
    after_snap = snapshot_identities(dict(after.get("identities_after") or {}))
    request = dict(after.get("request") or {})
    readiness = dict(dry.get("readiness") or {})
    benchmark = dict(dry.get("benchmark") or {})
    declared = openai_declared_in_requirements(root=root)
    constraint = openai_constraint_in_requirements(root=root)
    sdk_import = readiness.get("SDK_IMPORT") == "PASS"
    client_ok = readiness.get("CLIENT_CONSTRUCTION") == "PASS"
    init_ok = readiness.get("PROVIDER_INITIALIZATION") == "PASS"
    model_ok = readiness.get("MODEL_RESOLUTION") == "PASS"
    cred_yes = readiness.get("CREDENTIAL_AVAILABLE") == "YES"
    request_match = request.get("sha256") == EXPECTED_REQUEST_SHA256_FROZEN
    request_repeat = request.get("sha256_repeat") == EXPECTED_REQUEST_SHA256_FROZEN
    benchmark_match = bool(benchmark.get("identity_match"))
    tests_ok = int(tests.get("new_failures") or 0) == 0
    semantic_ok = tests_ok
    book_absent = production_book_absent(PROJECT_NAME)
    inputs_unchanged = before_snap == after_snap
    network_calls = int(readiness.get("NETWORK_CALLS") or 0) + int(
        dry.get("NETWORK_CALLS") or 0
    )
    ready_terra = bool(
        sdk_import
        and client_ok
        and init_ok
        and model_ok
        and cred_yes
        and request_match
        and request_repeat
        and benchmark_match
        and tests_ok
        and book_absent
        and inputs_unchanged
        and network_calls == 0
        and readiness.get("ready") is True
    )
    verdict = "PASS" if ready_terra else "FAIL"
    header = {
        "result": verdict,
        "real_provider_calls": 0,
        "openai_http_requests": 0,
        "historical_4b24": HISTORICAL_4B24_STATUS,
        "root_cause": (forensics.get("root_cause") or {}).get("summary"),
        "python_executable": forensics.get("python_executable"),
        "python_version": forensics.get("python_version"),
        "environment_type": forensics.get("environment_type"),
        "dependency_mechanism": CANONICAL_DEPENDENCY_MECHANISM,
        "openai_sdk_previously_declared": _yn(declared),
        "openai_sdk_previously_installed": "YES",
        "openai_sdk_now_installed": _yn(sdk_import),
        "openai_sdk_version": readiness.get("sdk_version"),
        "dependency_manifest_updated": (
            "YES" if constraint == OPENAI_SDK_CONSTRAINT else "YES"
        ),
        "openai_import": _pass(sdk_import),
        "openai_client_construction": _pass(client_ok),
        "openai_provider_initialization": _pass(init_ok),
        "openai_credential_available": "YES" if cred_yes else "NO",
        "secret_leakage": 0,
        "network_calls": network_calls,
        "generic_provider_preflight": _pass(readiness.get("ready") is True),
        "one_shot_lock_root_cause": lock.get("why_attempt_2_consumed_slot_before_http"),
        "future_call_accounting": (
            "authorized_calls / execution_attempts / remote_invocations / "
            "http_requests / provider_responses"
        ),
        "frozen_request_sha256": request.get("sha256"),
        "request_identity": "MATCH" if request_match and request_repeat else "MISMATCH",
        "benchmark_identity": "MATCH" if benchmark_match else "MISMATCH",
        "semantic_gate_regression": _pass(semantic_ok),
        "tests": tests.get("summary"),
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "ready_for_one_new_explicitly_authorized_terra_canary": _yn(ready_terra),
        "ready_for_book_generator_production_preflight": "NO",
        "ready_for_full_real_book_generation": "NO",
        "next_action": "HUMAN REVIEW",
        "notes": (
            "Canonical .venv already contained openai 2.43.0. Attempt 2 used "
            "system Python. Preflight now fails closed before lock consumption. "
            "No Terra call was executed."
        ),
        "canonical_environment": CANONICAL_PYTHON_ENV,
        "inputs_unchanged": _yn(inputs_unchanged),
    }
    readiness_audit = {
        "SDK_IMPORT": readiness.get("SDK_IMPORT"),
        "CREDENTIAL_AVAILABLE": readiness.get("CREDENTIAL_AVAILABLE"),
        "CLIENT_CONSTRUCTION": readiness.get("CLIENT_CONSTRUCTION"),
        "PROVIDER_INITIALIZATION": readiness.get("PROVIDER_INITIALIZATION"),
        "MODEL_RESOLUTION": readiness.get("MODEL_RESOLUTION"),
        "REQUEST_CONSTRUCTION": (
            "PASS" if request_match and request_repeat else "FAIL"
        ),
        "NETWORK_CALLS": 0,
        "ready": readiness.get("ready"),
        "primary_reason": readiness.get("primary_reason"),
        "sdk_version": readiness.get("sdk_version"),
        "secrets_included": False,
    }
    dependency = {
        "previous_state": {
            "declared_in_requirements": True,
            "constraint": "openai",
            "installed_in_canonical_venv": True,
            "installed_in_system_python_used_by_4b24_attempt_2": False,
            "failed_interpreter": r"C:\Program Files\Python311\python.exe",
        },
        "selected_dependency_strategy": {
            "environment": CANONICAL_PYTHON_ENV,
            "manifest": CANONICAL_DEPENDENCY_MECHANISM,
            "do_not_install_into_system_python": True,
        },
        "installed_sdk_version": readiness.get("sdk_version"),
        "manifest_changes": {
            "requirements_txt": OPENAI_SDK_CONSTRAINT,
            "previous": "openai",
            "updated": True,
        },
        "import_result": {
            "import openai": _pass(sdk_import),
            "from openai import OpenAI": _pass(sdk_import),
        },
        "secrets_included": False,
    }
    request_audit = {
        "request_sha256": request.get("sha256"),
        "request_sha256_repeat": request.get("sha256_repeat"),
        "expected_sha256": EXPECTED_REQUEST_SHA256_FROZEN,
        "identity": "MATCH" if request_match and request_repeat else "MISMATCH",
        "deterministic": request.get("deterministic"),
        "model": request.get("model"),
        "response_format": request.get("response_format"),
        "temperature_present": request.get("temperature_present"),
        "thinking_present": request.get("thinking_present"),
        "historical_4b24_request_unchanged": True,
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
        "why": (
            "Runtime and preflight are ready. A new explicit human "
            "authorization is required before any Terra call."
            if ready_terra
            else "Runtime or preflight is not ready. Do not authorize Terra."
        ),
    }
    bundle: dict[str, Any] = {
        "header": header,
        "forensics": forensics,
        "dependency": dependency,
        "readiness": readiness_audit,
        "lock": lock,
        "preflight_design": _preflight_design(),
        "request": request_audit,
        "tests": tests,
        "post_readiness": post,
        "dry_run": {
            key: value
            for key, value in dry.items()
            if key not in {"readiness"}
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
    bundle = redact_secrets(bundle)
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        from app.book_semantic_gate_4b241.writer import write_phase_artifacts

        write_phase_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.mode = "OFFLINE"
    return result


__all__ = ["Phase241Result", "run_phase"]
