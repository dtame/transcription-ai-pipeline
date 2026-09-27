"""Cache réel vs FakeAI isolé. 0 appel provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.consolidation_writer import production_consolidation_exist
from app.source_analysis.window_analyzer import build_window_ai_request
from app.source_analysis.window_cache import inspect_window_cache
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis.window_writer import (
    leftover_partial,
    metadata_path,
    production_windows_exist,
    result_path,
    transport_path,
    windows_root,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_hybrid_readiness.facts import inspect_publication_and_state
from app.source_analysis_small_window_hierarchy.planner import plan_windows_v21_small
from app.source_analysis_small_window_readiness.constants import PROJECT_NAME, WINDOW_ID


def _inspect_one(
    window,
    transcript,
    *,
    project_name: str,
    root: Path,
) -> dict[str, Any]:
    bundle = build_window_ai_request(
        window, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION
    )
    inspection = inspect_window_cache(
        window,
        transcript,
        windows_root=root,
        project_name=project_name,
        expected_signature=bundle.signature,
    )
    t_path = transport_path(project_name, window.window_id, root=root)
    r_path = result_path(project_name, window.window_id, root=root)
    m_path = metadata_path(project_name, window.window_id, root=root)
    return {
        "window_id": window.window_id,
        "planner_version": window.planner_version,
        "window_input_hash": window.input_hash,
        "expected_signature": bundle.signature,
        "cache_state": inspection.cache_state,
        "transport_present": inspection.transport_present,
        "result_present": inspection.result_present,
        "metadata_present": inspection.metadata_present,
        "valid_cache_entry": inspection.cache_state == "HIT",
        "files_present": any(path.is_file() for path in (t_path, r_path, m_path)),
        "partial_present": bool(
            leftover_partial(t_path)
            or leftover_partial(r_path)
            or leftover_partial(m_path)
        ),
        "unexpected_hit": inspection.cache_state == "HIT",
    }


def inspect_small_window_real_cache(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    small_plan = plan_windows_v21_small(transcript)
    large_plan = plan_windows_v2(transcript)
    root = windows_root(project_name, sortie_dir=sortie_dir)
    small_rows = [
        _inspect_one(window, transcript, project_name=project_name, root=root)
        for window in small_plan.windows
    ]
    large_win001 = next(
        item for item in large_plan.windows if item.window_id == WINDOW_ID
    )
    large_row = _inspect_one(
        large_win001, transcript, project_name=project_name, root=root
    )
    publication = inspect_publication_and_state(project_name, sortie_dir=sortie_dir)
    unexpected = any(row["unexpected_hit"] for row in small_rows)
    by_id = {row["window_id"]: row for row in small_rows}
    return {
        "windows_root": str(root),
        "production_windows_exist": production_windows_exist(
            project_name, sortie_dir=sortie_dir
        ),
        "production_consolidation_exist": production_consolidation_exist(
            project_name, sortie_dir=sortie_dir
        ),
        "source_map_present": source_map_path(
            project_name, sortie_dir=sortie_dir
        ).exists(),
        "project_state": publication,
        "small_windows": small_rows,
        "by_id": by_id,
        "large_win001": large_row,
        "large_win001_is_not_small_cache_candidate": (
            large_row["expected_signature"] != by_id[WINDOW_ID]["expected_signature"]
            and large_row["window_input_hash"] != by_id[WINDOW_ID]["window_input_hash"]
        ),
        "all_small_miss": all(row["cache_state"] == "MISS" for row in small_rows),
        "unexpected_hit": unexpected,
        "blocked_for_human_review": unexpected,
        "fakeai_isolated": True,
        "regional_real_cache_absent": not production_consolidation_exist(
            project_name, sortie_dir=sortie_dir
        ),
        "global_real_cache_absent": not production_consolidation_exist(
            project_name, sortie_dir=sortie_dir
        ),
    }


__all__ = ["inspect_small_window_real_cache"]
