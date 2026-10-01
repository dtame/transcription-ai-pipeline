"""Atomic A.3.1 audit writes. Never production editorial_plan.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.editorial_planner_forensics_4a31.constants import (
    AUDIT_ASSIGNMENTS,
    AUDIT_CHAPTERS,
    AUDIT_IDENTITY,
    AUDIT_LANGUAGE,
    AUDIT_POLICY,
    AUDIT_PUBLICATION,
    AUDIT_READINESS,
    AUDIT_SECTIONS,
    AUDIT_TITLE,
    PHASE,
)
from app.editorial_planner_forensics_4a31.paths import (
    audit_root,
    production_editorial_plan_path,
    report_path,
)
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def _write(path: Path, payload: Mapping[str, Any] | str) -> Path:
    return write_bytes_atomic(path, payload)


def write_forensics_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = audit_root(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    production = production_editorial_plan_path(root=root)
    written: dict[str, Path] = {}
    mapping = {
        "identity": (AUDIT_IDENTITY, bundle.get("identity")),
        "language": (AUDIT_LANGUAGE, bundle.get("language")),
        "policy": (AUDIT_POLICY, bundle.get("policy")),
        "title": (AUDIT_TITLE, bundle.get("title")),
        "assignments": (AUDIT_ASSIGNMENTS, bundle.get("assignments")),
        "chapters": (AUDIT_CHAPTERS, bundle.get("chapters")),
        "sections": (AUDIT_SECTIONS, bundle.get("sections")),
        "publication": (AUDIT_PUBLICATION, bundle.get("publication")),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
    }
    for key, (name, payload) in mapping.items():
        if payload is None:
            continue
        written[key] = _write(directory / name, payload)
    report_text = bundle.get("report_text")
    if isinstance(report_text, str) and report_text.strip():
        written["report"] = _write(report_path(root=root), report_text)
    if production.is_file() and root is None:
        raise RuntimeError("A.3.1 must not find a published editorial_plan.json.")
    header = {
        "phase": PHASE,
        "editorial_plan_json": "NOT PUBLISHED",
        "production_path_absent": not production.is_file(),
        "written": sorted(written),
        "result": (bundle.get("header") or {}).get("result"),
    }
    written["index"] = _write(directory / "editorial_planner_4a31_index.json", header)
    return written
