"""Deterministic checks on a stored PNG. No artistic judgment."""

from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path
from typing import Any

from app.cover.image_providers.bfl_download import DownloadRejected, decode_image
from app.cover.image_providers.openai_spec import MAX_IMAGE_BYTES, SELECTED_HEIGHT, SELECTED_WIDTH

_PNG = b"\x89PNG\r\n\x1a\n"
_COLOR = {
    0: "grayscale",
    2: "rgb",
    3: "palette",
    4: "grayscale_alpha",
    6: "rgba",
}


def inspect_png(path: Path, *, expected_width: int = SELECTED_WIDTH, expected_height: int = SELECTED_HEIGHT) -> dict[str, Any]:
    target = Path(path)
    result: dict[str, Any] = {
        "path": str(target),
        "exists": target.exists(),
        "empty": True,
        "bytes": 0,
        "sha256": None,
        "png_signature": False,
        "decoded": False,
        "width": None,
        "height": None,
        "expected_width": expected_width,
        "expected_height": expected_height,
        "dimensions_match": False,
        "color_type": None,
        "color_mode": None,
        "bit_depth": None,
        "alpha": None,
        "reasonable_size": False,
        "technical_validation": "FAIL",
        "output_dimension_status": None,
        "decode_error": None,
    }
    if not target.is_file():
        return result
    payload = target.read_bytes()
    result["bytes"] = len(payload)
    result["empty"] = len(payload) == 0
    result["sha256"] = hashlib.sha256(payload).hexdigest()
    result["png_signature"] = payload.startswith(_PNG)
    result["reasonable_size"] = 1024 <= len(payload) <= MAX_IMAGE_BYTES
    header = _ihdr(payload)
    if header is not None:
        result["width"] = header["width"]
        result["height"] = header["height"]
        result["bit_depth"] = header["bit_depth"]
        result["color_type"] = header["color_type"]
        result["color_mode"] = header["color_mode"]
        result["alpha"] = header["alpha"]
    try:
        decoded = decode_image(payload, "png")
    except DownloadRejected as exc:
        result["decode_error"] = exc.reason
    else:
        result["decoded"] = True
        result["width"] = decoded["width"]
        result["height"] = decoded["height"]
    result["dimensions_match"] = (
        result["width"] == expected_width and result["height"] == expected_height
    )
    if result["decoded"] and not result["dimensions_match"]:
        result["output_dimension_status"] = "OUTPUT_DIMENSION_MISMATCH"
    passed = (
        result["png_signature"]
        and result["decoded"]
        and result["dimensions_match"]
        and not result["empty"]
        and result["reasonable_size"]
        and result["sha256"] is not None
    )
    result["technical_validation"] = "PASS" if passed else "FAIL"
    return result


def _ihdr(payload: bytes) -> dict[str, Any] | None:
    if not payload.startswith(_PNG) or len(payload) < 33:
        return None
    cursor = len(_PNG)
    length = struct.unpack(">I", payload[cursor : cursor + 4])[0]
    tag = payload[cursor + 4 : cursor + 8]
    if tag != b"IHDR" or length != 13:
        return None
    data = payload[cursor + 8 : cursor + 21]
    expected = zlib.crc32(tag + data) & 0xFFFFFFFF
    actual = struct.unpack(">I", payload[cursor + 21 : cursor + 25])[0]
    if expected != actual:
        return None
    width, height, depth, color_type, _compression, _filt, _interlace = struct.unpack(">IIBBBBB", data)
    return {
        "width": width,
        "height": height,
        "bit_depth": depth,
        "color_type": color_type,
        "color_mode": _COLOR.get(color_type, "unknown"),
        "alpha": color_type in {4, 6},
    }


__all__ = ["inspect_png"]
