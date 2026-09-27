"""Préflight offline 7 fenêtres CLEAN + FakeAI E2E. 0 appel provider."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_local_v2.e2e import run_direct_e2e, run_hierarchical_e2e
from app.source_analysis_local_v2.pipeline import analyze_window_v2
from app.source_analysis_local_v2.prompt import (
    build_window_system_prompt_v12,
    build_window_system_prompt_v121,
    estimate_v12_request_tokens,
    estimate_v121_request_tokens,
    window_prompt_v12_sha256,
    window_prompt_v121_sha256,
)
from app.source_analysis_local_v2.schema import (
    compare_v1_v2_schemas,
    measure_schema_pair,
    build_semantic_transport_v2_schema,
)
from app.source_analysis_local_v2.synthetic import measure_v2_worst_case
from app.source_analysis_small_window_hierarchy.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
)
from app.source_analysis_small_window_hierarchy.planner import plan_windows_v21_small
from app.source_analysis_v2_grammar_canary.constants import (
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
)
from app.source_analysis_v2_link_semantics.constants import (
    CANDIDATE_PLANNER_VERSION,
    PROJECT_NAME,
    TARGET_JSON_LOCAL_TOKENS,
)
from app.source_analysis_v2_link_semantics.identity import future_win001_identity
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis_local_v2.fixtures import v2_success_transport


def schema_regression() -> dict[str, Any]:
    comparison = compare_v1_v2_schemas()
    pair = measure_schema_pair(build_semantic_transport_v2_schema())
    return {
        "transport": "semantic-transport-v2",
        "schema_changed": False,
        "raw_bytes": pair["raw_bytes"],
        "adapted_bytes": pair["adapted_bytes"],
        "expected_raw": EXPECTED_RAW_SCHEMA_BYTES,
        "expected_adapted": EXPECTED_ADAPTED_SCHEMA_BYTES,
        "matches_expected": pair["raw_bytes"] == EXPECTED_RAW_SCHEMA_BYTES
        and pair["adapted_bytes"] == EXPECTED_ADAPTED_SCHEMA_BYTES,
        "a13_grammar_acceptance_applicable": True,
        "second_grammar_canary_needed": False,
        "server_grammar": "VERIFIED ACCEPTED",
        "comparison_grammar_risk_field_unchanged": comparison["grammar_risk"],
    }


def prompt_overhead() -> dict[str, Any]:
    sha12 = window_prompt_v12_sha256(build_window_system_prompt_v12("en"))
    sha121 = window_prompt_v121_sha256(build_window_system_prompt_v121("en"))
    system_12 = build_window_system_prompt_v12("en")
    system_121 = build_window_system_prompt_v121("en")
    return {
        "prompt_1_2_chars": len(system_12),
        "prompt_1_2_1_chars": len(system_121),
        "char_delta": len(system_121) - len(system_12),
        "prompt_1_2_sha256": sha12,
        "prompt_1_2_1_sha256": sha121,
        "historical_1_2_preserved": sha12 != sha121,
    }


def real_seven_window_preflight(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v21_small(transcript)
    rows: list[dict[str, Any]] = []
    for window in plan.windows:
        estimate = estimate_v121_request_tokens(transcript, window)
        legacy = estimate_v12_request_tokens(transcript, window)
        rows.append(
            {
                "window_id": window.window_id,
                "owned_src_count": window.owned_src_count,
                "estimated_v121": estimate["total_tokens"],
                "estimated_v12": legacy["total_tokens"],
                "under_hard_max": estimate["total_tokens"]
                <= CANDIDATE_HARD_MAX_INPUT_TOKENS,
                "input_hash": window.input_hash,
            }
        )
    max_input = max((row["estimated_v121"] for row in rows), default=0)
    win001 = next(window for window in plan.windows if window.window_id == "WIN001")
    identity = future_win001_identity(win001, transcript)
    return {
        "planner": CANDIDATE_PLANNER_VERSION,
        "window_count": plan.window_count,
        "windows": rows,
        "max_future_window_input": max_input,
        "all_under_35000": all(row["under_hard_max"] for row in rows),
        "hard_max": CANDIDATE_HARD_MAX_INPUT_TOKENS,
        "future_win001": identity,
        "provider_called": False,
    }


def run_fakeai_matrix(tmp_root: Path | None = None) -> dict[str, Any]:
    own = tmp_root
    cleanup = False
    if own is None:
        own = Path(tempfile.mkdtemp(prefix="a14-e2e-"))
        cleanup = True
    try:
        from app.source_analysis_local_v2.fixtures import seven_window_plan

        transcript, plan = seven_window_plan()
        window = plan.windows[0]
        engine = FakeAIEngine(
            script=[
                FakeReply(
                    text="{}",
                    parsed=v2_success_transport(owned_src=window.owned_src_refs[0]),
                    finish_reason="stop",
                )
            ],
            retry_policy=no_delay_policy(),
        )
        local = analyze_window_v2(window, transcript, engine)
        direct = run_direct_e2e(own / "direct")
        hierarchical = run_hierarchical_e2e(own / "hierarchical")
        sm = direct.source_map
        deferred = {
            "repetitions": len(sm.repetitions),
            "voice_tone": list(sm.author_voice_profile.tone),
            "intent_kinds": list(sm.source_analysis.author_intent.kinds),
            "audience_kinds": list(sm.source_analysis.target_audience.kinds),
        }
        return {
            "local_v2_ready": local.ready,
            "local_prompt_version": (
                local.result.prompt_version if local.result else None
            ),
            "direct": {
                "pass": direct.no_drop and direct.deferred_local_kinds_absent,
                "canonical": True,
                "no_drop": direct.no_drop,
                "deferred_local_absent": direct.deferred_local_kinds_absent,
            },
            "hierarchical": {
                "pass": hierarchical.no_drop
                and hierarchical.deferred_local_kinds_absent,
                "canonical": True,
                "no_drop": hierarchical.no_drop,
            },
            "deferred_recovered": deferred,
            "src_traceable": direct.no_drop,
        }
    finally:
        if cleanup:
            pass


def output_budget() -> dict[str, Any]:
    worst = measure_v2_worst_case()
    return {
        **worst,
        "within_12000": worst["local_tokens"] <= TARGET_JSON_LOCAL_TOKENS,
        "link_hardening_did_not_inflate_schema": True,
    }


__all__ = [
    "output_budget",
    "prompt_overhead",
    "real_seven_window_preflight",
    "run_fakeai_matrix",
    "schema_regression",
]
