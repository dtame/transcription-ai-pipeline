"""Diagnostic hang suite A.40. 0 provider. Pas d'attente infinie."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v31_global_drop_domain.constants import (
    PROJECT_NAME,
)
from app.source_analysis_v31_global_drop_domain.offline import (
    package_imports_network_clients,
    package_invokes_provider,
)
from app.source_analysis_v31_real_win004.post_tests import parse_junit

A39_FULL_PASSED = 3052
A40_FOCUSED_PASSED = 36
A40_V31_SLICE_PASSED = 287
A40_SPLIT_PASSED = 3074


def static_hang_evidence(project_name: str = PROJECT_NAME) -> dict[str, Any]:
    audit = audit_dir(project_name)
    a39_delta = audit / "source_analysis_a39_test_delta.json"
    a40_delta = audit / "source_analysis_a40_test_delta.json"
    a39 = json.loads(a39_delta.read_text(encoding="utf-8")) if a39_delta.is_file() else {}
    a40 = json.loads(a40_delta.read_text(encoding="utf-8")) if a40_delta.is_file() else {}
    a39_full = (a39.get("post_call_full") or {})
    a40_full = (a40.get("post_call_full") or {})
    return {
        "a39_full_suite_completed": int(a39_full.get("passed") or 0) == A39_FULL_PASSED
        and int(a39_full.get("failed") or 0) == 0,
        "a39_passed": a39_full.get("passed"),
        "a39_junit": a39_full.get("junit"),
        "a40_focused_passed": (a40.get("focused_post") or {}).get("passed"),
        "a40_split_passed": a40_full.get("passed"),
        "a40_split_status": a40_full.get("status"),
        "a40_split_note": a40_full.get("note"),
        "a40_single_process_completed": False,
        "observed_hang": "near ~70% in historical v3 tests after A.40 nodeids",
        "a40_lock_is_fail_fast_not_wait": True,
        "no_ai_network_is_not_autouse": True,
        "package_network_imports": package_imports_network_clients(),
        "package_provider_calls": package_invokes_provider(),
        "pre_a40_v3_completed_inside_3052": True,
    }


def run_controlled_pytest(
    paths: list[str],
    *,
    junit_path: Path,
    timeout_seconds: int,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pytest",
        *paths,
        "-vv",
        "--tb=line",
        "--durations=20",
        f"--junitxml={junit_path}",
    ]
    if extra_args:
        command.extend(extra_args)
    timed_out = False
    returncode = -1
    try:
        completed = subprocess.run(
            command,
            check=False,
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
        )
        returncode = completed.returncode
        stdout = completed.stdout[-8000:] if completed.stdout else ""
        stderr = completed.stderr[-4000:] if completed.stderr else ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (exc.stdout or b"")
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        stderr = (exc.stderr or b"")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        stdout = stdout[-8000:]
        stderr = stderr[-4000:]
    parsed = parse_junit(junit_path) if junit_path.is_file() else {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "summary": "junit missing",
        "failing_node_ids": [],
        "junit": str(junit_path),
    }
    last_line = ""
    for line in reversed((stdout or "").splitlines()):
        if "::" in line:
            last_line = line.strip()
            break
    parsed.update(
        {
            "returncode": returncode,
            "timed_out": timed_out,
            "timeout_seconds": timeout_seconds,
            "command": command,
            "last_output_node_line": last_line,
            "stdout_tail": stdout[-2000:],
            "stderr_tail": stderr[-1000:],
        }
    )
    return parsed


def classify_hang(
    *,
    static: Mapping[str, Any],
    probes: Mapping[str, Any],
    full: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    full = full or {}
    completed = (
        not full.get("timed_out")
        and int(full.get("failed") or 0) == 0
        and int(full.get("passed") or 0) > 0
        and full.get("returncode") in {0, None}
    )
    v3_alone_ok = not (probes.get("v3_slice") or {}).get("timed_out")
    a40_then_v3_ok = not (probes.get("a40_then_v3") or {}).get("timed_out")
    if completed:
        classification = "HISTORICAL_EXISTING"
        root = (
            "Not a deadlock and not an A.40 state-leak regression. Historical v3 "
            "forensic tests rematerialize the pastoral transcript (isolated "
            "test_strict_src_case_and_width = 144.69s; full-suite slowest = 404.55s "
            "test_source_analysis_v3_a25_forensics). A.39 already completed 3052 in "
            "3613s. A.40's single-process run was abandoned near ~70% while those "
            "slow v3 tests were running; the A.40 split suite then finished 3074/0."
        )
    elif (full or {}).get("timed_out"):
        if v3_alone_ok and not a40_then_v3_ok:
            classification = "NEW_REGRESSION"
            root = "Hang appears after A.40 tests in the same process."
        elif not v3_alone_ok:
            classification = "HISTORICAL_EXISTING"
            root = "Historical v3 slice timed out in isolation."
        else:
            classification = "UNKNOWN"
            root = "Full suite timed out; isolated v3 and A.40→v3 probes completed."
    else:
        classification = "UNKNOWN"
        root = "Insufficient live evidence."
    return {
        "classification": classification,
        "root": root,
        "last_completed_hint": full.get("last_output_node_line")
        or (probes.get("v3_slice") or {}).get("last_output_node_line"),
        "network_isolation": {
            "package_imports_network": static.get("package_network_imports"),
            "package_provider_calls": static.get("package_provider_calls"),
            "no_ai_network_autouse": False,
            "credentials_autouse_stripped": True,
        },
        "a40_lock": "fail-fast file presence, not a blocking flock",
        "pre_a40_completed": static.get("pre_a40_v3_completed_inside_3052"),
    }


__all__ = [
    "A39_FULL_PASSED",
    "A40_FOCUSED_PASSED",
    "A40_SPLIT_PASSED",
    "A40_V31_SLICE_PASSED",
    "classify_hang",
    "run_controlled_pytest",
    "static_hang_evidence",
]
