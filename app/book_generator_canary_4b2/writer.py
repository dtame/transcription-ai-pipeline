"""Atomic 4B.2 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_generator_canary_4b2.constants import (
    AUDIT_COST,
    AUDIT_COVERAGE,
    AUDIT_CANDIDATE,
    AUDIT_EVIDENCE,
    AUDIT_EXECUTION,
    AUDIT_FIDELITY,
    AUDIT_HYDRATION,
    AUDIT_LANGUAGE,
    AUDIT_PRECALL,
    AUDIT_PROVIDER,
    AUDIT_PROVENANCE,
    AUDIT_QUALITY,
    AUDIT_RAW_RESPONSE,
    AUDIT_RAW_TEXT,
    AUDIT_READINESS,
    AUDIT_REQUEST,
    AUDIT_RESPONSE,
    AUDIT_STRUCTURAL,
    PHASE,
)
from app.book_generator_canary_4b2.paths import (
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
    """Write raw provider evidence FIRST, before semantic processing."""
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
    production = production_book_path()
    written: dict[str, Path] = {}
    mapping = {
        "precall": (AUDIT_PRECALL, bundle.get("precall")),
        "evidence": (AUDIT_EVIDENCE, bundle.get("evidence_bundle")),
        "hydration": (AUDIT_HYDRATION, bundle.get("hydration")),
        "request": (AUDIT_REQUEST, bundle.get("request_identity")),
        "provider": (AUDIT_PROVIDER, bundle.get("provider_evidence")),
        "response": (AUDIT_RESPONSE, bundle.get("response_identity")),
        "structural": (AUDIT_STRUCTURAL, bundle.get("structural")),
        "coverage": (AUDIT_COVERAGE, bundle.get("coverage_audit")),
        "provenance": (AUDIT_PROVENANCE, bundle.get("provenance")),
        "language": (AUDIT_LANGUAGE, bundle.get("language")),
        "fidelity": (AUDIT_FIDELITY, bundle.get("fidelity")),
        "quality": (AUDIT_QUALITY, bundle.get("quality")),
        "cost": (AUDIT_COST, bundle.get("cost")),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
        "execution": (AUDIT_EXECUTION, bundle.get("execution")),
        "raw_response": (AUDIT_RAW_RESPONSE, bundle.get("raw_response")),
    }
    for key, (name, payload) in mapping.items():
        if payload is None:
            continue
        written[key] = _write(directory / name, payload)
    candidate = bundle.get("candidate")
    if isinstance(candidate, Mapping) and candidate.get("chapter"):
        written["candidate"] = _write(directory / AUDIT_CANDIDATE, candidate["chapter"])
    raw = bundle.get("raw_response")
    if isinstance(raw, Mapping) and isinstance(raw.get("text"), str):
        written["raw_text"] = _write(directory / AUDIT_RAW_TEXT, raw["text"])
    report_text = bundle.get("report_text")
    if isinstance(report_text, str) and report_text.strip():
        written["report"] = _write(report_path(root=root), report_text)
    header = {
        "phase": PHASE,
        "book_json": "NOT PUBLISHED",
        "production_path_absent": not production.is_file(),
        "written": sorted(written),
        "result": (bundle.get("header") or {}).get("result"),
    }
    written["index"] = _write(directory / "index.json", header)
    return written


__all__ = ["persist_raw_evidence", "write_canary_artifacts"]
