"""Identité schéma transport 1.1 vs constantes A.36. Aucun POST ici."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v31_global_canary_forensics.constants import (
    NEXT_SCHEMA_ARTIFACT,
)
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    DROP_REASON_CODES,
    NON_DROP_REASON_CODE,
    REASON_CODES,
    REPRESENTATION_OPS,
    RETIRED_OPS,
    measure_global_schema_v11,
    schema_contains_unsupported_constructs,
)
from app.source_analysis_v31_global_canary_forensics.prompt_v101 import prompt_v101_bundle
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
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
from app.source_analysis_v31_global_v11_grammar_canary.guard import GlobalGrammarCanaryError


def load_a36_schema_artifact(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any] | None:
    path = audit_dir(project_name, sortie_dir=sortie_dir) / NEXT_SCHEMA_ARTIFACT
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _enum_contract(schema: dict[str, Any]) -> dict[str, Any]:
    items = ((schema.get("properties") or {}).get("d") or {}).get("items") or {}
    properties = items.get("properties") or {}
    op_enum = list((properties.get("o") or {}).get("enum") or [])
    reason_enum = list((properties.get("w") or {}).get("enum") or [])
    return {
        "d_o_enum": op_enum,
        "d_w_enum": reason_enum,
        "d_o_matches": op_enum == list(REPRESENTATION_OPS),
        "d_w_matches": reason_enum == list(REASON_CODES),
        "link_related_absent": "LINK_RELATED" not in op_enum,
        "free_prose_absent": reason_enum == list(REASON_CODES),
        "drop_reason_codes": list(DROP_REASON_CODES),
        "non_drop_reason": NON_DROP_REASON_CODE,
        "retired_ops": list(RETIRED_OPS),
    }


def recompute_schema_identity() -> dict[str, Any]:
    measured = measure_global_schema_v11()
    prompt = prompt_v101_bundle()
    schema = measured.get("schema") or {}
    enums = _enum_contract(schema if isinstance(schema, dict) else {})
    unsupported = schema_contains_unsupported_constructs(
        schema if isinstance(schema, dict) else {}
    )
    matches = (
        measured.get("raw_bytes") == SCHEMA_RAW_BYTES
        and measured.get("adapted_bytes") == SCHEMA_ADAPTED_BYTES
        and measured.get("hash") == SCHEMA_HASH
        and enums["d_o_matches"]
        and enums["d_w_matches"]
        and not unsupported
        and prompt.get("prompt_version") == PROMPT_VERSION
    )
    return {
        "raw_bytes": measured.get("raw_bytes"),
        "adapted_bytes": measured.get("adapted_bytes"),
        "hash": measured.get("hash"),
        "transport_version": measured.get("transport_version"),
        "prompt_version": prompt.get("prompt_version"),
        "prompt_combined_sha256": prompt.get("combined_sha256"),
        "expected_raw_bytes": SCHEMA_RAW_BYTES,
        "expected_adapted_bytes": SCHEMA_ADAPTED_BYTES,
        "expected_hash": SCHEMA_HASH,
        "matches_a36_constants": matches,
        "enum_contract": enums,
        "unsupported_constructs": unsupported,
        "schema": schema,
    }


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
        "MATCH" if recomputed["matches_a36_constants"] and matches_artifact else "MISMATCH"
    )
    if recomputed["schema_identity"] != "MATCH":
        raise GlobalGrammarCanaryError(
            "BLOCKED_PRECALL: schema identity differs from A.36 transport 1.1 "
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
    "load_a36_schema_artifact",
    "recompute_schema_identity",
    "verify_schema_identity",
]
