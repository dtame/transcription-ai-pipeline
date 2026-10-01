"""Atomic A.3.4 audit writes. Never production editorial_plan.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.editorial_planner_forensics_4a34.constants import (
    AUDIT_BUDGET,
    AUDIT_FUTURE_REQUEST,
    AUDIT_HARDENING,
    AUDIT_IDEA007,
    AUDIT_IDEA008,
    AUDIT_OMISSION,
    AUDIT_PROMPT,
    AUDIT_READINESS,
    AUDIT_ROOT_CAUSE,
    AUDIT_TRANSPORT,
    PHASE,
)
from app.editorial_planner_forensics_4a34.paths import (
    phase_audit_dir,
    production_editorial_plan_path,
    report_path,
)
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def write_phase_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    production = production_editorial_plan_path(root=root)
    written: dict[str, Path] = {}
    mapping = {
        "omission": (AUDIT_OMISSION, bundle.get("omission")),
        "idea007": (AUDIT_IDEA007, bundle.get("idea007")),
        "idea008": (AUDIT_IDEA008, bundle.get("idea008")),
        "prompt": (AUDIT_PROMPT, bundle.get("prompt")),
        "transport": (AUDIT_TRANSPORT, bundle.get("transport")),
        "root_cause": (AUDIT_ROOT_CAUSE, bundle.get("root_cause")),
        "hardening": (AUDIT_HARDENING, bundle.get("hardening")),
        "future_request": (AUDIT_FUTURE_REQUEST, bundle.get("future_request")),
        "budget": (AUDIT_BUDGET, bundle.get("budget")),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
    }
    for key, (name, payload) in mapping.items():
        if payload is None:
            continue
        written[key] = write_bytes_atomic(directory / name, payload)
    report_text = bundle.get("report_text")
    if isinstance(report_text, str) and report_text.strip():
        written["report"] = write_bytes_atomic(report_path(root=root), report_text)
    if production.is_file() and root is None:
        raise RuntimeError("A.3.4 must not find a published editorial_plan.json.")
    header = {
        "phase": PHASE,
        "editorial_plan_json": "NOT PUBLISHED",
        "production_path_absent": not production.is_file(),
        "written": sorted(written),
        "result": (bundle.get("header") or {}).get("result"),
    }
    written["index"] = write_bytes_atomic(directory / "index.json", header)
    return written


__all__ = ["write_phase_artifacts"]
