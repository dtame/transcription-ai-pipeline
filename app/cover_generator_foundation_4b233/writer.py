"""Atomic 4B.2.33 audit writes. No cover image, DOCX, or PDF."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.cover_generator_foundation_4b233.constants import (
    AUDIT_AUTHOR_SCHEMA,
    AUDIT_CONTENT,
    AUDIT_COVER_SCHEMA,
    AUDIT_DECISIONS,
    AUDIT_HARDWARE,
    AUDIT_HASHES,
    AUDIT_IMAGE,
    AUDIT_INVENTORY,
    AUDIT_MODELS,
    AUDIT_PAID,
    AUDIT_READINESS,
    AUDIT_RENDERER,
    AUDIT_TESTS,
    PHASE,
)
from app.cover_generator_foundation_4b233.guard import assert_write_target_allowed
from app.cover_generator_foundation_4b233.paths import phase_audit_dir, report_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def write_phase_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, str]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, Any] = {
        AUDIT_INVENTORY: bundle.get("existing_architecture_inventory"),
        AUDIT_AUTHOR_SCHEMA: bundle.get("author_library_schema"),
        AUDIT_COVER_SCHEMA: bundle.get("cover_schema"),
        AUDIT_CONTENT: bundle.get("cover_content_contract"),
        AUDIT_IMAGE: bundle.get("image_provider_contract"),
        AUDIT_HARDWARE: bundle.get("hardware_diagnostic"),
        AUDIT_MODELS: bundle.get("local_model_compatibility"),
        AUDIT_PAID: bundle.get("paid_provider_policy"),
        AUDIT_RENDERER: bundle.get("cover_renderer_contract"),
        AUDIT_TESTS: bundle.get("offline_tests"),
        AUDIT_HASHES: bundle.get("canonical_hashes_pre_post"),
        AUDIT_READINESS: bundle.get("readiness"),
    }
    written: dict[str, str] = {}
    for name, payload in mapping.items():
        if not isinstance(payload, Mapping):
            continue
        target = directory / name
        assert_write_target_allowed(target)
        path = write_bytes_atomic(target, payload)
        written[name] = str(path).replace("\\", "/")
    decisions = bundle.get("architecture_decisions_markdown")
    if isinstance(decisions, str):
        target = directory / AUDIT_DECISIONS
        assert_write_target_allowed(target)
        path = write_bytes_atomic(target, decisions)
        written[AUDIT_DECISIONS] = str(path).replace("\\", "/")
    report = bundle.get("report_text")
    if isinstance(report, str):
        target = report_path(root=root)
        assert_write_target_allowed(target)
        path = write_bytes_atomic(target, report)
        written["report"] = str(path).replace("\\", "/")
    written["phase"] = PHASE
    return written


__all__ = ["write_phase_artifacts"]
