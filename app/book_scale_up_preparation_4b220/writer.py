"""Atomic 4B.2.20 audit writes. Never production book.json. Never CH012."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_scale_up_preparation_4b220.constants import (
    AUDIT_CONTEXT,
    AUDIT_CONTRACT,
    AUDIT_COST,
    AUDIT_HASHES_POST,
    AUDIT_HASHES_PRE,
    AUDIT_INVENTORY,
    AUDIT_PLAN,
    AUDIT_PREFLIGHT,
    AUDIT_PROGRESS,
    AUDIT_PROMPT,
    AUDIT_READINESS,
    AUDIT_SELECTION,
    AUDIT_STOP,
    AUDIT_TESTS,
    PHASE,
)
from app.book_scale_up_preparation_4b220.paths import phase_audit_dir, report_path
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
        AUDIT_INVENTORY: bundle.get("remaining_chapters_inventory"),
        AUDIT_SELECTION: bundle.get("first_chapter_selection"),
        AUDIT_CONTRACT: bundle.get("generation_contract_matrix"),
        AUDIT_PROMPT: bundle.get("prompt_11_readiness"),
        AUDIT_CONTEXT: bundle.get("first_chapter_source_context_manifest"),
        AUDIT_COST: bundle.get("scale_up_cost_envelope"),
        AUDIT_PLAN: bundle.get("scale_up_execution_plan"),
        AUDIT_PROGRESS: bundle.get("scale_up_progress_manifest"),
        AUDIT_STOP: bundle.get("hard_stop_conditions"),
        AUDIT_TESTS: bundle.get("regression_tests"),
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
