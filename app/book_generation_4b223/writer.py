"""Atomic 4B.2.23 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_generation_4b223.constants import (
    AUDIT_AUTHORIZATION,
    AUDIT_CANDIDATE_JSON,
    AUDIT_CANDIDATE_MD,
    AUDIT_CONTEXT,
    AUDIT_COST,
    AUDIT_EDITORIAL,
    AUDIT_EX_REF,
    AUDIT_HASHES_POST,
    AUDIT_HASHES_PRE,
    AUDIT_IDEA,
    AUDIT_LEDGER,
    AUDIT_MANIFEST,
    AUDIT_PREFLIGHT,
    AUDIT_PROGRESS,
    AUDIT_PROMPT,
    AUDIT_READINESS,
    AUDIT_RESPONSE_RAW,
    AUDIT_STRUCTURAL,
    AUDIT_SUMMARY,
    AUDIT_TESTS,
    AUDIT_USAGE,
    PHASE,
)
from app.book_generation_4b223.lock import read_lock
from app.book_generation_4b223.paths import (
    batch_lock_path,
    chapter_audit_dir,
    lock_path,
    phase_audit_dir,
    report_path,
)
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic

_CALL_DEPENDENT = {
    AUDIT_RESPONSE_RAW,
    AUDIT_USAGE,
    AUDIT_CANDIDATE_JSON,
    AUDIT_CANDIDATE_MD,
    AUDIT_STRUCTURAL,
    AUDIT_IDEA,
    AUDIT_EX_REF,
    AUDIT_EDITORIAL,
}


def write_chapter_artifacts(
    chapter_id: str,
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
    call_completed: bool = False,
) -> dict[str, str]:
    directory = chapter_audit_dir(chapter_id, root=root)
    directory.mkdir(parents=True, exist_ok=True)
    mapping = {
        AUDIT_PREFLIGHT: bundle.get("preflight"),
        AUDIT_PROMPT: bundle.get("prompt_manifest"),
        AUDIT_CONTEXT: bundle.get("source_context_manifest"),
        AUDIT_COST: bundle.get("cost_preflight"),
        AUDIT_RESPONSE_RAW: bundle.get("provider_response_raw"),
        AUDIT_USAGE: bundle.get("provider_usage"),
        AUDIT_CANDIDATE_JSON: bundle.get("chapter_candidate"),
        AUDIT_STRUCTURAL: bundle.get("structural_validation"),
        AUDIT_IDEA: bundle.get("idea_traceability_review"),
        AUDIT_EX_REF: bundle.get("ex_ref_traceability_review"),
        AUDIT_EDITORIAL: bundle.get("editorial_readiness_review"),
        AUDIT_READINESS: bundle.get("readiness"),
    }
    written: dict[str, str] = {}
    for name, payload in mapping.items():
        if payload is None:
            continue
        if name in _CALL_DEPENDENT and not call_completed and name not in {
            AUDIT_STRUCTURAL,
            AUDIT_IDEA,
            AUDIT_EX_REF,
            AUDIT_EDITORIAL,
            AUDIT_READINESS,
        }:
            if name in {AUDIT_RESPONSE_RAW, AUDIT_USAGE, AUDIT_CANDIDATE_JSON}:
                continue
        if isinstance(payload, (Mapping, list)):
            path = write_bytes_atomic(directory / name, payload)
            written[name] = str(path).replace("\\", "/")
    markdown = bundle.get("chapter_candidate_md")
    if call_completed and isinstance(markdown, str):
        path = write_bytes_atomic(directory / AUDIT_CANDIDATE_MD, markdown)
        written[AUDIT_CANDIDATE_MD] = str(path).replace("\\", "/")
    lock = read_lock(lock_path(chapter_id, root=root))
    if lock is not None:
        written[AUDIT_CANDIDATE_JSON and "call_lock.json"] = str(
            lock_path(chapter_id, root=root)
        ).replace("\\", "/")
    return written


def write_batch_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, str]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    mapping = {
        AUDIT_MANIFEST: bundle.get("batch_manifest"),
        AUDIT_AUTHORIZATION: bundle.get("authorization_scope"),
        AUDIT_LEDGER: bundle.get("batch_budget_ledger"),
        AUDIT_PROGRESS: bundle.get("batch_progress"),
        AUDIT_SUMMARY: bundle.get("batch_summary"),
        AUDIT_HASHES_PRE: bundle.get("canonical_hashes_pre"),
        AUDIT_HASHES_POST: bundle.get("canonical_hashes_post"),
        AUDIT_TESTS: bundle.get("regression_tests"),
        AUDIT_READINESS: bundle.get("readiness"),
        AUDIT_PREFLIGHT: bundle.get("preflight"),
    }
    written: dict[str, str] = {}
    for name, payload in mapping.items():
        if payload is None:
            continue
        if isinstance(payload, (Mapping, list)):
            path = write_bytes_atomic(directory / name, payload)
            written[name] = str(path).replace("\\", "/")
    lock = read_lock(batch_lock_path(root=root))
    if lock is not None:
        written["batch_lock.json"] = str(batch_lock_path(root=root)).replace("\\", "/")
    report = bundle.get("report_text")
    if isinstance(report, str):
        path = write_bytes_atomic(report_path(root=root), report)
        written["report"] = str(path).replace("\\", "/")
    written["phase"] = PHASE
    return written


__all__ = ["write_batch_artifacts", "write_chapter_artifacts"]
