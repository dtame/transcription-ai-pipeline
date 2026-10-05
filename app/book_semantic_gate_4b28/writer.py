"""Atomic 4B.2.8 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b28.constants import (
    AUDIT_ARCH_A,
    AUDIT_ARCH_B,
    AUDIT_ARCH_C,
    AUDIT_COMPARISON,
    AUDIT_CONTRACT,
    AUDIT_COST,
    AUDIT_FALSE_REJECTION,
    AUDIT_H01,
    AUDIT_H02,
    AUDIT_H11,
    AUDIT_INDEX,
    AUDIT_INVENTORY,
    AUDIT_MIGRATION,
    AUDIT_READINESS,
    AUDIT_REPLAY,
    AUDIT_SEGMENTATION,
    AUDIT_TAXONOMY,
    AUDIT_TESTS,
    PHASE,
)
from app.book_semantic_gate_4b28.paths import (
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
        "h01": (AUDIT_H01, bundle.get("h01")),
        "h02": (AUDIT_H02, bundle.get("h02")),
        "h11": (AUDIT_H11, bundle.get("h11")),
        "taxonomy": (AUDIT_TAXONOMY, bundle.get("taxonomy")),
        "architecture_a": (AUDIT_ARCH_A, bundle.get("architecture_a")),
        "architecture_b": (AUDIT_ARCH_B, bundle.get("architecture_b")),
        "architecture_c": (AUDIT_ARCH_C, bundle.get("architecture_c")),
        "segmentation": (AUDIT_SEGMENTATION, bundle.get("segmentation")),
        "replay": (AUDIT_REPLAY, bundle.get("replay")),
        "false_rejection": (AUDIT_FALSE_REJECTION, bundle.get("false_rejection")),
        "cost": (AUDIT_COST, bundle.get("cost")),
        "contract": (AUDIT_CONTRACT, bundle.get("contract")),
        "comparison": (AUDIT_COMPARISON, bundle.get("comparison")),
        "migration": (AUDIT_MIGRATION, bundle.get("migration")),
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
        "contract_20_activated": False,
    }
    written["index"] = write_bytes_atomic(directory / AUDIT_INDEX, header)
    return written


__all__ = ["write_phase_artifacts"]
