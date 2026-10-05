"""Atomic 4B.2.18 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_authorial_voice_4b218.constants import (
    AUDIT_ATTRIBUTION,
    AUDIT_CHAPTER_V2_JSON,
    AUDIT_CHAPTER_V2_MD,
    AUDIT_CORRECTIONS,
    AUDIT_COVERAGE,
    AUDIT_DIFF,
    AUDIT_HASHES_POST,
    AUDIT_HASHES_PRE,
    AUDIT_HUMAN,
    AUDIT_IDEA_DIAGNOSIS,
    AUDIT_IDEA_MAPPINGS,
    AUDIT_NARRATIVE,
    AUDIT_POLICY,
    AUDIT_PREFLIGHT,
    AUDIT_PROMPT_11,
    AUDIT_READINESS,
    AUDIT_TESTS,
    PHASE,
)
from app.book_authorial_voice_4b218.paths import phase_audit_dir, report_path
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
        AUDIT_POLICY: bundle.get("authorial_voice_policy"),
        AUDIT_NARRATIVE: bundle.get("narrative_audit"),
        AUDIT_ATTRIBUTION: bundle.get("speaker_attribution_evidence"),
        AUDIT_CORRECTIONS: bundle.get("targeted_corrections"),
        AUDIT_CHAPTER_V2_JSON: bundle.get("chapter_candidate_authorial_v2"),
        AUDIT_PROMPT_11: bundle.get("generator_prompt_1_1_candidate"),
        AUDIT_IDEA_DIAGNOSIS: bundle.get("idea_traceability_diagnosis"),
        AUDIT_IDEA_MAPPINGS: bundle.get("idea_paragraph_mapping_proposals"),
        AUDIT_COVERAGE: bundle.get("source_coverage_review"),
        AUDIT_HUMAN: bundle.get("human_review_required"),
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
    markdown = bundle.get("chapter_candidate_authorial_v2_md")
    if isinstance(markdown, str):
        path = write_bytes_atomic(directory / AUDIT_CHAPTER_V2_MD, markdown)
        written[AUDIT_CHAPTER_V2_MD] = str(path).replace("\\", "/")
    diff = bundle.get("chapter_diff_md")
    if isinstance(diff, str):
        path = write_bytes_atomic(directory / AUDIT_DIFF, diff)
        written[AUDIT_DIFF] = str(path).replace("\\", "/")
    report = bundle.get("report_text")
    if isinstance(report, str):
        path = write_bytes_atomic(report_path(root=root), report)
        written["report"] = str(path).replace("\\", "/")
    written["phase"] = PHASE
    return written


__all__ = ["write_phase_artifacts"]
