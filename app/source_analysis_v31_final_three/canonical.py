"""Reconstruction canonique offline + compatibilité mixte READY 4/7. 0 provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.validator import ensure_valid_source_map, validate_source_map
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.decoder import decode_v31_local_lite_transport
from app.source_analysis_v31_final_three.constants import (
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    WIN003_PROVENANCE,
    WINDOW_SPECS,
)
from app.source_analysis_v31_final_three.paths import (
    a28_candidate_window_dir,
)
from app.source_analysis_v31_real_win004.canonical import normalized_src_refs
from app.source_analysis_v31_remaining_windows.canonical import (
    reconstruct_mixed as reconstruct_mixed_a28,
    reconstruct_window,
)


def _load_ready_local_lite(
    project_name: str,
    window_id: str,
    *,
    sortie_dir: Path | None,
) -> dict[str, Any] | None:
    path = (
        a28_candidate_window_dir(project_name, window_id, sortie_dir=sortie_dir)
        / "transport.json"
    )
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return {"path": str(path), "payload": payload}
    return None


def _readable_local_lite(payload: Mapping[str, Any]) -> tuple[bool, str | None]:
    try:
        decode_v31_local_lite_transport(
            payload, allowed_source_refs=set(normalized_src_refs(payload))
        )
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def reconstruct_mixed(
    transport: Mapping[str, Any],
    window: WindowInput,
    *,
    signature: str,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    base = reconstruct_mixed_a28(
        transport,
        window,
        signature=signature,
        project_name=project_name,
        sortie_dir=sortie_dir,
    )
    win002 = _load_ready_local_lite(project_name, "WIN002", sortie_dir=sortie_dir)
    win003 = _load_ready_local_lite(project_name, "WIN003", sortie_dir=sortie_dir)
    win002_ok = False
    win002_error = None
    if win002 is not None:
        win002_ok, win002_error = _readable_local_lite(win002["payload"])
    win003_ok = False
    win003_error = None
    if win003 is not None:
        win003_ok, win003_error = _readable_local_lite(win003["payload"])
    extra_ok = (win002 is None or win002_ok) and (win003 is None or win003_ok)
    compatible = base.get("mixed_compatibility") == "PASS" and extra_ok
    local = dict(base.get("local") or {})
    return {
        **base,
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "win002_v31_present": win002 is not None,
        "win002_path": None if win002 is None else win002["path"],
        "win002_readable_as_local_lite": win002_ok,
        "win002_error": win002_error,
        "win002_signature": WINDOW_SPECS["WIN002"]["analysis_signature"],
        "win003_v31_present": win003 is not None,
        "win003_path": None if win003 is None else win003["path"],
        "win003_readable_as_local_lite": win003_ok,
        "win003_error": win003_error,
        "win003_signature": WINDOW_SPECS["WIN003"]["analysis_signature"],
        "win003_provenance": WIN003_PROVENANCE,
        "ready_set": {
            "WIN001": "V3 historical",
            "WIN002": "V3.1 local-lite",
            "WIN003": "V3.1 local-lite revalidated from A.28",
            "WIN004": "V3.1 local-lite",
        },
        "importance_to_kind_contamination": local.get(
            "importance_to_kind_contamination", 0
        ),
        "all_kinds_empty": local.get("all_kinds_empty"),
        "mixed_compatibility": "PASS" if compatible else "FAIL",
    }


def attempt_source_map_validation(
    source_map,
    transcript: TranscriptInput,
) -> dict[str, Any]:
    errors = []
    ensure_ok = False
    try:
        errors = list(validate_source_map(source_map, transcript))
    except Exception as exc:  # noqa: BLE001
        errors = [str(exc)]
    try:
        ensure_valid_source_map(source_map, transcript)
        ensure_ok = True
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))
    return {
        "validate_source_map": "PASS" if errors == [] else "FAIL",
        "ensure_valid_source_map": "PASS" if ensure_ok else "FAIL",
        "errors": errors,
        "schema_py_used": False,
        "source_map_published": False,
    }


__all__ = [
    "attempt_source_map_validation",
    "reconstruct_mixed",
    "reconstruct_window",
]
