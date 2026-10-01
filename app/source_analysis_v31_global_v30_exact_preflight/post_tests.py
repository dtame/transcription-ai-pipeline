"""Baseline / focused / post-phase tests A.45. 0 provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_final_three.post_tests import run_pytest
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    BROADER_SLICE_TEST_PATHS,
    FOCUSED_TEST_PATHS,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    TEST_DELTA_ARTIFACT,
)
from app.source_analysis_v31_real_win004.post_tests import parse_junit


def run_focused_suite(*, junit_path: Path) -> dict[str, Any]:
    result = run_pytest(FOCUSED_TEST_PATHS, junit_path=junit_path)
    result["scope"] = "focused A.45 exact-production preflight"
    result["paths"] = list(FOCUSED_TEST_PATHS)
    result["full_suite"] = False
    return result


def run_broader_slice(*, junit_path: Path) -> dict[str, Any]:
    result = run_pytest(BROADER_SLICE_TEST_PATHS, junit_path=junit_path)
    result["scope"] = (
        "broader v31 global-consolidation slices "
        "(A.45 + A.44 + A.43 + A.42 + A.41 + A.40 canary + A.39 architecture). "
        "Not the full historical suite. Shared frozen 3.0 prompt/transport/schema "
        "were not mutated, so A.41 full-green historical rematerialization is "
        "not repeated."
    )
    result["paths"] = list(BROADER_SLICE_TEST_PATHS)
    result["full_suite"] = False
    return result


def write_a45_post_delta(
    project_name: str = PROJECT_NAME,
    *,
    post: dict[str, Any],
    focused: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
    sortie_dir: Path | None = None,
) -> Path:
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    pre = baseline or {}
    pre_fail = set(pre.get("failing_node_ids") or [])
    post_fail = set(post.get("failing_node_ids") or [])
    new_failures = sorted(post_fail - pre_fail)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "POST_PHASE_TEST_DELTA",
        "provider_calls": 0,
        "full_suite": False,
        "pre_call": pre,
        "post_call": post,
        "focused_post": focused or {},
        "new_failures": new_failures,
        "new_failure_count": len(new_failures),
        "source_map_published": source_map_path(
            project_name, sortie_dir=sortie_dir
        ).is_file(),
        "gate": "PASS" if not new_failures and int(post.get("failed") or 0) == 0 else "FAIL",
        "scope": post.get("scope") or "focused/broader slices, not full suite",
    }
    return write_bytes_atomic(audit / TEST_DELTA_ARTIFACT, payload)


__all__ = [
    "parse_junit",
    "run_broader_slice",
    "run_focused_suite",
    "run_pytest",
    "write_a45_post_delta",
]
