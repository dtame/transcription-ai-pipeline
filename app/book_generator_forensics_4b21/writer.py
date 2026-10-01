"""Atomic 4B.2.1 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_generator_forensics_4b21.constants import (
    AUDIT_CONNECTIVE,
    AUDIT_COST,
    AUDIT_EMPTY,
    AUDIT_FUTURE_REQUEST,
    AUDIT_ILLUSTRATION,
    AUDIT_PROMPT,
    AUDIT_READINESS,
    AUDIT_ROOT_CAUSE,
    AUDIT_SCHEMA,
    AUDIT_SEMANTIC,
    AUDIT_VALIDATOR,
    PHASE,
)
from app.book_generator_forensics_4b21.paths import (
    phase_audit_dir,
    production_book_path,
    report_path,
)
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def write_forensics_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    mapping = {
        "empty": (AUDIT_EMPTY, bundle.get("empty_paragraph")),
        "connective": (AUDIT_CONNECTIVE, bundle.get("connective_claim")),
        "illustration": (AUDIT_ILLUSTRATION, bundle.get("invented_illustration")),
        "root_cause": (AUDIT_ROOT_CAUSE, bundle.get("root_cause")),
        "prompt": (AUDIT_PROMPT, bundle.get("prompt_hardening")),
        "schema": (AUDIT_SCHEMA, bundle.get("schema_transport")),
        "validator": (AUDIT_VALIDATOR, bundle.get("validator_hardening")),
        "semantic": (AUDIT_SEMANTIC, bundle.get("semantic_architecture")),
        "future_request": (AUDIT_FUTURE_REQUEST, bundle.get("future_request")),
        "cost": (AUDIT_COST, bundle.get("future_cost")),
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
        directory / "book_generator_4b21_index.json", header
    )
    return written
