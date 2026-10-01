"""Lecture seule des preuves A.38. Aucune réparation. Aucune écriture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v31_global_output_architecture.constants import (
    A38_RAW_TEXT_CHARS,
    A38_RAW_TEXT_SHA256,
    A38_REQUEST_ID,
    A38_REQUEST_IDENTITY,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
)
from app.source_analysis_v31_global_output_architecture.paths import (
    a38_canary_root,
    sortie_root,
)


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def a38_raw_text_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    root = a38_canary_root(project_name, sortie_dir=sortie_dir)
    found = _first_existing(
        [
            root / "provider_raw_content.txt",
            root / "structured_output_forensics" / "provider_raw_content.txt",
        ]
    )
    if found is None:
        matches = sorted(root.rglob("provider_raw_content.txt"))
        if matches:
            return matches[0]
        raise FileNotFoundError("A.38 provider_raw_content.txt introuvable.")
    return found


def a38_raw_bin_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    root = a38_canary_root(project_name, sortie_dir=sortie_dir)
    found = _first_existing(
        [
            root / "provider_raw_response.bin",
            root / "provider_forensics" / "provider_raw_response.bin",
        ]
    )
    if found is None:
        matches = sorted(root.rglob("provider_raw_response.bin"))
        if matches:
            return matches[0]
        raise FileNotFoundError("A.38 provider_raw_response.bin introuvable.")
    return found


def a38_request_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return a38_canary_root(project_name, sortie_dir=sortie_dir) / (
        "global_consolidation_a38_request.json"
    )


def a38_usage_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return a38_canary_root(project_name, sortie_dir=sortie_dir) / (
        "global_consolidation_a38_usage_cost.json"
    )


def a38_max_tokens_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return a38_canary_root(project_name, sortie_dir=sortie_dir) / (
        "global_consolidation_a38_max_tokens_forensics.json"
    )


def read_a38_raw_text(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> str:
    raw_bytes = a38_raw_text_path(project_name, sortie_dir=sortie_dir).read_bytes()
    text = raw_bytes.decode("utf-8")
    if text.endswith("\n"):
        text = text[:-1]
    if text.endswith("\r"):
        text = text[:-1]
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if digest != A38_RAW_TEXT_SHA256:
        raise ValueError(
            f"A.38 raw text hash drift: {digest} ≠ {A38_RAW_TEXT_SHA256}."
        )
    if len(text) != A38_RAW_TEXT_CHARS:
        raise ValueError(
            f"A.38 raw text size drift: {len(text)} ≠ {A38_RAW_TEXT_CHARS}."
        )
    return text


def read_a38_raw_bin(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> bytes:
    return a38_raw_bin_path(project_name, sortie_dir=sortie_dir).read_bytes()


def load_json_artifact(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} is not an object")
    return payload


def verify_a38_identity(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    request = load_json_artifact(a38_request_path(project_name, sortie_dir=sortie_dir))
    usage = load_json_artifact(a38_usage_path(project_name, sortie_dir=sortie_dir))
    max_tokens = load_json_artifact(
        a38_max_tokens_path(project_name, sortie_dir=sortie_dir)
    )
    text = read_a38_raw_text(project_name, sortie_dir=sortie_dir)
    raw_bin = read_a38_raw_bin(project_name, sortie_dir=sortie_dir)
    text_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    bin_digest = hashlib.sha256(raw_bin).hexdigest()
    request_id = usage.get("request_id") or max_tokens.get("request_id")
    ok = (
        request_id == A38_REQUEST_ID
        and request.get("request_identity") == A38_REQUEST_IDENTITY
        and text_digest == A38_RAW_TEXT_SHA256
        and int(max_tokens.get("raw_text_chars") or 0) == A38_RAW_TEXT_CHARS
        and max_tokens.get("raw_text_sha256") == A38_RAW_TEXT_SHA256
        and usage.get("finish_reason") == "max_tokens"
        and int(usage.get("output") or 0) == 32000
        and max_tokens.get("repaired") is False
    )
    return {
        "ok": ok,
        "request_id": request_id,
        "expected_request_id": A38_REQUEST_ID,
        "request_identity": request.get("request_identity"),
        "expected_identity": A38_REQUEST_IDENTITY,
        "raw_text_sha256": text_digest,
        "raw_text_chars": len(text),
        "raw_bin_sha256": bin_digest,
        "raw_bin_bytes": len(raw_bin),
        "http_status": usage.get("http_status"),
        "finish_reason": usage.get("finish_reason"),
        "thinking_tokens": usage.get("thinking"),
        "input_tokens": usage.get("actual_provider_input"),
        "output_tokens": usage.get("output"),
        "cost_usd": ((usage.get("cost") or {}).get("total_cost")),
        "repaired": False,
        "json_loads_attempted_for_success": False,
        "max_tokens_artifact": {
            "finish_reason": max_tokens.get("finish_reason"),
            "failure_class": max_tokens.get("failure_class"),
            "candidate_created": max_tokens.get("candidate_created"),
        },
    }


def protected_a39_historical_hashes(
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
    "a38_max_tokens_path",
    "a38_raw_bin_path",
    "a38_raw_text_path",
    "a38_request_path",
    "a38_usage_path",
    "load_json_artifact",
    "protected_a39_historical_hashes",
    "read_a38_raw_bin",
    "read_a38_raw_text",
    "verify_a38_identity",
]
