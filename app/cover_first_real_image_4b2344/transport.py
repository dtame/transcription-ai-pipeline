"""One live Images API exchange through the sealed urllib client.

The module constant ``LIVE_HTTP_ENABLED`` stays false in source. This transport
opens a socket only while that flag is true for the current process, and it
refuses a second exchange.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from app.cover.image_providers.bfl_download import decode_image
from app.cover.image_providers.bfl_transport import (
    NetworkSealed,
    TransportRequest,
    TransportResponse,
    UrllibTransport,
)
import app.cover.image_providers.bfl_transport as live_transport
from app.cover.image_providers.openai_spec import GENERATION_URL, SELECTED_HEIGHT, SELECTED_WIDTH
from app.cover_first_real_image_4b2344.constants import LIVE_TIMEOUT_SECONDS
from app.cover_first_real_image_4b2344.paths import quarantine_path

_HEADER_ALLOW = ("x-request-id", "openai-request-id", "openai-processing-ms", "openai-version")
_SUMMARY_KEYS = ("created", "size", "quality", "output_format", "background", "model", "id")


class SingleUseLiveTransport:
    """UrllibTransport plus a longer image timeout and a one-exchange cap."""

    def __init__(self, *, timeout_seconds: float = LIVE_TIMEOUT_SECONDS, quarantine: Path | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.quarantine = quarantine if quarantine is not None else quarantine_path()
        self.exchange_count = 0
        self.trace: dict[str, Any] = {
            "transport": "UrllibTransport",
            "wrapper": "SingleUseLiveTransport",
            "endpoint": GENERATION_URL,
            "timeout_seconds": timeout_seconds,
            "timeout_reason": (
                "The sealed TransportRequest default is 30 seconds. "
                "A gpt-image-2 portrait can outlast that. "
                "This single exchange waits longer so a slow response is not abandoned."
            ),
            "automatic_retry": False,
            "socket_opened": False,
            "http_status": None,
            "provider_request_id": None,
            "response_summary": None,
            "quarantine_path": None,
            "dimension_mismatch": False,
        }

    def exchange(self, request: TransportRequest) -> TransportResponse:
        if self.exchange_count >= 1:
            raise RuntimeError("second provider exchange refused")
        self.exchange_count += 1
        self.trace["exchange_count"] = self.exchange_count
        request.timeout_seconds = self.timeout_seconds
        self.trace["method"] = request.method
        self.trace["url"] = request.url
        self.trace["header_names"] = sorted(request.headers)
        if not live_transport.LIVE_HTTP_ENABLED:
            self.trace["socket_opened"] = False
            self.trace["local_refusal"] = "LIVE_HTTP_ENABLED"
            raise NetworkSealed("LIVE_HTTP_ENABLED is false. No socket will be opened.")
        self.trace["socket_opened"] = True
        import urllib.error

        try:
            response = UrllibTransport().exchange(request)
        except urllib.error.HTTPError as exc:
            raw = exc.read() if exc.fp is not None else b""
            if not isinstance(raw, bytes):
                raw = b""
            response = TransportResponse(
                status=int(exc.code),
                headers={str(key): str(value) for key, value in exc.headers.items()},
                body=raw,
                url=request.url,
            )
        self._record(response)
        return response

    def _record(self, response: TransportResponse) -> None:
        self.trace["http_status"] = int(response.status)
        lowered = {str(key).lower(): value for key, value in response.headers.items()}
        kept = {name: lowered[name] for name in _HEADER_ALLOW if name in lowered}
        request_id = kept.get("x-request-id") or kept.get("openai-request-id")
        self.trace["provider_request_id"] = request_id
        self.trace["response_headers_allowlisted"] = kept
        summary = _summary(response.body)
        self._quarantine_if_dimensions_differ(summary, status=int(response.status))
        self.trace["response_summary"] = summary

    def _quarantine_if_dimensions_differ(self, summary: dict[str, Any], *, status: int) -> None:
        encoded = summary.pop("_png_bytes", None)
        width = summary.pop("_width", None)
        height = summary.pop("_height", None)
        if status != 200:
            return
        if not isinstance(encoded, bytes) or not isinstance(width, int) or not isinstance(height, int):
            return
        if width == SELECTED_WIDTH and height == SELECTED_HEIGHT:
            return
        self.trace["dimension_mismatch"] = True
        self.trace["received_width"] = width
        self.trace["received_height"] = height
        destination = self.quarantine
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            partial = destination.with_name(destination.name + ".partial")
            partial.write_bytes(encoded)
            partial.replace(destination)
        except OSError as exc:
            self.trace["quarantine_error"] = type(exc).__name__
            return
        self.trace["quarantine_path"] = str(destination)


def _summary(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return {"json": False, "body_retained": False}
    if not isinstance(payload, dict):
        return {"json": False, "body_retained": False}
    summary: dict[str, Any] = {"json": True, "body_retained": False}
    for key in _SUMMARY_KEYS:
        if key in payload and not isinstance(payload[key], (dict, list)):
            summary[key] = payload[key]
    usage = payload.get("usage")
    if isinstance(usage, dict):
        summary["usage"] = {
            key: value
            for key, value in usage.items()
            if isinstance(value, (int, str, float, bool)) or value is None
        }
        details = usage.get("input_tokens_details")
        if isinstance(details, dict):
            summary["usage"]["input_tokens_details"] = {
                key: value
                for key, value in details.items()
                if isinstance(value, (int, str, float, bool)) or value is None
            }
    error = payload.get("error")
    if isinstance(error, dict):
        summary["error"] = {
            key: error.get(key)
            for key in ("message", "type", "code", "param")
            if key in error
        }
    images = payload.get("data")
    summary["data_count"] = len(images) if isinstance(images, list) else None
    if isinstance(images, list) and len(images) == 1 and isinstance(images[0], dict):
        encoded = images[0].get("b64_json")
        if isinstance(encoded, str) and encoded.strip():
            try:
                raw = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError):
                summary["b64_json_decodable"] = False
            else:
                summary["b64_json_decodable"] = True
                summary["png_bytes"] = len(raw)
                try:
                    decoded = decode_image(raw, "png")
                except Exception:
                    summary["png_decodable"] = False
                else:
                    summary["png_decodable"] = True
                    summary["_png_bytes"] = raw
                    summary["_width"] = int(decoded["width"])
                    summary["_height"] = int(decoded["height"])
    return summary


__all__ = ["SingleUseLiveTransport"]
