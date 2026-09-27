"""
Frontière forensique HTTP — avant interprétation provider.

Une fois qu'une réponse HTTP a été reçue, les métadonnées et le corps brut
ne dépendent plus de ProviderResult, AIResponse, de l'extraction de contenu
ni du parse structuré.

Aucun secret. Aucun dump console. Aucune réparation JSON. Aucun retry.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping

from app.ai.errors import AIError, AIResponseError
from app.ai.structured_forensics import (
    assert_safe_analysis_signature,
    looks_like_secret_key,
    redact_secret_strings,
)

FORENSICS_DIR_NAME = "provider_forensics"
ENVELOPE_JSON_NAME = "provider_http_envelope.json"
RAW_BODY_NAME = "provider_raw_response.bin"
FORENSICS_SCHEMA_VERSION = "1.0"

CLASS_HTTP_TRANSPORT_FAILURE = "HTTP_TRANSPORT_FAILURE"
CLASS_HTTP_ERROR = "HTTP_ERROR"
CLASS_INVALID_RESPONSE_JSON = "INVALID_RESPONSE_JSON"
CLASS_INVALID_RESPONSE_TOP_LEVEL = "INVALID_RESPONSE_TOP_LEVEL"
CLASS_MISSING_CONTENT = "MISSING_CONTENT"
CLASS_INVALID_CONTENT_TYPE = "INVALID_CONTENT_TYPE"
CLASS_NO_TEXT_BLOCK = "NO_TEXT_BLOCK"
CLASS_INVALID_TEXT_BLOCK = "INVALID_TEXT_BLOCK"
CLASS_MISSING_PROVIDER_FIELD = "MISSING_PROVIDER_FIELD"
CLASS_SDK_UNEXPECTED = "SDK_UNEXPECTED"
CLASS_STRUCTURED_JSON_DECODE = "STRUCTURED_JSON_DECODE"
CLASS_STRUCTURED_SCHEMA_VALIDATION = "STRUCTURED_SCHEMA_VALIDATION"
CLASS_SEMANTIC_CAPACITY_EXCEEDED = "SEMANTIC_CAPACITY_EXCEEDED"
CLASS_SEMANTIC_GRANULARITY_LIMIT = "SEMANTIC_GRANULARITY_LIMIT"
CLASS_WINDOW_VALIDATION_FAILURE = "WINDOW_VALIDATION_FAILURE"
CLASS_INTERRUPTED_AFTER_HTTP_RESPONSE = "INTERRUPTED_AFTER_HTTP_RESPONSE"

SAFE_RESPONSE_HEADERS = frozenset(
    {
        "request-id",
        "x-request-id",
        "content-type",
        "content-length",
        "retry-after",
    }
)
REQUEST_ID_HEADER_NAMES = ("request-id", "x-request-id")

_SECRET_HEADER_NAMES = frozenset(
    {
        "authorization",
        "x-api-key",
        "api-key",
        "cookie",
        "set-cookie",
        "proxy-authorization",
    }
)

class ProviderForensicCollisionError(RuntimeError):
    """Un artefact forensique existe déjà pour cette signature. Pas d'écrasement."""


@dataclass
class ProviderForensicScope:
    windows_root: Path
    window_id: str
    analysis_signature: str
    provider: str | None = None
    model: str | None = None
    persist_on_failure: bool = True


