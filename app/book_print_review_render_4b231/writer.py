"""Atomic 4B.2.31 audit and binary writes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.book_print_review_render_4b231.constants import (
    AUDIT_FINALIZATION,
    AUDIT_GENERATION,
    AUDIT_HASHES,
    AUDIT_INTEGRITY,
    AUDIT_MAPPING,
    AUDIT_PAGINATION,
    AUDIT_PDF_CONTENT,
    AUDIT_PDF_EXPORT,
    AUDIT_PDF_GEOMETRY,
    AUDIT_PREFLIGHT,
    AUDIT_PUBLICATION,
    AUDIT_READINESS,
    AUDIT_TOC,
    AUDIT_VISUAL,
    AUDIT_WORD_ENV,
    PHASE,
)
from app.book_print_review_render_4b231.guard import BookPrintReviewRender4231Error
from app.book_print_review_render_4b231.paths import phase_audit_dir, report_path


def write_binary_atomic(path: Path, data: bytes) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_bytes(data)
        if partial.read_bytes() != data:
            raise BookPrintReviewRender4231Error(
                f"partial binary write mismatch for {path.name}. STOP."
            )
        leftover_name = path.with_name(path.name + ".partial")
        partial.replace(path)
        if leftover_name.exists() and leftover_name != path:
            leftover_name.unlink()
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()
    return path


def write_phase_artifacts(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, str]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, Any] = {
        AUDIT_PREFLIGHT: bundle.get("render_preflight"),
        AUDIT_WORD_ENV: bundle.get("word_environment_detection"),
        AUDIT_GENERATION: bundle.get("docx_generation_manifest"),
        AUDIT_INTEGRITY: bundle.get("docx_integrity_validation"),
        AUDIT_MAPPING: bundle.get("docx_content_mapping"),
        AUDIT_FINALIZATION: bundle.get("word_finalization_report"),
        AUDIT_TOC: bundle.get("toc_validation"),
        AUDIT_PAGINATION: bundle.get("pagination_validation"),
        AUDIT_PDF_EXPORT: bundle.get("pdf_export_report"),
        AUDIT_PDF_CONTENT: bundle.get("pdf_content_validation"),
        AUDIT_PDF_GEOMETRY: bundle.get("pdf_page_geometry_validation"),
        AUDIT_VISUAL: bundle.get("visual_inspection_report"),
        AUDIT_HASHES: bundle.get("canonical_hashes_pre_post"),
        AUDIT_PUBLICATION: bundle.get("publication_manifest"),
        AUDIT_READINESS: bundle.get("readiness"),
    }
    written: dict[str, str] = {}
    for name, payload in mapping.items():
        if not isinstance(payload, Mapping):
            continue
        safe = _json_safe(payload)
        path = write_bytes_atomic(directory / name, safe)
        written[name] = str(path).replace("\\", "/")
    report = bundle.get("report_text")
    if isinstance(report, str):
        path = write_bytes_atomic(report_path(root=root), report)
        written["report"] = str(path).replace("\\", "/")
    written["phase"] = PHASE
    return written


def _json_safe(payload: Mapping[str, Any]) -> dict[str, Any]:
    skip = {"payload", "profile", "book", "mapping", "doc"}
    data = {key: value for key, value in dict(payload).items() if key not in skip}
    mapping = payload.get("mapping")
    if isinstance(mapping, Mapping):
        mapped = list(mapping.get("mapped") or [])
        data["mapping"] = {
            key: value
            for key, value in dict(mapping).items()
            if key != "mapped"
        }
        data["mapping"]["mapped_count"] = len(mapped)
        data["mapping"]["mapped_sample"] = mapped[:5]
        data["mapping"]["mapped"] = mapped
    return data


__all__ = ["write_binary_atomic", "write_phase_artifacts"]
