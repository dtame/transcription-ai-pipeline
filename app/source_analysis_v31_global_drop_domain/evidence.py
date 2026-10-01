"""Lecture seule des preuves A.40. Aucune réparation. Aucune écriture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v31_global_drop_domain.constants import (
    A40_FIXTURE_HASH,
    A40_PROMPT_HASH,
    A40_RAW_SHA256,
    A40_RAW_SIZE,
    A40_RAW_TEXT_CHARS,
    A40_REQUEST_ID,
    A40_REQUEST_IDENTITY,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
    V20_PROMPT_VERSION,
    V20_SCHEMA_HASH,
    V20_TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_drop_domain.paths import (
    a40_canary_root,
    a40_forensic_dir,
    sortie_root,
)
from app.source_analysis_v31_global_output_architecture.prompt_v20 import prompt_v20_bundle
from app.source_analysis_v31_global_v20_grammar_canary.fixture import fixture_hash


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def a40_raw_bin_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    root = a40_forensic_dir(project_name, sortie_dir=sortie_dir)
    found = _first_existing([root / "provider_raw_response.bin"])
    if found is None:
        matches = sorted(a40_canary_root(project_name, sortie_dir=sortie_dir).rglob(
            "provider_raw_response.bin"
        ))
        if matches:
            return matches[0]
        raise FileNotFoundError("A.40 provider_raw_response.bin introuvable.")
    return found


def a40_envelope_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return a40_forensic_dir(project_name, sortie_dir=sortie_dir) / (
        "provider_http_envelope.json"
    )


def a40_execution_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return a40_canary_root(project_name, sortie_dir=sortie_dir) / (
        "global_consolidation_v20_canary_execution.json"
    )


def a40_fixture_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return a40_canary_root(project_name, sortie_dir=sortie_dir) / (
        "global_consolidation_v20_synthetic_fixture.json"
    )


def read_a40_raw_bytes(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> bytes:
    path = a40_raw_bin_path(project_name, sortie_dir=sortie_dir)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != A40_RAW_SHA256:
        raise ValueError(
            f"A.40 raw hash drift: {digest} ≠ {A40_RAW_SHA256}. Evidence must stay byte-identical."
        )
    if len(raw) != A40_RAW_SIZE:
        raise ValueError(f"A.40 raw size drift: {len(raw)} ≠ {A40_RAW_SIZE}.")
    return raw


def extract_a40_text_and_json(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> tuple[str, dict[str, Any], bytes]:
    raw = read_a40_raw_bytes(project_name, sortie_dir=sortie_dir)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("A.40 raw JSON is not an object")
    blocks = data.get("content") or []
    parts: list[str] = []
    if isinstance(blocks, list):
        for block in blocks:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
    text = "".join(parts)
    if len(text) != A40_RAW_TEXT_CHARS:
        raise ValueError(
            f"A.40 text length drift: {len(text)} ≠ {A40_RAW_TEXT_CHARS}."
        )
    return text, data, raw


def load_a40_envelope(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    path = a40_envelope_path(project_name, sortie_dir=sortie_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("A.40 envelope is not an object")
    return payload


def load_a40_execution(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    path = a40_execution_path(project_name, sortie_dir=sortie_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("A.40 execution is not an object")
    return payload


def verify_a40_identity(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    envelope = load_a40_envelope(project_name, sortie_dir=sortie_dir)
    raw = read_a40_raw_bytes(project_name, sortie_dir=sortie_dir)
    text, parsed, _ = extract_a40_text_and_json(project_name, sortie_dir=sortie_dir)
    request_id = envelope.get("request_id") or (
        (envelope.get("headers_subset") or {}).get("request-id")
    )
    identity = envelope.get("analysis_signature")
    prompt = prompt_v20_bundle()
    live_fixture = fixture_hash()
    ok = (
        request_id == A40_REQUEST_ID
        and identity == A40_REQUEST_IDENTITY
        and hashlib.sha256(raw).hexdigest() == A40_RAW_SHA256
        and len(raw) == A40_RAW_SIZE
        and len(text) == A40_RAW_TEXT_CHARS
        and prompt.get("prompt_version") == V20_PROMPT_VERSION
        and prompt.get("combined_sha256") == A40_PROMPT_HASH
        and live_fixture == A40_FIXTURE_HASH
    )
    return {
        "ok": ok,
        "request_id": request_id,
        "expected_request_id": A40_REQUEST_ID,
        "identity": identity,
        "expected_identity": A40_REQUEST_IDENTITY,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_size": len(raw),
        "text_chars": len(text),
        "prompt_version": prompt.get("prompt_version"),
        "prompt_hash": prompt.get("combined_sha256"),
        "prompt_hash_match": prompt.get("combined_sha256") == A40_PROMPT_HASH,
        "fixture_hash": live_fixture,
        "fixture_hash_match": live_fixture == A40_FIXTURE_HASH,
        "schema_hash": V20_SCHEMA_HASH,
        "transport_version": V20_TRANSPORT_VERSION,
        "parsed_top_level_type": type(parsed).__name__,
        "raw_immutable": hashlib.sha256(raw).hexdigest() == A40_RAW_SHA256,
    }


def protected_a41_historical_hashes(
    *, sortie_dir: Path | None = None
) -> dict[str, str | None]:
    root = sortie_root(sortie_dir)
    hashes: dict[str, str | None] = {}
    for relative in PROTECTED_HISTORICAL:
        path = root / PROJECT_NAME / relative
        hashes[relative] = sha256_of_file(path) if path.is_file() else None
    return hashes


__all__ = [
    "a40_envelope_path",
    "a40_execution_path",
    "a40_fixture_path",
    "a40_raw_bin_path",
    "extract_a40_text_and_json",
    "load_a40_envelope",
    "load_a40_execution",
    "protected_a41_historical_hashes",
    "read_a40_raw_bytes",
    "verify_a40_identity",
]
