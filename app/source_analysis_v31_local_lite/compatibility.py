"""Compatibilité V3 / v3.1 et dérivé A.21. Lecture seule de l'original."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.errors import WindowTransportValidationError
from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v3.compatibility import (
    normalize_v3_transport_to_local_lite,
    normalize_v3_window_result_to_local_lite,
)
from app.source_analysis_local_v3.decoder import decode_v3_transport
from app.source_analysis_local_v3.e2e import run_v3_windows
from app.source_analysis_local_v3.fixtures import seven_window_plan, v3_success_transport
from app.source_analysis_v3_hardened_win001.constants import EXPECTED_ANALYSIS_SIGNATURE
from app.source_analysis_v3_hardened_win001.paths import (
    candidate_cache_dir,
    candidate_window_dir,
)
from app.source_analysis_v31_local_lite.constants import (
    A21_STATUS_UNCHANGED,
    DERIVED_LABEL,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    SEMANTIC_TRANSPORT_VERSION_V3,
)


def _a21_transport_paths(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> list[Path]:
    isolated = candidate_window_dir(project_name, sortie_dir=sortie_dir) / "transport.json"
    cache = (
        candidate_cache_dir(
            project_name, EXPECTED_ANALYSIS_SIGNATURE, sortie_dir=sortie_dir
        )
        / "transport.json"
    )
    return [isolated, cache]


def load_a21_historical_transport(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any] | None:
    for path in _a21_transport_paths(project_name, sortie_dir=sortie_dir):
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return {
                    "path": str(path),
                    "sha256": sha256_of_file(path),
                    "payload": payload,
                }
    return None


def build_compatibility(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    historical = True
    decode_v3_transport(v3_success_transport(), allowed_source_refs={"SRC000001"})
    a21 = load_a21_historical_transport(project_name, sortie_dir=sortie_dir)
    a21_readable = False
    a21_hash = None
    derived = None
    if a21 is not None:
        a21_hash = a21["sha256"]
        try:
            decode_v3_transport(a21["payload"])
            a21_readable = True
        except WindowTransportValidationError:
            a21_readable = False
        normalized, provenance = normalize_v3_transport_to_local_lite(
            a21["payload"],
            source_transport_version=SEMANTIC_TRANSPORT_VERSION_V3,
        )
        derived = {
            "label": DERIVED_LABEL,
            "source": "A.21",
            "source_path": a21["path"],
            "source_sha256": a21_hash,
            "derived_sha256": content_hash(
                json.dumps(normalized, ensure_ascii=False, sort_keys=True)
            ),
            "overwrite_original": False,
            "provenance": provenance,
            "records": len(normalized.get("records") or []),
        }

    mixed_ok = False
    transcript, plan = seven_window_plan()
    v3_results = run_v3_windows(transcript, plan)
    derived_results = []
    provenances = []
    for result in v3_results:
        converted, provenance = normalize_v3_window_result_to_local_lite(result)
        derived_results.append(converted)
        provenances.append(provenance)
    mixed_ok = (
        len(derived_results) == 7
        and all(
            record.kind != "IDEA" or len(record.metadata) == 1
            for result in derived_results
            for record in result.records
        )
        and all(item["invented_semantics"] is False for item in provenances)
    )
    source_map_absent = not source_map_path(project_name, sortie_dir=sortie_dir).exists()
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "historical_v3": "PASS" if historical else "FAIL",
        "a21_historical_candidate": (
            "PASS" if a21 is None or a21_readable else "FAIL"
        ),
        "a21_present": a21 is not None,
        "a21_readable": a21_readable,
        "a21_original_sha256": a21_hash,
        "a21_status_unchanged": A21_STATUS_UNCHANGED,
        "a21_overwritten": False,
        "mixed_v3_v31_compatibility": "YES" if mixed_ok else "NO",
        "mixed_strategy": (
            "Version-aware normalization of historical V3 by deterministically "
            "dropping optional IDEA subtype. Preserve text, importance, SRC, "
            "topic, handles. No provider call. Derived artifact only."
        ),
        "do_not_regenerate_a21_merely_because_local_lite_exists": True,
        "derived_a21_local_lite": derived,
        "derived_label": DERIVED_LABEL,
        "win004_invalid_not_migrated": True,
        "source_map_absent": source_map_absent,
        "future_candidate_strategy": (
            "Keep A.21 as historical V3. Consume it later only through "
            "DERIVED_COMPATIBILITY_LOCAL_LITE, not by overwriting the cache."
        ),
    }


__all__ = [
    "build_compatibility",
    "load_a21_historical_transport",
]
