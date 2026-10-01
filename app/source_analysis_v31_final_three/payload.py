"""Requête v3.1-local-lite prompt 1.4.0 + audit payload. Réutilise A.27/A.28. 0 POST."""

from __future__ import annotations

from typing import Any

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v31_remaining_windows.guard import RemainingWindowsError
from app.source_analysis_v31_remaining_windows.payload import (
    assert_payload_conditions,
    assert_schema_identity,
    assert_schema_py_excluded,
    build_audited_request as _build_audited_request,
    dry_run_twice as _dry_run_twice,
    inspect_safe_payload,
    measure_schema,
)
from app.source_analysis_v31_final_three.guard import FinalThreeError


def build_audited_request(
    window: WindowInput,
    transcript: TranscriptInput,
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        return _build_audited_request(window, transcript, **kwargs)
    except RemainingWindowsError as exc:
        raise FinalThreeError(str(exc)) from exc


def dry_run_twice(
    window: WindowInput,
    transcript: TranscriptInput,
) -> dict[str, Any]:
    try:
        return _dry_run_twice(window, transcript)
    except RemainingWindowsError as exc:
        raise FinalThreeError(str(exc)) from exc


__all__ = [
    "assert_payload_conditions",
    "assert_schema_identity",
    "assert_schema_py_excluded",
    "build_audited_request",
    "dry_run_twice",
    "inspect_safe_payload",
    "measure_schema",
]
