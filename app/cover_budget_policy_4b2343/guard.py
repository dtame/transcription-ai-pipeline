"""Write guard. Audit text only. No cover binary and no manuscript edit."""

from __future__ import annotations

from pathlib import Path

from app.cover_budget_policy_4b2343.paths import phase_audit_dir, report_path


class BudgetPolicyPhaseError(RuntimeError):
    """Phase 4B.2.34.3 refused to continue."""


def assert_audit_target(path: Path, *, root: Path | None = None) -> None:
    resolved = Path(path).resolve()
    audit = phase_audit_dir(root=root).resolve()
    report = report_path(root=root).resolve()
    allowed = resolved == report or resolved == audit or audit in resolved.parents
    if not allowed:
        raise BudgetPolicyPhaseError(f"refusing to write outside the phase audit: {resolved}")
    if resolved.suffix.lower() in {".docx", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
        raise BudgetPolicyPhaseError(f"refusing to write a cover binary: {resolved}")
    if resolved.name == "book.json":
        raise BudgetPolicyPhaseError("refusing to write book.json")


__all__ = ["BudgetPolicyPhaseError", "assert_audit_target"]
