"""Atomic 4B.2.21 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_generation_4b221.constants import (
    AUDIT_AUTHORIZATION,
    AUDIT_CANDIDATE_JSON,
    AUDIT_CANDIDATE_MD,
    AUDIT_CONTEXT,
    AUDIT_COST,
    AUDIT_EDITORIAL,
    AUDIT_HASHES_POST,
    AUDIT_HASHES_PRE,
    AUDIT_IDEA,
    AUDIT_PREFLIGHT,
    AUDIT_PROMPT,
    AUDIT_READINESS,
    AUDIT_RESPONSE_RAW,
    AUDIT_STRUCTURAL,
    AUDIT_TESTS,
    AUDIT_USAGE,
    PHASE,
)
from app.book_generation_4b221.lock import read_lock
from app.book_generation_4b221.paths import lock_path, phase_audit_dir, report_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic

_CALL_DEPENDENT = {
    AUDIT_RESPONSE_RAW,
    AUDIT_USAGE,
    AUDIT_CANDIDATE_JSON,
    AUDIT_CANDIDATE_MD,
    AUDIT_STRUCTURAL,
    AUDIT_IDEA,
    AUDIT_EDITORIAL,
}


def write_phase_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
    call_completed: bool = False,
) -> dict[str, str]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    mapping = {
        AUDIT_PREFLIGHT: bundle.get("preflight"),
        AUDIT_HASHES_PRE: bundle.get("canonical_hashes_pre"),
        AUDIT_AUTHORIZATION: bundle.get("authorization_scope"),
        AUDIT_PROMPT: bundle.get("prompt_manifest"),
        AUDIT_CONTEXT: bundle.get("source_context_manifest"),
        AUDIT_COST: bundle.get("cost_preflight"),
        AUDIT_RESPONSE_RAW: bundle.get("provider_response_raw"),
        AUDIT_USAGE: bundle.get("provider_usage"),
        AUDIT_CANDIDATE_JSON: bundle.get("chapter_candidate"),
        AUDIT_STRUCTURAL: bundle.get("structural_validation"),
        AUDIT_IDEA: bundle.get("idea_traceability_review"),
        AUDIT_EDITORIAL: bundle.get("editorial_readiness_review"),
        AUDIT_HASHES_POST: bundle.get("canonical_hashes_post"),
        AUDIT_TESTS: bundle.get("regression_tests"),
        AUDIT_READINESS: bundle.get("readiness"),
    }
    written: dict[str, str] = {}
    for name, payload in mapping.items():
        if payload is None:
            if name in _CALL_DEPENDENT and not call_completed:
                continue
            continue
        if isinstance(payload, Mapping) or isinstance(payload, list):
            path = write_bytes_atomic(directory / name, payload)
            written[name] = str(path).replace("\\", "/")
    markdown = bundle.get("chapter_candidate_md")
    if call_completed and isinstance(markdown, str):
        path = write_bytes_atomic(directory / AUDIT_CANDIDATE_MD, markdown)
        written[AUDIT_CANDIDATE_MD] = str(path).replace("\\", "/")
    lock = read_lock(lock_path(root=root))
    if lock is not None:
        written[bundle.get("lock_name") or "call_lock.json"] = str(
            lock_path(root=root)
        ).replace("\\", "/")
    report = bundle.get("report_text")
    if isinstance(report, str):
        path = write_bytes_atomic(report_path(root=root), report)
        written["report"] = str(path).replace("\\", "/")
    written["phase"] = PHASE
    return written


__all__ = ["write_phase_artifacts"]
