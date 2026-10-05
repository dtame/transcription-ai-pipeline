"""Atomic 4B.2.7.6 audit writes. Never production book.json. Never historical mutation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b276.constants import (
    AUDIT_CONTRACT,
    AUDIT_COST,
    AUDIT_CRITERIA,
    AUDIT_DETERMINISM,
    AUDIT_EVIDENCE,
    AUDIT_HUMAN,
    AUDIT_INDEX,
    AUDIT_INVENTORY,
    AUDIT_LEAK,
    AUDIT_MATRIX,
    AUDIT_PARAGRAPH,
    AUDIT_PROVENANCE,
    AUDIT_READINESS,
    AUDIT_REASONS,
    AUDIT_REQUEST,
    AUDIT_SDK,
    AUDIT_TESTS,
    PHASE,
)
from app.book_semantic_gate_4b276.paths import (
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
        "matrix": (AUDIT_MATRIX, bundle.get("matrix")),
        "provenance": (AUDIT_PROVENANCE, bundle.get("provenance")),
        "evidence": (AUDIT_EVIDENCE, bundle.get("evidence")),
        "human": (AUDIT_HUMAN, bundle.get("human")),
        "request": (AUDIT_REQUEST, bundle.get("provider_request")),
        "determinism": (AUDIT_DETERMINISM, bundle.get("determinism")),
        "leak": (AUDIT_LEAK, bundle.get("leak")),
        "contract": (AUDIT_CONTRACT, bundle.get("contract")),
        "reasons": (AUDIT_REASONS, bundle.get("reasons")),
        "sdk": (AUDIT_SDK, bundle.get("serialization")),
        "cost": (AUDIT_COST, bundle.get("cost")),
        "criteria": (AUDIT_CRITERIA, bundle.get("criteria")),
        "tests": (AUDIT_TESTS, bundle.get("tests")),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
    }
    for key, (name, payload) in mapping.items():
        if payload is None:
            continue
        written[key] = write_bytes_atomic(directory / name, payload)
    paragraph = bundle.get("paragraph_text")
    if isinstance(paragraph, str) and paragraph.strip():
        written["paragraph"] = write_bytes_atomic(directory / AUDIT_PARAGRAPH, paragraph)
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
        "candidate_promoted": False,
    }
    written["index"] = write_bytes_atomic(directory / AUDIT_INDEX, header)
    return written


__all__ = ["write_phase_artifacts"]
