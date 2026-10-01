"""Atomic 4B.2.4 audit writes. Never production book.json or cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b24.constants import (
    ATTEMPT_2_DIRNAME,
    AUDIT_BENCHMARK,
    AUDIT_CASES,
    AUDIT_COST,
    AUDIT_HUMAN,
    AUDIT_LEAK,
    AUDIT_PRECALL,
    AUDIT_PROVIDER,
    AUDIT_RAW_RESPONSE,
    AUDIT_RAW_TEXT,
    AUDIT_READINESS,
    AUDIT_REASONS,
    AUDIT_REQUEST,
    AUDIT_RESPONSE,
    AUDIT_SCORE,
    AUDIT_VALIDATION,
    PHASE,
)
from app.book_semantic_gate_4b24.paths import (
    canary_audit_dir,
    production_book_path,
    report_path,
)
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def _write(path: Path, payload: Mapping[str, Any] | str) -> Path:
    return write_bytes_atomic(path, payload)


def persist_raw_evidence(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = canary_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    raw = bundle.get("raw_response")
    if raw is not None:
        written["raw_response"] = _write(directory / AUDIT_RAW_RESPONSE, raw)
    raw_text = None
    if isinstance(raw, Mapping):
        raw_text = raw.get("text")
    if isinstance(raw_text, str):
        written["raw_text"] = _write(directory / AUDIT_RAW_TEXT, raw_text)
    provider = bundle.get("provider_evidence")
    if provider is not None:
        written["provider"] = _write(directory / AUDIT_PROVIDER, provider)
    response = bundle.get("response_identity")
    if response is not None:
        written["response"] = _write(directory / AUDIT_RESPONSE, response)
    return written


def write_canary_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = canary_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    mapping = {
        "precall": (AUDIT_PRECALL, bundle.get("precall")),
        "benchmark": (AUDIT_BENCHMARK, bundle.get("benchmark_identity")),
        "leak": (AUDIT_LEAK, bundle.get("label_leak")),
        "request": (AUDIT_REQUEST, bundle.get("request_identity")),
        "provider": (AUDIT_PROVIDER, bundle.get("provider_evidence")),
        "response": (AUDIT_RESPONSE, bundle.get("response_identity")),
        "validation": (AUDIT_VALIDATION, bundle.get("response_validation")),
        "cases": (AUDIT_CASES, bundle.get("case_results")),
        "score": (AUDIT_SCORE, bundle.get("benchmark_score")),
        "reasons": (AUDIT_REASONS, bundle.get("reason_code_review")),
        "human": (AUDIT_HUMAN, bundle.get("human_review")),
        "cost": (AUDIT_COST, bundle.get("cost")),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
    }
    for key, (name, payload) in mapping.items():
        if payload is None:
            continue
        written[key] = _write(directory / name, payload)
    raw = bundle.get("raw_response")
    if raw is not None and "raw_response" not in written:
        written["raw_response"] = _write(directory / AUDIT_RAW_RESPONSE, raw)
        if isinstance(raw, Mapping) and isinstance(raw.get("text"), str):
            written["raw_text"] = _write(directory / AUDIT_RAW_TEXT, raw["text"])
    report_text = bundle.get("report_text")
    if isinstance(report_text, str) and report_text.strip():
        written["report"] = _write(report_path(root=root), report_text)
    header = {
        "phase": PHASE,
        "book_json": "NOT PUBLISHED",
        "production_book_absent": not production_book_path().is_file(),
        "written": sorted(written),
        "result": (bundle.get("header") or {}).get("result"),
        "actual_terra_calls": (bundle.get("header") or {}).get("actual_terra_calls"),
        "attempts": [
            {
                "attempt": 1,
                "result": "BLOCKED_PRECALL",
                "reason": "OPENAI_API_KEY missing",
                "actual_terra_calls": 0,
                "preserved_under": "attempt_1_blocked_precall",
            },
            {
                "attempt": 2,
                "result": (bundle.get("header") or {}).get("result"),
                "actual_terra_calls": (bundle.get("header") or {}).get(
                    "actual_terra_calls"
                ),
                "preserved_under": ATTEMPT_2_DIRNAME,
            },
        ],
        "attempt_1_preserved": True,
        "current_attempt": 2,
    }
    written["index"] = _write(directory / "book_semantic_gate_4b24_index.json", header)
    attempt2 = directory / ATTEMPT_2_DIRNAME
    attempt2.mkdir(parents=True, exist_ok=True)
    for path in written.values():
        if path.parent == directory:
            _write(attempt2 / path.name, path.read_text(encoding="utf-8"))
    return written


__all__ = ["persist_raw_evidence", "write_canary_artifacts"]