@dataclass
class ProviderHttpEnvelope:
    """
    Enveloppe HTTP générique. Le corps brut reste en mémoire (bytes).
    La sérialisation JSON n'inclut jamais le corps ni de secret.
    """

    schema_version: str = FORENSICS_SCHEMA_VERSION
    provider: str | None = None
    model: str | None = None
    post_attempted: bool = False
    response_received: bool = False
    http_success: bool = False
    http_status: int | None = None
    headers_subset: dict[str, str] = field(default_factory=dict)
    request_id: str | None = None
    raw_body: bytes | None = None
    raw_sha256: str | None = None
    raw_size: int | None = None
    text_encoding: str | None = None
    text_decode_ok: bool | None = None
    json_decode_ok: bool | None = None
    json_top_level_type: str | None = None
    parsed_top_level: Any = None
    usage: dict[str, Any] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None
    content_metadata: dict[str, Any] | None = None
    elapsed_ms: int | None = None
    classification: str | None = None
    provider_envelope_valid: bool = False
    airesponse_created: bool = False
    structured_parse_passed: bool = False
    persisted: bool = False
    forensic_path: str | None = None
    raw_persisted: bool = False

    def compact_metadata(self) -> dict[str, Any]:
        return redact_secret_strings(
            {
                "schema_version": self.schema_version,
                "provider": self.provider,
                "model": self.model,
                "post_attempted": self.post_attempted,
                "response_received": self.response_received,
                "http_success": self.http_success,
                "http_status": self.http_status,
                "headers_subset": dict(self.headers_subset),
                "request_id": self.request_id,
                "raw_sha256": self.raw_sha256,
                "raw_size": self.raw_size,
                "text_encoding": self.text_encoding,
                "text_decode_ok": self.text_decode_ok,
                "json_decode_ok": self.json_decode_ok,
                "json_top_level_type": self.json_top_level_type,
                "usage": self.usage,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "finish_reason": self.finish_reason,
                "content_metadata": self.content_metadata,
                "elapsed_ms": self.elapsed_ms,
                "classification": self.classification,
                "provider_envelope_valid": self.provider_envelope_valid,
                "airesponse_created": self.airesponse_created,
                "structured_parse_passed": self.structured_parse_passed,
                "secrets_included": False,
            }
        )


@dataclass(frozen=True)
class ProviderHttpExchange:
    payload: dict[str, Any]
    envelope: ProviderHttpEnvelope


@dataclass
class ProviderReplayDiagnosis:
    classification: str | None
    error_type: str | None
    response_received: bool
    http_status: int | None
    request_id: str | None
    usage: dict[str, Any] | None
    finish_reason: str | None
    airesponse_created: bool
    structured_parse_passed: bool
    transport_written: bool = False
    result_written: bool = False
    text_available: bool = False
    text_chars: int | None = None
    raw_sha256: str | None = None
    raw_size: int | None = None
    message: str | None = None


_current_envelope: contextvars.ContextVar[ProviderHttpEnvelope | None] = contextvars.ContextVar(
    "provider_http_envelope",
    default=None,
)
_current_scope: contextvars.ContextVar[ProviderForensicScope | None] = contextvars.ContextVar(
    "provider_forensic_scope",
    default=None,
)


def current_http_envelope() -> ProviderHttpEnvelope | None:
    return _current_envelope.get()


def current_forensic_scope() -> ProviderForensicScope | None:
    return _current_scope.get()


def set_current_http_envelope(envelope: ProviderHttpEnvelope | None) -> None:
    _current_envelope.set(envelope)


@contextmanager
def provider_forensic_scope(
    *,
    windows_root: Path,
    window_id: str,
    analysis_signature: str,
    provider: str | None = None,
    model: str | None = None,
) -> Iterator[ProviderForensicScope]:
    scope = ProviderForensicScope(
        windows_root=Path(windows_root),
        window_id=str(window_id),
        analysis_signature=assert_safe_analysis_signature(analysis_signature),
        provider=provider,
        model=model,
    )
    token = _current_scope.set(scope)
    envelope_token = _current_envelope.set(None)
    try:
        yield scope
    finally:
        _current_scope.reset(token)
        _current_envelope.reset(envelope_token)


def whitelist_response_headers(headers: Mapping[str, Any] | None) -> dict[str, str]:
    if not headers:
        return {}
    safe: dict[str, str] = {}
    items = headers.items() if hasattr(headers, "items") else []
    for key, value in items:
        name = str(key or "").strip().lower()
        if name in _SECRET_HEADER_NAMES or looks_like_secret_key(name):
            continue
        if name not in SAFE_RESPONSE_HEADERS:
            continue
        safe[name] = str(value)
    return safe


def request_id_from_headers(headers: Mapping[str, Any] | None) -> str | None:
    if not headers:
        return None
    lowered = {str(key).strip().lower(): value for key, value in headers.items()}
    for name in REQUEST_ID_HEADER_NAMES:
        value = lowered.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _raw_bytes_from_response(response: Any) -> bytes:
    raw = getattr(response, "content", None)
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, str):
        return raw.encode("utf-8")
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text.encode("utf-8")
    return b""


