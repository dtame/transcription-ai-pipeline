"""Reconstruction canonique offline + compatibilité mixte A.21/A.27. 0 provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.validator import ensure_valid_source_map, validate_source_map
from app.source_analysis_local_v3.compatibility import (
    normalize_v3_transport_to_local_lite,
)
from app.source_analysis_local_v3.constants import SEMANTIC_TRANSPORT_VERSION_V3
from app.source_analysis_local_v3.decoder import decode_v31_local_lite_transport
from app.source_analysis_v31_local_lite.compatibility import load_a21_historical_transport
from app.source_analysis_v31_real_win004.canonical import (
    normalized_src_refs,
    reconstruct_ideas,
)
from app.source_analysis_v31_real_win004.constants import (
    EXPECTED_ANALYSIS_SIGNATURE as A27_SIGNATURE,
)
from app.source_analysis_v31_remaining_windows.constants import (
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_remaining_windows.paths import a27_candidate_window_dir


def load_a27_win004_transport(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any] | None:
    path = a27_candidate_window_dir(project_name, sortie_dir=sortie_dir) / "transport.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return {"path": str(path), "payload": payload}
    return None


def reconstruct_window(
    transport: Mapping[str, Any],
    window: WindowInput,
    *,
    signature: str,
) -> dict[str, Any]:
    return reconstruct_ideas(transport, window, signature=signature)


def reconstruct_mixed(
    transport: Mapping[str, Any],
    window: WindowInput,
    *,
    signature: str,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    local = reconstruct_window(transport, window, signature=signature)
    historical = load_a21_historical_transport(project_name, sortie_dir=sortie_dir)
    a27 = load_a27_win004_transport(project_name, sortie_dir=sortie_dir)
    a21_ok = False
    a21_path = None
    normalized_ok = False
    invented = None
    old_rejected = False
    if historical is not None:
        a21_path = historical["path"]
        payload = historical["payload"]
        try:
            normalize_v3_transport_to_local_lite(
                payload, source_transport_version=SEMANTIC_TRANSPORT_VERSION_V3
            )
            a21_ok = True
        except Exception as exc:  # noqa: BLE001
            a21_ok = False
            invented = str(exc)
        try:
            normalized, provenance = normalize_v3_transport_to_local_lite(
                payload, source_transport_version=SEMANTIC_TRANSPORT_VERSION_V3
            )
            decode_v31_local_lite_transport(
                normalized,
                allowed_source_refs=set(normalized_src_refs(normalized)),
            )
            normalized_ok = True
            invented = provenance.get("invented_semantics")
        except Exception as exc:  # noqa: BLE001
            normalized_ok = False
            invented = str(exc)
        try:
            decode_v31_local_lite_transport(
                payload, allowed_source_refs=set(normalized_src_refs(payload))
            )
        except Exception:
            old_rejected = True
    a27_ok = False
    a27_path = None
    if a27 is not None:
        a27_path = a27["path"]
        try:
            decode_v31_local_lite_transport(
                a27["payload"],
                allowed_source_refs=set(normalized_src_refs(a27["payload"])),
            )
            a27_ok = True
        except Exception:
            a27_ok = False
    compatible = (
        local["idea_validation"] == "PASS"
        and local["all_kinds_empty"]
        and local["importance_to_kind_contamination"] == 0
        and (historical is None or (a21_ok and normalized_ok and old_rejected))
        and (a27 is None or a27_ok)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "window_id": window.window_id,
        "local": local,
        "a21_historical_present": historical is not None,
        "a21_path": a21_path,
        "a21_readable": a21_ok,
        "a21_normalized_to_local_lite": normalized_ok,
        "a21_old_v3_rejected_under_local_lite": old_rejected,
        "a27_win004_present": a27 is not None,
        "a27_path": a27_path,
        "a27_readable_as_local_lite": a27_ok,
        "a27_signature_untouched": A27_SIGNATURE,
        "normalization_invented_semantics": invented,
        "common_strategy": (
            "historical WIN001 V3 remains readable; normalize drops IDEA "
            "subtype; WIN004 and remaining windows native local-lite "
            "reconstruct kind=''. No real consolidation."
        ),
        "schema_py_used": False,
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
    "load_a27_win004_transport",
    "reconstruct_mixed",
    "reconstruct_window",
]
