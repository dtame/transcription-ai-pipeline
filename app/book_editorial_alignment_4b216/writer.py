"""Atomic 4B.2.16 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_editorial_alignment_4b216.constants import (
    AUDIT_BUDGET,
    AUDIT_CANDIDATES,
    AUDIT_COVERAGE,
    AUDIT_FAITHFUL_PROMPT,
    AUDIT_HASHES,
    AUDIT_HUMAN,
    AUDIT_POLICY,
    AUDIT_PROMPT_REVIEW,
    AUDIT_READINESS,
    AUDIT_RISK_MAP,
    AUDIT_SCENARIOS,
    AUDIT_SELECTED,
    AUDIT_SEMANTIC,
    AUDIT_TESTS,
    PHASE,
)
from app.book_editorial_alignment_4b216.paths import phase_audit_dir, report_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def write_phase_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, str]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    mapping = {
        AUDIT_POLICY: bundle.get("policy"),
        AUDIT_PROMPT_REVIEW: bundle.get("prompt_review"),
        AUDIT_RISK_MAP: bundle.get("risk_map"),
        AUDIT_FAITHFUL_PROMPT: bundle.get("faithful_prompt"),
        AUDIT_COVERAGE: bundle.get("coverage"),
        AUDIT_SEMANTIC: bundle.get("semantic"),
        AUDIT_HUMAN: bundle.get("human"),
        AUDIT_CANDIDATES: bundle.get("candidates"),
        AUDIT_SELECTED: bundle.get("selected"),
        AUDIT_BUDGET: bundle.get("budget"),
        AUDIT_SCENARIOS: bundle.get("scenarios"),
        AUDIT_HASHES: bundle.get("hashes"),
        AUDIT_TESTS: bundle.get("tests"),
        AUDIT_READINESS: bundle.get("readiness"),
    }
    written: dict[str, str] = {}
    for name, payload in mapping.items():
        if not isinstance(payload, Mapping):
            continue
        path = write_bytes_atomic(directory / name, payload)
        written[name] = str(path).replace("\\", "/")
    report = bundle.get("report")
    if isinstance(report, str):
        path = write_bytes_atomic(report_path(root=root), report)
        written["report"] = str(path).replace("\\", "/")
    written["phase"] = PHASE
    return written


__all__ = ["write_phase_artifacts"]
