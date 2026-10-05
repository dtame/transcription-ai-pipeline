"""Atomic 4B.2.7.5 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b275.constants import (
    AUDIT_BENCHMARK,
    AUDIT_CANARY,
    AUDIT_CATALOG,
    AUDIT_CONTRACT,
    AUDIT_COVERAGE,
    AUDIT_DIAGNOSTIC,
    AUDIT_INDETERMINATE,
    AUDIT_INDEX,
    AUDIT_INVENTORY,
    AUDIT_MATRIX,
    AUDIT_READINESS,
    AUDIT_REPLAYS,
    AUDIT_TESTS,
    AUDIT_TRANSPORT,
    AUDIT_UNKNOWN,
    AUDIT_VERDICTS,
    PHASE,
)
from app.book_semantic_gate_4b275.paths import (
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
        "verdicts": (AUDIT_VERDICTS, bundle.get("verdicts")),
        "indeterminate": (AUDIT_INDETERMINATE, bundle.get("indeterminate")),
        "catalog": (AUDIT_CATALOG, bundle.get("catalog")),
        "matrix": (AUDIT_MATRIX, bundle.get("matrix")),
        "unknown": (AUDIT_UNKNOWN, bundle.get("unknown")),
        "coverage": (AUDIT_COVERAGE, bundle.get("coverage")),
        "diagnostic": (AUDIT_DIAGNOSTIC, bundle.get("diagnostic_policy")),
        "replays": (AUDIT_REPLAYS, bundle.get("replays")),
        "benchmark": (AUDIT_BENCHMARK, bundle.get("benchmark")),
        "contract": (AUDIT_CONTRACT, bundle.get("contract")),
        "transport": (AUDIT_TRANSPORT, bundle.get("transport")),
        "canary": (AUDIT_CANARY, bundle.get("canary")),
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
        "candidate_promoted": False,
    }
    written["index"] = write_bytes_atomic(directory / AUDIT_INDEX, header)
    return written


__all__ = ["write_phase_artifacts"]
