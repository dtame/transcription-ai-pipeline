"""Atomic 4B.2.17 audit writes. Never production book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_generation_4b217.constants import (
    AUDIT_AUTHORIZATION,
    AUDIT_CANDIDATE_JSON,
    AUDIT_CANDIDATE_MD,
    AUDIT_CONTEXT,
    AUDIT_COST,
    AUDIT_COVERAGE,
    AUDIT_HASHES_POST,
    AUDIT_HASHES_PRE,
    AUDIT_HYDRATED,
    AUDIT_POLICY,
    AUDIT_PREFLIGHT,
    AUDIT_PROMPT,
    AUDIT_READINESS,
    AUDIT_REQUEST_HASH,
    AUDIT_RESPONSE,
    AUDIT_RISKS,
    AUDIT_STRUCTURAL,
    AUDIT_TESTS,
    PHASE,
)
from app.book_generation_4b217.paths import phase_audit_dir, report_path
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
        AUDIT_POLICY: bundle.get("editorial_policy_snapshot"),
        AUDIT_PROMPT: bundle.get("generator_prompt_snapshot"),
        AUDIT_CONTEXT: bundle.get("chapter_context_manifest"),
        AUDIT_HYDRATED: bundle.get("hydrated_source_manifest"),
        AUDIT_COST: bundle.get("cost_preflight"),
        AUDIT_AUTHORIZATION: bundle.get("provider_call_authorization"),
        AUDIT_REQUEST_HASH: bundle.get("provider_request_hash"),
        AUDIT_RESPONSE: bundle.get("provider_response_metadata"),
        AUDIT_CANDIDATE_JSON: bundle.get("chapter_candidate"),
        AUDIT_STRUCTURAL: bundle.get("structural_validation"),
        AUDIT_COVERAGE: bundle.get("source_coverage"),
        AUDIT_RISKS: bundle.get("editorial_risk_flags"),
        AUDIT_HASHES_POST: bundle.get("canonical_hashes_post"),
        AUDIT_TESTS: bundle.get("regression_tests"),
        AUDIT_READINESS: bundle.get("readiness"),
    }
    written: dict[str, str] = {}
    for name, payload in mapping.items():
        if payload is None:
            if name in {AUDIT_CANDIDATE_JSON, AUDIT_RESPONSE}:
                payload = {
                    "phase": PHASE,
                    "status": "NOT_PRODUCED",
                    "invented_provider_response": False,
                    "secrets_included": False,
                }
            else:
                continue
        if isinstance(payload, Mapping) or isinstance(payload, list):
            path = write_bytes_atomic(directory / name, payload)
            written[name] = str(path).replace("\\", "/")
    markdown = bundle.get("chapter_candidate_md")
    if isinstance(markdown, str):
        path = write_bytes_atomic(directory / AUDIT_CANDIDATE_MD, markdown)
        written[AUDIT_CANDIDATE_MD] = str(path).replace("\\", "/")
    report = bundle.get("report_text")
    if isinstance(report, str):
        path = write_bytes_atomic(report_path(root=root), report)
        written["report"] = str(path).replace("\\", "/")
    written["phase"] = PHASE
    return written


__all__ = ["write_phase_artifacts"]
