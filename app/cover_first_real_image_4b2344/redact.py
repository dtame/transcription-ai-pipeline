"""Strip provider credentials before any audit file is written."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_SK = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
_BEARER = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_API_KEY_ASSIGN = re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)\S+")


class SecretInArtifact(RuntimeError):
    """An audit write was refused because a credential was still present."""


def current_secret() -> str:
    return os.environ.get("OPENAI_API_KEY", "").strip()


def scrub_text(text: str, secret: str | None = None) -> str:
    cleaned = text
    if secret:
        cleaned = cleaned.replace(secret, "[REDACTED]")
    cleaned = _BEARER.sub("Bearer [REDACTED]", cleaned)
    cleaned = _API_KEY_ASSIGN.sub(r"\1[REDACTED]", cleaned)
    cleaned = _SK.sub("[REDACTED]", cleaned)
    return cleaned


def scrub_value(value: Any, secret: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            str(key): scrub_value(item, secret)
            for key, item in value.items()
            if "api_key" not in str(key).lower()
            and str(key) not in {"authorization", "Authorization", "bearer", "secret", "token"}
        }
    if isinstance(value, (list, tuple)):
        return [scrub_value(item, secret) for item in value]
    if isinstance(value, Path):
        return scrub_text(str(value), secret)
    if isinstance(value, str):
        return scrub_text(value, secret)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return scrub_text(str(value), secret)


def dump_json(path: Path, payload: Any, *, secret: str | None = None) -> None:
    key = current_secret() if secret is None else secret
    cleaned = scrub_value(payload, key)
    text = json.dumps(cleaned, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    text = scrub_text(text, key)
    if key and key in text:
        raise SecretInArtifact("refusing to write an artifact that still contains the API key")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def dump_text(path: Path, text: str, *, secret: str | None = None) -> None:
    key = current_secret() if secret is None else secret
    cleaned = scrub_text(text, key)
    if key and key in cleaned:
        raise SecretInArtifact("refusing to write an artifact that still contains the API key")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cleaned, encoding="utf-8")


def assert_text_file_clean(path: Path) -> None:
    key = current_secret()
    if not path.exists() or not key:
        return
    text = path.read_text(encoding="utf-8")
    if key in text or _SK.search(text):
        cleaned = scrub_text(text, key)
        path.write_text(cleaned, encoding="utf-8")
        if key in cleaned:
            raise SecretInArtifact("a written text file still contains the API key")


__all__ = [
    "SecretInArtifact",
    "assert_text_file_clean",
    "current_secret",
    "dump_json",
    "dump_text",
    "scrub_text",
    "scrub_value",
]
