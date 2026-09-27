"""Assemblage déterministe des artefacts de design 3B.7."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.file_utils import content_hash
from app.source_analysis_hybrid_design.constants import (
    MODE,
    PHASE,
    SCHEMA_VERSION,
    STRATEGY,
)
from app.source_analysis_hybrid_design.contracts import (
    architecture_design,
    consolidation_design,
    window_design,
)


def _with_header(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != SCHEMA_VERSION:
        payload = {"schema_version": SCHEMA_VERSION, **payload}
    payload.setdefault("phase", PHASE)
    payload.setdefault("mode", MODE)
    return payload


def build_window_artifact(simulation: Mapping[str, Any]) -> dict[str, Any]:
    return _with_header(window_design(simulation))


def build_consolidation_artifact(simulation: Mapping[str, Any]) -> dict[str, Any]:
    return _with_header(consolidation_design(simulation))


def build_architecture_artifact(
    simulation: Mapping[str, Any],
    window: Mapping[str, Any],
    consolidation: Mapping[str, Any],
) -> dict[str, Any]:
    payload = architecture_design(simulation, window, consolidation)
    payload["strategy"] = STRATEGY
    return _with_header(payload)


def artifact_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    return content_hash(encoded)


def build_deterministic_pair(builder, *args) -> tuple[dict[str, Any], str, str]:
    first = builder(*args)
    second = builder(*args)
    sha1 = artifact_sha256(first)
    sha2 = artifact_sha256(second)
    first["determinism"] = {
        "run1_sha256": sha1,
        "run2_sha256": sha2,
        "identical": sha1 == sha2,
        "timestamps": False,
        "uuid": False,
        "randomness": False,
    }
    return first, sha1, sha2
