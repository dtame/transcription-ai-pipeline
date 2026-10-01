"""Identité schéma 3.0 + hash de requête production. 0 POST."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.source_analysis_v31_global_reuse_output.prompt_v30 import prompt_v30_bundle
from app.source_analysis_v31_global_reuse_output.transport_v30 import (
    measure_global_schema_v30,
)
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    A43_SCHEMA_ARTIFACT,
    AUTHORIZATION_SCOPE,
    CONNECT_TIMEOUT_SECONDS,
    EFFORT,
    FUTURE_AUTHORIZATION_SCOPE,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v30_exact_preflight.offline import (
    GlobalExactPreflightError,
)


def load_a43_schema_artifact(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any] | None:
    candidates = []
    if sortie_dir is not None:
        candidates.append(audit_dir(project_name, sortie_dir=sortie_dir) / A43_SCHEMA_ARTIFACT)
    candidates.append(audit_dir(PROJECT_NAME, sortie_dir=SORTIE_DIR) / A43_SCHEMA_ARTIFACT)
    for path in candidates:
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
    return None


def recompute_schema_identity() -> dict[str, Any]:
    measured = measure_global_schema_v30()
    prompt = prompt_v30_bundle()
    matches = (
        measured.get("raw_bytes") == SCHEMA_RAW_BYTES
        and measured.get("adapted_bytes") == SCHEMA_ADAPTED_BYTES
        and measured.get("hash") == SCHEMA_HASH
        and str(measured.get("hash") or "")
        == "822397b642b0e1724e29686962caab32bff63effe18f05bff26b404bad9b2a90"
        and not measured.get("unsupported_constructs")
        and prompt.get("prompt_version") == PROMPT_VERSION
        and measured.get("transport_version") == TRANSPORT_VERSION
        and prompt.get("previous_prompt_mutated") is False
    )
    return {
        "raw_bytes": measured.get("raw_bytes"),
        "adapted_bytes": measured.get("adapted_bytes"),
        "hash": measured.get("hash"),
        "transport_version": measured.get("transport_version"),
        "prompt_version": prompt.get("prompt_version"),
        "prompt_combined_sha256": prompt.get("combined_sha256"),
        "previous_prompt_mutated": prompt.get("previous_prompt_mutated"),
        "expected_raw_bytes": SCHEMA_RAW_BYTES,
        "expected_adapted_bytes": SCHEMA_ADAPTED_BYTES,
        "expected_hash": SCHEMA_HASH,
        "matches_frozen_3_0": matches,
        "unsupported_constructs": measured.get("unsupported_constructs"),
        "conditional_schema_used": measured.get("conditional_schema_used"),
        "schema_identity": "MATCH" if matches else "MISMATCH",
    }


def verify_schema_identity(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    recomputed = recompute_schema_identity()
    artifact = load_a43_schema_artifact(project_name, sortie_dir=sortie_dir)
    artifact_hash = artifact.get("hash") if isinstance(artifact, dict) else None
    artifact_raw = artifact.get("raw_bytes") if isinstance(artifact, dict) else None
    artifact_adapted = (
        artifact.get("adapted_bytes") if isinstance(artifact, dict) else None
    )
    matches_artifact = True
    if artifact is not None:
        matches_artifact = (
            artifact_hash == SCHEMA_HASH
            and artifact_raw == SCHEMA_RAW_BYTES
            and artifact_adapted == SCHEMA_ADAPTED_BYTES
            and recomputed["hash"] == artifact_hash
            and recomputed["raw_bytes"] == artifact_raw
            and recomputed["adapted_bytes"] == artifact_adapted
        )
    recomputed["a43_artifact_present"] = artifact is not None
    recomputed["a43_artifact_hash"] = artifact_hash
    recomputed["matches_a43_artifact"] = matches_artifact
    recomputed["schema_identity"] = (
        "MATCH" if recomputed["matches_frozen_3_0"] and matches_artifact else "MISMATCH"
    )
    if recomputed["schema_identity"] != "MATCH":
        raise GlobalExactPreflightError(
            "BLOCKED: schema identity differs from frozen transport 3.0 "
            f"recomputed={recomputed['raw_bytes']}/{recomputed['adapted_bytes']} "
            f"hash={recomputed['hash']} "
            f"expected={SCHEMA_RAW_BYTES}/{SCHEMA_ADAPTED_BYTES} "
            f"hash={SCHEMA_HASH}."
        )
    return recomputed


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def request_identity_payload(
    *,
    schema_hash: str,
    prompt_hash: str,
    normalized_input_hash: str,
    provider_visible_hash: str,
    window_set_sha256: str,
    max_output: int = PRODUCTION_MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    return {
        "authorization_scope_future": FUTURE_AUTHORIZATION_SCOPE,
        "preflight_scope": AUTHORIZATION_SCOPE,
        "provider": PROVIDER,
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "effort": EFFORT,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash,
        "transport_version": TRANSPORT_VERSION,
        "schema_hash": schema_hash,
        "normalized_input_hash": normalized_input_hash,
        "provider_visible_hash": provider_visible_hash,
        "window_set_sha256": window_set_sha256,
        "max_output": int(max_output),
        "temperature": None,
        "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": READ_TIMEOUT_SECONDS,
        "manual_budget_tokens": None,
        "task_budget": None,
    }


def request_identity(**kwargs: Any) -> str:
    payload = request_identity_payload(**kwargs)
    return content_hash(canonical_json(payload))


__all__ = [
    "canonical_json",
    "load_a43_schema_artifact",
    "recompute_schema_identity",
    "request_identity",
    "request_identity_payload",
    "verify_schema_identity",
]
