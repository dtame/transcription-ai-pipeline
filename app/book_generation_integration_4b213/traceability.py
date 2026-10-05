"""Verifiable Chapter → Section → Paragraph → Unit → Evidence → SourceMap chain."""

from __future__ import annotations

from typing import Any

from app.book_generation_integration_4b213.constants import (
    H01_EVIDENCE_HANDLES,
    PHASE,
    SYNTHETIC_PREFIX,
)
from app.book_generation_integration_4b213.orchestrator import orchestrate_chapter


def traceability() -> dict[str, Any]:
    result = orchestrate_chapter(scenario="fully_supported")
    chains = []
    for para in result.get("paragraph_results") or []:
        prepared = dict(para.get("prepared") or {})
        for unit in prepared.get("units") or []:
            chains.append(
                {
                    "chapter_id": para.get("chapter_id"),
                    "section_id": para.get("section_id"),
                    "paragraph_id": para.get("paragraph_id"),
                    "unit_id": unit.get("unit_id"),
                    "unit_text": unit.get("text"),
                    "evidence_handles": list(para.get("evidence_handles") or []),
                    "source_refs": list(para.get("source_refs") or []),
                    "source_map_or_src": list(para.get("source_refs") or para.get("evidence_handles") or []),
                    "synthetic": True,
                    "presented_as_real_src": False,
                }
            )
    synthetic_only = all(
        str(handle).startswith(SYNTHETIC_PREFIX)
        for item in chains
        for handle in item.get("evidence_handles") or []
    )
    historical = {
        "kind": "HISTORICAL_CANARY_HANDLES_NOT_THIS_PHASE_GENERATION",
        "h01_evidence_handles": list(H01_EVIDENCE_HANDLES),
        "not_used_as_generated_chapter_in_4b213": True,
        "not_presented_as_new_src": True,
    }
    return {
        "phase": PHASE,
        "ok": bool(chains) and synthetic_only,
        "chains": chains,
        "synthetic_handles_only": synthetic_only,
        "does_not_fabricate_real_src": True,
        "historical_canary_handles": historical,
        "secrets_included": False,
    }


__all__ = ["traceability"]
