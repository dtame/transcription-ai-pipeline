"""Post-écriture : relire le disque, valider, identité déterministe."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.source_analysis.models import SourceMap, scan_editorial_structure
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.validator import validate_published_payload
from app.source_analysis.writer import render_source_map
from app.source_analysis_v31_global_a49_source_map_publication.constants import (
    BYTE_IDENTITY_EXACT,
)
from app.source_analysis_v31_global_a49_source_map_publication.gates import (
    _inventory_counts,
    _status,
)
from app.source_analysis_v31_global_a49_source_map_publication.identity import (
    bytes_identity,
    file_identity,
)


def reload_published(
    path: Path,
    *,
    candidate_bytes: bytes,
    transcript: TranscriptInput | None = None,
) -> dict[str, Any]:
    path = Path(path)
    identity = file_identity(path)
    raw = path.read_bytes() if path.is_file() else b""
    payload = identity.get("payload") or {}
    parse_ok = identity.get("json_parse") == "PASS" and bool(payload)
    model_ok = False
    model_error = ""
    source_map = None
    serialized = ""
    try:
        source_map = SourceMap.from_dict(payload)
        model_ok = True
        serialized = json.dumps(source_map.to_dict(), ensure_ascii=False, sort_keys=True)
    except Exception as exc:  # noqa: BLE001
        model_error = f"{type(exc).__name__}: {exc}"
    structural = scan_editorial_structure(payload if payload else {})
    canonical_errors: list[str] = []
    if transcript is not None and parse_ok:
        canonical_errors = validate_published_payload(payload, transcript)
    elif transcript is None:
        canonical_errors = [] if parse_ok and model_ok else ["reload without transcript"]
    canonical_ok = not canonical_errors and parse_ok and model_ok
    idea_src_ok = bool(source_map) and all(idea.source_refs for idea in source_map.ideas)
    published_render = ""
    if source_map is not None:
        published_render = render_source_map(source_map.to_dict())
    byte_match = raw == candidate_bytes
    canonical_match = (
        identity.get("canonical_json_sha256") == bytes_identity(candidate_bytes).get(
            "canonical_json_sha256"
        )
        if raw and candidate_bytes
        else False
    )
    deterministic = "PASS" if canonical_match and serialized else "FAIL"
    if byte_match:
        byte_identity = BYTE_IDENTITY_EXACT
    elif canonical_match:
        byte_identity = "CANONICAL_SEMANTIC_IDENTITY"
    else:
        byte_identity = "MISMATCH"
    return {
        "path": str(path),
        "exists": path.is_file(),
        "identity": identity,
        "json_parse": _status(parse_ok),
        "model_load": _status(model_ok),
        "model_error": model_error,
        "canonical_validation": _status(canonical_ok) if transcript is not None else (
            _status(parse_ok and model_ok)
        ),
        "canonical_errors": list(canonical_errors)[:12],
        "structural_scan": structural.get("status"),
        "forbidden_editorial_structure": "NO" if structural.get("ok") else "YES",
        "traceability": _status(canonical_ok and idea_src_ok)
        if transcript is not None
        else _status(model_ok),
        "deterministic_identity": deterministic if model_ok else "FAIL",
        "byte_identity": byte_identity,
        "published_bytes": len(raw),
        "published_sha256": identity.get("sha256") or "",
        "inventory": _inventory_counts(payload),
        "idea_count": len(payload.get("ideas") or []) if isinstance(payload.get("ideas"), list) else 0,
        "render_equals_disk": (
            published_render.encode("utf-8") == raw if published_render and raw else False
        ),
        "partial_leftover": path.with_name(path.name + ".partial").exists(),
    }


__all__ = ["reload_published"]
