"""Atomic audit writes. Never editorial_plan.json production."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.editorial_planner_preflight_4a2.constants import (
    AUDIT_CACHE,
    AUDIT_COST,
    AUDIT_COVERAGE,
    AUDIT_GATES,
    AUDIT_INPUT_BUDGET,
    AUDIT_OUTPUT_BUDGET,
    AUDIT_READINESS,
    AUDIT_REQUEST_IDENTITY,
    AUDIT_SOURCE_IDENTITY,
    AUDIT_THINKING,
    PHASE,
)
from app.editorial_planner_preflight_4a2.paths import (
    preflight_audit_dir,
    production_editorial_plan_path,
    report_path,
)
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def write_preflight_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = preflight_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    production = production_editorial_plan_path()
    written: dict[str, Path] = {}
    mapping = {
        "source_identity": (AUDIT_SOURCE_IDENTITY, bundle.get("source_identity")),
        "request_identity": (AUDIT_REQUEST_IDENTITY, bundle.get("request_identity")),
        "input_budget": (AUDIT_INPUT_BUDGET, bundle.get("input_budget")),
        "output_budget": (AUDIT_OUTPUT_BUDGET, bundle.get("output_budget")),
        "thinking": (AUDIT_THINKING, bundle.get("thinking")),
        "cost": (AUDIT_COST, bundle.get("cost")),
        "cache": (AUDIT_CACHE, bundle.get("cache")),
        "coverage": (AUDIT_COVERAGE, bundle.get("coverage")),
        "gates": (AUDIT_GATES, bundle.get("gates")),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
    }
    for key, (name, payload) in mapping.items():
        if payload is None:
            continue
        written[key] = write_bytes_atomic(directory / name, payload)
    report_text = bundle.get("report_text")
    if isinstance(report_text, str) and report_text.strip():
        written["report"] = write_bytes_atomic(report_path(root=root), report_text)
    header = {
        "phase": PHASE,
        "editorial_plan_json": "NOT PUBLISHED",
        "production_path_absent": not production.is_file(),
        "written": sorted(written),
        "result": (bundle.get("header") or {}).get("result"),
    }
    written["index"] = write_bytes_atomic(directory / "index.json", header)
    return written


__all__ = ["write_preflight_artifacts"]
