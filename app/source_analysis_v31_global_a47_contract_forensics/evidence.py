"""Lecture seule des preuves A.46. Aucune réparation. Aucune écriture A.46."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v31_global_a47_contract_forensics.constants import (
    A45_NORMALIZED_INPUT_HASH,
    A45_REQUEST_HASH,
    A46_COST_USD,
    A46_ELAPSED_MS,
    A46_FINISH_REASON,
    A46_HTTP_STATUS,
    A46_INPUT_TOKENS,
    A46_INTENT_LENGTH,
    A46_OUTPUT_TOKENS,
    A46_RAW_RESPONSE_HASH,
    A46_RAW_TEXT_BYTES,
    A46_RAW_TEXT_CHARS,
    A46_REQUEST_ID,
    A46_STATUS_PRESERVED,
    A46_THINKING_TOKENS,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
)
from app.source_analysis_v31_global_a47_contract_forensics.paths import (
    a46_candidate_path,
    a46_identity_path,
    a46_raw_path,
    a46_report_path,
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_a46_raw(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    path = a46_raw_path(project_name, sortie_dir=sortie_dir)
    if not path.is_file():
        raise FileNotFoundError(f"A.46 raw response missing: {path}")
    return _load_json(path)


def derived_a46_transport(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    raw = read_a46_raw(project_name, sortie_dir=sortie_dir)
    parsed = raw.get("raw_structured_response")
    if not isinstance(parsed, dict):
        raise ValueError("A.46 raw_structured_response is not an object")
    return copy.deepcopy(parsed)


def a46_intent_text(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> str:
    gm = derived_a46_transport(project_name, sortie_dir=sortie_dir).get("gm") or {}
    return str(gm.get("in") or "")


def read_a46_candidate(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any] | None:
    path = a46_candidate_path(project_name, sortie_dir=sortie_dir)
    if not path.is_file():
        return None
    return _load_json(path)


def protected_a47_historical_hashes(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, str]:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    hashes: dict[str, str] = {}
    for relative in PROTECTED_HISTORICAL:
        path = root / project_name / relative
        if path.is_file():
            hashes[relative] = sha256_of_file(path)
    report = a46_report_path(project_name, sortie_dir=sortie_dir)
    if report.is_file():
        rel = f"audit/{report.name}"
        hashes.setdefault(rel, sha256_of_file(report))
    return hashes


def verify_a46_identity(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    raw = read_a46_raw(project_name, sortie_dir=sortie_dir)
    identity_path = a46_identity_path(project_name, sortie_dir=sortie_dir)
    identity = _load_json(identity_path) if identity_path.is_file() else {}
    text = str(raw.get("raw_text") or "")
    recomputed = content_hash(text) if text else ""
    gm = (raw.get("raw_structured_response") or {}).get("gm") or {}
    intent = str(gm.get("in") or "")
    report = a46_report_path(project_name, sortie_dir=sortie_dir)
    report_text = report.read_text(encoding="utf-8") if report.is_file() else ""
    result_block = ""
    if "## Result" in report_text:
        result_block = report_text.split("## Result", 1)[1][:80]
    ok = (
        raw.get("immutable") is True
        and raw.get("repaired") is False
        and int(raw.get("http_status") or 0) == A46_HTTP_STATUS
        and str(raw.get("finish_reason") or "") == A46_FINISH_REASON
        and int(raw.get("thinking_tokens") if raw.get("thinking_tokens") is not None else -1)
        == A46_THINKING_TOKENS
        and int(raw.get("input_tokens") or 0) == A46_INPUT_TOKENS
        and int(raw.get("output_tokens") or 0) == A46_OUTPUT_TOKENS
        and str(raw.get("request_id") or "") == A46_REQUEST_ID
        and str(raw.get("raw_response_hash") or "") == A46_RAW_RESPONSE_HASH
        and recomputed == A46_RAW_RESPONSE_HASH
        and int(raw.get("raw_response_chars") or 0) == A46_RAW_TEXT_CHARS
        and int(raw.get("raw_response_bytes") or 0) == A46_RAW_TEXT_BYTES
        and len(intent) == A46_INTENT_LENGTH
        and A46_STATUS_PRESERVED == "FAIL"
        and "FAIL" in result_block
        and identity.get("raw_response_hash") == A46_RAW_RESPONSE_HASH
    )
    return {
        "ok": ok,
        "request_id": raw.get("request_id"),
        "http_status": raw.get("http_status"),
        "finish_reason": raw.get("finish_reason"),
        "thinking_tokens": raw.get("thinking_tokens"),
        "input_tokens": raw.get("input_tokens"),
        "output_tokens": raw.get("output_tokens"),
        "elapsed_ms": raw.get("elapsed_ms") or A46_ELAPSED_MS,
        "cost_usd": A46_COST_USD,
        "raw_response_hash": raw.get("raw_response_hash"),
        "recomputed_raw_text_hash": recomputed,
        "immutable": raw.get("immutable"),
        "repaired": raw.get("repaired"),
        "intent_length": len(intent),
        "normalized_input_hash_prefix": A45_NORMALIZED_INPUT_HASH[:8],
        "request_hash_prefix": A45_REQUEST_HASH[:8],
        "a46_historical_status": A46_STATUS_PRESERVED,
        "raw_not_modified": True,
        "audit_dir": str(audit_dir(project_name, sortie_dir=sortie_dir)),
    }


__all__ = [
    "a46_intent_text",
    "derived_a46_transport",
    "protected_a47_historical_hashes",
    "read_a46_candidate",
    "read_a46_raw",
    "verify_a46_identity",
]
