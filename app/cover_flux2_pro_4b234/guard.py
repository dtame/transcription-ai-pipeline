"""Write guard. Audit text only. No cover binary and no manuscript edit."""

from __future__ import annotations

from pathlib import Path

from app.cover_flux2_pro_4b234.paths import phase_audit_dir, report_path


class Flux2PhaseError(RuntimeError):
    """Phase 4B.2.34 refused to continue."""


def assert_audit_target(path: Path, *, root: Path | None = None) -> None:
    resolved = Path(path).resolve()
    audit = phase_audit_dir(root=root).resolve()
    report = report_path(root=root).resolve()
    allowed = resolved == report or resolved == audit or audit in resolved.parents
    if not allowed:
        raise Flux2PhaseError(f"refusing to write outside the phase audit: {resolved}")
    if resolved.suffix.lower() in {".docx", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
        raise Flux2PhaseError(f"refusing to write a cover binary: {resolved}")
    if resolved.name == "book.json":
        raise Flux2PhaseError("refusing to write book.json")


__all__ = ["Flux2PhaseError", "assert_audit_target"]