def capture_http_response(
    response: Any,
    *,
    provider: str,
    model: str | None = None,
    elapsed_ms: int | None = None,
) -> ProviderHttpEnvelope:
    """Capture immédiate après réception HTTP. Avant toute interprétation."""
    raw = _raw_bytes_from_response(response)
    headers = whitelist_response_headers(getattr(response, "headers", None))
    status = getattr(response, "status_code", None)
    status_int = int(status) if isinstance(status, int) else None
    http_success = status_int is not None and 200 <= status_int < 300
    encoding_ok: bool | None
    try:
        raw.decode("utf-8")
        encoding_ok = True
    except Exception:
        encoding_ok = False
    envelope = ProviderHttpEnvelope(
        provider=provider,
        model=model,
        post_attempted=True,
        response_received=True,
        http_success=http_success,
        http_status=status_int,
        headers_subset=headers,
        request_id=request_id_from_headers(getattr(response, "headers", None)),
        raw_body=raw,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        raw_size=len(raw),
        text_encoding="utf-8",
        text_decode_ok=encoding_ok,
        elapsed_ms=elapsed_ms,
    )
    set_current_http_envelope(envelope)
    return envelope


def extract_usage_best_effort(envelope: ProviderHttpEnvelope, data: Any) -> None:
    """Best-effort. Un échec d'extraction ne détruit pas le corps brut."""
    if not isinstance(data, dict):
        return
    try:
        usage = data.get("usage")
        if isinstance(usage, dict):
            compact: dict[str, Any] = {}
            for key in (
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "output_tokens_details",
                "thinking_tokens",
            ):
                if key in usage:
                    compact[key] = usage[key]
            envelope.usage = compact or dict(usage)
            if usage.get("input_tokens") is not None:
                envelope.input_tokens = int(usage["input_tokens"])
            if usage.get("output_tokens") is not None:
                envelope.output_tokens = int(usage["output_tokens"])
        if "stop_reason" in data and data.get("stop_reason") is not None:
            envelope.finish_reason = data.get("stop_reason")
        if envelope.request_id is None and isinstance(data.get("id"), str):
            envelope.request_id = data["id"]
    except (TypeError, ValueError):
        return


def anthropic_content_metadata(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"content_present": False, "content_type": None}
    if "content" not in data:
        return {"content_present": False, "content_type": None}
    content = data["content"]
    meta: dict[str, Any] = {
        "content_present": True,
        "content_type": type(content).__name__,
    }
    if isinstance(content, list):
        block_types: list[Any] = []
        text_lengths: list[int] = []
        for block in content:
            if isinstance(block, dict):
                block_types.append(block.get("type"))
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    text_lengths.append(len(block["text"]))
            else:
                block_types.append(type(block).__name__)
        meta["block_count"] = len(content)
        meta["block_types"] = block_types
        meta["text_block_count"] = sum(1 for item in block_types if item == "text")
        meta["text_lengths"] = text_lengths
    return meta


def decode_json_from_envelope(envelope: ProviderHttpEnvelope) -> Any:
    """JSON depuis les bytes capturés. Le corps reste disponible si ça échoue."""
    raw = envelope.raw_body if envelope.raw_body is not None else b""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        envelope.json_decode_ok = False
        envelope.classification = CLASS_INVALID_RESPONSE_JSON
        raise _response_error(
            envelope,
            CLASS_INVALID_RESPONSE_JSON,
            f"Réponse {envelope.provider or 'provider'} illisible (JSON attendu).",
        ) from exc
    try:
        data = json.loads(text)
    except Exception as exc:
        envelope.json_decode_ok = False
        envelope.classification = CLASS_INVALID_RESPONSE_JSON
        raise _response_error(
            envelope,
            CLASS_INVALID_RESPONSE_JSON,
            f"Réponse {envelope.provider or 'provider'} illisible (JSON attendu).",
        ) from exc
    envelope.json_decode_ok = True
    envelope.json_top_level_type = type(data).__name__
    envelope.parsed_top_level = data
    if not isinstance(data, dict):
        envelope.classification = CLASS_INVALID_RESPONSE_TOP_LEVEL
        raise _response_error(
            envelope,
            CLASS_INVALID_RESPONSE_TOP_LEVEL,
            f"Réponse {envelope.provider or 'provider'} inattendue : objet JSON attendu, "
            f"{type(data).__name__} reçu.",
        )
    extract_usage_best_effort(envelope, data)
    return data


