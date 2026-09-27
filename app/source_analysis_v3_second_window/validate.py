"""Parse / decoder / registry / resolver / validator V3 + audit SRC exhaustif."""

from __future__ import annotations

from typing import Any

from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v3_hardened_win001.validate import (
    interpret_hardened_response as _interpret_hardened_response,
    src_success_metrics,
)
from app.source_analysis_v3_second_window.constants import MODE, PHASE, SCHEMA_VERSION


def interpret_hardened_response(
    parsed: dict[str, Any] | None,
    *,
    window: WindowInput,
    raw_text: str | None = None,
) -> dict[str, Any]:
    result = _interpret_hardened_response(parsed, window=window, raw_text=raw_text)
    for key in ("src_audit", "inventory"):
        block = result.get(key)
        if isinstance(block, dict):
            block["schema_version"] = SCHEMA_VERSION
            block["phase"] = PHASE
            block["mode"] = MODE
    return result


__all__ = [
    "interpret_hardened_response",
    "src_success_metrics",
]
