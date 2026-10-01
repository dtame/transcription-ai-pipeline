"""Identité schéma 1.1 / prompt 1.0.1. 0 POST."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.source_analysis_v31_global_canary_forensics.prompt_v101 import prompt_v101_bundle
from app.source_analysis_v31_global_v11_grammar_canary.identity import (
    load_a36_schema_artifact,
    recompute_schema_identity as recompute_v11_schema_identity,
)
from app.source_analysis_v31_global_real_consolidation.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_VERSION,
    CONNECT_TIMEOUT_SECONDS,
    EFFORT,
    MAX_OUTPUT_TOKENS,
    MODEL,
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
from app.source_analysis_v31_global_real_consolidation.guard import (
    GlobalRealConsolidationError,
)


def recompute_schema_identity() -> dict[str, Any]:
    recomputed = recompute_v11_schema_identity()
    prompt = prompt_v101_bundle()
    matches = (
        recomputed.get("raw_bytes") == SCHEMA_RAW_BYTES
        and recomputed.get("adapted_bytes") == SCHEMA_ADAPTED_BYTES
        and recomputed.get("hash") == SCHEMA_HASH
        and recomputed.get("matches_a36_constants")
        and prompt.get("prompt_version") == PROMPT_VERSION
    )
    recomputed["matches_a38_constants"] = matches
    recomputed["prompt_version"] = prompt.get("prompt_version")
    recomputed["prompt_combined_sha256"] = prompt.get("combined_sha256")
    return recomputed


def verify_schema_identity(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    recomputed = recompute_schema_identity()
    artifact = load_a36_schema_artifact(project_name, sortie_dir=sortie_dir)
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
    recomputed["a36_artifact_present"] = artifact is not None
    recomputed["a36_artifact_hash"] = artifact_hash
    recomputed["matches_a36_artifact"] = matches_artifact
    recomputed["schema_identity"] = (
        "MATCH" if recomputed.get("matches_a38_constants") and matches_artifact else "MISMATCH"
    )
    if recomputed["schema_identity"] != "MATCH":
        raise GlobalRealConsolidationError(
            "BLOCKED_PRECALL: schema identity differs from frozen A.36/A.37 "
            f"recomputed={recomputed.get('raw_bytes')}/{recomputed.get('adapted_bytes')} "
            f"hash={recomputed.get('hash')} "
            f"expected={SCHEMA_RAW_BYTES}/{SCHEMA_ADAPTED_BYTES} "
            f"hash={SCHEMA_HASH}."
        )
    return recomputed


def request_identity_payload(
    *,
    schema_hash: str,
    prompt_hash: str,
    input_hash: str,
    max_output: int = MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    return {
        "canary_version": CANARY_VERSION,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider": PROVIDER,
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "effort": EFFORT,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash,
        "transport_version": TRANSPORT_VERSION,
        "schema_hash": schema_hash,
        "input_hash": input_hash,
        "max_output": int(max_output),
        "temperature": None,
        "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": READ_TIMEOUT_SECONDS,
        "manual_budget_tokens": None,
        "task_budget": None,
    }


def request_identity(**kwargs: Any) -> str:
    payload = request_identity_payload(**kwargs)
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


__all__ = [
    "recompute_schema_identity",
    "request_identity",
    "request_identity_payload",
    "verify_schema_identity",
]
