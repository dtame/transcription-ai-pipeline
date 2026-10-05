"""Atomic 4B.2.4.1 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b241.constants import (
    AUDIT_DEPENDENCY,
    AUDIT_FORENSICS,
    AUDIT_INDEX,
    AUDIT_LOCK,
    AUDIT_POST_READINESS,
    AUDIT_PREFLIGHT_DESIGN,
    AUDIT_READINESS,
    AUDIT_REQUEST,
    AUDIT_TESTS,
    PHASE,
)
from app.book_semantic_gate_4b241.paths import (
    phase_audit_dir,
    production_book_path,
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
    written: dict[str, Path] = {}
    mapping = {
        "forensics": (AUDIT_FORENSICS, bundle.get("forensics")),
        "dependency": (AUDIT_DEPENDENCY, bundle.get("dependency")),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
        "lock": (AUDIT_LOCK, bundle.get("lock")),
        "preflight_design": (AUDIT_PREFLIGHT_DESIGN, bundle.get("preflight_design")),
        "request": (AUDIT_REQUEST, bundle.get("request")),
        "tests": (AUDIT_TESTS, bundle.get("tests")),
        "post_readiness": (AUDIT_POST_READINESS, bundle.get("post_readiness")),
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
        "book_json": "NOT PUBLISHED",
        "production_book_absent": not production_book_path().is_file(),
        "written": sorted(written),
        "result": (bundle.get("header") or {}).get("result"),
        "real_provider_calls": 0,
        "openai_http_requests": 0,
    }
    written["index"] = write_bytes_atomic(directory / AUDIT_INDEX, header)
    return written


__all__ = ["write_phase_artifacts"]
