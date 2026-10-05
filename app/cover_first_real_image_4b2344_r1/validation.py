"""Technical PNG checks plus the metadata chunks that are actually present."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any

from app.cover_first_real_image_4b2344.validation import inspect_png

_PNG = b"\x89PNG\r\n\x1a\n"
_TEXT_CHUNKS = {b"tEXt", b"iTXt", b"zTXt"}


def inspect_received_png(path: Path) -> dict[str, Any]:
    result = inspect_png(path)
    result["metadata"] = _metadata(path)
    return result


def _metadata(path: Path) -> dict[str, Any]:
    target = Path(path)
    empty: dict[str, Any] = {
        "chunks": [],
        "text": [],
        "exif_present": False,
        "exif_bytes": 0,
        "pixels_per_unit": None,
    }
    if not target.is_file():
        return empty
    payload = target.read_bytes()
    if not payload.startswith(_PNG):
        return empty
    chunks: list[str] = []
    texts: list[dict[str, str]] = []
    exif_bytes = 0
    pixels: dict[str, Any] | None = None
    cursor = len(_PNG)
    while cursor + 8 <= len(payload):
        length = struct.unpack(">I", payload[cursor : cursor + 4])[0]
        tag = payload[cursor + 4 : cursor + 8]
        data_start = cursor + 8
        data_end = data_start + length
        if data_end + 4 > len(payload):
            break
        data = payload[data_start:data_end]
        expected = zlib.crc32(tag + data) & 0xFFFFFFFF
        actual = struct.unpack(">I", payload[data_end : data_end + 4])[0]
        cursor = data_end + 4
        name = tag.decode("ascii", errors="replace")
        chunks.append(name)
        if expected != actual:
            continue
        if tag in _TEXT_CHUNKS:
            item = _text_chunk(tag, data)
            if item is not None:
                texts.append(item)
        elif tag == b"eXIf":
            exif_bytes = length
        elif tag == b"pHYs" and length == 9:
            ppux, ppuy, unit = struct.unpack(">IIB", data)
            pixels = {"x": ppux, "y": ppuy, "unit": unit}
        if tag == b"IEND":
            break
    return {
        "chunks": chunks,
        "text": texts,
        "exif_present": exif_bytes > 0,
        "exif_bytes": exif_bytes,
        "pixels_per_unit": pixels,
    }


def _text_chunk(tag: bytes, data: bytes) -> dict[str, str] | None:
    if tag == b"tEXt":
        key, _, value = data.partition(b"\x00")
        return {"kind": "tEXt", "keyword": _latin(key), "text": _latin(value)[:500]}
    if tag == b"zTXt":
        key, _, _rest = data.partition(b"\x00")
        return {"kind": "zTXt", "keyword": _latin(key), "text": ""}
    if tag == b"iTXt":
        key, _, _rest = data.partition(b"\x00")
        return {"kind": "iTXt", "keyword": key.decode("latin-1", errors="replace"), "text": ""}
    return None


def _latin(value: bytes) -> str:
    return value.decode("latin-1", errors="replace")


__all__ = ["inspect_received_png"]
