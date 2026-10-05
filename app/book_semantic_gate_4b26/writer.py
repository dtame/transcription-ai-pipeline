"""Atomic 4B.2.6 audit writes. Never production book.json. Never historical audits."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b26.constants import (
    AUDIT_ACCOUNTING,
    AUDIT_CASES,
    AUDIT_COMPAT,
    AUDIT_COST,
    AUDIT_HUMAN,
    AUDIT_INDEX,
    AUDIT_PRECALL,
    AUDIT_PROVIDER,
    AUDIT_RAW_RESPONSE,
    AUDIT_RAW_TEXT,
    AUDIT_READINESS,
    AUDIT_REQUEST,
    AUDIT_RUNTIME,
    AUDIT_SCORE,
    AUDIT_TESTS,
    AUDIT_VALIDATION,
    PHASE,
)
from app.book_semantic_gate_4b26.paths import (
    canary_audit_dir,
    historical_audit_dirs,
    production_book_path,
    report_path,
)
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def _write(path: Path, payload: Mapping[str, Any] | str) -> Path:
    return write_bytes_atomic(path, payload)


def _assert_isolated(target: Path, historical: Mapping[str, Path]) -> None:
    resolved = target.resolve()
    for name, directory in historical.items():
        hist = directory.resolve()
        if resolved == hist or hist in resolved.parents or resolved.parent == hist:
            raise RuntimeError(
                f"4B.2.6 must not write into historical {name} audit directory."
            )


def persist_raw_evidence(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = canary_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    historical = historical_audit_dirs(root=root)
    written: dict[str, Path] = {}
    raw = bundle.get("raw_response")
    if raw is not None:
        target = directory / AUDIT_RAW_RESPONSE
        _assert_isolated(target, historical)
        written["raw_response"] = _write(target, raw)
    raw_text = None
    if isinstance(raw, Mapping):
        raw_text = raw.get("text")
    if isinstance(raw_text, str):
        target = directory / AUDIT_RAW_TEXT
        _assert_isolated(target, historical)
        written["raw_text"] = _write(target, raw_text)
    provider = bundle.get("provider_evidence")
    if provider is not None:
        target = directory / AUDIT_PROVIDER
        _assert_isolated(target, historical)
        written["provider"] = _write(target, provider)
    return written


def write_canary_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    directory = canary_audit_dir(root=root)
    historical = historical_audit_dirs(root=root)
    if directory.resolve() in {path.resolve() for path in historical.values()}:
        raise RuntimeError("4B.2.6 must not write into a historical audit directory.")
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    mapping = {
        "precall": (AUDIT_PRECALL, bundle.get("precall")),
        "runtime": (AUDIT_RUNTIME, bundle.get("runtime")),
        "request": (AUDIT_REQUEST, bundle.get("request_identity")),
        "compat": (AUDIT_COMPAT, bundle.get("api_compatibility")),
        "accounting": (AUDIT_ACCOUNTING, bundle.get("call_accounting")),
        "provider": (AUDIT_PROVIDER, bundle.get("provider_evidence")),
        "validation": (AUDIT_VALIDATION, bundle.get("response_validation")),
        "cases": (AUDIT_CASES, bundle.get("case_results")),
        "score": (AUDIT_SCORE, bundle.get("benchmark_score")),
        "human": (AUDIT_HUMAN, bundle.get("human_review")),
        "cost": (AUDIT_COST, bundle.get("cost")),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
        "tests": (AUDIT_TESTS, bundle.get("tests")),
    }
    for key, (name, payload) in mapping.items():
        if payload is None:
            continue
        target = directory / name
        _assert_isolated(target, historical)
        written[key] = _write(target, payload)
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
        "remote_invocations": (bundle.get("header") or {}).get("remote_invocations"),
        "historical_dirs_untouched": True,
        "historical_dirs": {name: str(path) for name, path in historical.items()},
    }
    written["index"] = _write(directory / AUDIT_INDEX, header)
    return written


__all__ = ["persist_raw_evidence", "write_canary_artifacts"]
