"""Atomic 4B.2.6.2 audit writes. Never production book.json. Never historical audits."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b262.constants import (
    AUDIT_BUDGET,
    AUDIT_CONTRACT,
    AUDIT_COST,
    AUDIT_EVIDENCE,
    AUDIT_INDEX,
    AUDIT_INVARIANTS,
    AUDIT_PREFLIGHT,
    AUDIT_READINESS,
    AUDIT_REQUEST,
    AUDIT_SELECTION,
    AUDIT_SERIALIZATION,
    AUDIT_TELEMETRY,
    AUDIT_TESTS,
    PHASE,
)
from app.book_semantic_gate_4b262.paths import (
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
        "contract": (AUDIT_CONTRACT, bundle.get("contract")),
        "invariants": (AUDIT_INVARIANTS, bundle.get("invariants")),
        "selection": (AUDIT_SELECTION, bundle.get("selection")),
        "evidence": (AUDIT_EVIDENCE, bundle.get("evidence")),
        "telemetry": (AUDIT_TELEMETRY, bundle.get("telemetry")),
        "serialization": (AUDIT_SERIALIZATION, bundle.get("serialization")),
        "request": (AUDIT_REQUEST, bundle.get("request")),
        "budget": (AUDIT_BUDGET, bundle.get("budget")),
        "cost": (AUDIT_COST, bundle.get("cost")),
        "preflight": (AUDIT_PREFLIGHT, bundle.get("preflight")),
        "tests": (AUDIT_TESTS, bundle.get("tests")),
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
        "book_json": "NOT PUBLISHED",
        "production_book_absent": not production_book_path().is_file(),
        "written": sorted(written),
        "result": (bundle.get("header") or {}).get("result"),
        "real_provider_calls": 0,
        "openai_http_requests": 0,
        "historical_dirs_untouched": True,
    }
    written["index"] = write_bytes_atomic(directory / AUDIT_INDEX, header)
    return written


__all__ = ["write_phase_artifacts"]
