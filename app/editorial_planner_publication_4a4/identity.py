"""Byte identity of the A.3.5 candidate and published EditorialPlan."""

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
    return {
        "path": str(path).replace("\\", "/"),
        "exists": path.is_file(),
        **bytes_identity(raw),
    }


def bytes_identity(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8") if raw else ""
    parsed: Any = None
    parse_ok = False
    canonical = ""
    canonical_hash = ""
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
        "canonical_json_sha256": canonical_hash,
        "json_parse": "PASS" if parse_ok else "FAIL",
        "payload": parsed if isinstance(parsed, dict) else {},
    }


def sha256_file(path: Path) -> str:
    path = Path(path)
    if not path.is_file():
        return ""
    return sha256_of_file(path)


__all__ = ["bytes_identity", "file_identity", "sha256_file"]
