"""Atomic 4B.2.32 audit writes. Never targets print-review-v1."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_print_review_pagination_fix_4b232.constants import (
    AUDIT_FRONT_MATTER,
    AUDIT_HASHES,
    AUDIT_INTEGRITY,
    AUDIT_PDF,
    AUDIT_POLICY,
    AUDIT_PUBLICATION,
    AUDIT_TESTS,
    AUDIT_TOC,
    AUDIT_TRANSITIONS,
    PHASE,
)
from app.book_print_review_pagination_fix_4b232.guard import (
    BookPrintReviewPaginationFix4232Error,
    assert_not_v1_target,
)
from app.book_print_review_pagination_fix_4b232.paths import phase_audit_dir, report_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def write_binary_atomic(path: Path, data: bytes) -> Path:
    assert_not_v1_target(path)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    leftover = path.with_name(path.name + ".partial")
    try:
        leftover.write_bytes(data)
        if leftover.read_bytes() != data:
            raise BookPrintReviewPaginationFix4232Error(
                f"partial binary write mismatch for {path.name}. STOP."
            )
        leftover.replace(path)
    except BaseException:
        leftover.unlink(missing_ok=True)
        raise
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
        AUDIT_POLICY: bundle.get("chapter_break_policy_before_after"),
        AUDIT_TRANSITIONS: bundle.get("chapter_transition_validation"),
        AUDIT_FRONT_MATTER: bundle.get("front_matter_comparison"),
        AUDIT_INTEGRITY: bundle.get("docx_integrity_validation"),
        AUDIT_PDF: bundle.get("pdf_integrity_validation"),
        AUDIT_TOC: bundle.get("toc_pagination_validation"),
        AUDIT_HASHES: bundle.get("canonical_hashes_pre_post"),
        AUDIT_PUBLICATION: bundle.get("publication_manifest"),
        AUDIT_TESTS: bundle.get("offline_tests"),
    }
    written: dict[str, str] = {}
    for name, payload in mapping.items():
        if not isinstance(payload, Mapping):
            continue
        path = write_bytes_atomic(directory / name, _json_safe(payload))
        written[name] = str(path).replace("\\", "/")
    report = bundle.get("report_text")
    if isinstance(report, str):
        path = write_bytes_atomic(report_path(root=root), report)
        written["report"] = str(path).replace("\\", "/")
    written["phase"] = PHASE
    return written


def _json_safe(payload: Mapping[str, Any]) -> dict[str, Any]:
    skip = {"payload", "profile", "book", "mapping", "doc"}
    return {key: value for key, value in dict(payload).items() if key not in skip}


__all__ = ["write_binary_atomic", "write_phase_artifacts"]
