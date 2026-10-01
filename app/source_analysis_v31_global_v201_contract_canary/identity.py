"""Identité schéma 2.0 inchangé + prompt 2.0.1. Aucun POST ici."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.source_analysis_v31_global_drop_domain.constants import A40_PROMPT_HASH
from app.source_analysis_v31_global_drop_domain.prompt_v201 import prompt_v201_bundle
from app.source_analysis_v31_global_output_architecture.prompt_v20 import prompt_v20_bundle
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    measure_global_schema_v20,
)
from app.source_analysis_v31_global_v201_contract_canary.constants import (
    A39_SCHEMA_ARTIFACT,
    A40_PROMPT_VERSION,
    AUTHORIZATION_SCOPE,
    CANARY_CONNECT_TIMEOUT_SECONDS,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_READ_TIMEOUT_SECONDS,
    CANARY_VERSION,
    EFFORT,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v201_contract_canary.guard import (
    GlobalGrammarCanaryError,
)


def load_a39_schema_artifact(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any] | None:
    candidates = []
    if sortie_dir is not None:
        candidates.append(audit_dir(project_name, sortie_dir=sortie_dir) / A39_SCHEMA_ARTIFACT)
    candidates.append(audit_dir(PROJECT_NAME, sortie_dir=SORTIE_DIR) / A39_SCHEMA_ARTIFACT)
    for path in candidates:
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
    return None


def recompute_schema_identity() -> dict[str, Any]:
    measured = measure_global_schema_v20()
    prompt_old = prompt_v20_bundle()
    prompt_new = prompt_v201_bundle()
    matches = (
        measured.get("raw_bytes") == SCHEMA_RAW_BYTES
        and measured.get("adapted_bytes") == SCHEMA_ADAPTED_BYTES
        and measured.get("hash") == SCHEMA_HASH
        and str(measured.get("hash") or "").startswith("90b99a38")
        and str(measured.get("hash") or "").endswith("6d8330")
        and not measured.get("unsupported_constructs")
        and prompt_old.get("prompt_version") == A40_PROMPT_VERSION
        and prompt_old.get("combined_sha256") == A40_PROMPT_HASH
        and prompt_new.get("prompt_version") == PROMPT_VERSION
        and prompt_new.get("previous_prompt_mutated") is False
        and prompt_new.get("combined_sha256") != A40_PROMPT_HASH
        and measured.get("transport_version") == TRANSPORT_VERSION
    )
    return {
        "raw_bytes": measured.get("raw_bytes"),
        "adapted_bytes": measured.get("adapted_bytes"),
        "hash": measured.get("hash"),
        "transport_version": measured.get("transport_version"),
        "prompt_version": prompt_new.get("prompt_version"),
        "prompt_combined_sha256": prompt_new.get("combined_sha256"),
        "previous_prompt_version": prompt_old.get("prompt_version"),
        "previous_prompt_hash": prompt_old.get("combined_sha256"),
        "previous_prompt_mutated": prompt_new.get("previous_prompt_mutated"),
        "expected_raw_bytes": SCHEMA_RAW_BYTES,
        "expected_adapted_bytes": SCHEMA_ADAPTED_BYTES,
        "expected_hash": SCHEMA_HASH,
        "matches_a39_constants": matches,
        "unsupported_constructs": measured.get("unsupported_constructs"),
        "schema": measured.get("schema"),
    }


def verify_schema_identity(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    recomputed = recompute_schema_identity()
    artifact = load_a39_schema_artifact(project_name, sortie_dir=sortie_dir)
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
    recomputed["a39_artifact_present"] = artifact is not None
    recomputed["a39_artifact_hash"] = artifact_hash
    recomputed["matches_a39_artifact"] = matches_artifact
    recomputed["schema_identity"] = (
        "MATCH" if recomputed["matches_a39_constants"] and matches_artifact else "MISMATCH"
    )
    if recomputed["schema_identity"] != "MATCH":
        raise GlobalGrammarCanaryError(
            "BLOCKED_PRECALL: schema identity differs from A.39/A.40 transport 2.0 "
            f"recomputed={recomputed['raw_bytes']}/{recomputed['adapted_bytes']} "
            f"hash={recomputed['hash']} "
            f"expected={SCHEMA_RAW_BYTES}/{SCHEMA_ADAPTED_BYTES} "
            f"hash={SCHEMA_HASH}."
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
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash,
        "transport_version": TRANSPORT_VERSION,
        "schema_hash": schema_hash,
        "fixture_hash": fixture_hash,
        "max_output": int(max_output),
        "production_max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
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
    "load_a39_schema_artifact",
    "recompute_schema_identity",
    "verify_schema_identity",
]
