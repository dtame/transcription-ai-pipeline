"""Validate a delivery URL and store the image only after it decodes.

The caller must pass a URL taken from a provider poll. User-supplied result
URLs are rejected by the host check. A failed download does not submit a
new generation.
"""

from __future__ import annotations

import hashlib
import os
import struct
import zlib
from pathlib import Path
from typing import Any

from app.cover.image_providers.bfl_spec import MAX_DOWNLOAD_BYTES, SpecError, validate_delivery_url
from app.cover.image_providers.bfl_transport import TransportRequest, TransportResponse

REQUIRED_PROVENANCE = (
    "provider_id",
    "model_id",
    "task_id",
    "prompt_sha256",
    "output_format",
)

_REDIRECTS = frozenset({301, 302, 303, 307, 308})
_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/webp": "webp",
}


class DownloadRejected(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def validate_provenance(metadata: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_PROVENANCE if not metadata.get(key)]
    if missing:
        raise DownloadRejected("metadata_missing:" + ",".join(missing))


def download_delivery_image(
    *,
    transport: Any,
    url: str,
    destination: Path,
    provenance: dict[str, Any],
    max_bytes: int = MAX_DOWNLOAD_BYTES,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    validate_provenance(provenance)
    try:
        current = validate_delivery_url(url)
    except SpecError as exc:
        raise DownloadRejected(str(exc)) from exc
    response = _get(transport, current, timeout_seconds)
    if response.status in _REDIRECTS:
        location = response.header("location") or ""
        try:
            location = validate_delivery_url(location)
        except Exception as exc:
            raise DownloadRejected("unauthorized_redirect") from exc
        response = _get(transport, location, timeout_seconds)
        if response.status in _REDIRECTS:
            raise DownloadRejected("redirect_chain_refused")
        current = location
    if response.status in {403, 404, 410}:
        raise DownloadRejected("result_expired_requires_human")
    if response.status != 200:
        raise DownloadRejected(f"download_status_{response.status}")
    declared = response.header("content-length")
    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
        raise DownloadRejected("file_too_large")
    if len(response.body) > max_bytes:
        raise DownloadRejected("file_too_large")
    observed = _media_type(response.header("content-type"))
    if observed is None:
        raise DownloadRejected("content_type_rejected")
    decoded = decode_image(response.body, observed)
    digest = hashlib.sha256(response.body).hexdigest()
    stored = dict(provenance)
    stored.update(
        {
            "sha256": digest,
            "byte_length": len(response.body),
            "observed_format": observed,
            "pixel_width": decoded["width"],
            "pixel_height": decoded["height"],
            "delivery_host": _host(current),
            "signed_url_stored": False,
        }
    )
    _atomic_write(Path(destination), response.body)
    written = Path(destination).read_bytes()
    if hashlib.sha256(written).hexdigest() != digest:
        Path(destination).unlink(missing_ok=True)
        raise DownloadRejected("sha256_mismatch_after_write")
    return {"path": str(destination), "sha256": digest, "metadata": stored, "generated": True}


def decode_image(payload: bytes, kind: str) -> dict[str, int]:
    if kind == "png":
        return _decode_png(payload)
    if kind == "jpeg":
        return _decode_jpeg(payload)
    if kind == "webp":
        return _decode_webp(payload)
    raise DownloadRejected("content_type_rejected")


def _get(transport: Any, url: str, timeout_seconds: float) -> TransportResponse:
    return transport.exchange(
        TransportRequest(method="GET", url=url, headers={"accept": "image/*"}, timeout_seconds=timeout_seconds)
    )


def _media_type(header: str | None) -> str | None:
    if not header:
        return None
    return _TYPES.get(header.split(";", 1)[0].strip().lower())


def _host(url: str) -> str:
    from urllib.parse import urlsplit

    return urlsplit(url).hostname or ""


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_bytes(payload)
        os.replace(partial, path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    finally:
        if partial.exists():
            partial.unlink(missing_ok=True)


def _decode_png(payload: bytes) -> dict[str, int]:
    signature = b"\x89PNG\r\n\x1a\n"
    if not payload.startswith(signature):
        raise DownloadRejected("corrupt_image")
    cursor = len(signature)
    width = height = None
    color_type = None
    inflated = b""
    saw_iend = False
    while cursor + 8 <= len(payload):
        length = struct.unpack(">I", payload[cursor : cursor + 4])[0]
        cursor += 4
        tag = payload[cursor : cursor + 4]
        cursor += 4
        if cursor + length + 4 > len(payload):
            raise DownloadRejected("corrupt_image")
        data = payload[cursor : cursor + length]
        cursor += length
        expected = zlib.crc32(tag + data) & 0xFFFFFFFF
        actual = struct.unpack(">I", payload[cursor : cursor + 4])[0]
        cursor += 4
        if expected != actual:
            raise DownloadRejected("corrupt_image")
        if tag == b"IHDR":
            if length != 13:
                raise DownloadRejected("corrupt_image")
            width, height, depth, color_type, compression, filt, interlace = struct.unpack(">IIBBBBB", data)
            if depth != 8 or compression or filt or interlace or color_type not in {2, 6}:
                raise DownloadRejected("corrupt_image")
        elif tag == b"IDAT":
            inflated += data
        elif tag == b"IEND":
            saw_iend = True
            break
    if not saw_iend or width is None or height is None or color_type is None:
        raise DownloadRejected("corrupt_image")
    try:
        raw = zlib.decompress(inflated)
    except zlib.error as exc:
        raise DownloadRejected("corrupt_image") from exc
    channels = 3 if color_type == 2 else 4
    if len(raw) < height * (1 + width * channels):
        raise DownloadRejected("corrupt_image")
    return {"width": width, "height": height}


def _decode_jpeg(payload: bytes) -> dict[str, int]:
    if len(payload) < 4 or not payload.startswith(b"\xff\xd8") or not payload.endswith(b"\xff\xd9"):
        raise DownloadRejected("corrupt_image")
    cursor = 2
    while cursor + 3 < len(payload) - 2:
        if payload[cursor] != 0xFF:
            raise DownloadRejected("corrupt_image")
        marker = payload[cursor + 1]
        cursor += 2
        if marker in {0xD8, 0xD9}:
            continue
        if cursor + 2 > len(payload):
            raise DownloadRejected("corrupt_image")
        size = struct.unpack(">H", payload[cursor : cursor + 2])[0]
        if marker in {0xC0, 0xC1, 0xC2}:
            if size < 7 or cursor + 7 > len(payload):
                raise DownloadRejected("corrupt_image")
            height, width = struct.unpack(">HH", payload[cursor + 3 : cursor + 7])
            return {"width": width, "height": height}
        cursor += size
    raise DownloadRejected("corrupt_image")


def _decode_webp(payload: bytes) -> dict[str, int]:
    if len(payload) < 30 or payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
        raise DownloadRejected("corrupt_image")
    if payload[12:16] == b"VP8X" and len(payload) >= 30:
        width = 1 + int.from_bytes(payload[24:27], "little")
        height = 1 + int.from_bytes(payload[27:30], "little")
        return {"width": width, "height": height}
    if payload[12:16] == b"VP8 " and len(payload) >= 30:
        width = int.from_bytes(payload[26:28], "little") & 0x3FFF
        height = int.from_bytes(payload[28:30], "little") & 0x3FFF
        return {"width": width, "height": height}
    if payload[12:16] == b"VP8L" and len(payload) >= 25:
        bits = int.from_bytes(payload[21:25], "little")
        return {"width": (bits & 0x3FFF) + 1, "height": ((bits >> 14) & 0x3FFF) + 1}
    raise DownloadRejected("corrupt_image")


__all__ = [
    "REQUIRED_PROVENANCE",
    "DownloadRejected",
    "decode_image",
    "download_delivery_image",
    "validate_provenance",
]
