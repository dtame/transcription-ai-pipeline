"""Atomic 4B.2.7.1 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b271.constants import (
    AUDIT_CALIBRATION,
    AUDIT_CLAUSE,
    AUDIT_COMPARISON,
    AUDIT_HUMAN,
    AUDIT_INDEX,
    AUDIT_INVENTORY,
    AUDIT_MATRIX,
    AUDIT_READINESS,
    AUDIT_SPANS,
    AUDIT_SRC180,
    AUDIT_TERRA,
    AUDIT_TESTS,
    PHASE,
)
from app.book_semantic_gate_4b271.paths import (
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
        "inventory": (AUDIT_INVENTORY, bundle.get("inventory")),
        "clause": (AUDIT_CLAUSE, bundle.get("clause")),
        "human": (AUDIT_HUMAN, bundle.get("human")),
        "src180": (AUDIT_SRC180, bundle.get("src180")),
        "terra": (AUDIT_TERRA, bundle.get("terra")),
        "matrix": (AUDIT_MATRIX, bundle.get("matrix")),
        "spans": (AUDIT_SPANS, bundle.get("spans")),
        "calibration": (AUDIT_CALIBRATION, bundle.get("calibration")),
        "comparison": (AUDIT_COMPARISON, bundle.get("comparison")),
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
        "anthropic_http_requests": 0,
        "historical_contracts_modified": False,
        "human_label_modified": False,
    }
    written["index"] = write_bytes_atomic(directory / AUDIT_INDEX, header)
    return written


__all__ = ["write_phase_artifacts"]
