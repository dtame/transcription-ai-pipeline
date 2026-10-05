"""Atomic 4B.2.13 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_generation_integration_4b213.constants import (
    AUDIT_ARCHITECTURE,
    AUDIT_CACHE,
    AUDIT_CHAPTER,
    AUDIT_CONTRACT,
    AUDIT_COST,
    AUDIT_FAKEAI_GENERATION,
    AUDIT_FAKEAI_SEMANTIC,
    AUDIT_HASHES,
    AUDIT_INDEX,
    AUDIT_INVALIDATION,
    AUDIT_INVENTORY,
    AUDIT_PHASE5,
    AUDIT_PREPARATION,
    AUDIT_READINESS,
    AUDIT_RECOVERY,
    AUDIT_SAFETY,
    AUDIT_STRATEGY,
    AUDIT_TESTS,
    AUDIT_TRACEABILITY,
    PHASE,
)
from app.book_generation_integration_4b213.paths import (
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
        "contract": (AUDIT_CONTRACT, bundle.get("contract")),
        "preparation": (AUDIT_PREPARATION, bundle.get("preparation")),
        "fakeai_generation": (AUDIT_FAKEAI_GENERATION, bundle.get("fakeai_generation")),
        "fakeai_semantic": (AUDIT_FAKEAI_SEMANTIC, bundle.get("fakeai_semantic")),
        "chapter": (AUDIT_CHAPTER, bundle.get("chapter")),
        "cache": (AUDIT_CACHE, bundle.get("cache")),
        "invalidation": (AUDIT_INVALIDATION, bundle.get("invalidation")),
        "recovery": (AUDIT_RECOVERY, bundle.get("recovery")),
        "traceability": (AUDIT_TRACEABILITY, bundle.get("traceability")),
        "phase5": (AUDIT_PHASE5, bundle.get("phase5")),
        "cost": (AUDIT_COST, bundle.get("cost")),
        "strategy": (AUDIT_STRATEGY, bundle.get("strategy")),
        "safety": (AUDIT_SAFETY, bundle.get("safety")),
        "hashes": (AUDIT_HASHES, bundle.get("hashes")),
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
        "historical_labels_modified": False,
        "production_pipeline_modified": False,
        "semantic_gate_20_activated": False,
        "real_chapter_generation_authorized": False,
    }
    written["index"] = write_bytes_atomic(directory / AUDIT_INDEX, header)
    return written


__all__ = ["write_phase_artifacts"]
