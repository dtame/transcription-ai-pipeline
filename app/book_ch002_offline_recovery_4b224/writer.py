"""Atomic 4B.2.24 audit writes. Never production book.json. Never originals."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_ch002_offline_recovery_4b224.constants import (
    AUDIT_CH001_JSON,
    AUDIT_CH001_MD,
    AUDIT_DIFF,
    AUDIT_FORENSIC,
    AUDIT_HASHES_POST,
    AUDIT_HASHES_PRE,
    AUDIT_MANIFEST,
    AUDIT_PREFLIGHT,
    AUDIT_PREVENTION,
    AUDIT_READINESS,
    AUDIT_RECOVERED_JSON,
    AUDIT_RECOVERED_MD,
    AUDIT_RECOVERY_READY,
    AUDIT_RESUME,
    AUDIT_TESTS,
    AUDIT_VALIDATION,
    PHASE,
)
from app.book_ch002_offline_recovery_4b224.paths import phase_audit_dir, report_path
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
        AUDIT_FORENSIC: bundle.get("ch002_empty_paragraph_forensic_review"),
        AUDIT_RECOVERED_JSON: bundle.get("chapter_candidate_recovered"),
        AUDIT_DIFF: bundle.get("recovery_diff"),
        AUDIT_MANIFEST: bundle.get("recovery_manifest"),
        AUDIT_VALIDATION: bundle.get("recovery_validation"),
        AUDIT_RECOVERY_READY: bundle.get("recovery_readiness"),
        AUDIT_CH001_JSON: bundle.get("ch001_human_editorial_review_packet"),
        AUDIT_RESUME: bundle.get("batch01_resume_plan"),
        AUDIT_TESTS: bundle.get("offline_regression_tests"),
        AUDIT_HASHES_POST: bundle.get("canonical_hashes_post"),
        AUDIT_READINESS: bundle.get("readiness"),
    }
    written: dict[str, str] = {}
    for name, payload in mapping.items():
        if payload is None:
            continue
        if isinstance(payload, (Mapping, list)):
            path = write_bytes_atomic(directory / name, payload)
            written[name] = str(path).replace("\\", "/")
    recovered_md = bundle.get("chapter_candidate_recovered_md")
    if isinstance(recovered_md, str):
        path = write_bytes_atomic(directory / AUDIT_RECOVERED_MD, recovered_md)
        written[AUDIT_RECOVERED_MD] = str(path).replace("\\", "/")
    ch001_md = bundle.get("ch001_human_editorial_review_packet_md")
    if isinstance(ch001_md, str):
        path = write_bytes_atomic(directory / AUDIT_CH001_MD, ch001_md)
        written[AUDIT_CH001_MD] = str(path).replace("\\", "/")
    prevention = bundle.get("empty_paragraph_prevention_analysis")
    if isinstance(prevention, str):
        path = write_bytes_atomic(directory / AUDIT_PREVENTION, prevention)
        written[AUDIT_PREVENTION] = str(path).replace("\\", "/")
    report = bundle.get("report_text")
    if isinstance(report, str):
        path = write_bytes_atomic(report_path(root=root), report)
        written["report"] = str(path).replace("\\", "/")
    written["phase"] = PHASE
    return written


__all__ = ["write_phase_artifacts"]
