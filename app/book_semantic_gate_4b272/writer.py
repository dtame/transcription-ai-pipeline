"""Atomic 4B.2.7.2 audit writes. Never production book.json. Never historical audits."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b272.constants import (
    AUDIT_BUDGET,
    AUDIT_CAUSAL,
    AUDIT_CONTRACT,
    AUDIT_COST,
    AUDIT_IDENTITY,
    AUDIT_INDEX,
    AUDIT_INVENTORY,
    AUDIT_LEAK,
    AUDIT_PREFLIGHT,
    AUDIT_REQUEST,
    AUDIT_SERIALIZATION,
    AUDIT_SPANS,
    AUDIT_TESTS,
    PHASE,
)
from app.book_semantic_gate_4b272.paths import (
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
        "identity": (AUDIT_IDENTITY, bundle.get("identity")),
        "inventory": (AUDIT_INVENTORY, bundle.get("inventory")),
        "causal": (AUDIT_CAUSAL, bundle.get("causal")),
        "leak": (AUDIT_LEAK, bundle.get("leak")),
        "contract": (AUDIT_CONTRACT, bundle.get("contract")),
        "spans": (AUDIT_SPANS, bundle.get("spans")),
        "serialization": (AUDIT_SERIALIZATION, bundle.get("serialization")),
        "request": (AUDIT_REQUEST, bundle.get("request")),
        "budget": (AUDIT_BUDGET, bundle.get("budget")),
        "cost": (AUDIT_COST, bundle.get("cost")),
        "tests": (AUDIT_TESTS, bundle.get("tests")),
        "preflight": (AUDIT_PREFLIGHT, bundle.get("preflight")),
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
        "historical_dirs_untouched": True,
        "historical_contracts_modified": False,
        "human_label_modified": False,
    }
    written["index"] = write_bytes_atomic(directory / AUDIT_INDEX, header)
    return written


__all__ = ["write_phase_artifacts"]
