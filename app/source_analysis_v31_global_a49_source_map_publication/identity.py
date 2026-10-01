"""Identité octet-à-octet du candidat A.48. Aucune resérialisation sémantique."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file


def file_identity(path: Path) -> dict[str, Any]:
    path = Path(path)
    raw = path.read_bytes() if path.is_file() else b""
    text = raw.decode("utf-8") if raw else ""
    canonical = ""
    canonical_hash = ""
    parsed: Any = None
    parse_ok = False
    if text:
        try:
            parsed = json.loads(text)
            parse_ok = True
            canonical = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
            canonical_hash = content_hash(canonical)
        except json.JSONDecodeError:
            parsed = None
    return {
        "path": str(path),
        "exists": path.is_file(),
        "sha256": sha256_of_file(path) if path.is_file() else "",
        "utf8_bytes": len(raw),
        "character_count": len(text),
        "canonical_json": canonical,
        "canonical_json_sha256": canonical_hash,
        "json_parse": "PASS" if parse_ok else "FAIL",
        "payload": parsed if isinstance(parsed, dict) else {},
    }


def bytes_identity(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8") if raw else ""
    canonical = ""
    canonical_hash = ""
    parsed: Any = None
    parse_ok = False
    if text:
        try:
            parsed = json.loads(text)
            parse_ok = True
            canonical = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
            canonical_hash = content_hash(canonical)
        except json.JSONDecodeError:
            parsed = None
    return {
        "sha256": hashlib.sha256(raw).hexdigest() if raw else "",
        "utf8_bytes": len(raw),
        "character_count": len(text),
        "canonical_json": canonical,
        "canonical_json_sha256": canonical_hash,
        "json_parse": "PASS" if parse_ok else "FAIL",
        "payload": parsed if isinstance(parsed, dict) else {},
    }


__all__ = ["bytes_identity", "file_identity"]
