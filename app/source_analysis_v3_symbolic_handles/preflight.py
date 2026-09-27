"""Préflight offline des 7 fenêtres futures v3. 0 HTTP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.materialize import materialize_window_content
from app.source_analysis_local_v3.prompt import estimate_v13_request_tokens
from app.source_analysis_small_window_hierarchy.planner import plan_windows_v21_small
from app.source_analysis_v2_real_win001.preflight import inspect_candidate_cache
from app.source_analysis_v3_symbolic_handles.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_PLANNER_VERSION,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    WINDOW_ID,
)
from app.source_analysis_v3_symbolic_handles.identity import future_v3_win001_identity


def build_seven_window_preflight(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v21_small(transcript)
    rows: list[dict[str, Any]] = []
    all_within = True
    win001_identity = None
    for window in plan.windows:
        content = materialize_window_content(transcript, window)
        estimate = estimate_v13_request_tokens(transcript, window, content=content)
        within = int(estimate["total_tokens"]) <= CANDIDATE_HARD_MAX_INPUT_TOKENS
        all_within = all_within and within
        identity = None
        if window.window_id == WINDOW_ID:
            identity = future_v3_win001_identity(window, transcript)
            win001_identity = identity
            cache = inspect_candidate_cache(
                project_name,
                identity["analysis_signature"],
                sortie_dir=sortie_dir,
            )
        else:
            cache = None
        rows.append(
            {
                "window_id": window.window_id,
                "src_range": f"{window.first_owned_src_ref} → {window.last_owned_src_ref}",
                "first_owned_src_ref": window.first_owned_src_ref,
                "last_owned_src_ref": window.last_owned_src_ref,
                "owned_src_count": window.owned_src_count,
                "word_count": window.word_count,
                "local_request_estimate": estimate["total_tokens"],
                "hard_max": CANDIDATE_HARD_MAX_INPUT_TOKENS,
                "hard_limit_status": "WITHIN" if within else "EXCEEDS",
                "planner_version": window.planner_version,
                "cache": cache,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "project_name": project_name,
        "planner": CANDIDATE_PLANNER_VERSION,
        "window_count": len(rows),
        "windows": rows,
        "all_within_35000": all_within,
        "provider_called": False,
        "win001_identity": win001_identity,
        "real_call_authorized": False,
    }


__all__ = ["build_seven_window_preflight"]
