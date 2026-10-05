"""Atomic 4B.2.6.1 audit writes. Never production book.json. Never historical audits."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b261.constants import (
    AUDIT_COMPARISON,
    AUDIT_COMPLEXITY,
    AUDIT_CONTRACT,
    AUDIT_COST,
    AUDIT_DIFF,
    AUDIT_INDEX,
    AUDIT_RAW,
    AUDIT_READINESS,
    AUDIT_SCHEMA,
    AUDIT_STRATEGY_A,
    AUDIT_STRATEGY_B,
    AUDIT_STRATEGY_C,
    AUDIT_TESTS,
    AUDIT_USAGE,
    PHASE,
)
from app.book_semantic_gate_4b261.paths import (
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
        "raw": (AUDIT_RAW, bundle.get("raw")),
        "usage": (AUDIT_USAGE, bundle.get("usage")),
        "contract": (AUDIT_CONTRACT, bundle.get("contract")),
        "complexity": (AUDIT_COMPLEXITY, bundle.get("complexity")),
        "schema": (AUDIT_SCHEMA, bundle.get("schema")),
        "strategy_a": (AUDIT_STRATEGY_A, bundle.get("strategy_a")),
        "strategy_b": (AUDIT_STRATEGY_B, bundle.get("strategy_b")),
        "strategy_c": (AUDIT_STRATEGY_C, bundle.get("strategy_c")),
        "comparison": (AUDIT_COMPARISON, bundle.get("comparison")),
        "diff": (AUDIT_DIFF, bundle.get("diff")),
        "cost": (AUDIT_COST, bundle.get("cost")),
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
