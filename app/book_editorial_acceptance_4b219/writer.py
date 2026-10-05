"""Atomic 4B.2.19 audit writes. Never production book.json. Never accepted CH012."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_editorial_acceptance_4b219.constants import (
    AUDIT_ACCEPTANCE,
    AUDIT_CONSISTENCY,
    AUDIT_COVERAGE,
    AUDIT_HASHES_POST,
    AUDIT_HASHES_PRE,
    AUDIT_IDEA_REVIEW,
    AUDIT_MANIFEST,
    AUDIT_PREFLIGHT,
    AUDIT_PROMPT,
    AUDIT_READINESS,
    AUDIT_SCALE,
    AUDIT_SEMANTIC,
    AUDIT_TESTS,
    PHASE,
)
from app.book_editorial_acceptance_4b219.paths import phase_audit_dir, report_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def write_phase_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, str]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    mapping = {
        AUDIT_PREFLIGHT: bundle.get("preflight"),
        AUDIT_HASHES_PRE: bundle.get("canonical_hashes_pre"),
        AUDIT_ACCEPTANCE: bundle.get("ch012_editorial_acceptance"),
        AUDIT_MANIFEST: bundle.get("ch012_accepted_editorial_manifest"),
        AUDIT_CONSISTENCY: bundle.get("markdown_json_consistency"),
        AUDIT_IDEA_REVIEW: bundle.get("idea_content_mapping_review"),
        AUDIT_COVERAGE: bundle.get("source_coverage_review"),
        AUDIT_SEMANTIC: bundle.get("semantic_validation_readiness"),
        AUDIT_PROMPT: bundle.get("generator_prompt_readiness"),
        AUDIT_SCALE: bundle.get("scale_up_options"),
        AUDIT_HASHES_POST: bundle.get("canonical_hashes_post"),
        AUDIT_TESTS: bundle.get("regression_tests"),
        AUDIT_READINESS: bundle.get("readiness"),
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
