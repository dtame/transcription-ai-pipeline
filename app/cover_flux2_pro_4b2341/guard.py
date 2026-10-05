"""Write guard. Audit text only. No cover binary and no manuscript edit."""

from __future__ import annotations

from pathlib import Path

from app.cover_flux2_pro_4b2341.paths import phase_audit_dir, report_path


class Flux2UnblockError(RuntimeError):
    """Phase 4B.2.34.1 refused to continue."""


def assert_audit_target(path: Path, *, root: Path | None = None) -> None:
    resolved = Path(path).resolve()
    audit = phase_audit_dir(root=root).resolve()
    report = report_path(root=root).resolve()
    allowed = resolved == report or resolved == audit or audit in resolved.parents
    if not allowed:
        raise Flux2UnblockError(f"refusing to write outside the phase audit: {resolved}")
    if resolved.suffix.lower() in {".docx", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
        raise Flux2UnblockError(f"refusing to write a cover binary: {resolved}")
    if resolved.name == "book.json":
        raise Flux2UnblockError("refusing to write book.json")


__all__ = ["Flux2UnblockError", "assert_audit_target"]
