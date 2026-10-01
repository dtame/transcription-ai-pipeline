"""Atomic A.3.3 audit writes. Never production editorial_plan.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.editorial_planner_canary_4a33.constants import (
    AUDIT_BUDGET,
    AUDIT_CANDIDATE,
    AUDIT_CHAPTER,
    AUDIT_COVERAGE,
    AUDIT_EXECUTION,
    AUDIT_LANGUAGE,
    AUDIT_PRECALL,
    AUDIT_PROVIDER,
    AUDIT_PUBLICATION,
    AUDIT_RAW_RESPONSE,
    AUDIT_RAW_TEXT,
    AUDIT_READINESS,
    AUDIT_RESPONSE,
    AUDIT_SECTION,
    AUDIT_SEMANTIC,
    AUDIT_TECHNICAL,
    AUDIT_THINKING,
    PHASE,
)
from app.editorial_planner_canary_4a33.paths import (
    canary_audit_dir,
    production_editorial_plan_path,
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
    production = production_editorial_plan_path()
    written: dict[str, Path] = {}
    mapping = {
        "precall": (AUDIT_PRECALL, bundle.get("precall")),
        "provider": (AUDIT_PROVIDER, bundle.get("provider_evidence")),
        "response": (AUDIT_RESPONSE, bundle.get("response_identity")),
        "thinking": (AUDIT_THINKING, bundle.get("thinking")),
        "budget": (AUDIT_BUDGET, bundle.get("budget")),
        "language": (AUDIT_LANGUAGE, bundle.get("language")),
        "technical": (AUDIT_TECHNICAL, bundle.get("technical")),
        "coverage": (AUDIT_COVERAGE, bundle.get("coverage_audit")),
        "chapter": (AUDIT_CHAPTER, bundle.get("chapter_review")),
        "section": (AUDIT_SECTION, bundle.get("section_review")),
        "semantic": (AUDIT_SEMANTIC, bundle.get("semantic")),
        "publication": (AUDIT_PUBLICATION, bundle.get("publication")),
        "readiness": (AUDIT_READINESS, bundle.get("readiness")),
        "execution": (AUDIT_EXECUTION, bundle.get("execution")),
        "raw_response": (AUDIT_RAW_RESPONSE, bundle.get("raw_response")),
    }
    for key, (name, payload) in mapping.items():
        if payload is None:
            continue
        written[key] = _write(directory / name, payload)
    candidate = bundle.get("candidate")
    if isinstance(candidate, Mapping) and candidate.get("plan"):
        written["candidate"] = _write(directory / AUDIT_CANDIDATE, candidate["plan"])
    raw = bundle.get("raw_response")
    if isinstance(raw, Mapping) and isinstance(raw.get("text"), str):
        written["raw_text"] = _write(directory / AUDIT_RAW_TEXT, raw["text"])
    report_text = bundle.get("report_text")
    if isinstance(report_text, str) and report_text.strip():
        written["report"] = _write(report_path(root=root), report_text)
    header = {
        "phase": PHASE,
        "editorial_plan_json": "NOT PUBLISHED",
        "production_path_absent": not production.is_file(),
        "written": sorted(written),
        "result": (bundle.get("header") or {}).get("result"),
    }
    written["index"] = _write(directory / "index.json", header)
    return written


__all__ = ["persist_raw_evidence", "write_canary_artifacts"]
