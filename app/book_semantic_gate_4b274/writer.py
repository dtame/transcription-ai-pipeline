"""Atomic 4B.2.7.4 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b274.constants import (
    AUDIT_BENCHMARK,
    AUDIT_CLAIMS,
    AUDIT_COMPARISON,
    AUDIT_CONTRACT,
    AUDIT_COST,
    AUDIT_COVERAGE_DESIGN,
    AUDIT_DISAGREEMENT,
    AUDIT_INDEX,
    AUDIT_INVENTORY,
    AUDIT_PUNCTUATION,
    AUDIT_READINESS,
    AUDIT_REASON_CATALOG,
    AUDIT_REASON_POLICY,
    AUDIT_REPLAYS,
    AUDIT_TESTS,
    AUDIT_TRANSPORT,
    PHASE,
)
from app.book_semantic_gate_4b274.paths import (
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
        "comparison": (AUDIT_COMPARISON, bundle.get("comparison")),
        "claims": (AUDIT_CLAIMS, bundle.get("claims")),
        "disagreement": (AUDIT_DISAGREEMENT, bundle.get("disagreement")),
        "reason_catalog": (AUDIT_REASON_CATALOG, bundle.get("reason_catalog")),
        "reason_policy": (AUDIT_REASON_POLICY, bundle.get("reason_policy")),
        "punctuation": (AUDIT_PUNCTUATION, bundle.get("punctuation")),
        "coverage_design": (AUDIT_COVERAGE_DESIGN, bundle.get("coverage_design")),
        "contract": (AUDIT_CONTRACT, bundle.get("contract")),
        "transport": (AUDIT_TRANSPORT, bundle.get("transport")),
        "replays": (AUDIT_REPLAYS, bundle.get("replays")),
        "benchmark": (AUDIT_BENCHMARK, bundle.get("benchmark")),
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
        "anthropic_http_requests": 0,
        "historical_contracts_modified": False,
        "human_label_modified": False,
        "candidate_promoted": False,
    }
    written["index"] = write_bytes_atomic(directory / AUDIT_INDEX, header)
    return written


__all__ = ["write_phase_artifacts"]
