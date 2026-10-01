"""Focused / broader post-phase tests for 4A.4. 0 provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.editorial_planner_publication_4a4.constants import (
    BROADER_SLICE_TEST_PATHS,
    FOCUSED_TEST_PATHS,
)
from app.source_analysis_v31_final_three.post_tests import run_pytest


def run_focused_suite(*, junit_path: Path) -> dict[str, Any]:
    result = run_pytest(FOCUSED_TEST_PATHS, junit_path=junit_path)
    result["scope"] = (
        "focused 4A.4 publication / identity / atomic write / idempotence / "
        "conflict / reload / validator / coverage / language / SourceMap"
    )
    result["paths"] = list(FOCUSED_TEST_PATHS)
    result["full_suite"] = False
    return result


def run_broader_slices(*, junit_path: Path) -> dict[str, Any]:
    result = run_pytest(BROADER_SLICE_TEST_PATHS, junit_path=junit_path)
    result["scope"] = (
        "4A.4 publication tests plus editorial_planning models, language "
        "policy, and document-language contracts. Historical canary suites "
        "that assert analysis/editorial_plan.json is absent are excluded "
        "because 4A.4 is authorized to publish that artifact."
    )
    result["paths"] = list(BROADER_SLICE_TEST_PATHS)
    result["full_suite"] = False
    return result


__all__ = ["run_broader_slices", "run_focused_suite", "run_pytest"]
