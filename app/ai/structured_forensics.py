"""
Forensics de sortie structurée — observabilité locale uniquement.

Aucun appel provider. Aucune réparation JSON. Le texte brut n'est jamais
journalisé : il peut être persisté dans un artefact contrôlé, hors logs.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from app.ai.errors import AIStructuredOutputError
from app.file_utils import write_text_atomic

_SIGNATURE_RE = re.compile(r"^[0-9a-f]{16,64}$")

FORENSICS_DIR_NAME = "structured_output_forensics"
FORENSICS_JSON_NAME = "provider_response_forensics.json"
FORENSICS_RAW_NAME = "provider_raw_content.txt"
FORENSICS_SCHEMA_VERSION = "1.0"

SECRET_KEY_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "x-api-key",
        "x_api_key",
        "password",
        "secret",
        "api_token",
        "access_token",
        "auth_token",
        "bearer",
    }
)

_SECRET_VALUE_PREFIXES = ("sk-ant-", "sk-", "Bearer ")


def raw_text_digest(text: str | None) -> dict[str, Any]:
    value = text if isinstance(text, str) else ""
    encoded = value.encode("utf-8")
    return {
        "raw_text_sha256": hashlib.sha256(encoded).hexdigest() if value else None,
        "raw_text_bytes": len(encoded),
        "raw_text_chars": len(value),
        "raw_text_present": bool(value),
    }


def looks_like_secret_key(name: str) -> bool:
    lowered = str(name or "").strip().lower().replace("-", "_")
    if lowered in SECRET_KEY_NAMES or lowered.replace("-", "_") in SECRET_KEY_NAMES:
        return True
    return lowered.endswith("_api_key") or lowered.endswith("_secret")


def redact_secret_strings(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): ("***REDACTED***" if looks_like_secret_key(str(key)) else redact_secret_strings(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secret_strings(item) for item in value]
    if isinstance(value, str):
        for prefix in _SECRET_VALUE_PREFIXES:
            if prefix in value:
                return "***REDACTED***"
    return value


def assert_safe_analysis_signature(signature: str) -> str:
    """Identité déterministe uniquement — hex minuscule, pas de secret."""
    value = str(signature or "").strip().lower()
    if not _SIGNATURE_RE.fullmatch(value):
        raise ValueError(
            "analysis_signature forensics invalide — hex déterministe requis, "
            "pas d'identité aléatoire, pas de secret."
        )
    return value


def build_structured_output_forensics(
    *,
    error: AIStructuredOutputError,
    provider: str | None = None,
    model: str | None = None,
    stage: str | None = None,
    window_id: str | None = None,
    analysis_signature: str | None = None,
    http_status: int | None = None,
    persist_raw_text: bool = True,
) -> dict[str, Any]:
    """
    Artefact déterministe de diagnostic. Jamais de clé API, jamais de prompt.

    Le texte brut n'est PAS recopié ici. Seuls hash / tailles / métadonnées
    provider. `raw_content_persisted` est renseigné par persist_*.
    """
    response = getattr(error, "response", None)
    if response is not None:
        error.attach_response_diagnostics(response)
        provider = provider or getattr(response, "provider", None)
        model = model or getattr(response, "model", None)
        stage = stage or getattr(response, "stage", None)
        digest = raw_text_digest(getattr(response, "text", None))
    else:
        digest = {
            "raw_text_sha256": error.raw_text_sha256,
            "raw_text_bytes": error.raw_text_bytes,
            "raw_text_chars": error.raw_text_chars,
            "raw_text_present": bool(error.raw_text_sha256),
        }

    payload = {
        "schema_version": FORENSICS_SCHEMA_VERSION,
        "kind": "PROVIDER_RESPONSE_FORENSICS",
        "provider": provider,
        "model": model,
        "stage": stage,
        "window_id": window_id,
        "analysis_signature": analysis_signature,
        "http_status": http_status,
        "http_status_available": http_status is not None,
        "usage": {
            "source": error.usage_source,
            "input_tokens": error.input_tokens,
            "output_tokens": error.output_tokens,
            "total_tokens": error.total_tokens,
        },
        "finish_reason": error.finish_reason,
        "request_id": error.request_id,
        "parse_error": {
            "error_type": type(error).__name__,
            "parse_failure_kind": error.parse_failure_kind,
            "message": str(error),
            "json_decode_msg": error.json_decode_msg,
            "json_decode_lineno": error.json_decode_lineno,
            "json_decode_colno": error.json_decode_colno,
        },
        "raw_content": {
            **digest,
            "persisted": False,
            "persist_requested": bool(persist_raw_text),
            "policy": (
                "persist locally under structured_output_forensics, "
                "never logs/console, no JSON repair"
            ),
        },
        "transport_written": False,
        "result_written": False,
        "retry": False,
        "secrets_included": False,
    }
    return redact_secret_strings(payload)


def forensics_window_root(windows_root: Path, window_id: str) -> Path:
    return Path(windows_root).parent / FORENSICS_DIR_NAME / window_id


def forensics_dir(
    windows_root: Path,
    window_id: str,
    analysis_signature: str | None = None,
) -> Path:
    """
    Répertoire forensics.

    Avec signature : WIN001/<analysis_signature>/ — pas d'écrasement
    entre analyses. Sans signature : racine WIN001/ (lecture historique
    uniquement ; persist refuse ce chemin).
    """
    root = forensics_window_root(windows_root, window_id)
    if analysis_signature is None:
        return root
    return root / assert_safe_analysis_signature(analysis_signature)


def persist_structured_output_forensics(
    *,
    error: AIStructuredOutputError,
    windows_root: Path,
    window_id: str,
    analysis_signature: str,
    provider: str | None = None,
    model: str | None = None,
    stage: str | None = None,
    persist_raw_text: bool = True,
) -> dict[str, Any]:
    """
    Persiste les forensics à côté de analysis/windows, jamais dedans.

    Layout :

        <project>/analysis/structured_output_forensics/WIN001/<signature>/
            provider_response_forensics.json
            provider_raw_content.txt   (si texte présent et demandé)

    N'écrit pas transport.json ni result.json. Aucun retry.
    La signature est obligatoire : un chemin keyed seulement par WIN001
    écraserait l'évidence historique.
    """
    safe_signature = assert_safe_analysis_signature(analysis_signature)
    directory = forensics_dir(windows_root, window_id, safe_signature)
    directory.mkdir(parents=True, exist_ok=True)
    payload = build_structured_output_forensics(
        error=error,
        provider=provider,
        model=model,
        stage=stage,
        window_id=window_id,
        analysis_signature=safe_signature,
        persist_raw_text=persist_raw_text,
    )
    raw_written = False
    response = getattr(error, "response", None)
    text = getattr(response, "text", None) if response is not None else None
    if persist_raw_text and isinstance(text, str) and text:
        write_text_atomic(directory / FORENSICS_RAW_NAME, text)
        raw_written = True
    payload["raw_content"]["persisted"] = raw_written
    json_path = directory / FORENSICS_JSON_NAME
    write_text_atomic(
        json_path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    payload["artifact_paths"] = {
        "forensics_json": str(json_path),
        "raw_content": str(directory / FORENSICS_RAW_NAME) if raw_written else None,
    }
    return payload


__all__ = [
    "FORENSICS_DIR_NAME",
    "FORENSICS_JSON_NAME",
    "FORENSICS_RAW_NAME",
    "FORENSICS_SCHEMA_VERSION",
    "assert_safe_analysis_signature",
    "build_structured_output_forensics",
    "forensics_dir",
    "forensics_window_root",
    "looks_like_secret_key",
    "persist_structured_output_forensics",
    "raw_text_digest",
    "redact_secret_strings",
]
