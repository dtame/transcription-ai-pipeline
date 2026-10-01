"""Persistance brute immuable A.46. Avant reconstruction. 0 réparation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.file_utils import content_hash
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_v30_real_canary.constants import (
    PHASE,
    RAW_RESPONSE_ARTIFACT,
    RESPONSE_IDENTITY_ARTIFACT,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_global_v30_real_canary.paths import canary_artifact_path


def persist_raw_provider_evidence(
    project_name: str,
    *,
    raw_text: str | None,
    parsed: Mapping[str, Any] | None,
    http_meta: Mapping[str, Any],
    response_meta: Mapping[str, Any],
    sortie_dir: Path | None = None,
) -> dict[str, Path]:
    text = raw_text or ""
    raw_chars = len(text)
    raw_bytes = len(text.encode("utf-8"))
    raw_hash = content_hash(text) if text else ""
    immutable = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "immutable": True,
        "repaired": False,
        "normalized_separately": True,
        "http_status": http_meta.get("http_status"),
        "request_id": http_meta.get("request_id") or response_meta.get("request_id"),
        "finish_reason": response_meta.get("finish_reason") or http_meta.get("finish_reason"),
        "elapsed_ms": http_meta.get("elapsed_ms") or response_meta.get("latency_ms"),
        "input_tokens": response_meta.get("input_tokens") or http_meta.get("input_tokens"),
        "output_tokens": response_meta.get("output_tokens") or http_meta.get("output_tokens"),
        "thinking_tokens": response_meta.get("thinking_tokens"),
        "http": dict(http_meta),
        "provider_metadata": dict(response_meta),
        "raw_text": text,
        "raw_structured_response": dict(parsed) if isinstance(parsed, Mapping) else None,
        "raw_response_chars": raw_chars,
        "raw_response_bytes": raw_bytes,
        "raw_response_hash": raw_hash,
    }
    identity = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "http_status": immutable["http_status"],
        "request_id": immutable["request_id"],
        "finish_reason": immutable["finish_reason"],
        "elapsed_ms": immutable["elapsed_ms"],
        "input_tokens": immutable["input_tokens"],
        "output_tokens": immutable["output_tokens"],
        "thinking_tokens": immutable["thinking_tokens"],
        "raw_response_chars": raw_chars,
        "raw_response_bytes": raw_bytes,
        "raw_response_hash": raw_hash,
        "usage_source": response_meta.get("usage_source"),
        "immutable": True,
    }
    written = {
        "raw": write_bytes_atomic(
            canary_artifact_path(project_name, RAW_RESPONSE_ARTIFACT, sortie_dir=sortie_dir),
            immutable,
        ),
        "identity": write_bytes_atomic(
            canary_artifact_path(
                project_name, RESPONSE_IDENTITY_ARTIFACT, sortie_dir=sortie_dir
            ),
            identity,
        ),
    }
    return written


__all__ = ["persist_raw_provider_evidence"]
