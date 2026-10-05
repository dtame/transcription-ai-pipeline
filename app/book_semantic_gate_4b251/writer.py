"""Atomic 4B.2.5.1 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b251.constants import (
    AUDIT_ACCOUNTING,
    AUDIT_BENCHMARK,
    AUDIT_COST,
    AUDIT_DIFF,
    AUDIT_FORENSICS,
    AUDIT_INDEX,
    AUDIT_MATRIX,
    AUDIT_POST_READINESS,
    AUDIT_PREFLIGHT,
    AUDIT_REQUEST,
    AUDIT_SDK,
    AUDIT_TESTS,
    PHASE,
)
from app.book_semantic_gate_4b251.paths import (
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
        "matrix": (AUDIT_MATRIX, bundle.get("matrix")),
        "sdk_capture": (AUDIT_SDK, bundle.get("sdk_capture")),
        "preflight": (AUDIT_PREFLIGHT, bundle.get("preflight")),
        "request": (AUDIT_REQUEST, bundle.get("request")),
        "diff": (AUDIT_DIFF, bundle.get("diff")),
        "cost": (AUDIT_COST, bundle.get("cost")),
        "benchmark": (AUDIT_BENCHMARK, bundle.get("benchmark")),
        "accounting": (AUDIT_ACCOUNTING, bundle.get("accounting")),
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
