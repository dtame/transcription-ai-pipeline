"""Atomic 4B.2.12 audit writes. Never production book.json. Never historical mutation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b212.constants import (
    AUDIT_ARCHITECTURE,
    AUDIT_CONCEPTS,
    AUDIT_CONTRACT,
    AUDIT_FAKEAI,
    AUDIT_FORENSICS,
    AUDIT_HASHES,
    AUDIT_INDEX,
    AUDIT_INVENTORY,
    AUDIT_MISMATCH,
    AUDIT_POLICY,
    AUDIT_READINESS,
    AUDIT_REPLAY_201,
    AUDIT_RESUMPTION,
    AUDIT_SAFETY,
    AUDIT_SCHEMA,
    AUDIT_SEMANTIC,
    AUDIT_SYNTHETIC,
    AUDIT_TESTS,
    PHASE,
)
from app.book_semantic_gate_4b212.paths import (
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
        "forensics": (AUDIT_FORENSICS, bundle.get("forensics")),
        "mismatch": (AUDIT_MISMATCH, bundle.get("mismatch")),
        "concepts": (AUDIT_CONCEPTS, bundle.get("concepts")),
        "contract": (AUDIT_CONTRACT, bundle.get("contract")),
        "schema": (AUDIT_SCHEMA, bundle.get("schema")),
        "replay_201": (AUDIT_REPLAY_201, bundle.get("replay_201")),
        "semantic": (AUDIT_SEMANTIC, bundle.get("semantic")),
        "synthetic": (AUDIT_SYNTHETIC, bundle.get("synthetic")),
        "fakeai": (AUDIT_FAKEAI, bundle.get("fakeai")),
        "policy": (AUDIT_POLICY, bundle.get("policy")),
        "architecture": (AUDIT_ARCHITECTURE, bundle.get("architecture")),
        "resumption": (AUDIT_RESUMPTION, bundle.get("resumption")),
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
        "human_label_modified": False,
        "historical_raw_response_modified": False,
        "production_pipeline_modified": False,
        "semantic_gate_20_activated": False,
        "real_terra_canary_authorized": False,
    }
    written["index"] = write_bytes_atomic(directory / AUDIT_INDEX, header)
    return written


__all__ = ["write_phase_artifacts"]
