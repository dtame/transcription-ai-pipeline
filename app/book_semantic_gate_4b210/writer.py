"""Atomic 4B.2.10 audit writes. Never production book.json. Never historical mutation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b210.constants import (
    AUDIT_CONTRACT,
    AUDIT_COST,
    AUDIT_CRITERIA,
    AUDIT_DETERMINISM,
    AUDIT_FAKEAI,
    AUDIT_INDEX,
    AUDIT_INSTRUCTIONS,
    AUDIT_INVENTORY,
    AUDIT_LEAK,
    AUDIT_READINESS,
    AUDIT_REQUEST,
    AUDIT_REQUEST_SHA,
    AUDIT_SAFETY,
    AUDIT_SDK,
    AUDIT_SELECTION,
    AUDIT_SERIALIZATION,
    AUDIT_STOP,
    AUDIT_TESTS,
    AUDIT_TRANSPORT,
    AUDIT_UNITS,
    PHASE,
)
from app.book_semantic_gate_4b210.paths import (
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
        "contract": (AUDIT_CONTRACT, bundle.get("contract_review")),
        "instructions": (AUDIT_INSTRUCTIONS, bundle.get("instructions")),
        "units": (AUDIT_UNITS, bundle.get("units")),
        "transport": (AUDIT_TRANSPORT, bundle.get("transport")),
        "sdk": (AUDIT_SDK, bundle.get("sdk")),
        "selection": (AUDIT_SELECTION, bundle.get("selection")),
        "request": (AUDIT_REQUEST, bundle.get("provider_request")),
        "leak": (AUDIT_LEAK, bundle.get("leak")),
        "determinism": (AUDIT_DETERMINISM, bundle.get("determinism")),
        "serialization": (AUDIT_SERIALIZATION, bundle.get("serialization")),
        "fakeai": (AUDIT_FAKEAI, bundle.get("fakeai")),
        "criteria": (AUDIT_CRITERIA, bundle.get("criteria")),
        "stop": (AUDIT_STOP, bundle.get("stop_rule")),
        "cost": (AUDIT_COST, bundle.get("cost")),
        "safety": (AUDIT_SAFETY, bundle.get("safety")),
        "tests": (AUDIT_TESTS, bundle.get("tests")),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
    }
    for key, (name, payload) in mapping.items():
        if payload is None:
            continue
        written[key] = write_bytes_atomic(directory / name, payload)
    sha = bundle.get("request_sha256_text")
    if isinstance(sha, str) and sha.strip():
        written["request_sha"] = write_bytes_atomic(directory / AUDIT_REQUEST_SHA, sha.strip())
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
        "real_terra_canary_authorized": False,
    }
    written["index"] = write_bytes_atomic(directory / AUDIT_INDEX, header)
    return written


__all__ = ["write_phase_artifacts"]
