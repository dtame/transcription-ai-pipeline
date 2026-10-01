"""Baseline / focused / post-phase tests A.37. 0 provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_final_three.post_tests import run_pytest
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    BASELINE_ARTIFACT,
    FOCUSED_TEST_PATHS,
    PHASE,
    POST_TEST_ARTIFACT,
    PROJECT_NAME,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_real_win004.post_tests import parse_junit


def run_focused_suite(*, junit_path: Path) -> dict[str, Any]:
    return run_pytest(FOCUSED_TEST_PATHS, junit_path=junit_path)


def run_full_suite(*, junit_path: Path) -> dict[str, Any]:
    return run_pytest(["app/tests"], junit_path=junit_path)


def write_a37_baseline(
    project_name: str = PROJECT_NAME,
    *,
    full: dict[str, Any],
    focused: dict[str, Any] | None = None,
    sortie_dir: Path | None = None,
) -> Path:
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "PRE_CALL_TEST_BASELINE",
        "provider_calls": 0,
        "full_suite": full,
        "focused": focused or {},
    }
    return write_bytes_atomic(audit / BASELINE_ARTIFACT, payload)


def write_a37_post_delta(
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
    pre = baseline.get("full_suite") or {}
    pre_fail = set(pre.get("failing_node_ids") or [])
    post_fail = set(post.get("failing_node_ids") or [])
    new_failures = sorted(post_fail - pre_fail)
    gone = sorted(pre_fail - post_fail)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "POST_PHASE_TEST_DELTA",
        "provider_calls": 0,
        "pre_call_full": pre,
        "post_call_full": post,
        "focused_post": focused or {},
        "new_failures": new_failures,
        "resolved_failures": gone,
        "new_failure_count": len(new_failures),
        "source_map_published": source_map_path(
            project_name, sortie_dir=sortie_dir
        ).is_file(),
        "gate": "PASS" if not new_failures and int(post.get("failed") or 0) == 0 else "FAIL",
    }
    return write_bytes_atomic(audit / POST_TEST_ARTIFACT, payload)


__all__ = [
    "parse_junit",
    "run_focused_suite",
    "run_full_suite",
    "run_pytest",
    "write_a37_baseline",
    "write_a37_post_delta",
]
