"""Requête V3 fenêtre sélectionnée prompt 1.3.1 + audit payload. 0 POST."""

from __future__ import annotations

from typing import Any

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v3_hardened_win001.guard import HardenedV3Win001Error
from app.source_analysis_v3_hardened_win001.payload import (
    assert_payload_conditions as _assert_payload_conditions,
    assert_schema_identity as _assert_schema_identity,
    build_a21_request,
    build_audited_request as _build_audited_request,
    dry_run_twice as _dry_run_twice,
    inspect_safe_payload,
    measure_schema,
)
from app.source_analysis_v3_second_window.guard import SecondWindowError


def _reraise(exc: HardenedV3Win001Error) -> None:
    raise SecondWindowError(str(exc)) from exc


def assert_schema_identity(metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return _assert_schema_identity(metrics)
    except HardenedV3Win001Error as exc:
        _reraise(exc)
        raise


def assert_payload_conditions(audit: dict[str, Any]) -> None:
    try:
        _assert_payload_conditions(audit)
    except HardenedV3Win001Error as exc:
        _reraise(exc)


def build_a22_request(window: WindowInput, transcript: TranscriptInput, **kwargs):
    return build_a21_request(window, transcript, **kwargs)


def build_audited_request(
    window: WindowInput,
    transcript: TranscriptInput,
    **kwargs,
) -> dict[str, Any]:
    try:
        return _build_audited_request(window, transcript, **kwargs)
    except HardenedV3Win001Error as exc:
        _reraise(exc)
        raise


def dry_run_twice(
    window: WindowInput,
    transcript: TranscriptInput,
) -> dict[str, Any]:
    try:
        return _dry_run_twice(window, transcript)
    except HardenedV3Win001Error as exc:
        _reraise(exc)
        raise


__all__ = [
    "assert_payload_conditions",
    "assert_schema_identity",
    "build_a22_request",
    "build_audited_request",
    "dry_run_twice",
    "inspect_safe_payload",
    "measure_schema",
]
