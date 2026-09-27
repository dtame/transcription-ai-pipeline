"""Estimations d'entrée 1.4.0 pour les 7 fenêtres candidates. Offline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.materialize import materialize_window_content
from app.source_analysis_local_v3.prompt import (
    estimate_v132_request_tokens,
    estimate_v140_request_tokens,
)
from app.source_analysis_small_window_hierarchy.planner import plan_windows_v21_small
from app.source_analysis_v31_local_lite.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
)


def build_window_estimates(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v21_small(transcript)
    win001 = next(item for item in plan.windows if item.window_id == "WIN001")
    overhead_132 = estimate_v132_request_tokens(transcript, win001)
    overhead_140 = estimate_v140_request_tokens(transcript, win001)
    delta = int(overhead_140["total_tokens"]) - int(overhead_132["total_tokens"])
    per_window: dict[str, int] = {}
    for window in plan.windows:
        content = materialize_window_content(transcript, window)
        estimate = estimate_v140_request_tokens(transcript, window, content=content)
        per_window[window.window_id] = int(estimate["total_tokens"])
    within = all(value <= CANDIDATE_HARD_MAX_INPUT_TOKENS for value in per_window.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "prompt_1_3_2_win001": int(overhead_132["total_tokens"]),
        "prompt_1_4_0_win001": int(overhead_140["total_tokens"]),
        "prompt_token_delta": delta,
        "windows": per_window,
        "within_35000": within,
        "limit": CANDIDATE_HARD_MAX_INPUT_TOKENS,
    }


__all__ = ["build_window_estimates"]
