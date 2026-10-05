"""Atomic 4B.2.9 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b29.constants import (
    AUDIT_ARCHITECTURE,
    AUDIT_BENCHMARK,
    AUDIT_CONTRACT,
    AUDIT_COVERAGE,
    AUDIT_FAKEAI,
    AUDIT_H01,
    AUDIT_H02,
    AUDIT_H11,
    AUDIT_INDEX,
    AUDIT_INTEGRATION,
    AUDIT_INVENTORY,
    AUDIT_POLICY,
    AUDIT_PREPARATION,
    AUDIT_READINESS,
    AUDIT_SAFETY,
    AUDIT_TESTS,
    AUDIT_TRANSPORT,
    AUDIT_VALIDATOR,
    PHASE,
)
from app.book_semantic_gate_4b29.paths import (
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
        "architecture": (AUDIT_ARCHITECTURE, bundle.get("architecture")),
        "preparation": (AUDIT_PREPARATION, bundle.get("preparation")),
        "coverage": (AUDIT_COVERAGE, bundle.get("coverage")),
        "contract": (AUDIT_CONTRACT, bundle.get("contract")),
        "transport": (AUDIT_TRANSPORT, bundle.get("transport")),
        "validator": (AUDIT_VALIDATOR, bundle.get("validator")),
        "policy": (AUDIT_POLICY, bundle.get("policy")),
        "fakeai": (AUDIT_FAKEAI, bundle.get("fakeai")),
        "h01": (AUDIT_H01, bundle.get("h01")),
        "h02": (AUDIT_H02, bundle.get("h02")),
        "h11": (AUDIT_H11, bundle.get("h11")),
        "benchmark": (AUDIT_BENCHMARK, bundle.get("benchmark")),
        "integration": (AUDIT_INTEGRATION, bundle.get("integration")),
        "safety": (AUDIT_SAFETY, bundle.get("safety")),
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
        "production_pipeline_modified": False,
        "semantic_gate_20_activated": False,
    }
    written["index"] = write_bytes_atomic(directory / AUDIT_INDEX, header)
    return written


__all__ = ["write_phase_artifacts"]
