"""Baseline / focused / post-phase tests A.42. 0 provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_final_three.post_tests import run_pytest
from app.source_analysis_v31_global_v201_contract_canary.constants import (
    BASELINE_ARTIFACT,
    BROADER_SLICE_TEST_PATHS,
    FOCUSED_TEST_PATHS,
    PHASE,
    POST_TEST_ARTIFACT,
    PROJECT_NAME,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_real_win004.post_tests import parse_junit


def run_focused_suite(*, junit_path: Path) -> dict[str, Any]:
    result = run_pytest(FOCUSED_TEST_PATHS, junit_path=junit_path)
    result["scope"] = "focused A.42/A.41/A.40/A.39 contract slices"
    result["paths"] = list(FOCUSED_TEST_PATHS)
    result["full_suite"] = False
    return result


def run_broader_slices(*, junit_path: Path) -> dict[str, Any]:
    result = run_pytest(BROADER_SLICE_TEST_PATHS, junit_path=junit_path)
    result["scope"] = (
        "broader v31 global-consolidation slices "
        "(A.42 + A.41 + A.40 canary + A.39 architecture + audits). "
        "Not the full historical suite."
    )
    result["paths"] = list(BROADER_SLICE_TEST_PATHS)
    result["full_suite"] = False
    return result


def write_a42_baseline(
    project_name: str = PROJECT_NAME,
    *,
    focused: dict[str, Any],
    broader: dict[str, Any] | None = None,
    sortie_dir: Path | None = None,
) -> Path:
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "PRE_CALL_FOCUSED_CONTRACT_BASELINE",
        "provider_calls": 0,
        "full_suite": False,
        "full_suite_not_repeated": (
            "A.41 already established historical v3 rematerialization slowness. "
            "A.42 does not spend another hour on that TEST_PERFORMANCE_DEBT."
        ),
        "focused": focused,
        "broader": broader or {},
    }
    return write_bytes_atomic(audit / BASELINE_ARTIFACT, payload)


def write_a42_post_delta(
    project_name: str = PROJECT_NAME,
    *,
    post: dict[str, Any],
    focused: dict[str, Any] | None = None,
    sortie_dir: Path | None = None,
) -> Path:
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    baseline_path = audit / BASELINE_ARTIFACT
    baseline = (
        json.loads(baseline_path.read_text(encoding="utf-8"))
        if baseline_path.is_file()
        else {}
    )
    pre = baseline.get("focused") or {}
    pre_fail = set(pre.get("failing_node_ids") or [])
    post_fail = set(post.get("failing_node_ids") or [])
    new_failures = sorted(post_fail - pre_fail)
    gone = sorted(pre_fail - post_fail)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "POST_PHASE_FOCUSED_CONTRACT_DELTA",
        "provider_calls": 0,
        "full_suite": False,
        "pre_call_focused": pre,
        "post_call": post,
        "focused_post": focused or {},
        "new_failures": new_failures,
        "resolved_failures": gone,
        "new_failure_count": len(new_failures),
        "source_map_published": source_map_path(
            project_name, sortie_dir=sortie_dir
        ).is_file(),
        "gate": "PASS" if not new_failures and int(post.get("failed") or 0) == 0 else "FAIL",
        "scope": post.get("scope") or "focused/broader contract slices, not full suite",
    }
    return write_bytes_atomic(audit / POST_TEST_ARTIFACT, payload)


__all__ = [
    "parse_junit",
    "run_broader_slices",
    "run_focused_suite",
    "run_pytest",
    "write_a42_baseline",
    "write_a42_post_delta",
]
