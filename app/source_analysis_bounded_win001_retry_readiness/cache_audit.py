"""Table de cache 1.0 historique vs 1.1 futur. 0 appel provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.window_analyzer import build_window_ai_request
from app.source_analysis.window_cache import inspect_window_cache
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis.window_writer import (
    leftover_partial,
    metadata_path,
    production_windows_exist,
    result_path,
    transport_path,
    windows_root,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_bounded_win001_retry_readiness.constants import (
    PROJECT_NAME,
    WINDOW_ID,
)
from app.source_analysis.consolidation_writer import production_consolidation_exist
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_hybrid_readiness.facts import inspect_publication_and_state


def _inspect_one(
    window,
    transcript,
    *,
    project_name: str,
    root: Path,
    prompt_version: str,
) -> dict[str, Any]:
    bundle = build_window_ai_request(
        window, transcript, prompt_version=prompt_version
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
    files_present = any(path.is_file() for path in (t_path, r_path, m_path))
    return {
        "window_id": window.window_id,
        "prompt_version": prompt_version,
        "expected_signature": bundle.signature,
        "cache_state": inspection.cache_state,
        "transport_present": inspection.transport_present,
        "result_present": inspection.result_present,
        "metadata_present": inspection.metadata_present,
        "valid_cache_entry": inspection.cache_state == "HIT",
        "failed_historical_call_evidence": (
            window.window_id == WINDOW_ID
            and prompt_version == WINDOW_ANALYSIS_PROMPT_VERSION_V10
            and not inspection.result_present
        ),
        "files_present": files_present,
        "partial_present": bool(
            leftover_partial(t_path)
            or leftover_partial(r_path)
            or leftover_partial(m_path)
        ),
        "unexpected_real_1_1_result": (
            prompt_version == WINDOW_ANALYSIS_PROMPT_VERSION
            and inspection.cache_state == "HIT"
        ),
    }


def inspect_versioned_cache(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v2(transcript)
    root = windows_root(project_name, sortie_dir=sortie_dir)
    rows: list[dict[str, Any]] = []
    for window in plan.windows:
        rows.append(
            _inspect_one(
                window,
                transcript,
                project_name=project_name,
                root=root,
                prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10,
            )
        )
        if window.window_id == WINDOW_ID:
            rows.append(
                _inspect_one(
                    window,
                    transcript,
                    project_name=project_name,
                    root=root,
                    prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
                )
            )
    win001_10 = next(
        row
        for row in rows
        if row["window_id"] == WINDOW_ID
        and row["prompt_version"] == WINDOW_ANALYSIS_PROMPT_VERSION_V10
    )
    win001_11 = next(
        row
        for row in rows
        if row["window_id"] == WINDOW_ID
        and row["prompt_version"] == WINDOW_ANALYSIS_PROMPT_VERSION
    )
    win002 = next(row for row in rows if row["window_id"] == "WIN002")
    win003 = next(row for row in rows if row["window_id"] == "WIN003")
    publication = inspect_publication_and_state(
        project_name, sortie_dir=sortie_dir
    )
    unexpected_hit = any(row["unexpected_real_1_1_result"] for row in rows)
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
        "WIN001_1_0": win001_10,
        "WIN001_1_1": win001_11,
        "WIN002": win002,
        "WIN003": win003,
        "windows": rows,
        "expected": {
            "WIN001_1_0_result": "absent",
            "WIN001_1_1": "MISS",
            "WIN002": "MISS",
            "WIN003": "MISS",
        },
        "matches_expected": (
            win001_10["result_present"] is False
            and win001_11["cache_state"] == "MISS"
            and win002["cache_state"] == "MISS"
            and win003["cache_state"] == "MISS"
            and not unexpected_hit
        ),
        "blocked_for_human_review": unexpected_hit,
    }
