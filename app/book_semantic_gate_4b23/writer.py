"""Atomic 4B.2.3 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b23.constants import (
    AUDIT_ACCEPTANCE,
    AUDIT_ARCHITECTURE,
    AUDIT_BENCHMARK,
    AUDIT_BUDGET,
    AUDIT_CACHE,
    AUDIT_CLAIMS,
    AUDIT_COST,
    AUDIT_EVIDENCE,
    AUDIT_MANIFEST,
    AUDIT_PROMPT,
    AUDIT_READINESS,
    AUDIT_REASONS,
    AUDIT_SCHEMA,
    AUDIT_SUFFICIENCY,
    AUDIT_TRANSPORT,
    PHASE,
)
from app.book_semantic_gate_4b23.paths import (
    phase_audit_dir,
    production_book_path,
    report_path,
)
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def write_semantic_gate_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    mapping = {
        "architecture": (AUDIT_ARCHITECTURE, bundle.get("architecture")),
        "evidence": (AUDIT_EVIDENCE, bundle.get("evidence_contract")),
        "claims": (AUDIT_CLAIMS, bundle.get("claim_contract")),
        "reasons": (AUDIT_REASONS, bundle.get("reason_codes")),
        "prompt": (AUDIT_PROMPT, bundle.get("prompt_identity")),
        "transport": (AUDIT_TRANSPORT, bundle.get("transport_identity")),
        "schema": (AUDIT_SCHEMA, bundle.get("schema_identity")),
        "benchmark": (AUDIT_BENCHMARK, bundle.get("historical_benchmark")),
        "manifest": (AUDIT_MANIFEST, bundle.get("benchmark_manifest")),
        "acceptance": (AUDIT_ACCEPTANCE, bundle.get("acceptance_policy")),
        "cache": (AUDIT_CACHE, bundle.get("cache_contract")),
        "budget": (AUDIT_BUDGET, bundle.get("budget")),
        "cost": (AUDIT_COST, bundle.get("cost_estimate")),
        "sufficiency": (AUDIT_SUFFICIENCY, bundle.get("sufficiency")),
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
    }
    written["index"] = write_bytes_atomic(
        directory / "book_semantic_gate_4b23_index.json", header
    )
    return written


__all__ = ["write_semantic_gate_artifacts"]
