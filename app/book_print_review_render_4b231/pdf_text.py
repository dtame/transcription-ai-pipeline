"""Stdlib PDF text and geometry extraction. No extra packages."""

from __future__ import annotations

import re
import zlib
from pathlib import Path
from typing import Any

_MEDIA_BOX = re.compile(
    rb"/MediaBox\s*\[\s*([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*\]"
)
_PAGE_TYPE = re.compile(rb"/Type\s*/Page(?!s)")
_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
_LITERAL = re.compile(rb"\((?:\\.|[^\\)])*\)")
_HEX = re.compile(rb"<([0-9A-Fa-f \t\r\n]+)>")


def extract_pdf_geometry(path: Path) -> dict[str, Any]:
    data = Path(path).read_bytes()
    if not data.startswith(b"%PDF"):
        return {
            "readable": False,
            "page_count": 0,
            "page_sizes": [],
            "error": "file is not a PDF",
        }
    boxes = [
        {
            "x0": float(match.group(1)),
            "y0": float(match.group(2)),
            "x1": float(match.group(3)),
            "y1": float(match.group(4)),
            "width_pt": float(match.group(3)) - float(match.group(1)),
            "height_pt": float(match.group(4)) - float(match.group(2)),
        }
        for match in _MEDIA_BOX.finditer(data)
    ]
    page_count = len(_PAGE_TYPE.findall(data))
    return {
        "readable": True,
        "page_count": page_count,
        "page_sizes": boxes,
        "error": "",
        "bytes": len(data),
    }


_TJ_OP = re.compile(rb"\((?:\\.|[^\\)])*\)\s*Tj")
_TJ_ARRAY = re.compile(rb"\[(.*?)\]\s*TJ", re.DOTALL)


def extract_pdf_text(path: Path) -> str:
    data = Path(path).read_bytes()
    chunks: list[str] = []
    for match in _STREAM.finditer(data):
        decoded = _maybe_flate(match.group(1))
        chunks.append(_operators_to_text(decoded))
    return _normalize_ws(" ".join(chunk for chunk in chunks if chunk))


def _maybe_flate(payload: bytes) -> bytes:
    for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
        try:
            return zlib.decompress(payload, wbits)
        except zlib.error:
            continue
    return payload


def _operators_to_text(payload: bytes) -> str:
    if b"Tj" not in payload and b"TJ" not in payload:
        return ""
    parts: list[str] = []
    for match in _TJ_OP.finditer(payload):
        literal = match.group(0).rsplit(b"Tj", 1)[0].strip()
        if literal.startswith(b"(") and literal.endswith(b")"):
            parts.append(_decode_literal(literal[1:-1]))
    for match in _TJ_ARRAY.finditer(payload):
        for item in _LITERAL.finditer(match.group(1)):
            parts.append(_decode_literal(item.group(0)[1:-1]))
        for item in _HEX.finditer(match.group(1)):
            decoded = _decode_hex(item.group(1))
            if decoded:
                parts.append(decoded)
    return "".join(part for part in parts if part)


def _decode_hex(payload: bytes) -> str:
    hexed = re.sub(rb"\s+", b"", payload)
    if len(hexed) % 2:
        hexed += b"0"
    try:
        raw = bytes.fromhex(hexed.decode("ascii"))
    except ValueError:
        return ""
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="ignore")
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16-le", errors="ignore")
    return raw.decode("latin-1", errors="ignore")


def _decode_literal(raw: bytes) -> str:
    text = (
        raw.replace(b"\\n", b"\n")
        .replace(b"\\r", b"\r")
        .replace(b"\\t", b"\t")
        .replace(b"\\(", b"(")
        .replace(b"\\)", b")")
        .replace(b"\\\\", b"\\")
    )
    if text.startswith(b"\xfe\xff"):
        return text[2:].decode("utf-16-be", errors="ignore")
    return text.decode("latin-1", errors="ignore")


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_for_compare(text: str) -> str:
    cleaned = (
        text.replace("\u00ad", "")
        .replace("-\n", "")
        .replace("\r", "\n")
    )
    cleaned = re.sub(r"\ben-[A-Z]{2}\b", " ", cleaned)
    return _normalize_ws(cleaned)


_PDF_PUNCT = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
        "\ufb01": "fi",
        "\ufb02": "fl",
    }
)


def fold_for_pdf(text: str) -> str:
    cleaned = normalize_for_compare(text).translate(_PDF_PUNCT)
    return re.sub(r"[^a-z0-9]", "", cleaned.casefold())


__all__ = [
    "extract_pdf_geometry",
    "extract_pdf_text",
    "fold_for_pdf",
    "normalize_for_compare",
]
