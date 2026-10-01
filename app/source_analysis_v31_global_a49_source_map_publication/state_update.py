"""Mise à jour project_state.json et report.json. N'altère pas la V1."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from app.project_state import ensure_state_structure
from app.source_analysis.models import SOURCE_MAP_SCHEMA_VERSION
from app.source_analysis.state import (
    STATE_KEY,
    build_completed_block,
    build_source_analysis_report,
)
from app.source_analysis_v31_global_a49_source_map_publication.constants import (
    FUTURE_PROMPT,
    HISTORICAL_PROMPT,
    MODEL,
    PROJECT_NAME,
    PROVIDER,
    RELATION_QUALITY_TECHNICAL_DEBT,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_a49_source_map_publication.paths import (
    project_report_path,
    project_state_path,
)
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_state(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    path = project_state_path(project_name, sortie_dir=sortie_dir)
    if path.is_file():
        state = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    else:
        state = {}
    ensure_state_structure(state)
    return state


def update_project_state(
    project_name: str,
    *,
    source_map_path: Path,
    sha256: str,
    stats: Mapping[str, Any],
    signature: str,
    prompt_version: str,
    schema_version: str = SOURCE_MAP_SCHEMA_VERSION,
    sortie_dir: Path | None = None,
    frozen: bool = True,
) -> dict[str, Any]:
    state = load_state(project_name, sortie_dir=sortie_dir)
    block = build_completed_block(
        signature=signature,
        path=str(source_map_path),
        provider=PROVIDER,
        model=MODEL,
        strategy=TRANSPORT_VERSION,
        prompt_version=prompt_version,
        schema_version=schema_version,
        cached=True,
        stats={
            "topic_count": int(stats.get("topics") or 0),
            "idea_count": int(stats.get("ideas") or 0),
            "example_count": int(stats.get("examples") or 0),
            "reference_count": int(stats.get("references") or 0),
            "uncertainty_count": int(stats.get("uncertainties") or 0),
            "repetition_count": int(stats.get("repetitions") or 0),
            "source_coverage_ratio": float(stats.get("source_coverage_ratio") or 0.0),
        },
        updated_at=_now(),
    )
    block["source_map_sha256"] = sha256
    block["transport_version"] = TRANSPORT_VERSION
    block["historical_prompt"] = HISTORICAL_PROMPT
    block["future_prompt"] = FUTURE_PROMPT
    block["phase_3b"] = "COMPLETE" if frozen else "INCOMPLETE"
    block["phase_3b_functionally_frozen"] = bool(frozen)
    block["relation_quality_technical_debt"] = RELATION_QUALITY_TECHNICAL_DEBT
    block["source_analyzer"] = "completed"
    state[STATE_KEY] = block
    write_bytes_atomic(
        project_state_path(project_name, sortie_dir=sortie_dir),
        state,
    )
    return block


def update_report_json(
    project_name: str,
    *,
    state: Mapping[str, Any],
    sortie_dir: Path | None = None,
) -> Path | None:
    path = project_report_path(project_name, sortie_dir=sortie_dir)
    section = build_source_analysis_report(state)
    if path.is_file():
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            report = {"project": project_name}
        report["source_analysis"] = section
        write_bytes_atomic(path, report)
        return path
    write_bytes_atomic(
        path,
        {
            "project": project_name,
            "source_analysis": section,
        },
    )
    return path


__all__ = ["load_state", "update_project_state", "update_report_json"]
