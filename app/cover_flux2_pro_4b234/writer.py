"""Write the 4B.2.34 audit. Text and JSON only."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.cover_flux2_pro_4b234.guard import assert_audit_target
from app.cover_flux2_pro_4b234.paths import phase_audit_dir, report_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def write_documents(documents: Mapping[str, Any], *, root: Path | None = None) -> dict[str, str]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for name, payload in documents.items():
        target = report_path(root=root) if name == "report_text" else directory / name
        assert_audit_target(target, root=root)
        if not isinstance(payload, (str, Mapping)):
            raise TypeError(f"unsupported audit payload for {name}")
        path = write_bytes_atomic(target, payload if isinstance(payload, str) else dict(payload))
        written[name] = str(path).replace("\\", "/")
    return written


__all__ = ["write_documents"]
