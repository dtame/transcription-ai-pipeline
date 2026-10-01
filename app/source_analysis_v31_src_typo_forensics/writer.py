"""Écriture atomique des artefacts A.32 — nouveaux fichiers seulement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v31_src_typo_forensics.constants import (
    CANONICAL_ARTIFACT,
    COUNTERFACTUAL_ARTIFACT,
    DECISION_ARTIFACT,
    HISTORY_ARTIFACT,
    OPTIONS_ARTIFACT,
    PHASE,
    REPORT_NAME,
    ROOT_FAILURE_ARTIFACT,
    SCHEMA_VERSION,
    SEMANTIC_ARTIFACT,
)
from app.source_analysis_v31_src_typo_forensics.counterfactual import (
    jsonable_counterfactual,
)
from app.source_analysis_v31_src_typo_forensics.report import render_report


def artifact_path(project_name: str, name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / name


def write_bytes_atomic(path: Path, payload: Mapping[str, Any] | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        content = payload if payload.endswith("\n") else payload + "\n"
    else:
        content = json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    encoded = content.encode("utf-8")
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_bytes(encoded)
        if partial.read_bytes() != encoded:
            raise ValueError(f"Octets partiels ≠ contenu canonique pour {path.name}.")
        if not isinstance(payload, str):
            loaded = json.loads(encoded.decode("utf-8"))
            if not isinstance(loaded, dict) or loaded.get("schema_version") != SCHEMA_VERSION:
                raise ValueError(f"Artefact partiel invalide : {path.name}.")
            if loaded.get("phase") != PHASE:
                raise ValueError(f"phase inattendue dans {path.name}.")
        leftover_name = path.with_name(path.name + ".partial")
        partial.replace(path)
        if leftover_name.exists() and leftover_name != path:
            leftover_name.unlink()
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()
    return path


def _jsonable_replay(replay: Mapping[str, Any]) -> dict[str, Any]:
    skip = {
        "window",
        "transcript",
        "payload",
        "validation",
        "raw_text",
        "raw_json",
        "raw_bytes",
        "handles",
    }
    public = {key: value for key, value in replay.items() if key not in skip}
    inventory = dict(replay.get("src_inventory") or {})
    inventory.pop("occurrences", None)
    public["src_inventory"] = inventory
    return public


def _semantic_public(semantic: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(semantic, Mapping):
        return None
    coverage = semantic.get("coverage") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "status": semantic.get("status"),
        "transport_valid": semantic.get("transport_valid"),
        "semantic_quality": semantic.get("semantic_quality"),
        "unsupported_content": semantic.get("unsupported_content"),
        "unsupported_count": semantic.get("unsupported_count"),
        "material_omissions": semantic.get("material_omissions"),
        "grounding_counts": semantic.get("grounding_counts"),
        "relation_quality_summary": semantic.get("relation_quality_summary"),
        "major_idea_checklist": semantic.get("major_idea_checklist"),
        "coverage": {
            "distinct_src_refs": coverage.get("distinct_src_refs"),
            "semantic_src_coverage_pct": coverage.get("semantic_src_coverage_pct"),
            "beginning": coverage.get("beginning"),
            "middle": coverage.get("middle"),
            "end": coverage.get("end"),
            "largest_substantive_gap": coverage.get("largest_substantive_gap"),
            "major_ideas_represented": coverage.get("major_ideas_represented"),
            "major_ideas_partial": coverage.get("major_ideas_partial"),
            "major_ideas_missing": coverage.get("major_ideas_missing"),
            "bands": coverage.get("bands"),
        },
        "duplication": semantic.get("duplication"),
        "reasons": semantic.get("reasons"),
        "external_knowledge": False,
        "second_llm": False,
        "win007_promoted": False,
    }


def _canonical_public(mixed: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(mixed, Mapping):
        return None
    local = mixed.get("local") or mixed
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "forensic_only": True,
        "production_cache_written": False,
        "consolidated": False,
        "idea_validation": local.get("idea_validation"),
        "idea_count": local.get("idea_count"),
        "all_kinds_empty": local.get("all_kinds_empty"),
        "all_importances_valid": local.get("all_importances_valid"),
        "importance_to_kind_contamination": local.get(
            "importance_to_kind_contamination"
        ),
        "expected_kind": "",
        "mixed_compatibility": mixed.get("mixed_compatibility"),
        "ready_windows_checked": mixed.get("ready_windows_checked"),
        "errors": local.get("errors") or [],
    }


def write_audit_bundle(
    project_name: str,
    bundle: Mapping[str, Any],
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.32",
) -> dict[str, Path]:
    replay_public = _jsonable_replay(bundle["replay"])
    intended = dict(bundle["intended"])
    neighborhood = dict(intended.get("neighborhood") or {})
    neighbors = []
    for row in neighborhood.get("neighbors") or []:
        neighbors.append(
            {
                key: row[key]
                for key in row
                if key != "text"
            }
            | {"text_preview": str(row.get("text") or "")[:180]}
        )
    neighborhood["neighbors"] = neighbors
    intended["neighborhood"] = neighborhood
    root = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        **bundle["root_cascade"],
        "transformation": bundle["transformation"],
        "replay": replay_public,
        "intended": intended,
    }
    written = {
        "root": write_bytes_atomic(
            artifact_path(project_name, ROOT_FAILURE_ARTIFACT, sortie_dir=sortie_dir),
            root,
        ),
        "history": write_bytes_atomic(
            artifact_path(project_name, HISTORY_ARTIFACT, sortie_dir=sortie_dir),
            bundle["history"],
        ),
        "options": write_bytes_atomic(
            artifact_path(project_name, OPTIONS_ARTIFACT, sortie_dir=sortie_dir),
            bundle["options"],
        ),
        "counterfactual": write_bytes_atomic(
            artifact_path(project_name, COUNTERFACTUAL_ARTIFACT, sortie_dir=sortie_dir),
            {
                "schema_version": SCHEMA_VERSION,
                "phase": PHASE,
                **jsonable_counterfactual(bundle["counterfactual"]),
            },
        ),
        "decision": write_bytes_atomic(
            artifact_path(project_name, DECISION_ARTIFACT, sortie_dir=sortie_dir),
            bundle["decision"],
        ),
        "report": write_bytes_atomic(
            artifact_path(project_name, REPORT_NAME, sortie_dir=sortie_dir),
            render_report(bundle, tests=tests),
        ),
    }
    semantic = _semantic_public(bundle["counterfactual"].get("semantic_review"))
    if semantic is not None:
        written["semantic"] = write_bytes_atomic(
            artifact_path(project_name, SEMANTIC_ARTIFACT, sortie_dir=sortie_dir),
            semantic,
        )
    canonical = _canonical_public(bundle["counterfactual"].get("mixed"))
    if canonical is None:
        canonical = _canonical_public(bundle["counterfactual"].get("canonical"))
    if canonical is not None:
        written["canonical"] = write_bytes_atomic(
            artifact_path(project_name, CANONICAL_ARTIFACT, sortie_dir=sortie_dir),
            canonical,
        )
    return written


__all__ = ["artifact_path", "write_audit_bundle", "write_bytes_atomic"]