def _response_error(
    envelope: ProviderHttpEnvelope,
    classification: str,
    message: str,
) -> AIResponseError:
    error = AIResponseError(message)
    error.classification = classification
    apply_envelope_to_error(error, envelope)
    return error


def apply_envelope_to_error(error: AIError, envelope: ProviderHttpEnvelope | None) -> None:
    if envelope is None:
        return
    error.http_envelope = envelope
    error.post_attempted = envelope.post_attempted
    error.response_received = envelope.response_received
    if error.classification is None:
        error.classification = envelope.classification
    error.http_status = envelope.http_status
    error.request_id = envelope.request_id
    error.elapsed_ms = envelope.elapsed_ms
    error.raw_sha256 = envelope.raw_sha256
    error.raw_size = envelope.raw_size
    error.forensic_path = envelope.forensic_path
    error.provider = error.provider or envelope.provider
    error.model = error.model or envelope.model
    if error.input_tokens is None:
        error.input_tokens = envelope.input_tokens
    if error.output_tokens is None:
        error.output_tokens = envelope.output_tokens
    if error.finish_reason is None:
        error.finish_reason = envelope.finish_reason
    if envelope.input_tokens is not None or envelope.output_tokens is not None:
        error.usage_source = error.usage_source or "provider"


def apply_current_envelope(error: AIError) -> None:
    apply_envelope_to_error(error, current_http_envelope())


def forensics_dir(
    windows_root: Path,
    window_id: str,
    analysis_signature: str,
) -> Path:
    safe = assert_safe_analysis_signature(analysis_signature)
    return Path(windows_root).parent / FORENSICS_DIR_NAME / window_id / safe


def write_bytes_atomic(path: Path, payload: bytes) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_bytes(payload)
        if partial.read_bytes() != payload:
            raise ValueError(f"Octets partiels ≠ contenu canonique pour {path.name}.")
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()
    return path


def _assert_no_secrets(payload: Mapping[str, Any]) -> None:
    blob = json.dumps(payload, ensure_ascii=False)
    lowered = blob.lower()
    for needle in (
        "authorization",
        "x-api-key",
        "sk-ant-",
        "bearer ",
        "cookie",
        "set-cookie",
    ):
        if needle in lowered:
            raise ValueError("forensics refuse un champ secret")


