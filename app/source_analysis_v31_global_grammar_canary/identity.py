"""Identité schéma A.35 vs artefact A.34. Aucun POST ici."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v31_global_grammar_canary.constants import (
    A34_SCHEMA_ADAPTED_BYTES,
    A34_SCHEMA_ARTIFACT,
    A34_SCHEMA_HASH,
    A34_SCHEMA_RAW_BYTES,
    AUTHORIZATION_SCOPE,
    CANARY_CONNECT_TIMEOUT_SECONDS,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_READ_TIMEOUT_SECONDS,
    CANARY_VERSION,
    EFFORT,
    GLOBAL_PROMPT_VERSION,
    GLOBAL_TRANSPORT_VERSION,
    MODEL,
    PROJECT_NAME,
    PROVIDER,
    THINKING_MODE,
)
from app.source_analysis_v31_global_grammar_canary.guard import GlobalGrammarCanaryError
from app.source_analysis_v31_global_preflight.prompt import prompt_bundle
from app.source_analysis_v31_global_preflight.transport import measure_global_schema


def load_a34_schema_artifact(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any] | None:
    path = audit_dir(project_name, sortie_dir=sortie_dir) / A34_SCHEMA_ARTIFACT
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def recompute_schema_identity() -> dict[str, Any]:
    measured = measure_global_schema()
    prompt = prompt_bundle()
    return {
        "raw_bytes": measured.get("raw_bytes"),
        "adapted_bytes": measured.get("adapted_bytes"),
        "hash": measured.get("hash"),
        "transport_version": measured.get("transport_version"),
        "prompt_version": prompt.get("prompt_version"),
        "prompt_combined_sha256": prompt.get("combined_sha256"),
        "a34_raw_bytes": A34_SCHEMA_RAW_BYTES,
        "a34_adapted_bytes": A34_SCHEMA_ADAPTED_BYTES,
        "a34_hash": A34_SCHEMA_HASH,
        "matches_a34_constants": (
            measured.get("raw_bytes") == A34_SCHEMA_RAW_BYTES
            and measured.get("adapted_bytes") == A34_SCHEMA_ADAPTED_BYTES
            and measured.get("hash") == A34_SCHEMA_HASH
        ),
        "schema": measured.get("schema"),
    }


def verify_schema_identity(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    recomputed = recompute_schema_identity()
    artifact = load_a34_schema_artifact(project_name, sortie_dir=sortie_dir)
    artifact_hash = artifact.get("hash") if isinstance(artifact, dict) else None
    artifact_raw = artifact.get("raw_bytes") if isinstance(artifact, dict) else None
    artifact_adapted = (
        artifact.get("adapted_bytes") if isinstance(artifact, dict) else None
    )
    matches_artifact = True
    if artifact is not None:
        matches_artifact = (
            artifact_hash == A34_SCHEMA_HASH
            and artifact_raw == A34_SCHEMA_RAW_BYTES
            and artifact_adapted == A34_SCHEMA_ADAPTED_BYTES
            and recomputed["hash"] == artifact_hash
            and recomputed["raw_bytes"] == artifact_raw
            and recomputed["adapted_bytes"] == artifact_adapted
        )
    recomputed["a34_artifact_present"] = artifact is not None
    recomputed["a34_artifact_hash"] = artifact_hash
    recomputed["matches_a34_artifact"] = matches_artifact
    recomputed["schema_identity"] = (
        "MATCH"
        if recomputed["matches_a34_constants"] and matches_artifact
        else "MISMATCH"
    )
    if recomputed["schema_identity"] != "MATCH":
        raise GlobalGrammarCanaryError(
            "BLOCKED_PRECALL: schema identity differs from A.34 "
            f"recomputed={recomputed['raw_bytes']}/{recomputed['adapted_bytes']} "
            f"hash={recomputed['hash']} "
            f"expected={A34_SCHEMA_RAW_BYTES}/{A34_SCHEMA_ADAPTED_BYTES} "
            f"hash={A34_SCHEMA_HASH}."
        )
    return recomputed


def canary_identity_payload(
    *,
    schema_hash: str,
    prompt_hash: str,
    fixture_hash: str,
    max_output: int = CANARY_MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    return {
        "canary_version": CANARY_VERSION,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider": PROVIDER,
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "effort": EFFORT,
        "prompt_version": GLOBAL_PROMPT_VERSION,
        "prompt_hash": prompt_hash,
        "transport_version": GLOBAL_TRANSPORT_VERSION,
        "schema_hash": schema_hash,
        "fixture_hash": fixture_hash,
        "max_output": int(max_output),
        "production_max_output": 32000,
        "temperature": None,
        "connect_timeout_seconds": CANARY_CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": CANARY_READ_TIMEOUT_SECONDS,
        "manual_budget_tokens": None,
        "task_budget": None,
    }


def canary_request_identity(**kwargs: Any) -> str:
    payload = canary_identity_payload(**kwargs)
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


__all__ = [
    "canary_identity_payload",
    "canary_request_identity",
    "load_a34_schema_artifact",
    "recompute_schema_identity",
    "verify_schema_identity",
]
