"""Lecture seule des preuves A.42. Aucune réparation. Aucune écriture historique."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v31_global_reuse_output.constants import (
    A42_CHARS_PER_TOKEN,
    A42_ESTIMATOR_ERROR_PERCENT,
    A42_FINISH_REASON,
    A42_HTTP_STATUS,
    A42_INPUT_TOKENS,
    A42_OUTPUT_TOKENS,
    A42_RAW_TEXT_CHARS,
    A42_REQUEST_ID,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
)
from app.source_analysis_v31_global_reuse_output.paths import (
    a42_canary_root,
    a42_report_path,
    sortie_root,
)


def a42_usage_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return a42_canary_root(project_name, sortie_dir=sortie_dir) / (
        "global_consolidation_v201_usage_cost.json"
    )


def a42_execution_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return a42_canary_root(project_name, sortie_dir=sortie_dir) / (
        "global_consolidation_v201_canary_execution.json"
    )


def verify_a42_identity(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    usage_path = a42_usage_path(project_name, sortie_dir=sortie_dir)
    report = a42_report_path(project_name, sortie_dir=sortie_dir)
    if not usage_path.is_file():
        return {"ok": False, "error": "A.42 usage artifact missing", "request_id": None}
    usage = json.loads(usage_path.read_text(encoding="utf-8"))
    request_id = usage.get("request_id")
    actual_cpt = float(usage.get("actual_chars_per_token") or 0)
    error = usage.get("estimator_error") or {}
    ok = (
        request_id == A42_REQUEST_ID
        and int(usage.get("http_status") or 0) == A42_HTTP_STATUS
        and usage.get("finish_reason") == A42_FINISH_REASON
        and int(usage.get("thinking") or 0) == 0
        and int(usage.get("actual_provider_input") or 0) == A42_INPUT_TOKENS
        and int(usage.get("output") or 0) == A42_OUTPUT_TOKENS
        and int(usage.get("raw_text_chars") or 0) == A42_RAW_TEXT_CHARS
        and abs(actual_cpt - A42_CHARS_PER_TOKEN) < 1e-9
        and abs(float(error.get("percent") or 0) - A42_ESTIMATOR_ERROR_PERCENT) < 0.01
        and report.is_file()
    )
    return {
        "ok": ok,
        "request_id": request_id,
        "expected_request_id": A42_REQUEST_ID,
        "http_status": usage.get("http_status"),
        "finish_reason": usage.get("finish_reason"),
        "input_tokens": usage.get("actual_provider_input"),
        "output_tokens": usage.get("output"),
        "actual_chars_per_token": actual_cpt,
        "estimator_error_percent": error.get("percent"),
        "report_present": report.is_file(),
        "mutated": False,
    }


def protected_a43_historical_hashes(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, str]:
    root = sortie_root(sortie_dir) / project_name
    hashes: dict[str, str] = {}
    for rel in PROTECTED_HISTORICAL:
        path = root / rel
        if path.is_file():
            hashes[rel] = sha256_of_file(path)
    return hashes


__all__ = [
    "a42_execution_path",
    "a42_usage_path",
    "protected_a43_historical_hashes",
    "verify_a42_identity",
]
