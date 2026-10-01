"""Delta de suite post-phase A.28. 0 provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_real_win004.post_tests import parse_junit
from app.source_analysis_v31_remaining_windows.constants import (
    BASELINE_ARTIFACT,
    PHASE,
    POST_TEST_ARTIFACT,
    PROJECT_NAME,
    SCHEMA_VERSION,
)


def write_post_test_delta(
    project_name: str = PROJECT_NAME,
    *,
    post_junit: Path,
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
    post = parse_junit(post_junit)
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
        "gate": "PASS" if not new_failures else "FAIL",
    }
    return write_bytes_atomic(audit / POST_TEST_ARTIFACT, payload)


def write_baseline(
    project_name: str,
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


__all__ = ["parse_junit", "write_baseline", "write_post_test_delta"]
