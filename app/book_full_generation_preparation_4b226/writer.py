"""Atomic 4B.2.26 audit writes. Never production book.json. Never accepted chapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_full_generation_preparation_4b226.constants import (
    AUDIT_ACCEPTED_INVENTORY,
    AUDIT_AUTHORIZATION,
    AUDIT_CH003_MANIFEST,
    AUDIT_CH004_MANIFEST,
    AUDIT_COST,
    AUDIT_HASHES_POST,
    AUDIT_HASHES_PRE,
    AUDIT_HASHES_PRE_POST,
    AUDIT_NORMALIZER_SPEC,
    AUDIT_NORMALIZER_TESTS,
    AUDIT_PLAN,
    AUDIT_PREFLIGHT,
    AUDIT_READINESS,
    AUDIT_REMAINING_INVENTORY,
    AUDIT_RESUME,
    AUDIT_SIMULATION,
    AUDIT_TESTS,
    PHASE,
)
from app.book_full_generation_preparation_4b226.paths import phase_audit_dir, report_path
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
        AUDIT_CH003_MANIFEST: bundle.get("ch003_accepted_editorial_manifest"),
        AUDIT_CH004_MANIFEST: bundle.get("ch004_accepted_editorial_manifest"),
        AUDIT_ACCEPTED_INVENTORY: bundle.get("accepted_chapters_inventory"),
        AUDIT_NORMALIZER_SPEC: bundle.get("empty_paragraph_normalization_spec"),
        AUDIT_NORMALIZER_TESTS: bundle.get("empty_paragraph_normalization_tests"),
        AUDIT_REMAINING_INVENTORY: bundle.get("remaining_chapters_inventory"),
        AUDIT_PLAN: bundle.get("remaining_chapters_generation_plan"),
        AUDIT_COST: bundle.get("remaining_chapters_budget_forecast"),
        AUDIT_AUTHORIZATION: bundle.get("global_authorization_proposal"),
        AUDIT_SIMULATION: bundle.get("full_batch_offline_simulation"),
        AUDIT_RESUME: bundle.get("resume_and_lock_validation"),
        AUDIT_HASHES_PRE_POST: bundle.get("canonical_hashes_pre_post"),
        AUDIT_HASHES_POST: bundle.get("canonical_hashes_post"),
        AUDIT_TESTS: bundle.get("offline_regression_tests"),
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
