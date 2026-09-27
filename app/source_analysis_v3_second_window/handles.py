"""Inspection handles V3 — diagnostic only. Aucune réparation."""

from app.source_analysis_v3_hardened_win001.handles import (
    example_target_kinds,
    handle_gate_status,
    inspect_handle_metrics,
    inspect_symbolic_refs,
)

__all__ = [
    "example_target_kinds",
    "handle_gate_status",
    "inspect_handle_metrics",
    "inspect_symbolic_refs",
]
