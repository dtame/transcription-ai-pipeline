"""Écriture atomique des artefacts 4A.1. Jamais editorial_plan.json production."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.editorial_planner_canary_4a1.constants import (
    AUDIT_BUDGET,
    AUDIT_CONTRACT,
    AUDIT_EXECUTION,
    AUDIT_FIXTURE,
    AUDIT_PRECALL,
    AUDIT_RAW_RESPONSE,
    AUDIT_RECONSTRUCTED,
    AUDIT_REQUEST,
    AUDIT_READINESS,
    AUDIT_RESPONSE,
    AUDIT_SEMANTIC,
    AUDIT_THINKING,
    PHASE,
)
from app.editorial_planner_canary_4a1.paths import (
    canary_audit_dir,
    production_editorial_plan_path,
    report_path,
)
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def _write(path: Path, payload: Mapping[str, Any] | str) -> Path:
    return write_bytes_atomic(path, payload)


def write_canary_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = canary_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    production = production_editorial_plan_path()
    written: dict[str, Path] = {}
    mapping = {
        "precall": (AUDIT_PRECALL, bundle.get("precall")),
        "fixture": (AUDIT_FIXTURE, bundle.get("fixture")),
        "request": (AUDIT_REQUEST, bundle.get("request_payload")),
        "raw_response": (AUDIT_RAW_RESPONSE, bundle.get("raw_response")),
        "response": (AUDIT_RESPONSE, bundle.get("response_identity")),
        "thinking": (AUDIT_THINKING, bundle.get("thinking")),
        "contract": (AUDIT_CONTRACT, bundle.get("contract")),
        "semantic": (AUDIT_SEMANTIC, bundle.get("semantic")),
        "budget": (AUDIT_BUDGET, bundle.get("budget")),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
        "execution": (AUDIT_EXECUTION, bundle.get("execution")),
        "reconstructed": (AUDIT_RECONSTRUCTED, bundle.get("reconstructed_plan")),
    }
    for key, (name, payload) in mapping.items():
        if payload is None:
            continue
        written[key] = _write(directory / name, payload)
    report_text = bundle.get("report_text")
    if isinstance(report_text, str) and report_text.strip():
        written["report"] = _write(report_path(root=root), report_text)
    header = {
        "phase": PHASE,
        "editorial_plan_json": "NOT PUBLISHED",
        "production_path_absent": not production.is_file(),
        "written": sorted(written),
    }
    written["index"] = _write(directory / "index.json", header)
    return written


def dump_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return _write(path, payload)


__all__ = ["dump_json", "write_canary_artifacts"]
