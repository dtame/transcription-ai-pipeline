"""Baseline / focused / post-phase tests A.49. 0 provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_final_three.post_tests import run_pytest
from app.source_analysis_v31_global_a49_source_map_publication.constants import (
    A41_FULL_SUITE_NOTE,
    BASELINE_ARTIFACT,
    BROADER_SLICE_TEST_PATHS,
    CANONICAL_VALIDATOR_TEST_PATHS,
    FOCUSED_TEST_PATHS,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    TEST_DELTA_ARTIFACT,
)
from app.source_analysis_v31_real_win004.post_tests import parse_junit


def run_focused_suite(*, junit_path: Path) -> dict[str, Any]:
    result = run_pytest(FOCUSED_TEST_PATHS, junit_path=junit_path)
    result["scope"] = (
        "focused A.49 publication / idempotence / conflict / eligibility / "
        "invalid / network / atomicity slices"
    )
    result["paths"] = list(FOCUSED_TEST_PATHS)
    result["full_suite"] = False
    return result


def run_broader_slices(*, junit_path: Path) -> dict[str, Any]:
    result = run_pytest(BROADER_SLICE_TEST_PATHS, junit_path=junit_path)
    result["scope"] = (
        "A.49 publication tests plus canonical source-map validator / models / "
        "normalization / compact schema. Historical A.34–A.48 suites that "
        "assert analysis/source_map.json is absent are excluded because A.49 "
        "is authorized to publish that artifact."
    )
    result["paths"] = list(BROADER_SLICE_TEST_PATHS)
    result["full_suite"] = False
    return result


def run_canonical_validator_suite(*, junit_path: Path) -> dict[str, Any]:
    result = run_pytest(CANONICAL_VALIDATOR_TEST_PATHS, junit_path=junit_path)
    result["scope"] = "canonical source-map validator / models / normalization / compact schema"
    result["paths"] = list(CANONICAL_VALIDATOR_TEST_PATHS)
    result["full_suite"] = False
    return result


def write_a49_baseline(
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
        "mode": "FOCUSED_PUBLICATION_BASELINE",
        "provider_calls": 0,
        "full_suite": False,
        "focused": focused,
        "broader": broader or {},
        "a41_full_suite_note": A41_FULL_SUITE_NOTE,
    }
    return write_bytes_atomic(audit / BASELINE_ARTIFACT, payload)


def write_a49_post_delta(
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
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "POST_PHASE_FOCUSED_PUBLICATION_DELTA",
        "provider_calls": 0,
        "full_suite": bool(post.get("full_suite")),
        "pre_call_focused": pre,
        "post": post,
        "focused_post": focused or {},
        "new_failures": new_failures,
        "new_failure_count": len(new_failures),
        "source_map_published": source_map_path(
            project_name, sortie_dir=sortie_dir
        ).is_file(),
        "gate": "PASS" if not new_failures and int(post.get("failed") or 0) == 0 else "FAIL",
        "scope": post.get("scope") or "focused/broader slices",
        "a41_full_suite_baseline_note": A41_FULL_SUITE_NOTE,
    }
    return write_bytes_atomic(audit / TEST_DELTA_ARTIFACT, payload)


__all__ = [
    "parse_junit",
    "run_broader_slices",
    "run_canonical_validator_suite",
    "run_focused_suite",
    "run_pytest",
    "write_a49_baseline",
    "write_a49_post_delta",
]
