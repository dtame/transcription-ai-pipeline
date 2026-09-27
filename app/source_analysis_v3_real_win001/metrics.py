"""Métriques records / SRC / taille. Déterministe. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v2.constants import LOCAL_KINDS
from app.source_analysis_v2_real_win001.metrics import (
    output_size_metrics,
    record_metrics,
    src_metrics,
)


def _records(transport: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(transport, Mapping):
        return []
    records = transport.get("records") or []
    return [item for item in records if isinstance(item, Mapping)]


def kind_counts(transport: Mapping[str, Any] | None) -> dict[str, Any]:
    return record_metrics(transport)


def window_src_metrics(
    transport: Mapping[str, Any] | None,
    window: WindowInput,
) -> dict[str, Any]:
    return src_metrics(transport, window)


__all__ = [
    "LOCAL_KINDS",
    "kind_counts",
    "output_size_metrics",
    "record_metrics",
    "src_metrics",
    "window_src_metrics",
]
