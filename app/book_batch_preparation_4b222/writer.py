"""Atomic 4B.2.22 audit writes. Never production book.json. Never accepted chapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_batch_preparation_4b222.constants import (
    AUDIT_ACCEPTANCE,
    AUDIT_AUTHORIZATION,
    AUDIT_COST,
    AUDIT_EX046,
    AUDIT_HASHES_POST,
    AUDIT_HASHES_PRE,
    AUDIT_INVENTORY,
    AUDIT_MANIFEST,
    AUDIT_PLAN,
    AUDIT_PREFLIGHT,
    AUDIT_PROGRESS,
    AUDIT_READINESS,
    AUDIT_STOP,
    AUDIT_TESTS,
    PHASE,
)
from app.book_batch_preparation_4b222.paths import phase_audit_dir, report_path
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
        AUDIT_ACCEPTANCE: bundle.get("ch018_editorial_acceptance"),
        AUDIT_MANIFEST: bundle.get("ch018_accepted_editorial_manifest"),
        AUDIT_EX046: bundle.get("ch018_ex046_traceability_review"),
        AUDIT_INVENTORY: bundle.get("remaining_17_chapters_inventory"),
        AUDIT_PLAN: bundle.get("batch_generation_plan"),
        AUDIT_COST: bundle.get("batch_cost_envelope"),
        AUDIT_AUTHORIZATION: bundle.get("batch_authorization_template"),
        AUDIT_PROGRESS: bundle.get("batch_progress_manifest"),
        AUDIT_STOP: bundle.get("batch_hard_stop_conditions"),
        AUDIT_TESTS: bundle.get("offline_regression_tests"),
        AUDIT_HASHES_POST: bundle.get("canonical_hashes_post"),
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
