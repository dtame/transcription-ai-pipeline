"""Atomic 4B.2.29 audit writes. Chapter sources are never rewritten."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_print_review_canonical_4b229.constants import (
    AUDIT_CHAPTER_SOURCES,
    AUDIT_EDITORIAL_STATUS,
    AUDIT_HASHES,
    AUDIT_INTEGRITY,
    AUDIT_MANIFEST,
    AUDIT_MARKDOWN,
    AUDIT_OBSERVATIONS,
    AUDIT_PREFLIGHT,
    AUDIT_PUBLICATION,
    AUDIT_READINESS,
    AUDIT_SCHEMA,
    AUDIT_TESTS,
    AUDIT_WORD,
    PHASE,
)
from app.book_print_review_canonical_4b229.paths import phase_audit_dir, report_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def write_phase_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, str]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, Any] = {
        AUDIT_PREFLIGHT: bundle.get("preflight"),
        AUDIT_MANIFEST: bundle.get("book_canonical_manifest"),
        AUDIT_CHAPTER_SOURCES: bundle.get("chapter_sources_manifest"),
        AUDIT_EDITORIAL_STATUS: bundle.get("editorial_status_manifest"),
        AUDIT_INTEGRITY: bundle.get("book_integrity_validation"),
        AUDIT_SCHEMA: bundle.get("book_schema_validation"),
        AUDIT_MARKDOWN: bundle.get("book_markdown_comparison"),
        AUDIT_WORD: bundle.get("word_renderer_readiness"),
        AUDIT_OBSERVATIONS: bundle.get("editorial_observations_manifest"),
        AUDIT_HASHES: bundle.get("canonical_hashes_pre_post"),
        AUDIT_PUBLICATION: bundle.get("publication_audit"),
        AUDIT_READINESS: bundle.get("readiness"),
        AUDIT_TESTS: bundle.get("offline_regression_tests"),
    }
    written: dict[str, str] = {}
    for name, payload in mapping.items():
        if not isinstance(payload, Mapping):
            continue
        path = write_bytes_atomic(directory / name, payload)
        written[name] = str(path).replace("\\", "/")
    report = bundle.get("report_text")
    if isinstance(report, str):
        path = write_bytes_atomic(report_path(root=root), report)
        written["report"] = str(path).replace("\\", "/")
    written["phase"] = PHASE
    return written


__all__ = ["write_phase_artifacts"]
