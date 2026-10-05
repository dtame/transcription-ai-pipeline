"""Atomic 4B.2.28 audit writes. Never production book.json. Never chapter sources."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_full_manuscript_review_4b228.constants import (
    AUDIT_ASSEMBLY_SPEC,
    AUDIT_CONTINUITY,
    AUDIT_EDITORIAL_JSON,
    AUDIT_EDITORIAL_MD,
    AUDIT_HASHES_POST,
    AUDIT_HASHES_PRE,
    AUDIT_HASHES_PRE_POST,
    AUDIT_HUMAN_CHECKLIST,
    AUDIT_HUMAN_GUIDE,
    AUDIT_INTEGRITY,
    AUDIT_INVENTORY,
    AUDIT_MANUSCRIPT,
    AUDIT_PREFLIGHT,
    AUDIT_PROVENANCE,
    AUDIT_READINESS,
    AUDIT_REFERENCES,
    AUDIT_STRENGTHENED,
    AUDIT_TESTS,
    AUDIT_TRACEABILITY,
    PHASE,
)
from app.book_full_manuscript_review_4b228.paths import phase_audit_dir, report_path
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
        AUDIT_HASHES_PRE: bundle.get("canonical_hashes_pre"),
        AUDIT_INVENTORY: bundle.get("chapters_inventory"),
        AUDIT_PROVENANCE: bundle.get("manuscript_provenance_manifest"),
        AUDIT_INTEGRITY: bundle.get("manuscript_integrity_validation"),
        AUDIT_EDITORIAL_JSON: bundle.get("editorial_global_review_payload"),
        AUDIT_STRENGTHENED: bundle.get("strengthened_claims_review"),
        AUDIT_REFERENCES: bundle.get("references_examples_review"),
        AUDIT_CONTINUITY: bundle.get("continuity_review"),
        AUDIT_HUMAN_CHECKLIST: bundle.get("human_review_checklist"),
        AUDIT_HASHES_PRE_POST: bundle.get("canonical_hashes_pre_post"),
        AUDIT_HASHES_POST: bundle.get("canonical_hashes_post"),
        AUDIT_TESTS: bundle.get("offline_regression_tests"),
        AUDIT_READINESS: bundle.get("readiness"),
        AUDIT_TRACEABILITY: bundle.get("paragraph_traceability"),
        AUDIT_ASSEMBLY_SPEC: bundle.get("manuscript_assembly_spec"),
    }
    written: dict[str, str] = {}
    for name, payload in mapping.items():
        if not isinstance(payload, Mapping):
            continue
        path = write_bytes_atomic(directory / name, payload)
        written[name] = str(path).replace("\\", "/")
    texts = {
        AUDIT_MANUSCRIPT: bundle.get("manuscript_text"),
        AUDIT_EDITORIAL_MD: bundle.get("editorial_global_review_markdown"),
        AUDIT_HUMAN_GUIDE: bundle.get("human_review_guide_text"),
    }
    for name, payload in texts.items():
        if not isinstance(payload, str):
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
