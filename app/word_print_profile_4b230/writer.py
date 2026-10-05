"""Atomic 4B.2.30 audit writes. No DOCX. No PDF. No book.json rewrite."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.word_print_profile_4b230.constants import (
    AUDIT_COVER,
    AUDIT_FINALIZER,
    AUDIT_GEOMETRY,
    AUDIT_HASHES,
    AUDIT_HEADERS,
    AUDIT_INVENTORY,
    AUDIT_MAPPING,
    AUDIT_PROFILE,
    AUDIT_READINESS,
    AUDIT_STYLES,
    AUDIT_TESTS,
    AUDIT_TOC,
    PHASE,
)
from app.word_print_profile_4b230.paths import phase_audit_dir, report_path
from app.word_renderer.document import assert_not_published


def write_phase_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, str]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, Any] = {
        AUDIT_INVENTORY: bundle.get("word_renderer_inventory"),
        AUDIT_PROFILE: bundle.get("print_profile_6x9"),
        AUDIT_STYLES: bundle.get("styles_validation"),
        AUDIT_GEOMETRY: bundle.get("page_geometry_validation"),
        AUDIT_TOC: bundle.get("toc_validation"),
        AUDIT_HEADERS: bundle.get("headers_footers_validation"),
        AUDIT_MAPPING: bundle.get("book_mapping_validation"),
        AUDIT_FINALIZER: bundle.get("word_finalizer_readiness"),
        AUDIT_COVER: bundle.get("cover_integration_contract"),
        AUDIT_TESTS: bundle.get("offline_tests"),
        AUDIT_HASHES: bundle.get("canonical_hashes_pre_post"),
        AUDIT_READINESS: bundle.get("readiness"),
    }
    written: dict[str, str] = {}
    for name, payload in mapping.items():
        if not isinstance(payload, Mapping):
            continue
        target = directory / name
        assert_not_published(target)
        path = write_bytes_atomic(target, payload)
        written[name] = str(path).replace("\\", "/")
    report = bundle.get("report_text")
    if isinstance(report, str):
        target = report_path(root=root)
        assert_not_published(target)
        path = write_bytes_atomic(target, report)
        written["report"] = str(path).replace("\\", "/")
    written["phase"] = PHASE
    return written


__all__ = ["write_phase_artifacts"]