def persist_provider_forensics(
    envelope: ProviderHttpEnvelope,
    *,
    windows_root: Path | None = None,
    window_id: str | None = None,
    analysis_signature: str | None = None,
    persist_raw: bool = True,
    classification: str | None = None,
) -> dict[str, Any]:
    """
    Persiste l'enveloppe + le corps brut. Collision = refus, pas d'écrasement.

    N'écrit jamais transport.json ni result.json.
    """
    scope = current_forensic_scope()
    root = windows_root or (scope.windows_root if scope else None)
    window = window_id or (scope.window_id if scope else None)
    signature = analysis_signature or (scope.analysis_signature if scope else None)
    if root is None or not window or not signature:
        return {"written": False, "reason": "no_forensic_scope"}
    if classification:
        envelope.classification = classification
    if envelope.provider is None and scope is not None:
        envelope.provider = scope.provider
    if envelope.model is None and scope is not None:
        envelope.model = scope.model

    directory = forensics_dir(root, window, signature)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / ENVELOPE_JSON_NAME
    raw_path = directory / RAW_BODY_NAME

    if json_path.exists() or raw_path.exists():
        if json_path.exists():
            existing = json.loads(json_path.read_text(encoding="utf-8"))
            existing_sha = (
                existing.get("raw_content", {}).get("sha256")
                if isinstance(existing, dict)
                else None
            )
            if existing_sha and existing_sha == envelope.raw_sha256:
                envelope.persisted = True
                envelope.forensic_path = str(directory)
                envelope.raw_persisted = raw_path.exists()
                return existing if isinstance(existing, dict) else {"written": True, "idempotent": True}
        raise ProviderForensicCollisionError(
            f"forensics déjà présentes pour {window}/{signature} — pas d'écrasement."
        )

    raw_written = False
    if persist_raw and envelope.response_received and envelope.raw_body is not None:
        write_bytes_atomic(raw_path, envelope.raw_body)
        raw_written = True
        envelope.raw_persisted = True

    payload = {
        "schema_version": FORENSICS_SCHEMA_VERSION,
        "kind": "PROVIDER_HTTP_ENVELOPE",
        "window_id": window,
        "analysis_signature": assert_safe_analysis_signature(signature),
        **envelope.compact_metadata(),
        "raw_content": {
            "sha256": envelope.raw_sha256,
            "size": envelope.raw_size,
            "persisted": raw_written,
            "encoding": envelope.text_encoding,
            "text_decode_ok": envelope.text_decode_ok,
            "policy": (
                "persist bytes locally under provider_forensics, "
                "never logs/console, no JSON repair"
            ),
        },
        "transport_written": False,
        "result_written": False,
        "retry": False,
        "secrets_included": False,
        "artifact_paths": {
            "envelope_json": str(json_path),
            "raw_body": str(raw_path) if raw_written else None,
        },
    }
    payload = redact_secret_strings(payload)
    _assert_no_secrets(payload)
    write_bytes_atomic(
        json_path,
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    envelope.persisted = True
    envelope.forensic_path = str(directory)
    return payload


def persist_current_failure(*, classification: str | None = None) -> dict[str, Any] | None:
    envelope = current_http_envelope()
    scope = current_forensic_scope()
    if envelope is None or scope is None or not scope.persist_on_failure:
        return None
    if envelope.persisted:
        return None
    try:
        return persist_provider_forensics(envelope, classification=classification)
    except ProviderForensicCollisionError:
        return {"written": False, "collision": True}


def persist_error_forensics(
    error: AIError,
    *,
    windows_root: Path,
    window_id: str,
    analysis_signature: str,
) -> dict[str, Any] | None:
    envelope = getattr(error, "http_envelope", None) or current_http_envelope()
    if envelope is None:
        return None
    apply_envelope_to_error(error, envelope)
    try:
        payload = persist_provider_forensics(
            envelope,
            windows_root=windows_root,
            window_id=window_id,
            analysis_signature=analysis_signature,
            classification=error.classification,
        )
    except ProviderForensicCollisionError:
        return {"written": False, "collision": True}
    error.forensic_path = envelope.forensic_path
    return payload


def persist_interrupt_forensics() -> dict[str, Any] | None:
    envelope = current_http_envelope()
    if envelope is None or not envelope.response_received:
        return None
    envelope.classification = envelope.classification or CLASS_INTERRUPTED_AFTER_HTTP_RESPONSE
    return persist_current_failure(classification=envelope.classification)


class _ReplayHttpResponse:
    def __init__(
        self,
        raw_body: bytes,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.content = raw_body
        self.status_code = status_code
        self.headers = dict(headers or {})
        try:
            self.text = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            self.text = ""


def replay_provider_http(
    raw_body: bytes,
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
    provider: str = "anthropic",
    model: str | None = None,
    response_schema: Mapping[str, Any] | None = None,
) -> ProviderReplayDiagnosis:
    """
    Rejeu diagnostique offline. Mêmes parseurs que la production.
    Aucun réseau. Aucune réparation. N'écrit pas transport/result.
    """
    from app.ai.providers.anthropic_engine import extract_anthropic_text
    from app.ai.structured import parse_structured_output

    envelope = capture_http_response(
        _ReplayHttpResponse(raw_body, status_code=status_code, headers=headers),
        provider=provider,
        model=model,
    )
    if envelope.http_status is not None and envelope.http_status >= 400:
        envelope.classification = CLASS_HTTP_ERROR
        return ProviderReplayDiagnosis(
            classification=CLASS_HTTP_ERROR,
            error_type="HTTP_ERROR",
            response_received=True,
            http_status=envelope.http_status,
            request_id=envelope.request_id,
            usage=envelope.usage,
            finish_reason=envelope.finish_reason,
            airesponse_created=False,
            structured_parse_passed=False,
            raw_sha256=envelope.raw_sha256,
            raw_size=envelope.raw_size,
            message=f"{provider} a répondu {envelope.http_status}.",
        )
    try:
        data = decode_json_from_envelope(envelope)
    except AIResponseError as exc:
        return ProviderReplayDiagnosis(
            classification=exc.classification,
            error_type=type(exc).__name__,
            response_received=True,
            http_status=envelope.http_status,
            request_id=envelope.request_id,
            usage=envelope.usage,
            finish_reason=envelope.finish_reason,
            airesponse_created=False,
            structured_parse_passed=False,
            raw_sha256=envelope.raw_sha256,
            raw_size=envelope.raw_size,
            message=str(exc),
        )
    if provider.lower() == "anthropic":
        try:
            text = extract_anthropic_text(data, envelope=envelope)
        except AIResponseError as exc:
            return ProviderReplayDiagnosis(
                classification=exc.classification,
                error_type=type(exc).__name__,
                response_received=True,
                http_status=envelope.http_status,
                request_id=envelope.request_id,
                usage=envelope.usage,
                finish_reason=envelope.finish_reason,
                airesponse_created=False,
                structured_parse_passed=False,
                raw_sha256=envelope.raw_sha256,
                raw_size=envelope.raw_size,
                message=str(exc),
            )
    else:
        text = json.dumps(data)
    envelope.provider_envelope_valid = True
    if response_schema is None:
        return ProviderReplayDiagnosis(
            classification=None,
            error_type=None,
            response_received=True,
            http_status=envelope.http_status,
            request_id=envelope.request_id,
            usage=envelope.usage,
            finish_reason=envelope.finish_reason,
            airesponse_created=True,
            structured_parse_passed=False,
            text_available=True,
            text_chars=len(text),
            raw_sha256=envelope.raw_sha256,
            raw_size=envelope.raw_size,
        )
    try:
        parse_structured_output(text, response_schema)
    except AIError as exc:
        return ProviderReplayDiagnosis(
            classification=getattr(exc, "classification", None),
            error_type=type(exc).__name__,
            response_received=True,
            http_status=envelope.http_status,
            request_id=envelope.request_id,
            usage=envelope.usage,
            finish_reason=envelope.finish_reason,
            airesponse_created=True,
            structured_parse_passed=False,
            text_available=True,
            text_chars=len(text),
            raw_sha256=envelope.raw_sha256,
            raw_size=envelope.raw_size,
            message=str(exc),
        )
    envelope.structured_parse_passed = True
    return ProviderReplayDiagnosis(
        classification=None,
        error_type=None,
        response_received=True,
        http_status=envelope.http_status,
        request_id=envelope.request_id,
        usage=envelope.usage,
        finish_reason=envelope.finish_reason,
        airesponse_created=True,
        structured_parse_passed=True,
        text_available=True,
        text_chars=len(text),
        raw_sha256=envelope.raw_sha256,
        raw_size=envelope.raw_size,
    )


__all__ = [
    "CLASS_HTTP_ERROR",
    "CLASS_HTTP_TRANSPORT_FAILURE",
    "CLASS_INVALID_CONTENT_TYPE",
    "CLASS_INVALID_RESPONSE_JSON",
    "CLASS_INVALID_RESPONSE_TOP_LEVEL",
    "CLASS_INVALID_TEXT_BLOCK",
    "CLASS_MISSING_CONTENT",
    "CLASS_MISSING_PROVIDER_FIELD",
    "CLASS_NO_TEXT_BLOCK",
    "CLASS_SDK_UNEXPECTED",
    "CLASS_STRUCTURED_JSON_DECODE",
    "CLASS_STRUCTURED_SCHEMA_VALIDATION",
    "ENVELOPE_JSON_NAME",
    "FORENSICS_DIR_NAME",
    "FORENSICS_SCHEMA_VERSION",
    "ProviderForensicCollisionError",
    "ProviderHttpEnvelope",
    "ProviderHttpExchange",
    "ProviderReplayDiagnosis",
    "RAW_BODY_NAME",
    "SAFE_RESPONSE_HEADERS",
    "apply_current_envelope",
    "apply_envelope_to_error",
    "anthropic_content_metadata",
    "capture_http_response",
    "current_forensic_scope",
    "current_http_envelope",
    "decode_json_from_envelope",
    "extract_usage_best_effort",
    "forensics_dir",
    "persist_current_failure",
    "persist_error_forensics",
    "persist_interrupt_forensics",
    "persist_provider_forensics",
    "provider_forensic_scope",
    "replay_provider_http",
    "request_id_from_headers",
    "set_current_http_envelope",
    "whitelist_response_headers",
    "write_bytes_atomic",
]
