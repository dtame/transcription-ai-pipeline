"""Load preserved 4B.2.6 evidence. Read-only. No provider call."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b23.identity import file_identity, verify_canonical_inputs
from app.book_semantic_gate_4b261.constants import (
    EXPECTED_REQUEST_SHA256_4B26,
    OBSERVED_4B26_REQUEST_ID,
)
from app.book_semantic_gate_4b261.paths import (
    historical_4b26_dir,
    historical_4b26_report_path,
)

_USAGE_KEYS = (
    "usage",
    "prompt_tokens",
    "completion_tokens",
    "completion_tokens_details",
    "output_tokens_details",
    "reasoning_tokens",
    "thinking_tokens",
    "refusal",
    "finish_reason",
    "message",
    "content",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_optional_json(path: Path) -> Any:
    if not path.is_file():
        return None
    return load_json(path)


def _read_optional_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def walk_keys(payload: Any, *, target: str, path: str = "$") -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            child = f"{path}.{key}"
            if str(key) == target:
                hits.append({"path": child, "value": value})
            hits.extend(walk_keys(value, target=target, path=child))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            hits.extend(walk_keys(item, target=target, path=f"{path}[{index}]"))
    return hits


def load_4b26_bundle(*, root: Path | None = None) -> dict[str, Any]:
    directory = historical_4b26_dir(root=root)
    report = historical_4b26_report_path(root=root)
    forensics = (
        directory
        / "structured_output_forensics"
        / "book-semantic-gate-4b26"
        / EXPECTED_REQUEST_SHA256_4B26
        / "provider_response_forensics.json"
    )
    files = {
        "request": directory / "book_semantic_gate_4b26_request_identity.json",
        "provider": directory / "book_semantic_gate_4b26_provider_evidence.json",
        "raw_structured": directory / "book_semantic_gate_4b26_raw_structured_response.json",
        "raw_text": directory / "book_semantic_gate_4b26_raw_provider_text.txt",
        "validation": directory / "book_semantic_gate_4b26_response_validation.json",
        "cost": directory / "book_semantic_gate_4b26_cost.json",
        "cases": directory / "book_semantic_gate_4b26_case_results.json",
        "score": directory / "book_semantic_gate_4b26_benchmark_score.json",
        "precall": directory / "book_semantic_gate_4b26_precall.json",
        "runtime": directory / "book_semantic_gate_4b26_runtime.json",
        "compat": directory / "book_semantic_gate_4b26_api_compatibility.json",
        "index": directory / "book_semantic_gate_4b26_index.json",
        "forensics": forensics,
        "report": report,
    }
    loaded = {
        key: (
            _read_optional_text(path)
            if path.suffix == ".txt" or path.suffix == ".md"
            else _read_optional_json(path)
        )
        for key, path in files.items()
    }
    identities = {key: file_identity(path) for key, path in files.items()}
    request = loaded.get("request") or {}
    payload = dict(request.get("payload") or {})
    return {
        "directory": str(directory).replace("\\", "/"),
        "files": identities,
        "loaded": loaded,
        "payload": payload,
        "request_sha256": request.get("request_sha256"),
        "request_id": OBSERVED_4B26_REQUEST_ID,
        "canonical_inputs": verify_canonical_inputs(root=root),
    }


def usage_field_inventory(bundle: dict[str, Any]) -> dict[str, Any]:
    inventory: dict[str, list[dict[str, Any]]] = {}
    loaded = dict(bundle.get("loaded") or {})
    searchable = {
        name: loaded.get(name)
        for name in (
            "provider",
            "raw_structured",
            "cost",
            "forensics",
            "validation",
            "runtime",
            "compat",
            "precall",
        )
    }
    for key in _USAGE_KEYS:
        hits: list[dict[str, Any]] = []
        for source, payload in searchable.items():
            for hit in walk_keys(payload, target=key):
                hits.append({"source": source, **hit})
        inventory[key] = hits
    return inventory


__all__ = [
    "load_4b26_bundle",
    "load_json",
    "usage_field_inventory",
    "walk_keys",
]
